// Copyright (c) 2025, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('SPP Warehouse Mapping', {
	refresh: function(frm) {
		// Add custom buttons
		frm.add_custom_button(__('Import from CSV'), function() {
			import_csv_mapping(frm);
		}, __('Actions'));
		
		frm.add_custom_button(__('Test Mapping'), function() {
			test_warehouse_mapping(frm);
		}, __('Actions'));
		
		frm.add_custom_button(__('Export to CSV'), function() {
			export_csv_mapping(frm);
		}, __('Actions'));
		
		// Set indicator formatter for active status
		frm.set_indicator_formatter('is_active', function(doc) {
			return doc.is_active ? 'green' : 'red';
		});
		
		// Add mapping statistics
		if (frm.doc.warehouse_mappings && frm.doc.warehouse_mappings.length) {
			let active_count = frm.doc.warehouse_mappings.filter(wh => wh.is_active).length;
			let total_count = frm.doc.warehouse_mappings.length;
			
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

frappe.ui.form.on('SPP Warehouse Mapping Detail', {
	warehouse_mappings_add: function(frm, cdt, cdn) {
		// New row added
	}
});

function import_csv_mapping(frm) {
	if (frm.is_new()) {
		frappe.msgprint(__('Please save this SPP Warehouse Mapping before importing a CSV.'));
		return;
	}
	new frappe.ui.Dialog({
		title: __('Import Warehouse Mappings from CSV'),
		fields: [
			{
				fieldtype: 'Attach',
				fieldname: 'csv_file',
				label: __('CSV File'),
				reqd: 1,
				description: __('Accepted headers: producer_warehouse, consumer_warehouse, item_group, operations')
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
					frm.refresh_field('warehouse_mappings');
					let info = r.message || {};
					frappe.show_alert({
						message: __('Imported {0} mappings', [info.count || info.added || 0]),
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

function test_warehouse_mapping(frm) {
	new frappe.ui.Dialog({
		title: __('Test Warehouse Mapping'),
		fields: [
			{
				fieldtype: 'Data',
				fieldname: 'producer_warehouse',
				label: __('Producer Warehouse'),
				reqd: 1
			},
			{
				fieldtype: 'Data',
				fieldname: 'item_group',
				label: __('Item Group (Optional)'),
			},
			{
				fieldtype: 'Data',
				fieldname: 'operations',
				label: __('Operations (Optional)'),
			}
		],
		primary_action_label: __('Test'),
		primary_action: function(values) {
			let filters = { producer_warehouse: values.producer_warehouse };
			if (values.item_group) filters.item_group = values.item_group;
			if (values.operations) filters.operations = values.operations;
			
			// Simple local search for simulation
			let results = frm.doc.warehouse_mappings.filter(wh => {
				let match = wh.producer_warehouse === values.producer_warehouse;
				if (values.item_group && wh.item_group) {
					match = match && wh.item_group.includes(values.item_group);
				}
				if (values.operations && wh.operations) {
					match = match && wh.operations.includes(values.operations);
				}
				return match && wh.is_active;
			});
			
			if (results.length > 0) {
				let msg = __('Mapping Results for {0}:', [values.producer_warehouse]);
				results.forEach(r => {
					msg += `<br>→ ${r.consumer_warehouse} (Group: ${r.item_group || 'Any'}, Ops: ${r.operations || 'Any'})`;
				});
				frappe.msgprint(msg);
			} else {
				frappe.msgprint(__('No mapping found for warehouse: {0}', [values.producer_warehouse]));
			}
			
			this.hide();
		}
	}).show();
}

function export_csv_mapping(frm) {
	let csv_data = 'producer_warehouse,consumer_warehouse,item_group,operations,is_active,notes\n';
	
	frm.doc.warehouse_mappings.forEach(wh => {
		csv_data += `"${wh.producer_warehouse}","${wh.consumer_warehouse}","${wh.item_group || ''}","${wh.operations || ''}","${wh.is_active}","${wh.notes || ''}"\n`;
	});
	
	let blob = new Blob([csv_data], { type: 'text/csv' });
	let url = window.URL.createObjectURL(blob);
	let a = document.createElement('a');
	a.href = url;
	a.download = `${frm.doc.mapping_name}_warehouse_mappings.csv`;
	a.click();
	window.URL.revokeObjectURL(url);
}