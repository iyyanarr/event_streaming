// Copyright (c) 2025, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('SPP Special Supplier Mapping', {
	refresh: function(frm) {
		// Add custom buttons
		frm.add_custom_button(__('Import from CSV'), function() {
			import_csv_mapping(frm);
		}, __('Actions'));
		
		frm.add_custom_button(__('Test Mapping'), function() {
			test_special_mapping(frm);
		}, __('Actions'));
		
		frm.add_custom_button(__('Export to CSV'), function() {
			export_csv_mapping(frm);
		}, __('Actions'));
		
		// Set indicator formatter for active status
		frm.set_indicator_formatter('is_active', function(doc) {
			return doc.is_active ? 'green' : 'red';
		});
		
		// Add mapping statistics
		if (frm.doc.special_mappings && frm.doc.special_mappings.length) {
			let active_count = frm.doc.special_mappings.filter(sup => sup.is_active).length;
			let total_count = frm.doc.special_mappings.length;
			
			frm.dashboard.add_indicator(__('Active Mappings: {0} / {1}', [active_count, total_count]), 
				active_count === total_count ? 'green' : 'orange');
		}

		// Keep existing specialized buttons if any, or provide one for processing debugging
		frm.add_custom_button(__('Process Log (Debug)'), function() {
			frappe.msgprint(__('Special Supplier Mapping logic is based on Mapping Type (Direct/Address Based/Custom). Use "Test Mapping" to verify entries.'));
		}, __('Debug'));
	}
});

function import_csv_mapping(frm) {
	if (frm.is_new()) {
		frappe.msgprint(__('Please save this SPP Special Supplier Mapping before importing a CSV.'));
		return;
	}
	new frappe.ui.Dialog({
		title: __('Import Special Mappings from CSV'),
		fields: [
			{
				fieldtype: 'Attach',
				fieldname: 'csv_file',
				label: __('CSV File'),
				reqd: 1,
				description: __('Accepted headers: producer_supplier, consumer_supplier, mapping_type')
			}
		],
		primary_action_label: __('Import'),
		primary_action: function(values) {
			if (!values.csv_file) {
				frappe.msgprint(__('Please attach a CSV file'));
				return;
			}
			frm.call('import_csv_mapping', { csv_file_url: values.csv_file }).then((r) => {
				frm.reload_doc().then(() => {
					frm.refresh_field('special_mappings');
					let info = r.message || {};
					frappe.show_alert({
						message: __('Imported {0} mappings', [info.count || 0]),
						indicator: 'green'
					});
				});
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

function test_special_mapping(frm) {
	new frappe.ui.Dialog({
		title: __('Test Special Supplier Mapping'),
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
			let target_item = frm.doc.special_mappings.find(
				sup => sup.producer_supplier === values.producer_supplier
			);
			
			if (target_item) {
				frappe.msgprint(__('Mapping Result: {0} → {1} (Type: {2})', 
					[values.producer_supplier, target_item.consumer_supplier, target_item.mapping_type]));
			} else {
				frappe.msgprint(__('No mapping found for supplier: {0}', [values.producer_supplier]));
			}
			
			this.hide();
		}
	}).show();
}

function export_csv_mapping(frm) {
	let csv_data = 'producer_supplier,consumer_supplier,mapping_type,is_active,notes\n';
	
	frm.doc.special_mappings.forEach(sup => {
		csv_data += `"${sup.producer_supplier}","${sup.consumer_supplier}","${sup.mapping_type}","${sup.is_active}","${sup.notes || ''}"\n`;
	});
	
	let blob = new Blob([csv_data], { type: 'text/csv' });
	let url = window.URL.createObjectURL(blob);
	let a = document.createElement('a');
	a.href = url;
	a.download = `${frm.doc.mapping_name}_special_supplier_mappings.csv`;
	a.click();
	window.URL.revokeObjectURL(url);
}