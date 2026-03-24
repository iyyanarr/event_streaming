// Copyright (c) 2025, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('SPP Address Mapping', {
	refresh: function(frm) {
		// Add custom buttons
		frm.add_custom_button(__('Import from CSV'), function() {
			import_csv_mapping(frm);
		}, __('Actions'));
		
		frm.add_custom_button(__('Test Mapping'), function() {
			test_address_mapping(frm);
		}, __('Actions'));
		
		frm.add_custom_button(__('Export to CSV'), function() {
			export_csv_mapping(frm);
		}, __('Actions'));
		
		// Set indicator formatter for active status
		frm.set_indicator_formatter('is_active', function(doc) {
			return doc.is_active ? 'green' : 'red';
		});
		
		// Add mapping statistics
		if (frm.doc.address_mappings && frm.doc.address_mappings.length) {
			let active_count = frm.doc.address_mappings.filter(addr => addr.is_active).length;
			let total_count = frm.doc.address_mappings.length;
			
			frm.dashboard.add_indicator(__('Active Mappings: {0} / {1}', [active_count, total_count]), 
				active_count === total_count ? 'green' : 'orange');
		}
	}
});

frappe.ui.form.on('SPP Address Mapping Detail', {
	producer_address: function(frm, cdt, cdn) {
		// Auto-fill suggestions removed for consistency
	}
});

function import_csv_mapping(frm) {
	if (frm.is_new()) {
		frappe.msgprint(__('Please save this SPP Address Mapping before importing a CSV.'));
		return;
	}
	new frappe.ui.Dialog({
		title: __('Import Address Mappings from CSV'),
		fields: [
			{
				fieldtype: 'Attach',
				fieldname: 'csv_file',
				label: __('CSV File'),
				reqd: 1,
				description: __('Accepted headers: producer_address, consumer_address')
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
					frm.refresh_field('address_mappings');
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

function test_address_mapping(frm) {
	new frappe.ui.Dialog({
		title: __('Test Address Mapping'),
		fields: [
			{
				fieldtype: 'Data',
				fieldname: 'producer_address',
				label: __('Producer Address'),
				reqd: 1
			}
		],
		primary_action_label: __('Test'),
		primary_action: function(values) {
			let target_item = frm.doc.address_mappings.find(
				addr => addr.producer_address === values.producer_address
			);
			
			if (target_item) {
				frappe.msgprint(__('Mapping Result: {0} → {1}', 
					[values.producer_address, target_item.consumer_address]));
			} else {
				frappe.msgprint(__('No mapping found for address: {0}', [values.producer_address]));
			}
			
			this.hide();
		}
	}).show();
}

function export_csv_mapping(frm) {
	let csv_data = 'producer_address,consumer_address,is_active,notes\n';
	
	frm.doc.address_mappings.forEach(addr => {
		csv_data += `"${addr.producer_address}","${addr.consumer_address}","${addr.is_active}","${addr.notes || ''}"\n`;
	});
	
	let blob = new Blob([csv_data], { type: 'text/csv' });
	let url = window.URL.createObjectURL(blob);
	let a = document.createElement('a');
	a.href = url;
	a.download = `${frm.doc.mapping_name}_address_mappings.csv`;
	a.click();
	window.URL.revokeObjectURL(url);
}
