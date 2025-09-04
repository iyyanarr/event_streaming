// Copyright (c) 2025, Frappe Technologies and contributors
// License: MIT. See LICENSE

frappe.ui.form.on('SPP Item Mapping', {
	refresh: function(frm) {
		// Add custom buttons
		frm.add_custom_button(__('Import from CSV'), function() {
			import_csv_mapping(frm);
		}, __('Actions'));
		
		frm.add_custom_button(__('Test Mapping'), function() {
			test_item_mapping(frm);
		}, __('Actions'));
		
		frm.add_custom_button(__('Export to CSV'), function() {
			export_csv_mapping(frm);
		}, __('Actions'));
		
		// Set indicator formatter for active status
		frm.set_indicator_formatter('is_active', function(doc) {
			return doc.is_active ? 'green' : 'red';
		});
		
		// Add mapping statistics
		if (frm.doc.item_mappings && frm.doc.item_mappings.length) {
			let active_count = frm.doc.item_mappings.filter(item => item.is_active).length;
			let total_count = frm.doc.item_mappings.length;
			
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

frappe.ui.form.on('SPP Item Mapping Detail', {
	producer_item_code: function(frm, cdt, cdn) {
		// Auto-fill removed: previously copied producer -> consumer when blank.
		// This caused overwriting during render/import race conditions.
		// Users must now enter consumer code explicitly or rely on CSV import.
	}
});

function import_csv_mapping(frm) {
	// Prevent import before initial save to avoid duplicate insert issues
	if (frm.is_new()) {
		frappe.msgprint(__('Please save this SPP Item Mapping before importing a CSV.'));
		return;
	}
	new frappe.ui.Dialog({
		title: __('Import Item Mappings from CSV'),
		fields: [
			{
				fieldtype: 'Attach',
				fieldname: 'csv_file',
				label: __('CSV File'),
				reqd: 1,
				description: __('Accepted headers (any pair): old_item_code/new_item_code, source_item_code/target_item_code, producer_item_code/consumer_item_code, Producer Item Code/Consumer Item Code')
			}
		],
		primary_action_label: __('Import'),
		primary_action: function(values) {
			if (!values.csv_file) {
				frappe.msgprint(__('Please attach a CSV file'));
				return;
			}
			frm.call('import_csv_mapping', { csv_file_url: values.csv_file }).then((r) => {
				// Force reload so freshly saved child table rows are fetched from server
				frm.reload_doc().then(() => {
					// Explicitly refresh child table field
					frm.refresh_field('item_mappings');
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

function test_item_mapping(frm) {
	new frappe.ui.Dialog({
		title: __('Test Item Mapping'),
		fields: [
			{
				fieldtype: 'Data',
				fieldname: 'producer_item_code',
				label: __('Producer Item Code'),
				reqd: 1
			}
		],
		primary_action_label: __('Test'),
		primary_action: function(values) {
			let target_item = frm.doc.item_mappings.find(
				item => item.producer_item_code === values.producer_item_code
			);
			
			if (target_item) {
				frappe.msgprint(__('Mapping Result: {0} → {1}', 
					[values.producer_item_code, target_item.consumer_item_code]));
			} else {
				frappe.msgprint(__('No mapping found for item code: {0}', [values.producer_item_code]));
			}
			
			this.hide();
		}
	}).show();
}

function export_csv_mapping(frm) {
	let csv_data = 'producer_item_code,consumer_item_code,item_group,is_active,notes\n';
	
	frm.doc.item_mappings.forEach(item => {
		csv_data += `"${item.producer_item_code}","${item.consumer_item_code}","${item.item_group || ''}","${item.is_active}","${item.notes || ''}"\n`;
	});
	
	// Create and download CSV file
	let blob = new Blob([csv_data], { type: 'text/csv' });
	let url = window.URL.createObjectURL(blob);
	let a = document.createElement('a');
	a.href = url;
	a.download = `${frm.doc.mapping_name}_item_mappings.csv`;
	a.click();
	window.URL.revokeObjectURL(url);
}