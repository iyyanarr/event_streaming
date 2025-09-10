// Copyright (c) 2025, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('SPP Special Supplier Mapping', {
	refresh: function(frm) {
		// Custom refresh logic can be added here
		if (frm.doc.is_active) {
			frm.page.set_indicator(__('Active'), 'green');
		} else {
			frm.page.set_indicator(__('Inactive'), 'red');
		}
		
		// Add debug button for address-supplier mapping
		if (!frm.doc.__islocal) {
			frm.add_custom_button(__('Debug Address Mapping'), function() {
				debug_address_supplier_mapping(frm);
			}, __('Tools'));
		}
	},

	validate: function(frm) {
		// Additional client-side validation can be added here
	}
});

frappe.ui.form.on('SPP Special Supplier Mapping Detail', {
	mapping_type: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		
		// Clear dependent fields when mapping type changes
		if (row.mapping_type === 'Address Based') {
			frappe.model.set_value(cdt, cdn, 'consumer_supplier', '');
		} else if (row.mapping_type === 'Direct' || row.mapping_type === 'Custom') {
			frappe.model.set_value(cdt, cdn, 'address_field', '');
		}
	},

	producer_supplier: function(frm, cdt, cdn) {
		// Can add validation or auto-suggestions for producer suppliers
	}
});

function debug_address_supplier_mapping(frm) {
	new frappe.ui.Dialog({
		title: __('Debug Address-Supplier Mapping'),
		fields: [
			{
				fieldtype: 'Data',
				fieldname: 'address_name',
				label: __('Address Name'),
				reqd: 1,
				description: __('Enter the mapped address name to debug')
			}
		],
		primary_action_label: __('Debug'),
		primary_action: function(values) {
			if (!values.address_name) {
				frappe.msgprint(__('Please enter an address name'));
				return;
			}
			
			frm.call('debug_address_supplier_mapping', {
				address_name: values.address_name
			}).then(result => {
				let debug_info = result.message;
				let message = '<div class="debug-info">';
				
				if (debug_info.error) {
					message += `<p><strong>Error:</strong> ${debug_info.error}</p>`;
				} else if (debug_info.address_exists) {
					message += `<p><strong>Address Found:</strong> Yes</p>`;
					message += `<p><strong>Title:</strong> ${debug_info.address_details.title}</p>`;
					message += `<p><strong>Line 1:</strong> ${debug_info.address_details.line1}</p>`;
					message += `<p><strong>Dynamic Links:</strong> ${debug_info.dynamic_links.length}</p>`;
					message += `<p><strong>Supplier Links:</strong> ${debug_info.supplier_links.length}</p>`;
					message += `<p><strong>Found Supplier:</strong> ${debug_info.found_supplier || 'None'}</p>`;
					
					if (debug_info.dynamic_links.length > 0) {
						message += '<h5>All Dynamic Links:</h5><ul>';
						debug_info.dynamic_links.forEach(dl => {
							message += `<li>${dl.link_doctype}: ${dl.link_name}</li>`;
						});
						message += '</ul>';
					}
				} else {
					message += `<p><strong>Address Found:</strong> No</p>`;
					if (debug_info.similar_addresses && debug_info.similar_addresses.length > 0) {
						message += '<h5>Similar Addresses:</h5><ul>';
						debug_info.similar_addresses.forEach(addr => {
							message += `<li>${addr.name} - ${addr.address_title}</li>`;
						});
						message += '</ul>';
					}
				}
				
				message += '</div>';
				
				frappe.msgprint({
					title: __('Debug Results'),
					message: message,
					indicator: debug_info.found_supplier ? 'green' : 'orange'
				});
			});
			
			this.hide();
		}
	}).show();
}