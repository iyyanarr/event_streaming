# Copyright (c) 2025, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document


class SPPWarehouseMapping(Document):
	def validate(self):
		self.validate_duplicate_source_warehouses()
		self.validate_sites()
	
	def validate_duplicate_source_warehouses(self):
		"""Ensure no duplicate source warehouse names in the mapping"""
		source_warehouses = []
		for warehouse in self.warehouse_mappings:
			if warehouse.source_warehouse in source_warehouses:
				frappe.throw(_("Row #{0}: Duplicate source warehouse {1}").format(
					warehouse.idx, frappe.bold(warehouse.source_warehouse)
				))
			source_warehouses.append(warehouse.source_warehouse)
	
	def validate_sites(self):
		"""Validate source and target sites"""
		if self.source_site == self.target_site:
			frappe.throw(_("Source site and target site cannot be the same"))
	
	def get_target_warehouse(self, source_warehouse, item_group=None):
		"""Get target warehouse for a given source warehouse with optional item group filtering"""
		if not self.is_active:
			return source_warehouse
			
		for warehouse in self.warehouse_mappings:
			if warehouse.source_warehouse == source_warehouse and warehouse.is_active:
				# Check item group filter if specified
				if item_group and warehouse.item_group_filter:
					item_groups = [ig.strip() for ig in warehouse.item_group_filter.split(',')]
					if item_group not in item_groups:
						continue
				return warehouse.target_warehouse
		
		# Return source warehouse if no mapping found
		return source_warehouse
	
	def get_source_warehouse(self, target_warehouse):
		"""Get source warehouse for a given target warehouse (reverse mapping)"""
		if not self.is_active:
			return target_warehouse
			
		for warehouse in self.warehouse_mappings:
			if warehouse.target_warehouse == target_warehouse and warehouse.is_active:
				return warehouse.source_warehouse
		
		# Return target warehouse if no mapping found
		return target_warehouse

	@frappe.whitelist()
	def import_csv_mapping(self, csv_data):
		"""Import warehouse mappings from CSV data"""
		import csv
		import io
		
		# Clear existing mappings
		self.warehouse_mappings = []
		
		# Parse CSV data
		reader = csv.DictReader(io.StringIO(csv_data))
		for row in reader:
			if row.get('Old Warehouse') and row.get('New Warehouse'):
				self.append('warehouse_mappings', {
					'source_warehouse': row['Old Warehouse'].strip(),
					'target_warehouse': row['New Warehouse'].strip(),
					'company': row.get('', '').strip() if row.get('') else None,
					'warehouse_type': row.get('', '').strip() if row.get('') else None,
					'item_group_filter': row.get('Item Group', '').strip() if row.get('Item Group') else None,
					'is_active': 1
				})
		
		self.save()
		frappe.msgprint(_("Successfully imported {0} warehouse mappings").format(len(self.warehouse_mappings)))


@frappe.whitelist()
def get_warehouse_mapping_for_sites(source_site, target_site, source_warehouse, item_group=None):
	"""Get warehouse mapping between two sites for a specific warehouse"""
	mapping = frappe.db.get_value(
		"SPP Warehouse Mapping",
		{"source_site": source_site, "target_site": target_site, "is_active": 1},
		"name"
	)
	
	if mapping:
		doc = frappe.get_doc("SPP Warehouse Mapping", mapping)
		return doc.get_target_warehouse(source_warehouse, item_group)
	
	return source_warehouse


@frappe.whitelist()
def bulk_create_warehouse_mappings_from_csv(file_path, mapping_name, source_site, target_site):
	"""Create warehouse mappings from CSV file"""
	try:
		# Check if mapping already exists
		if frappe.db.exists("SPP Warehouse Mapping", mapping_name):
			frappe.throw(_("Mapping with name {0} already exists").format(mapping_name))
		
		# Create new mapping document
		doc = frappe.new_doc("SPP Warehouse Mapping")
		doc.mapping_name = mapping_name
		doc.source_site = source_site
		doc.target_site = target_site
		doc.is_active = 1
		
		# Read CSV file and create mappings
		import csv
		with open(file_path, 'r') as file:
			reader = csv.DictReader(file)
			for row in reader:
				if row.get('Old Warehouse') and row.get('New Warehouse'):
					doc.append('warehouse_mappings', {
						'source_warehouse': row['Old Warehouse'].strip(),
						'target_warehouse': row['New Warehouse'].strip(),
						'company': row.get('', '').strip() if row.get('') else None,
						'warehouse_type': row.get('', '').strip() if row.get('') else None,
						'item_group_filter': row.get('Item Group', '').strip() if row.get('Item Group') else None,
						'is_active': 1
					})
		
		doc.save()
		frappe.db.commit()
		
		return {
			"status": "success",
			"message": _("Successfully created mapping {0} with {1} warehouses").format(
				mapping_name, len(doc.warehouse_mappings)
			),
			"mapping_name": mapping_name
		}
		
	except Exception as e:
		frappe.log_error(f"Error creating warehouse mapping: {str(e)}")
		return {
			"status": "error", 
			"message": str(e)
		}