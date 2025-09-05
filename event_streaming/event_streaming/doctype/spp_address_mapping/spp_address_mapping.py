# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class SPPAddressMapping(Document):
	def validate(self):
		self.validate_duplicate_mappings()

	def validate_duplicate_mappings(self):
		"""Ensure no duplicate producer addresses in the mapping table"""
		producer_addresses = []
		for address_mapping in self.address_mappings:
			if address_mapping.producer_address in producer_addresses:
				frappe.throw(f"Duplicate producer address: {address_mapping.producer_address}")
			producer_addresses.append(address_mapping.producer_address)
