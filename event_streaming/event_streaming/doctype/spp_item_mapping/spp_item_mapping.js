// Copyright (c) 2025, Frappe Technologies and contributors
// License: MIT. See LICENSE

frappe.ui.form.on('SPP Item Mapping', {
	refresh: function(frm) {
		// Add custom buttons
		frm.add_custom_button(__('Import from CSV'), function() {
			import_csv_mapping(frm);
		}, __('Actions'));
		
		frm.add_custom_button(__('Test Mapping'), function() {
			test_item_mapping(frm);
		}, __('Actions'));
		
		frm.add_custom_button(__('Export to CSV'), function() {
			export_csv_mapping(frm);
		}, __('Actions'));
		
		// Set indicator formatter for active status
		frm.set_indicator_formatter('is_active', function(doc) {
			return doc.is_active ? 'green' : 'red';
		});
		
		// Add mapping statistics
		if (frm.doc.item_mappings && frm.doc.item_mappings.length) {
			let active_count = frm.doc.item_mappings.filter(item => item.is_active).length;
			let total_count = frm.doc.item_mappings.length;
			
			frm.dashboard.add_indicator(__('Active Mappings: {0} / {1}', [active_count, total_count]), 
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

frappe.ui.form.on('SPP Item Mapping Detail', {
	source_item_code: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (!row.target_item_code) {
			// Auto-fill target with source if empty
			frappe.model.set_value(cdt, cdn, 'target_item_code', row.source_item_code);
		}
	}
});

function import_csv_mapping(frm) {
	new frappe.ui.Dialog({
		title: __('Import Item Mappings from CSV'),
		fields: [
			{
				fieldtype: 'Attach',
				fieldname: 'csv_file',
				label: __('CSV File'),
				reqd: 1,
				description: __('CSV file should have columns: old_item_code, new_item_code')
			}
		],
		primary_action_label: __('Import'),
		primary_action: function(values) {
			if (!values.csv_file) {
				frappe.msgprint(__('Please attach a CSV file'));
				return;
			}
			
			frappe.call({
				method: 'frappe.client.get_file',
				args: {
					file_url: values.csv_file
				},
				callback: function(r) {
					if (r.message) {
						frm.call('import_csv_mapping', {
							csv_data: r.message
						}).then(() => {
							frm.refresh();
							frappe.msgprint(__('CSV import completed successfully'));
						});
					}
				}
			});
			
			this.hide();
		}
	}).show();
}

function test_item_mapping(frm) {
	new frappe.ui.Dialog({
		title: __('Test Item Mapping'),
		fields: [
			{
				fieldtype: 'Data',
				fieldname: 'source_item_code',
				label: __('Source Item Code'),
				reqd: 1
			}
		],
		primary_action_label: __('Test'),
		primary_action: function(values) {
			let target_item = frm.doc.item_mappings.find(
				item => item.source_item_code === values.source_item_code
			);
			
			if (target_item) {
				frappe.msgprint(__('Mapping Result: {0} → {1}', 
					[values.source_item_code, target_item.target_item_code]));
			} else {
				frappe.msgprint(__('No mapping found for item code: {0}', [values.source_item_code]));
			}
			
			this.hide();
		}
	}).show();
}

function export_csv_mapping(frm) {
	let csv_data = 'old_item_code,new_item_code,item_group,is_active,notes\n';
	
	frm.doc.item_mappings.forEach(item => {
		csv_data += `"${item.source_item_code}","${item.target_item_code}","${item.item_group || ''}","${item.is_active}","${item.notes || ''}"\n`;
	});
	
	// Create and download CSV file
	let blob = new Blob([csv_data], { type: 'text/csv' });
	let url = window.URL.createObjectURL(blob);
	let a = document.createElement('a');
	a.href = url;
	a.download = `${frm.doc.mapping_name}_item_mappings.csv`;
	a.click();
	window.URL.revokeObjectURL(url);
}