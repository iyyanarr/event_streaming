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
			# Check if there's an address mapping in the child table
			address_mapping = frappe.db.get_value(
				"SPP Address Mapping Detail", 
				{"producer_address": original_address}, 
				"consumer_address"
			)
			
			if address_mapping:
				# Verify the parent mapping is active
				parent_mapping = frappe.db.get_value(
					"SPP Address Mapping Detail",
					{"producer_address": original_address},
					"parent"
				)
				
				if parent_mapping:
					is_active = frappe.db.get_value(
						"SPP Address Mapping",
						{"name": parent_mapping},
						"is_active"
					)
					
					if is_active:
						frappe.logger().info(f"Found SPP address mapping: {original_address} -> {address_mapping}")
						return address_mapping
					else:
						frappe.logger().info(f"SPP address mapping is inactive: {parent_mapping}")
						return None
				
			frappe.logger().info(f"No SPP address mapping found for: {original_address}")
			return None
				
		except Exception as e:
			frappe.logger().error(f"Error getting address mapping for {original_address}: {str(e)}")
			return None

	def get_supplier_from_mapped_address(self, mapped_address):
		"""Find which supplier is linked to the mapped address"""
		try:
			frappe.logger().info(f"Looking for supplier linked to address: {mapped_address}")
			
			# Method 1: Direct Dynamic Link lookup
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
				frappe.logger().info(f"Found supplier via Dynamic Link: {linked_supplier}")
				return linked_supplier
			
			# Method 2: Search by address title (sometimes addresses are referenced by title)
			address_title = frappe.db.get_value("Address", mapped_address, "address_title")
			if address_title:
				frappe.logger().info(f"Searching for supplier by address title: {address_title}")
				
				# Look for Dynamic Links using address title
				linked_supplier = frappe.db.sql("""
					SELECT dl.link_name 
					FROM `tabDynamic Link` dl
					INNER JOIN `tabAddress` addr ON dl.parent = addr.name
					WHERE addr.address_title = %s 
					AND dl.link_doctype = 'Supplier'
					AND dl.parenttype = 'Address'
					LIMIT 1
				""", (address_title,))
				
				if linked_supplier:
					supplier_name = linked_supplier[0][0]
					frappe.logger().info(f"Found supplier via address title: {supplier_name}")
					return supplier_name
			
			# Method 3: Partial match search for address content
			frappe.logger().info(f"Trying partial match for address: {mapped_address}")
			
			# Search for addresses that contain parts of the mapped address
			similar_addresses = frappe.db.sql("""
				SELECT addr.name, dl.link_name
				FROM `tabAddress` addr
				INNER JOIN `tabDynamic Link` dl ON addr.name = dl.parent
				WHERE (addr.address_title LIKE %s 
					OR addr.address_line1 LIKE %s 
					OR addr.name LIKE %s)
				AND dl.link_doctype = 'Supplier'
				AND dl.parenttype = 'Address'
				LIMIT 5
			""", (f"%{mapped_address}%", f"%{mapped_address}%", f"%{mapped_address}%"))
			
			if similar_addresses:
				frappe.logger().info(f"Found similar addresses: {similar_addresses}")
				# Return the first match
				supplier_name = similar_addresses[0][1]
				frappe.logger().info(f"Using supplier from similar address: {supplier_name}")
				return supplier_name
			
			# Method 4: Check if mapped_address is actually a supplier name
			if frappe.db.exists("Supplier", mapped_address):
				frappe.logger().info(f"Mapped address is actually a supplier name: {mapped_address}")
				return mapped_address
				
			# Method 5: Search for supplier by name containing the address
			supplier_by_name = frappe.db.sql("""
				SELECT name FROM `tabSupplier` 
				WHERE supplier_name LIKE %s OR name LIKE %s
				LIMIT 1
			""", (f"%{mapped_address}%", f"%{mapped_address}%"))
			
			if supplier_by_name:
				supplier_name = supplier_by_name[0][0]
				frappe.logger().info(f"Found supplier by name match: {supplier_name}")
				return supplier_name
			
			frappe.logger().warning(f"No supplier found for address: {mapped_address}")
			return None
				
		except Exception as e:
			frappe.logger().error(f"Error finding supplier for address {mapped_address}: {str(e)}")
			return None

	def process_custom_mapping(self, mapping, doc_data):
		"""Process custom mapping logic (can be extended for future complex rules)"""
		# For now, treat custom as direct mapping
		# This can be extended in the future for more complex logic
		return mapping.consumer_supplier or mapping.fallback_supplier

	@frappe.whitelist()
	def debug_address_supplier_mapping(self, address_name):
		"""Debug method to help troubleshoot address-supplier mapping issues"""
		try:
			frappe.logger().info(f"=== DEBUG: Address-Supplier Mapping for {address_name} ===")
			
			# Check if address exists
			address_exists = frappe.db.exists("Address", address_name)
			frappe.logger().info(f"Address exists: {address_exists}")
			
			if address_exists:
				# Get address details
				address_doc = frappe.get_doc("Address", address_name)
				frappe.logger().info(f"Address Title: {address_doc.address_title}")
				frappe.logger().info(f"Address Line 1: {address_doc.address_line1}")
				
				# Check Dynamic Links
				dynamic_links = frappe.get_all("Dynamic Link", 
					filters={
						"parent": address_name,
						"parenttype": "Address"
					},
					fields=["link_doctype", "link_name"]
				)
				frappe.logger().info(f"Dynamic Links: {dynamic_links}")
				
				# Check for supplier links specifically
				supplier_links = [dl for dl in dynamic_links if dl.link_doctype == "Supplier"]
				frappe.logger().info(f"Supplier Links: {supplier_links}")
				
				# Test the get_supplier_from_mapped_address method
				found_supplier = self.get_supplier_from_mapped_address(address_name)
				frappe.logger().info(f"Found Supplier via method: {found_supplier}")
				
				return {
					"address_exists": address_exists,
					"address_details": {
						"title": address_doc.address_title,
						"line1": address_doc.address_line1
					},
					"dynamic_links": dynamic_links,
					"supplier_links": supplier_links,
					"found_supplier": found_supplier
				}
			else:
				# Try to find similar addresses
				similar = frappe.db.sql("""
					SELECT name, address_title, address_line1 
					FROM `tabAddress` 
					WHERE address_title LIKE %s OR name LIKE %s
					LIMIT 10
				""", (f"%{address_name}%", f"%{address_name}%"), as_dict=True)
				
				frappe.logger().info(f"Similar addresses found: {similar}")
				
				return {
					"address_exists": False,
					"similar_addresses": similar
				}
				
		except Exception as e:
			frappe.logger().error(f"Debug error: {str(e)}")
			return {"error": str(e)}