# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class SPPContactMapping(Document):
	def validate(self):
		self.validate_duplicate_mappings()

	def validate_duplicate_mappings(self):
		"""Ensure no duplicate producer contacts in the mapping table"""
		producer_contacts = []
		for contact_mapping in self.contact_mappings:
			if contact_mapping.producer_contact in producer_contacts:
				frappe.throw(f"Duplicate producer contact: {contact_mapping.producer_contact}")
			producer_contacts.append(contact_mapping.producer_contact)