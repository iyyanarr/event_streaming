// Copyright (c) 2025, Frappe Technologies and contributors
// License: MIT. See LICENSE

frappe.ui.form.on('SPP Warehouse Mapping', {
	refresh: function(frm) {
		// Add custom buttons
		frm.add_custom_button(__('Import from CSV'), function() {
			import_warehouse_csv_mapping(frm);
		}, __('Actions'));

		frm.add_custom_button(__('Test Mapping'), function() {
			test_warehouse_mapping(frm);
		}, __('Actions'));

		frm.add_custom_button(__('Export to CSV'), function() {
			export_warehouse_csv_mapping(frm);
		}, __('Actions'));

		// Set indicator formatter for active status
		frm.set_indicator_formatter('is_active', function(doc) {
			return doc.is_active ? 'green' : 'red';
		});

		// Add mapping statistics
		if (frm.doc.warehouse_mappings && frm.doc.warehouse_mappings.length) {
			let active_count = frm.doc.warehouse_mappings.filter(wh => wh.is_active).length;
			let total_count = frm.doc.warehouse_mappings.length;

			frm.dashboard.add_indicator(__('Active Warehouse Mappings: {0} / {1}', [active_count, total_count]), 
				active_count === total_count ? 'green' : 'orange');
		}
	},

	producer_site: function(frm) {
		if (frm.doc.producer_site === frm.doc.consumer_site) {
			frappe.msgprint(__('Producer site and consumer site cannot be the same'));
			frm.set_value('producer_site', '');
		}
	},

	consumer_site: function(frm) {
		if (frm.doc.producer_site === frm.doc.consumer_site) {
			frappe.msgprint(__('Producer site and consumer site cannot be the same'));
			frm.set_value('consumer_site', '');
		}
	}
});

frappe.ui.form.on('SPP Warehouse Mapping Detail', {
	producer_warehouse: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (!row.consumer_warehouse) {
			// Auto-fill consumer with producer if empty (user can change manually or via CSV import)
			frappe.model.set_value(cdt, cdn, 'consumer_warehouse', row.producer_warehouse);
		}
	}
});

function import_warehouse_csv_mapping(frm) {
	new frappe.ui.Dialog({
		title: __('Import Warehouse Mappings from CSV'),
		fields: [
			{
				fieldtype: 'Attach',
				fieldname: 'csv_file',
				label: __('CSV File'),
				reqd: 1,
				description: __('Accepted headers: Producer Warehouse, Consumer Warehouse, Item Group (optional, comma-separated for multiple groups). Backward compatible: Old Warehouse / New Warehouse.')
			}
		],
		primary_action_label: __('Import'),
		primary_action: function(values) {
			if (!values.csv_file) {
				frappe.msgprint(__('Please attach a CSV file'));
				return;
			}

			frm.call('import_csv_mapping', {
				csv_file_url: values.csv_file
			}).then(() => {
				frm.reload_doc();
				frappe.msgprint(__('CSV import completed successfully'));
			}).catch(e => {
				frappe.msgprint({
					title: __('Import Failed'),
					message: e.message || __('Unknown error during import'),
					indicator: 'red'
				});
			});

			this.hide();
		}
	}).show();
}

function test_warehouse_mapping(frm) {
	new frappe.ui.Dialog({
		title: __('Test Warehouse Mapping'),
		fields: [
			{
				fieldtype: 'Data',
				fieldname: 'producer_warehouse',
				label: __('Producer Warehouse'),
				reqd: 1
			},
			{
				fieldtype: 'Data',
				fieldname: 'item_group',
				label: __('Item Group (Optional)'),
				description: __('For Stock Entry: Comma-separated item groups (e.g., Raw Material,Chemical). Leave empty to test without item group filtering')
			},
			{
				fieldtype: 'Data',
				fieldname: 'operations',
				label: __('Operations (Optional)'),
				description: __('For Work Order/BOM: Comma-separated operations (e.g., Mixing,Extrusion,Packing). Leave empty to test without operations filtering')
			}
		],
		primary_action_label: __('Test'),
		primary_action: function(values) {
			let consumer_warehouse = null;
			let filter_values_to_check = [];
			let filter_field = null;
			
			// Determine which filter to use - operations takes priority
			if (values.operations) {
				filter_field = 'operations';
				filter_values_to_check = values.operations.split(',').map(g => g.trim()).filter(g => g);
			} else if (values.item_group) {
				filter_field = 'item_group';
				filter_values_to_check = values.item_group.split(',').map(g => g.trim()).filter(g => g);
			} else {
				filter_values_to_check = [null]; // Check for general mappings
			}

			// Check each filter value
			for (let check_value of filter_values_to_check) {
				for (let wh of (frm.doc.warehouse_mappings || [])) {
					if (!wh.is_active) continue;
					if (wh.producer_warehouse !== values.producer_warehouse) continue;

					if (filter_field) {
						// Check for exact match
						if (wh[filter_field] === check_value) {
							consumer_warehouse = wh.consumer_warehouse;
							break;
						}
						
						// Check if mapping's filter values contain our check value
						if (wh[filter_field] && check_value) {
							let mapping_values = wh[filter_field].split(',').map(v => v.trim());
							if (mapping_values.includes(check_value)) {
								consumer_warehouse = wh.consumer_warehouse;
								break;
							}
						}
						
						// Fallback to general mapping if no filter field specified in mapping
						if (!wh[filter_field] && !check_value) {
							consumer_warehouse = wh.consumer_warehouse;
							break;
						}
					} else {
						// No filter specified - use general mapping
						if (!wh.item_group && !wh.operations) {
							consumer_warehouse = wh.consumer_warehouse;
							break;
						}
					}
				}
				
				if (consumer_warehouse) break;
			}

			if (consumer_warehouse) {
				let filter_display = '';
				if (values.operations) {
					filter_display = ` (Operations: ${values.operations})`;
				} else if (values.item_group) {
					filter_display = ` (Item Group: ${values.item_group})`;
				}
				frappe.msgprint(__('Mapping Result: {0}{1} → {2}', [values.producer_warehouse, filter_display, consumer_warehouse]));
			} else {
				let filter_display = '';
				if (values.operations) {
					filter_display = ` with operations: ${values.operations}`;
				} else if (values.item_group) {
					filter_display = ` with item group(s): ${values.item_group}`;
				}
				frappe.msgprint(__('No mapping found for warehouse: {0}{1}', [values.producer_warehouse, filter_display]));
			}

			this.hide();
		}
	}).show();
}

function export_warehouse_csv_mapping(frm) {
	let csv_data = 'Producer Warehouse,Consumer Warehouse,Item Group,Is Active,Notes\n';

	(frm.doc.warehouse_mappings || []).forEach(wh => {
		// Handle multiple item groups by wrapping in quotes if they contain commas
		let item_group_value = wh.item_group || '';
		if (item_group_value.includes(',')) {
			item_group_value = `"${item_group_value}"`;
		}
		
		csv_data += `"${wh.producer_warehouse}","${wh.consumer_warehouse}","${item_group_value}","${wh.is_active}","${wh.notes || ''}"\n`;
	});

	let blob = new Blob([csv_data], { type: 'text/csv' });
	let url = window.URL.createObjectURL(blob);
	let a = document.createElement('a');
	a.href = url;
	a.download = `${frm.doc.mapping_name}_warehouse_mappings.csv`;
	a.click();
	window.URL.revokeObjectURL(url);
}