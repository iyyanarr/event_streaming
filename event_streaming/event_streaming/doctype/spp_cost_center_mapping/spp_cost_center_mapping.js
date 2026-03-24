// Copyright (c) 2025, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('SPP Cost Center Mapping', {
	refresh: function(frm) {
		// Add custom buttons
		frm.add_custom_button(__('Import from CSV'), function() {
			import_csv_mapping(frm);
		}, __('Actions'));
		
		frm.add_custom_button(__('Test Mapping'), function() {
			test_cost_center_mapping(frm);
		}, __('Actions'));
		
		frm.add_custom_button(__('Export to CSV'), function() {
			export_csv_mapping(frm);
		}, __('Actions'));
		
		// Set indicator formatter for active status
		frm.set_indicator_formatter('is_active', function(doc) {
			return doc.is_active ? 'green' : 'red';
		});
		
		// Add mapping statistics
		if (frm.doc.cost_center_mappings && frm.doc.cost_center_mappings.length) {
			let active_count = frm.doc.cost_center_mappings.filter(cc => cc.is_active).length;
			let total_count = frm.doc.cost_center_mappings.length;
			
			frm.dashboard.add_indicator(__('Active Mappings: {0} / {1}', [active_count, total_count]), 
				active_count === total_count ? 'green' : 'orange');
		}
	},
	
	producer_site: function(frm) {
		if (frm.doc.producer_site === frm.doc.consumer_site) {
			frappe.msgprint(__('Producer site and consumer site cannot be the same'));
			frm.set_value('producer_site', '');
		}
	},
	
	consumer_site: function(frm) {
		if (frm.doc.producer_site === frm.doc.consumer_site) {
			frappe.msgprint(__('Producer site and consumer site cannot be the same'));
			frm.set_value('consumer_site', '');
		}
	}
});

function import_csv_mapping(frm) {
	if (frm.is_new()) {
		frappe.msgprint(__('Please save this SPP Cost Center Mapping before importing a CSV.'));
		return;
	}
	new frappe.ui.Dialog({
		title: __('Import Cost Center Mappings from CSV'),
		fields: [
			{
				fieldtype: 'Attach',
				fieldname: 'csv_file',
				label: __('CSV File'),
				reqd: 1,
				description: __('Accepted headers: producer_cost_center, consumer_cost_center')
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
					frm.refresh_field('cost_center_mappings');
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

function test_cost_center_mapping(frm) {
	new frappe.ui.Dialog({
		title: __('Test Cost Center Mapping'),
		fields: [
			{
				fieldtype: 'Data',
				fieldname: 'producer_cost_center',
				label: __('Producer Cost Center'),
				reqd: 1
			}
		],
		primary_action_label: __('Test'),
		primary_action: function(values) {
			let target_item = frm.doc.cost_center_mappings.find(
				cc => cc.producer_cost_center === values.producer_cost_center
			);
			
			if (target_item) {
				frappe.msgprint(__('Mapping Result: {0} → {1}', 
					[values.producer_cost_center, target_item.consumer_cost_center]));
			} else {
				frappe.msgprint(__('No mapping found for cost center: {0}', [values.producer_cost_center]));
			}
			
			this.hide();
		}
	}).show();
}

function export_csv_mapping(frm) {
	let csv_data = 'producer_cost_center,consumer_cost_center,is_active,notes\n';
	
	frm.doc.cost_center_mappings.forEach(cc => {
		csv_data += `"${cc.producer_cost_center}","${cc.consumer_cost_center}","${cc.is_active}","${cc.notes || ''}"\n`;
	});
	
	let blob = new Blob([csv_data], { type: 'text/csv' });
	let url = window.URL.createObjectURL(blob);
	let a = document.createElement('a');
	a.href = url;
	a.download = `${frm.doc.mapping_name}_cost_center_mappings.csv`;
	a.click();
	window.URL.revokeObjectURL(url);
}