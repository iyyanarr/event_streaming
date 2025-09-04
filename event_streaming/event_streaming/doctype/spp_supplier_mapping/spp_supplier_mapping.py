# Copyright (c) 2025, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document


class SPPSupplierMapping(Document):
	def validate(self):
		self.validate_duplicate_producer_suppliers()
		self.validate_sites()
	
	def validate_duplicate_producer_suppliers(self):
		"""Ensure no duplicate producer supplier names in the mapping (backward compatible)"""
		producer_suppliers = []
		for supplier in self.supplier_mappings or []:
			producer_val = getattr(supplier, 'producer_supplier', None) or getattr(supplier, 'source_supplier', None)
			if not producer_val:
				continue
			if producer_val in producer_suppliers:
				frappe.throw(_("Row #{0}: Duplicate producer supplier {1}").format(
					supplier.idx, frappe.bold(producer_val)
				))
			producer_suppliers.append(producer_val)
	
	def validate_sites(self):
		"""Validate producer and consumer sites (backward compatible fields)"""
		producer_site = getattr(self, 'producer_site', None) or getattr(self, 'source_site', None)
		consumer_site = getattr(self, 'consumer_site', None) or getattr(self, 'target_site', None)
		if producer_site and consumer_site and producer_site == consumer_site:
			frappe.throw(_("Producer site and consumer site cannot be the same"))
	
	def get_consumer_supplier(self, producer_supplier):
		"""Get consumer supplier for a given producer supplier (fallback to original if inactive or not found)"""
		if not self.is_active:
			return producer_supplier
		for supplier in self.supplier_mappings or []:
			row_producer = getattr(supplier, 'producer_supplier', None) or getattr(supplier, 'source_supplier', None)
			row_consumer = getattr(supplier, 'consumer_supplier', None) or getattr(supplier, 'target_supplier', None)
			if row_producer == producer_supplier and supplier.is_active:
				return row_consumer
		return producer_supplier
	
	def get_producer_supplier(self, consumer_supplier):
		"""Reverse mapping: find producer supplier from consumer supplier"""
		if not self.is_active:
			return consumer_supplier
		for supplier in self.supplier_mappings or []:
			row_producer = getattr(supplier, 'producer_supplier', None) or getattr(supplier, 'source_supplier', None)
			row_consumer = getattr(supplier, 'consumer_supplier', None) or getattr(supplier, 'target_supplier', None)
			if row_consumer == consumer_supplier and supplier.is_active:
				return row_producer
		return consumer_supplier

	@frappe.whitelist()
	def import_csv_mapping(self, csv_file_url=None, csv_data=None, replace=0):
		"""Import supplier mappings from CSV data (supports old & new headers).
		Args:
			csv_file_url: URL of uploaded File (standard Attach field behaviour)
			csv_data: Raw CSV text (alternative path)
			replace: If truthy, clear existing mappings before import
		"""
		import csv, io
		
		if not (csv_file_url or csv_data):
			frappe.throw(_('Please supply a CSV file'))
		
		# Fetch file content if url provided
		if csv_file_url and not csv_data:
			file_name = frappe.db.get_value('File', {'file_url': csv_file_url}, 'name')
			if not file_name:
				frappe.throw(_('File not found for URL: {0}').format(csv_file_url))
			file_doc = frappe.get_doc('File', file_name)
			content = file_doc.get_content()
			if isinstance(content, bytes):
				content = content.decode('utf-8')
			csv_data = content
		
		if replace:
			self.supplier_mappings = []  # clear existing only if replace is True
		
		reader = csv.DictReader(io.StringIO(csv_data))
		added = 0
		for row in reader:
			producer_supplier = (row.get('producer_supplier') or row.get('Producer Supplier') or
				row.get('source_supplier') or row.get('Source Supplier') or
				row.get('old_supplier') or row.get('Old Supplier'))
			consumer_supplier = (row.get('consumer_supplier') or row.get('Consumer Supplier') or
				row.get('target_supplier') or row.get('Target Supplier') or
				row.get('new_supplier') or row.get('New Supplier'))
			
			# Skip invalid or N/A entries
			if not producer_supplier or not consumer_supplier or producer_supplier.strip() == '#N/A' or consumer_supplier.strip() == '#N/A':
				continue
			
			if producer_supplier and consumer_supplier:
				self.append('supplier_mappings', {
					'producer_supplier': producer_supplier.strip(),
					'consumer_supplier': consumer_supplier.strip(),
					'supplier_group': row.get('supplier_group', '').strip() if row.get('supplier_group') else None,
					'is_active': 1
					})
				added += 1
		
		if added == 0:
			frappe.throw(_('No valid supplier mappings found in CSV. Please check the format and column headers.'))
		
		self.save()
		frappe.msgprint(_("Successfully imported {0} supplier mappings").format(added))


@frappe.whitelist()
def get_supplier_mapping_for_sites(producer_site, consumer_site, producer_supplier):
	"""Get supplier mapping between two sites for a specific producer supplier (backward compatible with old field names)"""
	# Try new field names first
	mapping = frappe.db.get_value(
		"SPP Supplier Mapping",
		{"producer_site": producer_site, "consumer_site": consumer_site, "is_active": 1},
		"name"
	)
	if not mapping:
		# Fallback to old field names if not yet migrated
		mapping = frappe.db.get_value(
			"SPP Supplier Mapping",
			{"source_site": producer_site, "target_site": consumer_site, "is_active": 1},
			"name"
		)
	if mapping:
		doc = frappe.get_doc("SPP Supplier Mapping", mapping)
		return doc.get_consumer_supplier(producer_supplier)
	return producer_supplier


@frappe.whitelist()
def bulk_create_supplier_mappings_from_csv(file_path, mapping_name, producer_site, consumer_site):
	"""Create supplier mappings from CSV file (supports old headers)"""
	try:
		if frappe.db.exists("SPP Supplier Mapping", mapping_name):
			frappe.throw(_("Mapping with name {0} already exists").format(mapping_name))
		import csv
		doc = frappe.new_doc("SPP Supplier Mapping")
		doc.mapping_name = mapping_name
		doc.producer_site = producer_site
		doc.consumer_site = consumer_site
		doc.is_active = 1
		with open(file_path, 'r') as file:
			reader = csv.DictReader(file)
			for row in reader:
				producer_supplier = (row.get('producer_supplier') or row.get('Producer Supplier') or
					row.get('source_supplier') or row.get('Source Supplier') or row.get('old_supplier'))
				consumer_supplier = (row.get('consumer_supplier') or row.get('Consumer Supplier') or
					row.get('target_supplier') or row.get('Target Supplier') or row.get('new_supplier'))
				if producer_supplier and consumer_supplier:
					doc.append('supplier_mappings', {
						'producer_supplier': producer_supplier.strip(),
						'consumer_supplier': consumer_supplier.strip(),
						'supplier_group': row.get('supplier_group', '').strip() if row.get('supplier_group') else None,
						'is_active': 1
					})
		doc.save()
		frappe.db.commit()
		return {"status": "success", "message": _("Successfully created mapping {0} with {1} suppliers").format(mapping_name, len(doc.supplier_mappings)), "mapping_name": mapping_name}
	except Exception as e:
		frappe.log_error(f"Error creating supplier mapping: {str(e)}")
		return {"status": "error", "message": str(e)}