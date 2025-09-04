# Copyright (c) 2025, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document


class SPPWarehouseMapping(Document):
	def validate(self):
		"""Validate warehouse mapping entries"""
		if not self.warehouse_mappings:
			frappe.throw(_("Please add at least one warehouse mapping"))
		
		# Check for duplicate producer warehouses within same item group
		producer_warehouses = {}
		for mapping in self.warehouse_mappings:
			key = f"{mapping.producer_warehouse}|{mapping.item_group or 'All'}"
			if key in producer_warehouses:
				frappe.throw(_("Duplicate producer warehouse '{0}' for item group '{1}'").format(
					mapping.producer_warehouse, mapping.item_group or 'All'
				))
			producer_warehouses[key] = True
	
	def get_consumer_warehouse(self, producer_warehouse, item_group=None):
		"""Get the consumer warehouse for a given producer warehouse"""
		# First try to find specific item group mapping
		if item_group:
			for mapping in self.warehouse_mappings:
				if mapping.producer_warehouse == producer_warehouse and mapping.item_group == item_group:
					return mapping.consumer_warehouse
		
		# Fallback to general mapping (no item group specified)
		for mapping in self.warehouse_mappings:
			if mapping.producer_warehouse == producer_warehouse and not mapping.item_group:
				return mapping.consumer_warehouse
		
		return producer_warehouse  # Return original if no mapping found


@frappe.whitelist()
def get_warehouse_mapping_for_sites(producer_site, consumer_site, producer_warehouse, item_group=None):
	"""Get warehouse mapping between two sites for a specific warehouse"""
	mapping = frappe.db.get_value(
		"SPP Warehouse Mapping",
		{"producer_site": producer_site, "consumer_site": consumer_site, "is_active": 1},
		"name"
	)
	
	if mapping:
		doc = frappe.get_doc("SPP Warehouse Mapping", mapping)
		return doc.get_consumer_warehouse(producer_warehouse, item_group)
	
	return producer_warehouse


@frappe.whitelist()
def bulk_create_warehouse_mappings_from_csv(file_path, mapping_name, producer_site, consumer_site):
	"""Create warehouse mappings from CSV file"""
	import csv
	
	# Create or get existing mapping document
	existing_mapping = frappe.db.get_value(
		"SPP Warehouse Mapping", 
		{"mapping_name": mapping_name}
	)
	
	if existing_mapping:
		doc = frappe.get_doc("SPP Warehouse Mapping", existing_mapping)
		doc.warehouse_mappings = []  # Clear existing mappings
	else:
		doc = frappe.new_doc("SPP Warehouse Mapping")
		doc.mapping_name = mapping_name
		doc.producer_site = producer_site
		doc.consumer_site = consumer_site
	
	# Read CSV and create mappings
	with open(file_path, 'r', encoding='utf-8') as csvfile:
		reader = csv.DictReader(csvfile)
		for row in reader:
			if row.get('Producer Warehouse') and row.get('Consumer Warehouse'):
				doc.append("warehouse_mappings", {
					"producer_warehouse": row['Producer Warehouse'].strip(),
					"consumer_warehouse": row['Consumer Warehouse'].strip(),
					"item_group": row.get('Item Group', '').strip() if row.get('Item Group') else None
				})
	
	doc.save()
	frappe.db.commit()
	
	return f"Created warehouse mapping '{mapping_name}' with {len(doc.warehouse_mappings)} entries"