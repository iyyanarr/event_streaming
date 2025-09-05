// Copyright (c) 2025, Frappe Technologies and contributors
// License: MIT. See LICENSE

frappe.ui.form.on('SPP Tax Template Mapping', {
	refresh: function(frm) {
		// Add any custom refresh logic here
	}
});

frappe.ui.form.on('SPP Tax Template Mapping Detail', {
	producer_tax_template: function(frm, cdt, cdn) {
		// Add any validation or auto-population logic here
	},
	
	consumer_tax_template: function(frm, cdt, cdn) {
		// Add any validation logic here
	},
	
	template_type: function(frm, cdt, cdn) {
		// Add any logic based on template type selection
	}
});