# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class SPPSpecialSupplierMapping(Document):
	def validate(self):
		"""Validate the special supplier mapping configuration"""
		self.validate_duplicate_suppliers()
		self.validate_mapping_logic()
		self.validate_sites()

	def validate_duplicate_suppliers(self):
		"""Ensure no duplicate producer suppliers in the same mapping"""
		suppliers = []
		for mapping in self.special_mappings:
			if mapping.producer_supplier in suppliers:
				frappe.throw(f"Duplicate producer supplier: {mapping.producer_supplier}")
			suppliers.append(mapping.producer_supplier)

	def validate_sites(self):
		"""Validate producer and consumer sites (if present)"""
		if hasattr(self, 'producer_site') and hasattr(self, 'consumer_site'):
			if self.producer_site == self.consumer_site:
				frappe.throw(_("Producer site and consumer site cannot be the same"))

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
		
		# 1. Normal mapping (where we have a supplier name to match)
		if producer_supplier:
			for mapping in self.special_mappings:
				# Check for exact match OR partial match
				is_match = (mapping.producer_supplier == producer_supplier or 
						   mapping.producer_supplier in producer_supplier or
						   producer_supplier in mapping.producer_supplier)
						   
				if is_match and mapping.is_active:
					if mapping.mapping_type == "Address Based":
						return self.process_address_based_mapping(mapping, doc_data)
					elif mapping.mapping_type == "Direct":
						return mapping.consumer_supplier
					elif mapping.mapping_type == "Custom":
						return self.process_custom_mapping(mapping, doc_data)
					elif mapping.mapping_type == "Warehouse Based":
						return self.process_warehouse_based_mapping(mapping, doc_data)

		# 2. Fallback for Warehouse Based mapping (where we don't have a supplier yet)
		# This is common for Stock Entries coming from spp15.local
		for mapping in self.special_mappings:
			if mapping.mapping_type == "Warehouse Based" and mapping.is_active:
				result = self.process_warehouse_based_mapping(mapping, doc_data)
				if result:
					return result
		
		frappe.logger().warning(f"No special mapping found for supplier: {producer_supplier}")
		return None

	@frappe.whitelist()
	def import_csv_mapping(self, csv_file_url):
		"""Import special supplier mappings from uploaded CSV file."""
		import csv
		import os
		
		try:
			file_doc = frappe.get_doc("File", {"file_url": csv_file_url})
			file_path = file_doc.get_full_path()
			if not os.path.exists(file_path):
				frappe.throw(_("File not found: {0}").format(csv_file_url))
				
			self.special_mappings = []
			
			with open(file_path, 'r', encoding='utf-8') as csvfile:
				reader = csv.DictReader(csvfile)
				fieldnames = reader.fieldnames
				if not fieldnames:
					frappe.throw(_("CSV file is empty or invalid"))
				
				producer_col = None
				consumer_col = None
				for field in fieldnames:
					f = field.lower().strip().replace('\ufeff', '')
					if f in ['producer_supplier', 'producer supplier', 'old_supplier', 'source_supplier']:
						if not producer_col: producer_col = field
					elif f in ['consumer_supplier', 'consumer supplier', 'new_supplier', 'target_supplier']:
						if not consumer_col: consumer_col = field
				
				if (not producer_col or not consumer_col) and len(fieldnames) >= 2:
					if not producer_col: producer_col = fieldnames[0]
					if not consumer_col: consumer_col = fieldnames[1]
					
				if not producer_col or not consumer_col:
					frappe.throw(_("CSV must have columns for producer and consumer supplier"))
					
				imported = 0
				for row in reader:
					p = (row.get(producer_col) or '').strip()
					c = (row.get(consumer_col) or '').strip()
					if p and c:
						self.append('special_mappings', {
							'producer_supplier': p,
							'consumer_supplier': c,
							'mapping_type': row.get('mapping_type', 'Direct').strip(),
							'is_active': 1
						})
						imported += 1
						
			self.flags.ignore_links = True
			self.save()
			frappe.db.commit()
			return {"message": _("Successfully imported {0} special mappings").format(imported), "count": imported}
		except Exception as e:
			frappe.log_error(frappe.get_traceback(), "CSV Import Error")
			frappe.throw(_("Error importing CSV: {0}").format(str(e)))

	def process_address_based_mapping(self, mapping, doc_data):
		"""Process address-based mapping logic - works with consumer site data after Document Type Mapping"""
		frappe.logger().info(f"Processing address-based mapping for {mapping.producer_supplier}")
		
		if not doc_data:
			frappe.logger().warning(f"No document data provided for address-based mapping: {mapping.producer_supplier}")
			return mapping.fallback_supplier or mapping.producer_supplier

		# Get consumer address field value from document (already mapped by Document Type Mapping)
		consumer_address = doc_data.get(mapping.address_field)
		frappe.logger().info(f"Consumer address field '{mapping.address_field}' value: {consumer_address}")
		
		if not consumer_address:
			frappe.logger().warning(f"No {mapping.address_field} found in document for supplier {mapping.producer_supplier}")
			return mapping.fallback_supplier or mapping.producer_supplier

		# Find supplier linked to this consumer address directly
		linked_supplier = self.get_supplier_from_mapped_address(consumer_address)
		frappe.logger().info(f"Supplier linked to consumer address {consumer_address}: {linked_supplier}")
		
		if linked_supplier:
			frappe.logger().info(f"Address-based mapping SUCCESS: {mapping.producer_supplier} -> {linked_supplier} (via consumer address {consumer_address})")
			return linked_supplier
		else:
			frappe.logger().warning(f"No supplier found linked to consumer address: {consumer_address}")

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

	def process_warehouse_based_mapping(self, mapping, doc_data):
		"""Process warehouse-based mapping logic by extracting code from warehouse name"""
		frappe.logger().info(f"Processing warehouse-based mapping for {mapping.producer_supplier}")
		
		if not doc_data:
			return mapping.fallback_supplier
			
		# 1. Get the list of fields to check
		# We start with the configured field, then try common fallbacks
		fields_to_check = []
		if mapping.get("warehouse_field"):
			fields_to_check.append(mapping.get("warehouse_field"))
		
		# Add standard fallbacks
		fields_to_check.extend(["from_warehouse", "to_warehouse", "warehouse", "source_warehouse", "target_warehouse"])
		
		vendor_code = None
		for field in fields_to_check:
			val = doc_data.get(field)
			if val and isinstance(val, str) and ":" in val:
				prefix = val.split(":")[0].strip()
				if prefix.startswith("DF"):
					vendor_code = prefix
					frappe.logger().info(f"Found vendor code {vendor_code} in field {field}")
					break
			elif val and isinstance(val, str) and val.startswith("DF"):
				vendor_code = val.split(" ")[0].strip()
				frappe.logger().info(f"Found vendor code {vendor_code} in field {field} (no colon)")
				break
					
		if not vendor_code:
			return mapping.fallback_supplier
			
		# 3. Check if this extracted code matches the producer_supplier in the mapping
		if mapping.producer_supplier == vendor_code:
			return mapping.consumer_supplier
			
		# 4. If no match, check other mappings in this same document
		# We iterate through all mappings to find one that matches the extracted code
		for other_mapping in self.special_mappings:
			if other_mapping.is_active and other_mapping.mapping_type == "Warehouse Based":
				if other_mapping.producer_supplier == vendor_code:
					frappe.logger().info(f"Found match in other mapping row: {vendor_code} -> {other_mapping.consumer_supplier}")
					return other_mapping.consumer_supplier
					
		# 5. Last resort: try to find a supplier whose name or ID matches the vendor code directly on the consumer site
		if frappe.db.exists("Supplier", vendor_code):
			return vendor_code
			
		# Fallback to general mapping or the original value
		return mapping.fallback_supplier

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