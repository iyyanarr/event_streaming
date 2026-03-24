# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _


class SPPContactMapping(Document):
	def validate(self):
		self.validate_duplicate_mappings()
		self.validate_sites()

	def validate_duplicate_mappings(self):
		"""Ensure no duplicate producer contacts in the mapping table"""
		producer_contacts = []
		for contact_mapping in self.contact_mappings:
			if contact_mapping.producer_contact in producer_contacts:
				frappe.throw(f"Duplicate producer contact: {contact_mapping.producer_contact}")
			producer_contacts.append(contact_mapping.producer_contact)

	def validate_sites(self):
		"""Validate producer and consumer sites (if present)"""
		if hasattr(self, 'producer_site') and hasattr(self, 'consumer_site'):
			if self.producer_site == self.consumer_site:
				frappe.throw(_("Producer site and consumer site cannot be the same"))

	def get_target_contact(self, producer_contact):
		"""Return consumer contact for a given producer contact"""
		for mapping in self.contact_mappings:
			if mapping.producer_contact == producer_contact and mapping.is_active:
				return mapping.consumer_contact
		return producer_contact

	@frappe.whitelist()
	def import_csv_mapping(self, csv_file_url):
		"""Import contact mappings from uploaded CSV file."""
		import csv
		import os
		
		try:
			file_doc = frappe.get_doc("File", {"file_url": csv_file_url})
			file_path = file_doc.get_full_path()
			if not os.path.exists(file_path):
				frappe.throw(_("File not found: {0}").format(csv_file_url))
				
			self.contact_mappings = []
			
			with open(file_path, 'r', encoding='utf-8') as csvfile:
				reader = csv.DictReader(csvfile)
				fieldnames = reader.fieldnames
				if not fieldnames:
					frappe.throw(_("CSV file is empty or invalid"))
				
				producer_col = None
				consumer_col = None
				for field in fieldnames:
					f = field.lower().strip().replace('\ufeff', '')
					if f in ['producer_contact', 'producer contact', 'old_contact', 'source_contact']:
						if not producer_col: producer_col = field
					elif f in ['consumer_contact', 'consumer contact', 'new_contact', 'target_contact']:
						if not consumer_col: consumer_col = field
				
				if (not producer_col or not consumer_col) and len(fieldnames) >= 2:
					if not producer_col: producer_col = fieldnames[0]
					if not consumer_col: consumer_col = fieldnames[1]
					
				if not producer_col or not consumer_col:
					frappe.throw(_("CSV must have columns for producer and consumer contact"))
					
				imported = 0
				for row in reader:
					p = (row.get(producer_col) or '').strip()
					c = (row.get(consumer_col) or '').strip()
					if p and c:
						self.append('contact_mappings', {
							'producer_contact': p,
							'consumer_contact': c,
							'is_active': 1
						})
						imported += 1
						
			self.save()
			frappe.db.commit()
			return {"message": _("Successfully imported {0} contact mappings").format(imported), "count": imported}
		except Exception as e:
			frappe.log_error(frappe.get_traceback(), "CSV Import Error")
			frappe.throw(_("Error importing CSV: {0}").format(str(e)))


@frappe.whitelist()
def get_contact_mapping_for_sites(producer_site, consumer_site, producer_contact):
	"""Get contact mapping between two sites for a specific contact"""
	mapping = frappe.db.get_value(
		"SPP Contact Mapping",
		{"producer_site": producer_site, "consumer_site": consumer_site, "is_active": 1},
		"name"
	)
	if not mapping:
		mapping = frappe.db.get_value("SPP Contact Mapping", {"is_active": 1}, "name")

	if mapping:
		doc = frappe.get_doc("SPP Contact Mapping", mapping)
		return doc.get_target_contact(producer_contact)
	return producer_contact