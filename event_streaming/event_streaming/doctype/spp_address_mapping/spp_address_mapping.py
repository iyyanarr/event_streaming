import frappe
from frappe import _
from frappe.model.document import Document


class SPPAddressMapping(Document):
	def validate(self):
		self.validate_duplicate_mappings()
		self.validate_sites()

	def validate_duplicate_mappings(self):
		"""Ensure no duplicate producer addresses in the mapping table"""
		producer_addresses = []
		for address_mapping in self.address_mappings:
			if address_mapping.producer_address in producer_addresses:
				frappe.throw(f"Duplicate producer address: {address_mapping.producer_address}")
			producer_addresses.append(address_mapping.producer_address)

	def validate_sites(self):
		"""Validate producer and consumer sites (if present)"""
		if hasattr(self, 'producer_site') and hasattr(self, 'consumer_site'):
			if self.producer_site == self.consumer_site:
				frappe.throw(_("Producer site and consumer site cannot be the same"))

	def get_target_address(self, producer_address):
		"""Return consumer address for a given producer address"""
		for mapping in self.address_mappings:
			if mapping.producer_address == producer_address and mapping.is_active:
				return mapping.consumer_address
		return producer_address

	@frappe.whitelist()
	def import_csv_mapping(self, csv_file_url):
		"""Import address mappings from uploaded CSV file."""
		import csv
		import os
		
		try:
			file_doc = frappe.get_doc("File", {"file_url": csv_file_url})
			file_path = file_doc.get_full_path()
			if not os.path.exists(file_path):
				frappe.throw(_("File not found: {0}").format(csv_file_url))
				
			self.address_mappings = []
			
			with open(file_path, 'r', encoding='utf-8') as csvfile:
				reader = csv.DictReader(csvfile)
				fieldnames = reader.fieldnames
				if not fieldnames:
					frappe.throw(_("CSV file is empty or invalid"))
				
				producer_col = None
				consumer_col = None
				for field in fieldnames:
					f = field.lower().strip().replace('\ufeff', '')
					if f in ['producer_address', 'producer address', 'old_address', 'source_address']:
						if not producer_col: producer_col = field
					elif f in ['consumer_address', 'consumer address', 'new_address', 'target_address']:
						if not consumer_col: consumer_col = field
				
				if (not producer_col or not consumer_col) and len(fieldnames) >= 2:
					if not producer_col: producer_col = fieldnames[0]
					if not consumer_col: consumer_col = fieldnames[1]
					
				if not producer_col or not consumer_col:
					frappe.throw(_("CSV must have columns for producer and consumer address"))
					
				imported = 0
				for row in reader:
					p = (row.get(producer_col) or '').strip()
					c = (row.get(consumer_col) or '').strip()
					if p and c:
						self.append('address_mappings', {
							'producer_address': p,
							'consumer_address': c,
							'is_active': 1
						})
						imported += 1
						
			self.flags.ignore_links = True
			self.save()
			frappe.db.commit()
			return {"message": _("Successfully imported {0} address mappings").format(imported), "count": imported}
		except Exception as e:
			frappe.log_error(frappe.get_traceback(), "CSV Import Error")
			frappe.throw(_("Error importing CSV: {0}").format(str(e)))


@frappe.whitelist()
def get_address_mapping_for_sites(producer_site, consumer_site, producer_address):
	"""Get address mapping between two sites for a specific address"""
	mapping = frappe.db.get_value(
		"SPP Address Mapping",
		{"producer_site": producer_site, "consumer_site": consumer_site, "is_active": 1},
		"name"
	)
	if not mapping:
		# fallback if site fields not present in doc
		mapping = frappe.db.get_value("SPP Address Mapping", {"is_active": 1}, "name")

	if mapping:
		doc = frappe.get_doc("SPP Address Mapping", mapping)
		return doc.get_target_address(producer_address)
	return producer_address
