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

frappe.ui.form.on('SPP Supplier Mapping Detail', {
	producer_supplier: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (!row.consumer_supplier) {
			// Auto-fill consumer with producer if empty
			frappe.model.set_value(cdt, cdn, 'consumer_supplier', row.producer_supplier);
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
				description: __('Preferred headers: producer_supplier, consumer_supplier, supplier_group. Backward compatible: source_supplier / target_supplier.')
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
				fieldname: 'producer_supplier',
				label: __('Producer Supplier'),
				reqd: 1
			}
		],
		primary_action_label: __('Test'),
		primary_action: function(values) {
			let row = (frm.doc.supplier_mappings || []).find(
				sup => (sup.producer_supplier || sup.source_supplier) === values.producer_supplier && sup.is_active
			);
			let consumer_supplier = row ? (row.consumer_supplier || row.target_supplier) : null;
			
			if (consumer_supplier) {
				frappe.msgprint(__('Mapping Result: {0} → {1}', 
					[values.producer_supplier, consumer_supplier]));
			} else {
				frappe.msgprint(__('No mapping found for supplier: {0}', [values.producer_supplier]));
			}
			
			this.hide();
		}
	}).show();
}

function export_supplier_csv_mapping(frm) {
	let csv_data = 'producer_supplier,consumer_supplier,supplier_group,is_active,notes\n';
	
	(frm.doc.supplier_mappings || []).forEach(sup => {
		csv_data += `"${sup.producer_supplier || sup.source_supplier}","${sup.consumer_supplier || sup.target_supplier}","${sup.supplier_group || ''}","${sup.is_active}","${sup.notes || ''}"\n`;
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