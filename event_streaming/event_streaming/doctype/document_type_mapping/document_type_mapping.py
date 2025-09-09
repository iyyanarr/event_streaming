# Copyright (c) 2019, Frappe Technologies and contributors
# License: MIT. See LICENSE
import json

import frappe
from frappe import _
from frappe.model import child_table_fields, default_fields
from frappe.model.document import Document


class DocumentTypeMapping(Document):
	def validate(self):
		self.validate_inner_mapping()

	def validate_inner_mapping(self):
		meta = frappe.get_meta(self.local_doctype)
		for field_map in self.field_mapping:
			if field_map.local_fieldname not in (default_fields + child_table_fields):
				field = meta.get_field(field_map.local_fieldname)
				if not field:
					frappe.throw(_("Row #{0}: Invalid Local Fieldname").format(field_map.idx))

			fieldtype = field.get("fieldtype")
			if fieldtype in ["Link", "Dynamic Link", "Table"]:
				if not field_map.mapping and not field_map.default_value:
					msg = _(
						"Row #{0}: Please set Mapping or Default Value for the field {1} since its a dependency field"
					).format(field_map.idx, frappe.bold(field_map.local_fieldname))
					frappe.throw(msg, title="Inner Mapping Missing")

			if field_map.mapping_type == "Document" and not field_map.remote_value_filters:
				msg = _(
					"Row #{0}: Please set remote value filters for the field {1} to fetch the unique remote dependency document"
				).format(field_map.idx, frappe.bold(field_map.remote_fieldname))
				frappe.throw(msg, title="Remote Value Filters Missing")

	def get_mapping(self, doc, producer_site, update_type):
		remote_fields = []
		# list of tuples (local_fieldname, dependent_doc)
		dependencies = []

		for mapping in self.field_mapping:
			if doc.get(mapping.remote_fieldname):
				if mapping.mapping_type == "Document":
					if not mapping.default_value:
						dependency = self.get_mapped_dependency(mapping, producer_site, doc)
						if dependency:
							dependencies.append((mapping.local_fieldname, dependency))
					else:
						doc[mapping.local_fieldname] = mapping.default_value

				if mapping.mapping_type == "Child Table" and update_type != "Update":
					doc[mapping.local_fieldname] = get_mapped_child_table_docs(
						mapping.mapping, doc[mapping.remote_fieldname], producer_site
					)
				else:
					# copy value into local fieldname key and remove remote fieldname key
					doc[mapping.local_fieldname] = doc[mapping.remote_fieldname]

				if mapping.local_fieldname != mapping.remote_fieldname:
					remote_fields.append(mapping.remote_fieldname)

			if not doc.get(mapping.remote_fieldname) and mapping.default_value and update_type != "Update":
				doc[mapping.local_fieldname] = mapping.default_value

		# remove the remote fieldnames
		for field in remote_fields:
			doc.pop(field, None)

		if update_type != "Update":
			doc["doctype"] = self.local_doctype

		# Apply custom value mappings
		doc = self.apply_value_mappings(doc)

		mapping = {"doc": frappe.as_json(doc)}
		if len(dependencies):
			mapping["dependencies"] = dependencies
		return mapping

	def apply_value_mappings(self, doc):
		"""Apply value mappings using existing SPP mapping DocTypes"""
		# Get list of fields that are mapped in this Document Type Mapping
		mapped_fields = [fm.local_fieldname for fm in self.field_mapping]
		
		# Apply mappings only to fields that are in the Document Type Mapping configuration
		for field_name in mapped_fields:
			if doc.get(field_name):
				doc[field_name] = self.get_mapped_value(field_name, doc[field_name])
		
		# Apply to child tables that are mapped
		child_table_fields = [fm.local_fieldname for fm in self.field_mapping if fm.mapping_type == "Child Table"]
		for table_field in child_table_fields:
			if doc.get(table_field) and isinstance(doc[table_field], list):
				for row in doc[table_field]:
					if isinstance(row, dict):
						# Get child table mapping to know which fields to map
						child_mapping = self.get_child_table_mapping(table_field)
						if child_mapping:
							child_mapped_fields = [fm.local_fieldname for fm in child_mapping.field_mapping]
							for child_field in child_mapped_fields:
								if row.get(child_field):
									row[child_field] = self.get_mapped_value(child_field, row[child_field])
		
		return doc

	def get_child_table_mapping(self, table_field):
		"""Get the Document Type Mapping for a child table"""
		try:
			mapping_name = None
			for fm in self.field_mapping:
				if fm.local_fieldname == table_field and fm.mapping_type == "Child Table":
					mapping_name = fm.mapping
					break
			
			if mapping_name:
				return frappe.get_doc("Document Type Mapping", mapping_name)
		except:
			pass
		return None

	def get_mapped_value(self, field_name, field_value):
		"""Get mapped value based on field name and existing SPP mapping tables"""
		# Skip mapping for empty values
		if not field_value:
			return field_value
			
		# Check each SPP mapping table to see if this field should be mapped
		
		# Company mapping
		if self.field_maps_to_company(field_name):
			return self.get_company_mapping(field_value)
		
		# Supplier mapping  
		elif self.field_maps_to_supplier(field_name):
			return self.get_supplier_mapping(field_value)
		
		# Item mapping
		elif self.field_maps_to_item(field_name):
			return self.get_item_mapping(field_value)
		
		# Warehouse mapping
		elif self.field_maps_to_warehouse(field_name):
			return self.get_warehouse_mapping(field_value)
		
		# Account mapping
		elif self.field_maps_to_account(field_name):
			return self.get_account_mapping(field_value)
		
		# Cost Center mapping
		elif self.field_maps_to_cost_center(field_name):
			return self.get_cost_center_mapping(field_value)
		
		# Tax Template mapping
		elif self.field_maps_to_tax_template(field_name):
			# Determine template type based on field name or document context
			template_type = None
			if field_name in ['taxes_and_charges']:
				# For main document tax template, try to determine type from doctype
				if hasattr(self, 'local_doctype'):
					if 'Purchase' in self.local_doctype:
						template_type = "Purchase Taxes and Charges Template"
					elif 'Sales' in self.local_doctype:
						template_type = "Sales Taxes and Charges Template"
			elif field_name == 'item_tax_template':
				# Item tax templates are different - they use Item Tax Template doctype
				return self.get_item_tax_template_mapping(field_value)
			
			return self.get_tax_template_mapping(field_value, template_type)
			
		# Contact mapping
		elif self.field_maps_to_contact(field_name):
			return self.get_contact_mapping(field_value)
			
		# Address mapping
		elif self.field_maps_to_address(field_name):
			return self.get_address_mapping(field_value)
		
		# No mapping found, return original value
		return field_value

	def field_maps_to_company(self, field_name):
		"""Check if field should use company mapping"""
		return field_name in ['company']

	def field_maps_to_supplier(self, field_name):
		"""Check if field should use supplier mapping"""
		return field_name in ['supplier']

	def field_maps_to_item(self, field_name):
		"""Check if field should use item mapping"""
		return field_name in ['item_code', 'item', 'production_item']

	def field_maps_to_warehouse(self, field_name):
		"""Check if field should use warehouse mapping"""
		return field_name in ['warehouse', 's_warehouse', 't_warehouse', 'source_warehouse', 'target_warehouse', 'set_warehouse']

	def field_maps_to_account(self, field_name):
		"""Check if field should use account mapping"""
		return field_name in ['expense_account', 'income_account', 'account', 'debit_to', 'credit_to', 'account_head']

	def field_maps_to_cost_center(self, field_name):
		"""Check if field should use cost center mapping"""
		return field_name in ['cost_center']

	def field_maps_to_tax_template(self, field_name):
		"""Check if field should use tax template mapping"""
		return field_name in ['taxes_and_charges', 'tax_template', 'item_tax_template']

	def field_maps_to_item_tax_template(self, field_name):
		"""Check if field should use item tax template mapping (separate from purchase/sales tax templates)"""
		return field_name in ['item_tax_template']

	def field_maps_to_contact(self, field_name):
		"""Check if field should use contact mapping"""
		return field_name in ['contact_person', 'supplier_contact', 'customer_contact']
		
	def field_maps_to_address(self, field_name):
		"""Check if field should use address mapping"""
		return field_name in ['shipping_address', 'billing_address', 'address_display', 'supplier_address', 'customer_address']

	def get_company_mapping(self, company):
		"""Get mapped company name from SPP Company Mapping child table"""
		try:
			mapping_doc = frappe.db.get_value("SPP Company Mapping", 
				{"is_active": 1}, "name")
			
			if mapping_doc:
				mapped_company = frappe.db.get_value("SPP Company Mapping Detail",
					{"parent": mapping_doc, "producer_company": company}, "consumer_company")
				if mapped_company:
					if frappe.db.exists("Company", mapped_company):
						frappe.logger().info(f"Company mapping: {company} -> {mapped_company}")
						return mapped_company
					else:
						frappe.logger().warning(f"Mapped company '{mapped_company}' does not exist for original '{company}'")
				else:
					frappe.logger().warning(f"No mapping found for company: {company}")
			
			return company
		except Exception as e:
			frappe.logger().error(f"Error in company mapping for '{company}': {str(e)}")
			return company

	def get_supplier_mapping(self, supplier):
		"""Get mapped supplier name from SPP Supplier Mapping child table"""
		try:
			mapping_doc = frappe.db.get_value("SPP Supplier Mapping", 
				{"is_active": 1}, "name")
			
			if mapping_doc:
				mapped_supplier = frappe.db.get_value("SPP Supplier Mapping Detail",
					{"parent": mapping_doc, "producer_supplier": supplier}, "consumer_supplier")
				if mapped_supplier:
					if frappe.db.exists("Supplier", mapped_supplier):
						frappe.logger().info(f"Supplier mapping: {supplier} -> {mapped_supplier}")
						return mapped_supplier
					else:
						frappe.logger().warning(f"Mapped supplier '{mapped_supplier}' does not exist for original '{supplier}'")
				else:
					frappe.logger().warning(f"No mapping found for supplier: {supplier}")
			
			return supplier
		except Exception as e:
			frappe.logger().error(f"Error in supplier mapping for '{supplier}': {str(e)}")
			return supplier

	def get_item_mapping(self, item_code):
		"""Get mapped item code from SPP Item Mapping child table"""
		try:
			mapping_doc = frappe.db.get_value("SPP Item Mapping", 
				{"is_active": 1}, "name")
			
			if mapping_doc:
				mapped_item = frappe.db.get_value("SPP Item Mapping Detail",
					{"parent": mapping_doc, "producer_item_code": item_code}, "consumer_item_code")
				if mapped_item:
					if frappe.db.exists("Item", mapped_item):
						frappe.logger().info(f"Item mapping: {item_code} -> {mapped_item}")
						return mapped_item
					else:
						frappe.logger().warning(f"Mapped item '{mapped_item}' does not exist for original '{item_code}'")
				else:
					frappe.logger().warning(f"No mapping found for item: {item_code}")
			
			return item_code
		except Exception as e:
			frappe.logger().error(f"Error in item mapping for '{item_code}': {str(e)}")
			return item_code

	def get_warehouse_mapping(self, warehouse):
		"""Get mapped warehouse name from SPP Warehouse Mapping child table"""
		try:
			mapping_doc = frappe.db.get_value("SPP Warehouse Mapping", 
				{"is_active": 1}, "name")
			
			if mapping_doc:
				mapped_warehouse = frappe.db.get_value("SPP Warehouse Mapping Detail",
					{"parent": mapping_doc, "producer_warehouse": warehouse}, "consumer_warehouse")
				if mapped_warehouse:
					if frappe.db.exists("Warehouse", mapped_warehouse):
						frappe.logger().info(f"Warehouse mapping: {warehouse} -> {mapped_warehouse}")
						return mapped_warehouse
					else:
						frappe.logger().warning(f"Mapped warehouse '{mapped_warehouse}' does not exist for original '{warehouse}'")
				else:
					frappe.logger().warning(f"No mapping found for warehouse: {warehouse}")
			
			return warehouse
		except Exception as e:
			frappe.logger().error(f"Error in warehouse mapping for '{warehouse}': {str(e)}")
			return warehouse

	def get_account_mapping(self, account):
		"""Get mapped account name from SPP Account Mapping child table"""
		try:
			mapping_doc = frappe.db.get_value("SPP Account Mapping", 
				{"is_active": 1}, "name")
			
			if mapping_doc:
				mapped_account = frappe.db.get_value("SPP Account Mapping Detail",
					{"parent": mapping_doc, "source_account": account}, "target_account")
				if mapped_account:
					if frappe.db.exists("Account", mapped_account):
						frappe.logger().info(f"Account mapping: {account} -> {mapped_account}")
						return mapped_account
					else:
						frappe.logger().warning(f"Mapped account '{mapped_account}' does not exist for original '{account}'")
				else:
					frappe.logger().warning(f"No mapping found for account: {account}")
			
			return account
		except Exception as e:
			frappe.logger().error(f"Error in account mapping for '{account}': {str(e)}")
			return account

	def get_cost_center_mapping(self, cost_center):
		"""Get mapped cost center name from SPP Cost Center Mapping child table"""
		try:
			mapping_doc = frappe.db.get_value("SPP Cost Center Mapping", 
				{"is_active": 1}, "name")
			
			if mapping_doc:
				mapped_cost_center = frappe.db.get_value("SPP Cost Center Mapping Detail",
					{"parent": mapping_doc, "producer_cost_center": cost_center}, "consumer_cost_center")
				if mapped_cost_center:
					if frappe.db.exists("Cost Center", mapped_cost_center):
						frappe.logger().info(f"Cost Center mapping: {cost_center} -> {mapped_cost_center}")
						return mapped_cost_center
					else:
						frappe.logger().warning(f"Mapped cost center '{mapped_cost_center}' does not exist for original '{cost_center}'")
				else:
					frappe.logger().warning(f"No mapping found for cost center: {cost_center}")
			
			return cost_center
		except Exception as e:
			frappe.logger().error(f"Error in cost center mapping for '{cost_center}': {str(e)}")
			return cost_center

	def get_tax_template_mapping(self, tax_template, template_type=None):
		"""Get mapped tax template name from SPP Tax Template Mapping child table"""
		try:
			mapping_doc = frappe.db.get_value("SPP Tax Template Mapping", 
				{"is_active": 1}, "name")
			
			if mapping_doc:
				# Build filters with template type if provided
				filters = {
					"parent": mapping_doc, 
					"producer_tax_template": tax_template,
					"is_active": 1
				}
				
				# Add template type filter if specified
				if template_type:
					filters["template_type"] = template_type
				
				mapped_tax_template = frappe.db.get_value("SPP Tax Template Mapping Detail",
					filters, "consumer_tax_template")
				
				if mapped_tax_template:
					# Check if the mapped template exists in the correct doctype
					target_doctypes = []
					if template_type:
						target_doctypes = [template_type]
					else:
						target_doctypes = ["Purchase Taxes and Charges Template", "Sales Taxes and Charges Template"]
					
					for doctype in target_doctypes:
						if frappe.db.exists(doctype, mapped_tax_template):
							frappe.logger().info(f"Tax Template mapping: {tax_template} -> {mapped_tax_template} ({doctype})")
							return mapped_tax_template
					
					frappe.logger().warning(f"Mapped tax template '{mapped_tax_template}' does not exist for original '{tax_template}'")
				else:
					filter_info = f" with template_type='{template_type}'" if template_type else ""
					frappe.logger().warning(f"No mapping found for tax template: {tax_template}{filter_info}")
			
			return tax_template
		except Exception as e:
			frappe.logger().error(f"Error in tax template mapping for '{tax_template}': {str(e)}")
			return tax_template

	def get_item_tax_template_mapping(self, item_tax_template):
		"""Get mapped item tax template name from SPP Tax Template Mapping child table"""
		try:
			mapping_doc = frappe.db.get_value("SPP Tax Template Mapping", 
				{"is_active": 1}, "name")
			
			if mapping_doc:
				# Build filters for item tax template (use Item Tax Template as template_type)
				filters = {
					"parent": mapping_doc, 
					"producer_tax_template": item_tax_template,
					"is_active": 1,
					"template_type": "Item Tax Template"  # Specific to Item Tax Template doctype
				}
				
				mapped_item_tax_template = frappe.db.get_value("SPP Tax Template Mapping Detail",
					filters, "consumer_tax_template")
				
				if mapped_item_tax_template:
					# Check if the mapped template exists in Item Tax Template doctype
					if frappe.db.exists("Item Tax Template", mapped_item_tax_template):
						frappe.logger().info(f"Item Tax Template mapping: {item_tax_template} -> {mapped_item_tax_template}")
						return mapped_item_tax_template
					else:
						frappe.logger().warning(f"Mapped item tax template '{mapped_item_tax_template}' does not exist for original '{item_tax_template}'")
				else:
					frappe.logger().warning(f"No item tax template mapping found for: {item_tax_template}")
			
			return item_tax_template
		except Exception as e:
			frappe.logger().error(f"Error in item tax template mapping for '{item_tax_template}': {str(e)}")
			return item_tax_template

	def get_contact_mapping(self, contact):
		"""Get mapped contact name from SPP Contact Mapping child table"""
		try:
			# Get the SPP Contact Mapping document for this site combination
			mapping_doc = frappe.db.get_value("SPP Contact Mapping", 
				{"is_active": 1}, "name")
			
			if mapping_doc:
				# Look in the child table contact_mappings
				mapped_contact = frappe.db.get_value("SPP Contact Mapping Detail",
					{"parent": mapping_doc, "producer_contact": contact}, "consumer_contact")
				if mapped_contact:
					# Validate that the mapped contact exists
					if frappe.db.exists("Contact", mapped_contact):
						frappe.logger().info(f"Contact mapping: {contact} -> {mapped_contact}")
						return mapped_contact
					else:
						frappe.logger().warning(f"Mapped contact '{mapped_contact}' does not exist for original '{contact}'")
				else:
					frappe.logger().warning(f"No mapping found for contact: {contact}")
			
			# Return original if no mapping found or mapped value doesn't exist
			return contact
		except Exception as e:
			frappe.logger().error(f"Error in contact mapping for '{contact}': {str(e)}")
			return contact

	def get_address_mapping(self, address):
		"""Get mapped address name from SPP Address Mapping child table"""
		try:
			# Get the SPP Address Mapping document for this site combination
			mapping_doc = frappe.db.get_value("SPP Address Mapping", 
				{"is_active": 1}, "name")
			
			if mapping_doc:
				# Look in the child table address_mappings
				mapped_address = frappe.db.get_value("SPP Address Mapping Detail",
					{"parent": mapping_doc, "producer_address": address}, "consumer_address")
				if mapped_address:
					# Validate that the mapped address exists
					if frappe.db.exists("Address", mapped_address):
						frappe.logger().info(f"Address mapping: {address} -> {mapped_address}")
						return mapped_address
					else:
						frappe.logger().warning(f"Mapped address '{mapped_address}' does not exist for original '{address}'")
				else:
					frappe.logger().warning(f"No mapping found for address: {address}")
			
			# Return original if no mapping found or mapped value doesn't exist
			return address
		except Exception as e:
			frappe.logger().error(f"Error in address mapping for '{address}': {str(e)}")
			return address

	def get_mapped_update(self, update, producer_site):
		update_diff = frappe._dict(json.loads(update.data))
		mapping = update_diff
		dependencies = []
		if update_diff.changed:
			doc_map = self.get_mapping(update_diff.changed, producer_site, "Update")
			mapped_doc = doc_map.get("doc")
			mapping.changed = json.loads(mapped_doc)
			if doc_map.get("dependencies"):
				dependencies += doc_map.get("dependencies")

		if update_diff.removed:
			mapping = self.map_rows_removed(update_diff, mapping)
		if update_diff.added:
			mapping = self.map_rows(update_diff, mapping, producer_site, operation="added")
		if update_diff.row_changed:
			mapping = self.map_rows(update_diff, mapping, producer_site, operation="row_changed")

		update = {"doc": frappe.as_json(mapping)}
		if len(dependencies):
			update["dependencies"] = dependencies
		return update

	def get_mapped_dependency(self, mapping, producer_site, doc):
		inner_mapping = frappe.get_doc("Document Type Mapping", mapping.mapping)
		filters = json.loads(mapping.remote_value_filters)
		for key, value in filters.items():
			if value.startswith("eval:"):
				val = frappe.safe_eval(value[5:], None, dict(doc=doc))
				filters[key] = val
			if doc.get(value):
				filters[key] = doc.get(value)
		matching_docs = producer_site.get_doc(inner_mapping.remote_doctype, filters=filters)
		if len(matching_docs):
			remote_docname = matching_docs[0].get("name")
			remote_doc = producer_site.get_doc(inner_mapping.remote_doctype, remote_docname)
			dependency_doc = inner_mapping.get_mapping(remote_doc, producer_site, "Insert").get("doc")
			
			return dependency_doc
		return

	def map_rows_removed(self, update_diff, mapping):
		removed = []
		mapping["removed"] = update_diff.removed
		for key, value in update_diff.removed.copy().items():
			local_table_name = frappe.db.get_value(
				"Document Type Field Mapping",
				{"remote_fieldname": key, "parent": self.name},
				"local_fieldname",
			)
			mapping.removed[local_table_name] = value
			if local_table_name != key:
				removed.append(key)

		# remove the remote fieldnames
		for field in removed:
			mapping.removed.pop(field, None)
		return mapping

	def map_rows(self, update_diff, mapping, producer_site, operation):
		remote_fields = []
		for tablename, entries in update_diff.get(operation).copy().items():
			local_table_name = frappe.db.get_value(
				"Document Type Field Mapping", {"remote_fieldname": tablename}, "local_fieldname"
			)
			table_map = frappe.db.get_value(
				"Document Type Field Mapping",
				{"local_fieldname": local_table_name, "parent": self.name},
				"mapping",
				)
			
			# Skip if no mapping configuration found for this table
			if not table_map:
				frappe.logger().warning(f"No Document Type Mapping found for table '{tablename}', skipping value mapping")
				# Just copy the entries as-is without mapping
				mapping.get(operation)[local_table_name or tablename] = entries
				continue
				
			table_map = frappe.get_doc("Document Type Mapping", table_map)
			docs = []
			for entry in entries:
				mapped_doc = table_map.get_mapping(entry, producer_site, "Update").get("doc")
				entry_doc = json.loads(mapped_doc)
				
				docs.append(entry_doc)
			mapping.get(operation)[local_table_name] = docs
			if local_table_name != tablename:
				remote_fields.append(tablename)

		# remove the remote fieldnames
		for field in remote_fields:
			mapping.get(operation).pop(field, None)

		return mapping


