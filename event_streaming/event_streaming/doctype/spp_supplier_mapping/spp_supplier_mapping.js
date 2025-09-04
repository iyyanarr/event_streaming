// Copyright (c) 2025, Frappe Technologies and contributors
// License: MIT. See LICENSE

frappe.ui.form.on('SPP Supplier Mapping', {
	refresh: function(frm) {
		// Add custom buttons
		frm.add_custom_button(__('Import from CSV'), function() {
			import_supplier_csv_mapping(frm);
		}, __('Actions'));
		
		frm.add_custom_button(__('Test Mapping'), function() {
			test_supplier_mapping(frm);
		}, __('Actions'));
		
		frm.add_custom_button(__('Export to CSV'), function() {
			export_supplier_csv_mapping(frm);
		}, __('Actions'));
		
		// Set indicator formatter for active status
		frm.set_indicator_formatter('is_active', function(doc) {
			return doc.is_active ? 'green' : 'red';
		});
		
		// Add mapping statistics
		if (frm.doc.supplier_mappings && frm.doc.supplier_mappings.length) {
			let active_count = frm.doc.supplier_mappings.filter(sup => sup.is_active).length;
			let total_count = frm.doc.supplier_mappings.length;
			
			frm.dashboard.add_indicator(__('Active Supplier Mappings: {0} / {1}', [active_count, total_count]), 
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

frappe.ui.form.on('SPP Supplier Mapping Detail', {
	source_supplier: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (!row.target_supplier) {
			// Auto-fill target with source if empty
			frappe.model.set_value(cdt, cdn, 'target_supplier', row.source_supplier);
		}
	}
});

function import_supplier_csv_mapping(frm) {
	new frappe.ui.Dialog({
		title: __('Import Supplier Mappings from CSV'),
		fields: [
			{
				fieldtype: 'Attach',
				fieldname: 'csv_file',
				label: __('CSV File'),
				reqd: 1,
				description: __('CSV file should have columns: source_supplier, target_supplier, supplier_group')
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

function test_supplier_mapping(frm) {
	new frappe.ui.Dialog({
		title: __('Test Supplier Mapping'),
		fields: [
			{
				fieldtype: 'Data',
				fieldname: 'source_supplier',
				label: __('Source Supplier'),
				reqd: 1
			}
		],
		primary_action_label: __('Test'),
		primary_action: function(values) {
			let target_supplier = frm.doc.supplier_mappings.find(
				sup => sup.source_supplier === values.source_supplier && sup.is_active
			);
			
			if (target_supplier) {
				frappe.msgprint(__('Mapping Result: {0} → {1}', 
					[values.source_supplier, target_supplier.target_supplier]));
			} else {
				frappe.msgprint(__('No mapping found for supplier: {0}', [values.source_supplier]));
			}
			
			this.hide();
		}
	}).show();
}

function export_supplier_csv_mapping(frm) {
	let csv_data = 'source_supplier,target_supplier,supplier_group,is_active,notes\n';
	
	frm.doc.supplier_mappings.forEach(sup => {
		csv_data += `"${sup.source_supplier}","${sup.target_supplier}","${sup.supplier_group || ''}","${sup.is_active}","${sup.notes || ''}"\n`;
	});
	
	// Create and download CSV file
	let blob = new Blob([csv_data], { type: 'text/csv' });
	let url = window.URL.createObjectURL(blob);
	let a = document.createElement('a');
	a.href = url;
	a.download = `${frm.doc.mapping_name}_supplier_mappings.csv`;
	a.click();
	window.URL.revokeObjectURL(url);
}