# Copyright (c) 2025, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
import json


def apply_spp_mappings(doc_data, source_site, target_site):
	"""
	Apply SPP custom mappings to document data during event streaming
	This function integrates with the existing event streaming mapping system
	"""
	if not doc_data or not isinstance(doc_data, dict):
		return doc_data
	
	# Apply company mapping
	if doc_data.get('company'):
		doc_data['company'] = get_company_mapping(
			source_site, target_site, doc_data['company']
		)
	
	# Apply item code mappings for Item doctype
	if doc_data.get('doctype') == 'Item' and doc_data.get('item_code'):
		doc_data['item_code'] = get_item_mapping(
			source_site, target_site, doc_data['item_code']
		)
	
	# Apply item code mappings for Stock Entry and other inventory documents
	if 'items' in doc_data and isinstance(doc_data['items'], list):
		for item in doc_data['items']:
			if item.get('item_code'):
				item['item_code'] = get_item_mapping(
					source_site, target_site, item['item_code']
				)
			if item.get('s_warehouse'):
				item['s_warehouse'] = get_warehouse_mapping(
					source_site, target_site, item['s_warehouse'], item.get('item_code')
				)
			if item.get('t_warehouse'):
				item['t_warehouse'] = get_warehouse_mapping(
					source_site, target_site, item['t_warehouse'], item.get('item_code')
				)
	
	# Apply warehouse mappings for Warehouse doctype
	if doc_data.get('doctype') == 'Warehouse' and doc_data.get('warehouse_name'):
		doc_data['warehouse_name'] = get_warehouse_mapping(
			source_site, target_site, doc_data['warehouse_name']
		)
	
	# Apply warehouse mappings for Stock Ledger Entry
	if doc_data.get('doctype') == 'Stock Ledger Entry':
		if doc_data.get('warehouse'):
			doc_data['warehouse'] = get_warehouse_mapping(
				source_site, target_site, doc_data['warehouse'], doc_data.get('item_code')
			)
		if doc_data.get('item_code'):
			doc_data['item_code'] = get_item_mapping(
				source_site, target_site, doc_data['item_code']
			)
	
	# Apply mappings for Manufacturing documents
	manufacturing_doctypes = ['Work Order', 'Job Card', 'Material Request']
	if doc_data.get('doctype') in manufacturing_doctypes:
		if doc_data.get('production_item'):
			doc_data['production_item'] = get_item_mapping(
				source_site, target_site, doc_data['production_item']
			)
		if doc_data.get('source_warehouse'):
			doc_data['source_warehouse'] = get_warehouse_mapping(
				source_site, target_site, doc_data['source_warehouse']
			)
		if doc_data.get('wip_warehouse'):
			doc_data['wip_warehouse'] = get_warehouse_mapping(
				source_site, target_site, doc_data['wip_warehouse']
			)
		if doc_data.get('fg_warehouse'):
			doc_data['fg_warehouse'] = get_warehouse_mapping(
				source_site, target_site, doc_data['fg_warehouse']
			)
	
	return doc_data


def get_company_mapping(source_site, target_site, source_company):
	"""Get mapped company name using SPP Company Mapping"""
	try:
		from event_streaming.event_streaming.doctype.spp_company_mapping.spp_company_mapping import get_company_mapping_for_sites
		return get_company_mapping_for_sites(source_site, target_site, source_company)
	except Exception:
		frappe.log_error(f"Error in company mapping: {source_company}")
		return source_company


def get_item_mapping(source_site, target_site, source_item_code):
	"""Get mapped item code using SPP Item Mapping"""
	try:
		from event_streaming.event_streaming.doctype.spp_item_mapping.spp_item_mapping import get_item_mapping_for_sites
		return get_item_mapping_for_sites(source_site, target_site, source_item_code)
	except Exception:
		frappe.log_error(f"Error in item mapping: {source_item_code}")
		return source_item_code


