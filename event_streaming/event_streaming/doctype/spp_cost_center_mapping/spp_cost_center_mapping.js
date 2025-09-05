// Copyright (c) 2025, Frappe Technologies and contributors
// License: MIT. See LICENSE

frappe.ui.form.on('SPP Cost Center Mapping', {
	refresh: function(frm) {
		// Add any custom refresh logic here
	}
});

frappe.ui.form.on('SPP Cost Center Mapping Detail', {
	producer_cost_center: function(frm, cdt, cdn) {
		// Add any validation or auto-population logic here
	},
	
	consumer_cost_center: function(frm, cdt, cdn) {
		// Add any validation logic here
	}
});