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