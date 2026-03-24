// Copyright (c) 2025, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('SPP Contact Mapping', {
	refresh: function(frm) {
		// Add custom buttons
		frm.add_custom_button(__('Import from CSV'), function() {
			import_csv_mapping(frm);
		}, __('Actions'));
		
		frm.add_custom_button(__('Test Mapping'), function() {
			test_contact_mapping(frm);
		}, __('Actions'));
		
		frm.add_custom_button(__('Export to CSV'), function() {
			export_csv_mapping(frm);
		}, __('Actions'));
		
		// Set indicator formatter for active status
		frm.set_indicator_formatter('is_active', function(doc) {
			return doc.is_active ? 'green' : 'red';
		});
		
		// Add mapping statistics
		if (frm.doc.contact_mappings && frm.doc.contact_mappings.length) {
			let active_count = frm.doc.contact_mappings.filter(con => con.is_active).length;
			let total_count = frm.doc.contact_mappings.length;
			
			frm.dashboard.add_indicator(__('Active Mappings: {0} / {1}', [active_count, total_count]), 
				active_count === total_count ? 'green' : 'orange');
		}
	}
});

function import_csv_mapping(frm) {
	if (frm.is_new()) {
		frappe.msgprint(__('Please save this SPP Contact Mapping before importing a CSV.'));
		return;
	}
	new frappe.ui.Dialog({
		title: __('Import Contact Mappings from CSV'),
		fields: [
			{
				fieldtype: 'Attach',
				fieldname: 'csv_file',
				label: __('CSV File'),
				reqd: 1,
				description: __('Accepted headers: producer_contact, consumer_contact')
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
					frm.refresh_field('contact_mappings');
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

function test_contact_mapping(frm) {
	new frappe.ui.Dialog({
		title: __('Test Contact Mapping'),
		fields: [
			{
				fieldtype: 'Data',
				fieldname: 'producer_contact',
				label: __('Producer Contact'),
				reqd: 1
			}
		],
		primary_action_label: __('Test'),
		primary_action: function(values) {
			let target_item = frm.doc.contact_mappings.find(
				con => con.producer_contact === values.producer_contact
			);
			
			if (target_item) {
				frappe.msgprint(__('Mapping Result: {0} → {1}', 
					[values.producer_contact, target_item.consumer_contact]));
			} else {
				frappe.msgprint(__('No mapping found for contact: {0}', [values.producer_contact]));
			}
			
			this.hide();
		}
	}).show();
}

function export_csv_mapping(frm) {
	let csv_data = 'producer_contact,consumer_contact,is_active,notes\n';
	
	frm.doc.contact_mappings.forEach(con => {
		csv_data += `"${con.producer_contact}","${con.consumer_contact}","${con.is_active}","${con.notes || ''}"\n`;
	});
	
	let blob = new Blob([csv_data], { type: 'text/csv' });
	let url = window.URL.createObjectURL(blob);
	let a = document.createElement('a');
	a.href = url;
	a.download = `${frm.doc.mapping_name}_contact_mappings.csv`;
	a.click();
	window.URL.revokeObjectURL(url);
}