def get_warehouse_mapping(source_site, target_site, source_warehouse, item_code=None):
	"""Get mapped warehouse name using SPP Warehouse Mapping"""
	try:
		from event_streaming.event_streaming.doctype.spp_warehouse_mapping.spp_warehouse_mapping import get_warehouse_mapping_for_sites
		
		# Get item group for filtering if item_code is provided
		item_group = None
		if item_code:
			item_group = frappe.db.get_value("Item", item_code, "item_group")
		
		return get_warehouse_mapping_for_sites(source_site, target_site, source_warehouse, item_group)
	except Exception:
		frappe.log_error(f"Error in warehouse mapping: {source_warehouse}")
		return source_warehouse


@frappe.whitelist()
def bulk_import_mappings_from_csv():
	"""Utility function to bulk import all SPP mappings from CSV files"""
	
	# Import paths from your mappings folder
	import os
	mappings_path = frappe.get_app_path("event_streaming", "mappings")
	
	results = {
		"items": None,
		"warehouses": None,
		"companies": None
	}
	
	try:
		# Import Item Mappings
		item_csv_path = os.path.join(mappings_path, "item_mapping.csv")
		if os.path.exists(item_csv_path):
			from event_streaming.event_streaming.doctype.spp_item_mapping.spp_item_mapping import bulk_create_mappings_from_csv
			results["items"] = bulk_create_mappings_from_csv(
				item_csv_path, 
				"SPP Master to 2526 - Item Mapping",
				"sppmaster.local",
				"2526spp.local"
			)
		
		# Import Warehouse Mappings  
		warehouse_csv_path = os.path.join(mappings_path, "Wharehouse Mapping - Sheet1.csv")
		if os.path.exists(warehouse_csv_path):
			from event_streaming.event_streaming.doctype.spp_warehouse_mapping.spp_warehouse_mapping import bulk_create_warehouse_mappings_from_csv
			results["warehouses"] = bulk_create_warehouse_mappings_from_csv(
				warehouse_csv_path,
				"SPP Master to 2526 - Warehouse Mapping", 
				"sppmaster.local",
				"2526spp.local"
			)
		
		# Import Company Mappings
		company_csv_path = os.path.join(mappings_path, "company_mapping.csv")
		if os.path.exists(company_csv_path):
			# Create company mapping manually since it's simple
			if not frappe.db.exists("SPP Company Mapping", "SPP Master to 2526 - Company Mapping"):
				doc = frappe.new_doc("SPP Company Mapping")
				doc.mapping_name = "SPP Master to 2526 - Company Mapping"
				doc.source_site = "sppmaster.local"
				doc.target_site = "2526spp.local"
				doc.is_active = 1
				doc.append('company_mappings', {
					'source_company': 'SPP',
					'target_company': 'Shree Polymer Products',
					'is_active': 1
				})
				doc.save()
				results["companies"] = {"status": "success", "message": "Company mapping created"}
		
		frappe.db.commit()
		return results
		
	except Exception as e:
		frappe.log_error(f"Error in bulk import: {str(e)}")
		return {"status": "error", "message": str(e)}


@frappe.whitelist() 
def test_spp_mappings(doctype, doc_name):
	"""Test function to see how SPP mappings would be applied to a document"""
	
	doc = frappe.get_doc(doctype, doc_name)
	original_data = doc.as_dict()
	
	# Apply SPP mappings
	mapped_data = apply_spp_mappings(
		original_data.copy(),
		"sppmaster.local", 
		"2526spp.local"
	)
	
	return {
		"original": original_data,
		"mapped": mapped_data,
		"changes": get_mapping_changes(original_data, mapped_data)
	}


def get_mapping_changes(original, mapped):
	"""Compare original and mapped data to show what changed"""
	changes = {}
	
	def compare_values(orig_val, mapped_val, path):
		if orig_val != mapped_val:
			changes[path] = {
				"from": orig_val,
				"to": mapped_val
			}
	
	# Compare top-level fields
	for key in original:
		if key in mapped:
			if isinstance(original[key], list) and isinstance(mapped[key], list):
				# Handle child tables
				for i, (orig_item, mapped_item) in enumerate(zip(original[key], mapped[key])):
					if isinstance(orig_item, dict) and isinstance(mapped_item, dict):
						for sub_key in orig_item:
							if sub_key in mapped_item:
								compare_values(
									orig_item[sub_key], 
									mapped_item[sub_key], 
									f"{key}[{i}].{sub_key}"
								)
			else:
				compare_values(original[key], mapped[key], key)
	
	return changes