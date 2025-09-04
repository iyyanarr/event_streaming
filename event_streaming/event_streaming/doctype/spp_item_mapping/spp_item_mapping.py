# Copyright (c) 2025, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document


class SPPItemMapping(Document):
	def validate(self):
		"""Validate item mapping entries"""
		if not self.item_mappings:
			frappe.throw(_("Please add at least one item mapping"))
		
		# Check for duplicate producer item codes
		producer_items = []
		for mapping in self.item_mappings:
			if mapping.producer_item_code in producer_items:
				frappe.throw(_("Duplicate producer item code: {0}").format(mapping.producer_item_code))
			producer_items.append(mapping.producer_item_code)
	
	def get_consumer_item_code(self, producer_item_code):
		"""Get the consumer item code for a given producer item code"""
		for mapping in self.item_mappings:
			if mapping.producer_item_code == producer_item_code:
				return mapping.consumer_item_code
		return producer_item_code  # Return original if no mapping found


@frappe.whitelist()
def get_item_mapping_for_sites(producer_site, consumer_site, producer_item_code):
	"""Get item mapping between two sites for a specific item"""
	mapping = frappe.db.get_value(
		"SPP Item Mapping",
		{"producer_site": producer_site, "consumer_site": consumer_site, "is_active": 1},
		"name"
	)
	
	if mapping:
		doc = frappe.get_doc("SPP Item Mapping", mapping)
		return doc.get_consumer_item_code(producer_item_code)
	
	return producer_item_code


@frappe.whitelist()
def bulk_create_mappings_from_csv(file_path, mapping_name, producer_site, consumer_site):
	"""Create item mappings from CSV file"""
	import csv
	
	# Create or get existing mapping document
	existing_mapping = frappe.db.get_value(
		"SPP Item Mapping", 
		{"mapping_name": mapping_name}
	)
	
	if existing_mapping:
		doc = frappe.get_doc("SPP Item Mapping", existing_mapping)
		doc.item_mappings = []  # Clear existing mappings
	else:
		doc = frappe.new_doc("SPP Item Mapping")
		doc.mapping_name = mapping_name
		doc.producer_site = producer_site
		doc.consumer_site = consumer_site
	
	# Read CSV and create mappings
	with open(file_path, 'r', encoding='utf-8') as csvfile:
		reader = csv.DictReader(csvfile)
		for row in reader:
			if row.get('Producer Item Code') and row.get('Consumer Item Code'):
				doc.append("item_mappings", {
					"producer_item_code": row['Producer Item Code'].strip(),
					"consumer_item_code": row['Consumer Item Code'].strip(),
					"item_group": row.get('Item Group', '').strip() if row.get('Item Group') else None
				})
	
	doc.save()
	frappe.db.commit()
	
	return f"Created item mapping '{mapping_name}' with {len(doc.item_mappings)} entries"