// Copyright (c) 2025, Frappe Technologies and contributors
// License: MIT. See LICENSE

frappe.ui.form.on('SPP Account Mapping', {
	refresh: function(frm) {
		// Add custom buttons
		frm.add_custom_button(__('Import from CSV'), function() {
			import_csv_mapping(frm);
		}, __('Actions'));
		
		frm.add_custom_button(__('Test Mapping'), function() {
			test_account_mapping(frm);
		}, __('Actions'));
		
		frm.add_custom_button(__('Export to CSV'), function() {
			export_csv_mapping(frm);
		}, __('Actions'));
		
		// Set indicator formatter for active status
		frm.set_indicator_formatter('is_active', function(doc) {
			return doc.is_active ? 'green' : 'red';
		});
		
		// Add mapping statistics
		if (frm.doc.account_mappings && frm.doc.account_mappings.length) {
			let active_count = frm.doc.account_mappings.filter(acc => acc.is_active).length;
			let total_count = frm.doc.account_mappings.length;
			
			frm.dashboard.add_indicator(__('Active Mappings: {0} / {1}', [active_count, total_count]), 
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

frappe.ui.form.on('SPP Account Mapping Detail', {
	source_account: function(frm, cdt, cdn) {
		// Auto-fill removed for consistency with other mapping Doctypes
	}
});

function import_csv_mapping(frm) {
	if (frm.is_new()) {
		frappe.msgprint(__('Please save this SPP Account Mapping before importing a CSV.'));
		return;
	}
	new frappe.ui.Dialog({
		title: __('Import Account Mappings from CSV'),
		fields: [
			{
				fieldtype: 'Attach',
				fieldname: 'csv_file',
				label: __('CSV File'),
				reqd: 1,
				description: __('Accepted headers: source_account, target_account, account_type')
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
					frm.refresh_field('account_mappings');
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

function test_account_mapping(frm) {
	new frappe.ui.Dialog({
		title: __('Test Account Mapping'),
		fields: [
			{
				fieldtype: 'Data',
				fieldname: 'source_account',
				label: __('Source Account'),
				reqd: 1
			}
		],
		primary_action_label: __('Test'),
		primary_action: function(values) {
			let target_item = frm.doc.account_mappings.find(
				acc => acc.source_account === values.source_account
			);
			
			if (target_item) {
				frappe.msgprint(__('Mapping Result: {0} → {1}', 
					[values.source_account, target_item.target_account]));
			} else {
				frappe.msgprint(__('No mapping found for account: {0}', [values.source_account]));
			}
			
			this.hide();
		}
	}).show();
}

function export_csv_mapping(frm) {
	let csv_data = 'source_account,target_account,account_type,is_active,notes\n';
	
	frm.doc.account_mappings.forEach(acc => {
		csv_data += `"${acc.source_account}","${acc.target_account}","${acc.account_type || ''}","${acc.is_active}","${acc.notes || ''}"\n`;
	});
	
	let blob = new Blob([csv_data], { type: 'text/csv' });
	let url = window.URL.createObjectURL(blob);
	let a = document.createElement('a');
	a.href = url;
	a.download = `${frm.doc.mapping_name}_account_mappings.csv`;
	a.click();
	window.URL.revokeObjectURL(url);
}