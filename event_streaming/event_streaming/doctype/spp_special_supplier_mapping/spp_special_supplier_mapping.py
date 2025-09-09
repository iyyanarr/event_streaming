# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class SPPSpecialSupplierMapping(Document):
	def validate(self):
		"""Validate the special supplier mapping configuration"""
		self.validate_duplicate_suppliers()
		self.validate_mapping_logic()

	def validate_duplicate_suppliers(self):
		"""Ensure no duplicate producer suppliers in the same mapping"""
		suppliers = []
		for mapping in self.special_mappings:
			if mapping.producer_supplier in suppliers:
				frappe.throw(f"Duplicate producer supplier: {mapping.producer_supplier}")
			suppliers.append(mapping.producer_supplier)

	def validate_mapping_logic(self):
		"""Validate the mapping logic configuration"""
		for mapping in self.special_mappings:
			if mapping.mapping_type == "Address Based":
				if not mapping.address_field:
					frappe.throw(f"Address field is required for Address Based mapping: {mapping.producer_supplier}")
			elif mapping.mapping_type == "Direct":
				if not mapping.consumer_supplier:
					frappe.throw(f"Consumer supplier is required for Direct mapping: {mapping.producer_supplier}")

	def get_special_supplier_mapping(self, producer_supplier, doc_data=None):
		"""Get special mapping for a producer supplier"""
		frappe.logger().info(f"Special supplier mapping called for: {producer_supplier}")
		frappe.logger().info(f"Document data keys: {list(doc_data.keys()) if doc_data else 'None'}")
		
		for mapping in self.special_mappings:
			# Check for exact match OR partial match (in case Document Type Mapping already modified the supplier name)
			is_match = (mapping.producer_supplier == producer_supplier or 
			           mapping.producer_supplier in producer_supplier or
			           producer_supplier in mapping.producer_supplier or
			           # Also check for B P CHEMICALS variations
			           (mapping.producer_supplier == "B P CHEMICALS" and "B P Chemicals" in producer_supplier))
			           
			if is_match and mapping.is_active:
				frappe.logger().info(f"Found matching mapping for {producer_supplier}: type={mapping.mapping_type}")
				
				if mapping.mapping_type == "Address Based":
					return self.process_address_based_mapping(mapping, doc_data)
				elif mapping.mapping_type == "Direct":
					return mapping.consumer_supplier
				elif mapping.mapping_type == "Custom":
					return self.process_custom_mapping(mapping, doc_data)
		
		frappe.logger().warning(f"No special mapping found for supplier: {producer_supplier}")
		return None

	def process_address_based_mapping(self, mapping, doc_data):
		"""Process address-based mapping logic"""
		frappe.logger().info(f"Processing address-based mapping for {mapping.producer_supplier}")
		
		if not doc_data:
			frappe.logger().warning(f"No document data provided for address-based mapping: {mapping.producer_supplier}")
			return mapping.fallback_supplier or mapping.producer_supplier

		# Get address field value from document
		address_value = doc_data.get(mapping.address_field)
		frappe.logger().info(f"Address field '{mapping.address_field}' value: {address_value}")
		
		if not address_value:
			frappe.logger().warning(f"No {mapping.address_field} found in document for supplier {mapping.producer_supplier}")
			return mapping.fallback_supplier or mapping.producer_supplier

			# REAL ADDRESS-BASED MAPPING LOGIC:
		# 1. Get mapped address using SPP Address Mapping
		mapped_address = self.get_mapped_address(address_value)
		frappe.logger().info(f"Mapped address: {address_value} -> {mapped_address}")

		if mapped_address:
			# 2. Find supplier linked to the mapped address
			linked_supplier = self.get_supplier_from_mapped_address(mapped_address)
			frappe.logger().info(f"Supplier linked to mapped address {mapped_address}: {linked_supplier}")
			
			if linked_supplier:
				frappe.logger().info(f"Address-based mapping SUCCESS: {mapping.producer_supplier} -> {linked_supplier} (via address {address_value} -> {mapped_address})")
				return linked_supplier
			else:
				frappe.logger().warning(f"No supplier found linked to mapped address: {mapped_address}")
		else:
			frappe.logger().warning(f"No address mapping found for: {address_value}")

		# Fallback to configured fallback supplier
		fallback = mapping.fallback_supplier
		if fallback:
			frappe.logger().info(f"Using fallback supplier for {mapping.producer_supplier}: {fallback}")
			return fallback
		else:
			frappe.logger().warning(f"No fallback supplier configured for {mapping.producer_supplier}, keeping original")
			return mapping.producer_supplier

	def get_mapped_address(self, original_address):
		"""Get the mapped address using SPP Address Mapping"""
		try:
			# Check if there's an address mapping
			address_mapping = frappe.db.get_value(
				"SPP Address Mapping", 
				{"producer_address": original_address, "is_active": 1}, 
				"consumer_address"
			)
			
			if address_mapping:
				frappe.logger().info(f"Found SPP address mapping: {original_address} -> {address_mapping}")
				return address_mapping
			else:
				frappe.logger().info(f"No SPP address mapping found for: {original_address}")
				return None
				
		except Exception as e:
			frappe.logger().error(f"Error getting address mapping for {original_address}: {str(e)}")
			return None

	def get_supplier_from_mapped_address(self, mapped_address):
		"""Find which supplier is linked to the mapped address"""
		try:
			# Look for supplier linked to this address
			# Check in Address doctype for the address name and get linked supplier
			address_doc = frappe.db.get_value(
				"Address", 
				{"name": mapped_address}, 
				["name"]
			)
			
			if address_doc:
				# Get Dynamic Link entries for this address to find linked supplier
				linked_supplier = frappe.db.get_value(
					"Dynamic Link",
					{
						"parent": mapped_address,
						"parenttype": "Address", 
						"link_doctype": "Supplier"
					},
					"link_name"
				)
				
				if linked_supplier:
					frappe.logger().info(f"Found supplier {linked_supplier} linked to address {mapped_address}")
					return linked_supplier
				else:
					frappe.logger().warning(f"No supplier linked to address: {mapped_address}")
					return None
			else:
				frappe.logger().warning(f"Address document not found: {mapped_address}")
				return None
				
		except Exception as e:
			frappe.logger().error(f"Error finding supplier for address {mapped_address}: {str(e)}")
			return None

	def process_custom_mapping(self, mapping, doc_data):
		"""Process custom mapping logic (can be extended for future complex rules)"""
		# For now, treat custom as direct mapping
		# This can be extended in the future for more complex logic
		return mapping.consumer_supplier or mapping.fallback_supplier