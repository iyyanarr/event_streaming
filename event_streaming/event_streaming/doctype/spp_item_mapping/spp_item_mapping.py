# Copyright (c) 2025, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document


class SPPItemMapping(Document):
	def validate(self):
		self.validate_duplicate_source_items()
		self.validate_sites()
	
	def validate_duplicate_source_items(self):
		"""Ensure no duplicate source item codes in the mapping"""
		source_items = []
		for item in self.item_mappings:
			if item.source_item_code in source_items:
				frappe.throw(_("Row #{0}: Duplicate source item code {1}").format(
					item.idx, frappe.bold(item.source_item_code)
				))
			source_items.append(item.source_item_code)
	
	def validate_sites(self):
		"""Validate source and target sites"""
		if self.source_site == self.target_site:
			frappe.throw(_("Source site and target site cannot be the same"))
	
	def get_target_item_code(self, source_item_code):
		"""Get target item code for a given source item code"""
		if not self.is_active:
			return source_item_code
			
		for item in self.item_mappings:
			if item.source_item_code == source_item_code and item.is_active:
				return item.target_item_code
		
		# Return source item code if no mapping found
		return source_item_code
	
	def get_source_item_code(self, target_item_code):
		"""Get source item code for a given target item code (reverse mapping)"""
		if not self.is_active:
			return target_item_code
			
		for item in self.item_mappings:
			if item.target_item_code == target_item_code and item.is_active:
				return item.source_item_code
		
		# Return target item code if no mapping found
		return target_item_code

	@frappe.whitelist()
	def import_csv_mapping(self, csv_data):
		"""Import item mappings from CSV data"""
		import csv
		import io
		
		# Clear existing mappings
		self.item_mappings = []
		
		# Parse CSV data
		reader = csv.DictReader(io.StringIO(csv_data))
		for row in reader:
			if row.get('old_item_code') and row.get('new_item_code'):
				self.append('item_mappings', {
					'source_item_code': row['old_item_code'].strip(),
					'target_item_code': row['new_item_code'].strip(),
					'is_active': 1
				})
		
		self.save()
		frappe.msgprint(_("Successfully imported {0} item mappings").format(len(self.item_mappings)))


@frappe.whitelist()
def get_item_mapping_for_sites(source_site, target_site, source_item_code):
	"""Get item mapping between two sites for a specific item"""
	mapping = frappe.db.get_value(
		"SPP Item Mapping",
		{"source_site": source_site, "target_site": target_site, "is_active": 1},
		"name"
	)
	
	if mapping:
		doc = frappe.get_doc("SPP Item Mapping", mapping)
		return doc.get_target_item_code(source_item_code)
	
	return source_item_code


@frappe.whitelist()
def bulk_create_mappings_from_csv(file_path, mapping_name, source_site, target_site):
	"""Create item mappings from CSV file"""
	try:
		# Check if mapping already exists
		if frappe.db.exists("SPP Item Mapping", mapping_name):
			frappe.throw(_("Mapping with name {0} already exists").format(mapping_name))
		
		# Create new mapping document
		doc = frappe.new_doc("SPP Item Mapping")
		doc.mapping_name = mapping_name
		doc.source_site = source_site
		doc.target_site = target_site
		doc.is_active = 1
		
		# Read CSV file and create mappings
		import csv
		with open(file_path, 'r') as file:
			reader = csv.DictReader(file)
			for row in reader:
				if row.get('old_item_code') and row.get('new_item_code'):
					doc.append('item_mappings', {
						'source_item_code': row['old_item_code'].strip(),
						'target_item_code': row['new_item_code'].strip(),
						'is_active': 1
					})
		
		doc.save()
		frappe.db.commit()
		
		return {
			"status": "success",
			"message": _("Successfully created mapping {0} with {1} items").format(
				mapping_name, len(doc.item_mappings)
			),
			"mapping_name": mapping_name
		}
		
	except Exception as e:
		frappe.log_error(f"Error creating item mapping: {str(e)}")
		return {
			"status": "error", 
			"message": str(e)
		}