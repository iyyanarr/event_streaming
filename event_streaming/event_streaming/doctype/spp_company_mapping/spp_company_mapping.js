// Copyright (c) 2025, Frappe Technologies and contributors
// License: MIT. See LICENSE

frappe.ui.form.on('SPP Company Mapping', {
	refresh: function(frm) {
		// Add custom buttons
		frm.add_custom_button(__('Test Mapping'), function() {
			test_company_mapping(frm);
		}, __('Actions'));
		
		frm.add_custom_button(__('Export to CSV'), function() {
			export_company_csv_mapping(frm);
		}, __('Actions'));
		
		// Set indicator formatter for active status
		frm.set_indicator_formatter('is_active', function(doc) {
			return doc.is_active ? 'green' : 'red';
		});
		
		// Add mapping statistics
		if (frm.doc.company_mappings && frm.doc.company_mappings.length) {
			let active_count = frm.doc.company_mappings.filter(comp => comp.is_active).length;
			let total_count = frm.doc.company_mappings.length;
			
			frm.dashboard.add_indicator(__('Active Company Mappings: {0} / {1}', [active_count, total_count]), 
				active_count === total_count ? 'green' : 'orange');
		}
	},
	
	source_site: function(frm) {
		if (frm.doc.source_site === frm.doc.target_site) {
			frappe.msgprint(__('Source site and target site cannot be the same'));
			frm.set_value('source_site', '');
		}
	},
	
	target_site: function(frm) {
		if (frm.doc.source_site === frm.doc.target_site) {
			frappe.msgprint(__('Source site and target site cannot be the same'));
			frm.set_value('target_site', '');
		}
	}
});

frappe.ui.form.on('SPP Company Mapping Detail', {
	source_company: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (!row.target_company) {
			// Auto-fill target with source if empty
			frappe.model.set_value(cdt, cdn, 'target_company', row.source_company);
		}
	}
});

function test_company_mapping(frm) {
	new frappe.ui.Dialog({
		title: __('Test Company Mapping'),
		fields: [
			{
				fieldtype: 'Data',
				fieldname: 'source_company',
				label: __('Source Company'),
				reqd: 1
			}
		],
		primary_action_label: __('Test'),
		primary_action: function(values) {
			let target_company = frm.doc.company_mappings.find(
				comp => comp.source_company === values.source_company && comp.is_active
			);
			
			if (target_company) {
				frappe.msgprint(__('Mapping Result: {0} → {1}', 
					[values.source_company, target_company.target_company]));
			} else {
				frappe.msgprint(__('No mapping found for company: {0}', [values.source_company]));
			}
			
			this.hide();
		}
	}).show();
}

function export_company_csv_mapping(frm) {
	let csv_data = 'source_company,target_company,is_active,notes\n';
	
	frm.doc.company_mappings.forEach(comp => {
		csv_data += `"${comp.source_company}","${comp.target_company}","${comp.is_active}","${comp.notes || ''}"\n`;
	});
	
	// Create and download CSV file
	let blob = new Blob([csv_data], { type: 'text/csv' });
	let url = window.URL.createObjectURL(blob);
	let a = document.createElement('a');
	a.href = url;
	a.download = `${frm.doc.mapping_name}_company_mappings.csv`;
	a.click();
	window.URL.revokeObjectURL(url);
}