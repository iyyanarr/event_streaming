# Copyright (c) 2025, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document


class SPPSupplierMapping(Document):
	def validate(self):
		self.validate_duplicate_source_suppliers()
		self.validate_sites()
	
	def validate_duplicate_source_suppliers(self):
		"""Ensure no duplicate source supplier names in the mapping"""
		source_suppliers = []
		for supplier in self.supplier_mappings:
			if supplier.source_supplier in source_suppliers:
				frappe.throw(_("Row #{0}: Duplicate source supplier {1}").format(
					supplier.idx, frappe.bold(supplier.source_supplier)
				))
			source_suppliers.append(supplier.source_supplier)
	
	def validate_sites(self):
		"""Validate source and target sites"""
		if self.source_site == self.target_site:
			frappe.throw(_("Source site and target site cannot be the same"))
	
	def get_target_supplier(self, source_supplier):
		"""Get target supplier for a given source supplier"""
		if not self.is_active:
			return source_supplier
			
		for supplier in self.supplier_mappings:
			if supplier.source_supplier == source_supplier and supplier.is_active:
				return supplier.target_supplier
		
		# Return source supplier if no mapping found
		return source_supplier
	
	def get_source_supplier(self, target_supplier):
		"""Get source supplier for a given target supplier (reverse mapping)"""
		if not self.is_active:
			return target_supplier
			
		for supplier in self.supplier_mappings:
			if supplier.target_supplier == target_supplier and supplier.is_active:
				return supplier.source_supplier
		
		# Return target supplier if no mapping found
		return target_supplier

	@frappe.whitelist()
	def import_csv_mapping(self, csv_data):
		"""Import supplier mappings from CSV data"""
		import csv
		import io
		
		# Clear existing mappings
		self.supplier_mappings = []
		
		# Parse CSV data
		reader = csv.DictReader(io.StringIO(csv_data))
		for row in reader:
			# Handle different CSV column names
			source_supplier = row.get('source_supplier') or row.get('Source Supplier') or row.get('old_supplier')
			target_supplier = row.get('target_supplier') or row.get('Target Supplier') or row.get('new_supplier')
			
			if source_supplier and target_supplier:
				self.append('supplier_mappings', {
					'source_supplier': source_supplier.strip(),
					'target_supplier': target_supplier.strip(),
					'supplier_group': row.get('supplier_group', '').strip() if row.get('supplier_group') else None,
					'is_active': 1
				})
		
		self.save()
		frappe.msgprint(_("Successfully imported {0} supplier mappings").format(len(self.supplier_mappings)))


@frappe.whitelist()
def get_supplier_mapping_for_sites(source_site, target_site, source_supplier):
	"""Get supplier mapping between two sites for a specific supplier"""
	mapping = frappe.db.get_value(
		"SPP Supplier Mapping",
		{"source_site": source_site, "target_site": target_site, "is_active": 1},
		"name"
	)
	
	if mapping:
		doc = frappe.get_doc("SPP Supplier Mapping", mapping)
		return doc.get_target_supplier(source_supplier)
	
	return source_supplier


@frappe.whitelist()
def bulk_create_supplier_mappings_from_csv(file_path, mapping_name, source_site, target_site):
	"""Create supplier mappings from CSV file"""
	try:
		# Check if mapping already exists
		if frappe.db.exists("SPP Supplier Mapping", mapping_name):
			frappe.throw(_("Mapping with name {0} already exists").format(mapping_name))
		
		# Create new mapping document
		doc = frappe.new_doc("SPP Supplier Mapping")
		doc.mapping_name = mapping_name
		doc.source_site = source_site
		doc.target_site = target_site
		doc.is_active = 1
		
		# Read CSV file and create mappings
		import csv
		with open(file_path, 'r') as file:
			reader = csv.DictReader(file)
			for row in reader:
				# Handle different CSV column names
				source_supplier = row.get('source_supplier') or row.get('Source Supplier') or row.get('old_supplier')
				target_supplier = row.get('target_supplier') or row.get('Target Supplier') or row.get('new_supplier')
				
				if source_supplier and target_supplier:
					doc.append('supplier_mappings', {
						'source_supplier': source_supplier.strip(),
						'target_supplier': target_supplier.strip(),
						'supplier_group': row.get('supplier_group', '').strip() if row.get('supplier_group') else None,
						'is_active': 1
					})
		
		doc.save()
		frappe.db.commit()
		
		return {
			"status": "success",
			"message": _("Successfully created mapping {0} with {1} suppliers").format(
				mapping_name, len(doc.supplier_mappings)
			),
			"mapping_name": mapping_name
		}
		
	except Exception as e:
		frappe.log_error(f"Error creating supplier mapping: {str(e)}")
		return {
			"status": "error", 
			"message": str(e)
		}