def get_mapped_child_table_docs(child_map, table_entries, producer_site):
	"""Get mapping for child doctypes"""
	child_map = frappe.get_doc("Document Type Mapping", child_map)
	mapped_entries = []
	remote_fields = []
	
	# Handle case where table_entries might be strings or mixed types
	if not table_entries:
		return mapped_entries
	
	# Ensure table_entries is a list
	if not isinstance(table_entries, list):
		table_entries = [table_entries]
	
	for child_doc in table_entries:
		# Handle string values - convert to dict or skip
		if isinstance(child_doc, str):
			try:
				# Try to parse as JSON first
				child_doc = json.loads(child_doc)
			except (json.JSONDecodeError, ValueError):
				# If not JSON, skip this entry with warning
				frappe.logger().warning(f"Skipping non-dict child table entry: {child_doc}")
				continue
		
		# Ensure child_doc is a dictionary
		if not isinstance(child_doc, dict):
			frappe.logger().warning(f"Skipping non-dict child table entry of type {type(child_doc)}: {child_doc}")
			continue
		
		# Reset remote_fields for each document
		doc_remote_fields = []
		
		for mapping in child_map.field_mapping:
			if child_doc.get(mapping.remote_fieldname):
				child_doc[mapping.local_fieldname] = child_doc[mapping.remote_fieldname]
				if mapping.local_fieldname != mapping.remote_fieldname:
					doc_remote_fields.append(mapping.remote_fieldname)

		# Apply value mappings to child documents as well
		child_doc = child_map.apply_value_mappings(child_doc)

		# remove the remote fieldnames
		for field in doc_remote_fields:
			child_doc.pop(field, None)

		child_doc["doctype"] = child_map.local_doctype
		mapped_entries.append(child_doc)

	return mapped_entries
