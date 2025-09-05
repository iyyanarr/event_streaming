// Copyright (c) 2025, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('SPP Address Mapping', {
	refresh: function(frm) {
		// Add custom button to test mappings
		if (!frm.doc.__islocal) {
			frm.add_custom_button(__('Test Mappings'), function() {
				test_address_mappings(frm);
			});
		}
	},

	mapping_name: function(frm) {
		// Auto-generate mapping name if empty
		if (!frm.doc.mapping_name) {
			frm.set_value('mapping_name', 'Address Mapping - ' + frappe.datetime.now_date());
		}
	}
});

frappe.ui.form.on('SPP Address Mapping Detail', {
	producer_address: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (row.producer_address && !row.consumer_address) {
			// Auto-suggest consumer address based on producer address
			frappe.db.get_list('Address', {
				filters: {
					'address_title': ['like', '%' + row.producer_address.split(';')[0] + '%']
				},
				fields: ['name', 'address_title', 'address_line1']
			}).then(addresses => {
				if (addresses.length > 0) {
					frappe.msgprint({
						title: __('Suggested Addresses'),
						message: __('Found {0} potential matches for consumer address', [addresses.length]),
						indicator: 'blue'
					});
				}
			});
		}
	},

	consumer_address: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (row.consumer_address) {
			// Validate that the consumer address exists
			frappe.db.exists('Address', row.consumer_address).then(exists => {
				if (!exists) {
					frappe.msgprint({
						title: __('Address Not Found'),
						message: __('Consumer address {0} does not exist', [row.consumer_address]),
						indicator: 'red'
					});
				}
			});
		}
	}
});

function test_address_mappings(frm) {
	if (!frm.doc.address_mappings || frm.doc.address_mappings.length === 0) {
		frappe.msgprint(__('No address mappings to test'));
		return;
	}

	let test_results = [];
	let promises = [];

	frm.doc.address_mappings.forEach(mapping => {
		let promise = frappe.db.exists('Address', mapping.consumer_address).then(exists => {
			test_results.push({
				producer: mapping.producer_address,
				consumer: mapping.consumer_address,
				exists: exists
			});
		});
		promises.push(promise);
	});

	Promise.all(promises).then(() => {
		let message = '<table class="table table-bordered"><thead><tr><th>Producer Address</th><th>Consumer Address</th><th>Status</th></tr></thead><tbody>';
		
		test_results.forEach(result => {
			let status_icon = result.exists ? '✓' : '✗';
			let status_color = result.exists ? 'green' : 'red';
			message += `<tr><td>${result.producer}</td><td>${result.consumer}</td><td style="color:${status_color}">${status_icon}</td></tr>`;
		});
		
		message += '</tbody></table>';

		frappe.msgprint({
			title: __('Address Mapping Test Results'),
			message: message,
			indicator: 'blue'
		});
	});
}
