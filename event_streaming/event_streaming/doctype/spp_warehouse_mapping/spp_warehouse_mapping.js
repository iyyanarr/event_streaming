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
	
	source_site: function(frm) {
		if (frm.doc.source_site === frm.doc.target_site) {
			frappe.msgprint(__('Source site and target site cannot be the same'));
			frm.set_value('source_site', '');
		}
	},
	
	target_site: function(frm) {
		if (frm.doc.source_site === frm.doc.target_site) {
			frappe.msgprint(__('Source site and target site cannot be the same'));
			frm.set_value('target_site', '');
		}
	}
});

frappe.ui.form.on('SPP Warehouse Mapping Detail', {
	source_warehouse: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (!row.target_warehouse) {
			// Auto-fill target with source if empty
			frappe.model.set_value(cdt, cdn, 'target_warehouse', row.source_warehouse);
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
				description: __('CSV file should have columns: Old Warehouse, New Warehouse, Company, Warehouse Type, Item Group')
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
				frm.refresh();
				frappe.msgprint(__('CSV import completed successfully'));
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
				fieldname: 'source_warehouse',
				label: __('Source Warehouse'),
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
			let target_warehouse = null;
			
			// Find matching warehouse with optional item group filtering
			for (let wh of frm.doc.warehouse_mappings) {
				if (wh.source_warehouse === values.source_warehouse && wh.is_active) {
					// Check item group filter if specified
					if (values.item_group && wh.item_group_filter) {
						let item_groups = wh.item_group_filter.split(',').map(ig => ig.trim());
						if (!item_groups.includes(values.item_group)) {
							continue;
						}
					}
					target_warehouse = wh.target_warehouse;
					break;
				}
			}
			
			if (target_warehouse) {
				frappe.msgprint(__('Mapping Result: {0} → {1}', 
					[values.source_warehouse, target_warehouse]));
			} else {
				frappe.msgprint(__('No mapping found for warehouse: {0}', [values.source_warehouse]));
			}
			
			this.hide();
		}
	}).show();
}

function export_warehouse_csv_mapping(frm) {
	let csv_data = 'Old Warehouse,New Warehouse,Company,Warehouse Type,Item Group Filter,Is Active,Notes\n';
	
	frm.doc.warehouse_mappings.forEach(wh => {
		csv_data += `"${wh.source_warehouse}","${wh.target_warehouse}","${wh.company || ''}","${wh.warehouse_type || ''}","${wh.item_group_filter || ''}","${wh.is_active}","${wh.notes || ''}"\n`;
	});
	
	// Create and download CSV file
	let blob = new Blob([csv_data], { type: 'text/csv' });
	let url = window.URL.createObjectURL(blob);
	let a = document.createElement('a');
	a.href = url;
	a.download = `${frm.doc.mapping_name}_warehouse_mappings.csv`;
	a.click();
	window.URL.revokeObjectURL(url);
}