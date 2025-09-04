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
				description: __('Accepted headers: Producer Warehouse, Consumer Warehouse, Item Group (optional). Backward compatible: Old Warehouse / New Warehouse.')
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
				description: __('Leave empty to test without item group filtering')
			}
		],
		primary_action_label: __('Test'),
		primary_action: function(values) {
			let consumer_warehouse = null;

			for (let wh of (frm.doc.warehouse_mappings || [])) {
				if (!wh.is_active) continue;
				if (wh.producer_warehouse !== values.producer_warehouse) continue;

				// If an item group is supplied, prefer an exact item_group match
				if (values.item_group) {
					if (wh.item_group && wh.item_group === values.item_group) {
						consumer_warehouse = wh.consumer_warehouse;
						break; // exact match wins
					} else if (!wh.item_group) {
						// fallback candidate if no specific group match found yet
						consumer_warehouse = consumer_warehouse || wh.consumer_warehouse;
					}
				} else {
					// No item group provided: prefer a mapping without item_group, else first active
					if (wh.item_group) {
						consumer_warehouse = consumer_warehouse || wh.consumer_warehouse;
					} else {
						consumer_warehouse = wh.consumer_warehouse;
						break;
					}
				}
			}

			if (consumer_warehouse) {
				frappe.msgprint(__('Mapping Result: {0} → {1}', [values.producer_warehouse, consumer_warehouse]));
			} else {
				frappe.msgprint(__('No mapping found for warehouse: {0}', [values.producer_warehouse]));
			}

			this.hide();
		}
	}).show();
}

function export_warehouse_csv_mapping(frm) {
	let csv_data = 'Producer Warehouse,Consumer Warehouse,Item Group,Is Active,Notes\n';

	(frm.doc.warehouse_mappings || []).forEach(wh => {
		csv_data += `"${wh.producer_warehouse}","${wh.consumer_warehouse}","${wh.item_group || ''}","${wh.is_active}","${wh.notes || ''}"\n`;
	});

	let blob = new Blob([csv_data], { type: 'text/csv' });
	let url = window.URL.createObjectURL(blob);
	let a = document.createElement('a');
	a.href = url;
	a.download = `${frm.doc.mapping_name}_warehouse_mappings.csv`;
	a.click();
	window.URL.revokeObjectURL(url);
}