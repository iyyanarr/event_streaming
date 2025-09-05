// Copyright (c) 2025, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('SPP Contact Mapping', {
	refresh: function(frm) {
		// Add custom button to test mappings
		if (!frm.doc.__islocal) {
			frm.add_custom_button(__('Test Mappings'), function() {
				test_contact_mappings(frm);
			});
		}
	},

	mapping_name: function(frm) {
		// Auto-generate mapping name if empty
		if (!frm.doc.mapping_name) {
			frm.set_value('mapping_name', 'Contact Mapping - ' + frappe.datetime.now_date());
		}
	}
});

frappe.ui.form.on('SPP Contact Mapping Detail', {
	producer_contact: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (row.producer_contact && !row.consumer_contact) {
			// Auto-suggest consumer contact based on producer contact
			frappe.db.get_list('Contact', {
				filters: {
					'name': ['like', '%' + row.producer_contact.split('-')[0] + '%']
				},
				fields: ['name', 'first_name', 'last_name']
			}).then(contacts => {
				if (contacts.length > 0) {
					frappe.msgprint({
						title: __('Suggested Contacts'),
						message: __('Found {0} potential matches for consumer contact', [contacts.length]),
						indicator: 'blue'
					});
				}
			});
		}
	},

	consumer_contact: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (row.consumer_contact) {
			// Validate that the consumer contact exists
			frappe.db.exists('Contact', row.consumer_contact).then(exists => {
				if (!exists) {
					frappe.msgprint({
						title: __('Contact Not Found'),
						message: __('Consumer contact {0} does not exist', [row.consumer_contact]),
						indicator: 'red'
					});
				}
			});
		}
	}
});

function test_contact_mappings(frm) {
	if (!frm.doc.contact_mappings || frm.doc.contact_mappings.length === 0) {
		frappe.msgprint(__('No contact mappings to test'));
		return;
	}

	let test_results = [];
	let promises = [];

	frm.doc.contact_mappings.forEach(mapping => {
		let promise = frappe.db.exists('Contact', mapping.consumer_contact).then(exists => {
			test_results.push({
				producer: mapping.producer_contact,
				consumer: mapping.consumer_contact,
				exists: exists
			});
		});
		promises.push(promise);
	});

	Promise.all(promises).then(() => {
		let message = '<table class="table table-bordered"><thead><tr><th>Producer Contact</th><th>Consumer Contact</th><th>Status</th></tr></thead><tbody>';
		
		test_results.forEach(result => {
			let status_icon = result.exists ? '✓' : '✗';
			let status_color = result.exists ? 'green' : 'red';
			message += `<tr><td>${result.producer}</td><td>${result.consumer}</td><td style="color:${status_color}">${status_icon}</td></tr>`;
		});
		
		message += '</tbody></table>';

		frappe.msgprint({
			title: __('Contact Mapping Test Results'),
			message: message,
			indicator: 'blue'
		});
	});
}