# Copyright (c) 2025, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document


class SPPWarehouseMapping(Document):
	def validate(self):
		"""Validate warehouse mapping entries"""
		if not self.warehouse_mappings:
			frappe.throw(_("Please add at least one warehouse mapping"))
		
		# Check for duplicate producer warehouses within same item group
		producer_warehouses = {}
		for mapping in self.warehouse_mappings:
			# Handle multiple item groups by creating keys for each group
			if mapping.item_group:
				item_groups = [g.strip() for g in mapping.item_group.split(',') if g.strip()]
				if not item_groups:
					item_groups = ['All']
			else:
				item_groups = ['All']
			
			for group in item_groups:
				key = f"{mapping.producer_warehouse}|{group}"
				if key in producer_warehouses:
					frappe.throw(_("Duplicate producer warehouse '{0}' for item group '{1}'").format(
						mapping.producer_warehouse, group
					))
				producer_warehouses[key] = True
	
	def get_consumer_warehouse(self, producer_warehouse, item_group=None, operations=None):
		"""Get the consumer warehouse for a given producer warehouse with item group or operations filtering.
		Supports multiple item groups or operations (comma-separated) in the mapping.
		
		Args:
			producer_warehouse: The source warehouse to map from
			item_group: Item group(s) for filtering (used for Stock Entry)
			operations: Operation(s) for filtering (used for Work Order/BOM)
		"""
		if not self.warehouse_mappings:
			return producer_warehouse
		
		# Determine which filter to use - operations takes priority if both are provided
		filter_field = None
		filter_values_to_check = []
		
		if operations:
			filter_field = "operations"
			filter_values_to_check = [op.strip() for op in operations.split(',') if op.strip()]
		elif item_group:
			filter_field = "item_group"
			filter_values_to_check = [ig.strip() for ig in item_group.split(',') if ig.strip()]
		else:
			filter_values_to_check = [None]  # Check for general mappings
		
		# First, try to find exact matches for each filter value
		for check_value in filter_values_to_check:
			for mapping in self.warehouse_mappings:
				if (mapping.producer_warehouse == producer_warehouse and 
					mapping.is_active):
					if filter_field and hasattr(mapping, filter_field):
						mapping_filter_value = getattr(mapping, filter_field)
						if mapping_filter_value == check_value:
							return mapping.consumer_warehouse
					elif not filter_field and not getattr(mapping, 'item_group', None) and not getattr(mapping, 'operations', None):
						# General mapping - no filters specified
						return mapping.consumer_warehouse
		
		# If no exact match, check if any of the mapping's filter values match our filter values
		if filter_field:
			for mapping in self.warehouse_mappings:
				if (mapping.producer_warehouse == producer_warehouse and 
					mapping.is_active and 
					hasattr(mapping, filter_field)):
					mapping_filter_value = getattr(mapping, filter_field)
					if mapping_filter_value:
						# Check if any of our filter values match the mapping's filter values
						mapping_values = [v.strip() for v in mapping_filter_value.split(',') if v.strip()]
						for check_value in filter_values_to_check:
							if check_value in mapping_values:
								return mapping.consumer_warehouse
		
		# Finally, check for general mappings (no item group specified)
		for mapping in self.warehouse_mappings:
			if (mapping.producer_warehouse == producer_warehouse and 
				mapping.is_active and 
				not mapping.item_group):
				return mapping.consumer_warehouse
		
		return producer_warehouse  # Return original if no mapping found

	@frappe.whitelist()
	def import_csv_mapping(self, csv_file_url=None, csv_data=None, replace=0):
		"""Import warehouse mappings from an attached CSV (supports old & new headers).
		Adds: multi item_group support (comma-separated) and validation.
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
			self.warehouse_mappings = []

		existing = {f"{m.producer_warehouse}|{m.item_group or 'All'}" for m in (self.warehouse_mappings or [])}

		reader = csv.DictReader(io.StringIO(csv_data))
		added = 0
		skipped_duplicates = 0
		invalid_item_groups = {}
		for row in reader:
			producer_wh = (row.get('producer_warehouse') or row.get('Producer Warehouse') or
				row.get('source_warehouse') or row.get('Source Warehouse') or row.get('Old Warehouse'))
			consumer_wh = (row.get('consumer_warehouse') or row.get('Consumer Warehouse') or
				row.get('target_warehouse') or row.get('Target Warehouse') or row.get('New Warehouse'))
			item_group_raw = (row.get('item_group') or row.get('Item Group') or
				row.get('item_group_filter') or row.get('Item Group Filter'))

			if not (producer_wh and consumer_wh):
				continue

			# Support comma-separated item groups; if blank treat as [None]
			if item_group_raw:
				raw_groups = [g.strip() for g in item_group_raw.split(',') if g.strip()]
			else:
				raw_groups = [None]

			# Validate each group; collect valid groups (existing Item Group) else skip
			valid_groups = []
			for g in raw_groups:
				if g is None:
					valid_groups.append(None)
				elif frappe.db.exists('Item Group', g):
					valid_groups.append(g)
				else:
					invalid_item_groups.setdefault(producer_wh, []).append(g)

			# If no valid groups, create a generic (no item group) mapping
			if not valid_groups:
				valid_groups = [None]

			for g in valid_groups:
				key = f"{producer_wh.strip()}|{g or 'All'}"
				if key in existing:
					skipped_duplicates += 1
					continue
				self.append('warehouse_mappings', {
					'producer_warehouse': producer_wh.strip(),
					'consumer_warehouse': consumer_wh.strip(),
					'item_group': g,
					'is_active': 1
				})
				existing.add(key)
				added += 1

		self.save()

		msg_parts = [_("Imported {0} warehouse mappings").format(added)]
		if skipped_duplicates:
			msg_parts.append(_("Skipped {0} duplicates").format(skipped_duplicates))
		if invalid_item_groups:
			# Summarize invalid groups
			invalid_summary = []
			for wh, groups in invalid_item_groups.items():
				invalid_summary.append(f"{wh}: {', '.join(groups)}")
			msg_parts.append(_("Invalid Item Groups skipped: {0}").format('; '.join(invalid_summary)))
		frappe.msgprint('<br>'.join(msg_parts))
		return {"added": added, "skipped_duplicates": skipped_duplicates, "invalid_item_groups": invalid_item_groups}


@frappe.whitelist()
def get_warehouse_mapping_for_sites(producer_site, consumer_site, producer_warehouse, item_group=None, operations=None):
	"""Get warehouse mapping between two sites for a specific warehouse
	
	Args:
		producer_site: Source site
		consumer_site: Target site  
		producer_warehouse: Source warehouse to map from
		item_group: Item group(s) for filtering (used for Stock Entry)
		operations: Operation(s) for filtering (used for Work Order/BOM)
	"""
	# Query for mapping using the correct field names
	mapping = frappe.db.get_value(
		"SPP Warehouse Mapping",
		{"producer_site": producer_site, "consumer_site": consumer_site, "is_active": 1},
		"name"
	)
	
	if mapping:
		doc = frappe.get_doc("SPP Warehouse Mapping", mapping)
		return doc.get_consumer_warehouse(producer_warehouse, item_group, operations)
	
	return producer_warehouse


@frappe.whitelist()
def bulk_create_warehouse_mappings_from_csv(file_path, mapping_name, producer_site, consumer_site):
	"""Create warehouse mappings from CSV file with support for multiple item groups"""
	import csv
	
	# Create or get existing mapping document
	existing_mapping = frappe.db.get_value(
		"SPP Warehouse Mapping", 
		{"mapping_name": mapping_name}
	)
	
	if existing_mapping:
		doc = frappe.get_doc("SPP Warehouse Mapping", existing_mapping)
		doc.warehouse_mappings = []  # Clear existing mappings
	else:
		doc = frappe.new_doc("SPP Warehouse Mapping")
		doc.mapping_name = mapping_name
		doc.producer_site = producer_site
		doc.consumer_site = consumer_site
	
	# Read CSV and create mappings
	with open(file_path, 'r', encoding='utf-8') as csvfile:
		reader = csv.DictReader(csvfile)
		for row in reader:
			if row.get('Producer Warehouse') and row.get('Consumer Warehouse'):
				# Handle multiple item groups (comma-separated)
				item_group_value = row.get('Item Group', '').strip()
				if item_group_value:
					# Validate and clean item groups
					item_groups = [g.strip() for g in item_group_value.split(',') if g.strip()]
					valid_groups = []
					for group in item_groups:
						if frappe.db.exists('Item Group', group):
							valid_groups.append(group)
						else:
							frappe.msgprint(_("Warning: Item Group '{0}' does not exist, skipping").format(group))
					
					if valid_groups:
						# Create separate mapping entries for each valid item group
						for group in valid_groups:
							doc.append("warehouse_mappings", {
								"producer_warehouse": row['Producer Warehouse'].strip(),
								"consumer_warehouse": row['Consumer Warehouse'].strip(),
								"item_group": group,
								"is_active": 1
							})
					else:
						# If no valid groups, create general mapping
						doc.append("warehouse_mappings", {
							"producer_warehouse": row['Producer Warehouse'].strip(),
							"consumer_warehouse": row['Consumer Warehouse'].strip(),
							"item_group": None,
							"is_active": 1
						})
				else:
					# No item group specified - general mapping
					doc.append("warehouse_mappings", {
						"producer_warehouse": row['Producer Warehouse'].strip(),
						"consumer_warehouse": row['Consumer Warehouse'].strip(),
						"item_group": None,
						"is_active": 1
					})
	
	doc.save()
	frappe.db.commit()
	
	return f"Created warehouse mapping '{mapping_name}' with {len(doc.warehouse_mappings)} entries"


@frappe.whitelist()
def test_warehouse_mapping_functionality():
	"""Test function to verify warehouse mapping functionality with item groups and operations"""
	print("Testing warehouse mapping functionality...")
	print("=" * 60)
	
	# Test data
	test_warehouse = 'Incoming Store - SPP INDIA'
	test_item_groups = ['Raw Materials - SPP', 'Carbon', 'Chemical', 'Chemicals']
	test_operations = ['Mixing', 'Extrusion', 'Packing', 'Quality Control']
	
	print(f'Producer Warehouse: {test_warehouse}')
	print(f'Item Groups: {test_item_groups}')
	print(f'Operations: {test_operations}')
	print()
	
	try:
		# Test item group mapping (for Stock Entry)
		print("Testing Item Group Mapping (Stock Entry):")
		mapped_warehouse_ig = get_warehouse_mapping_for_sites(
			producer_site='sppmaster.local',
			consumer_site='2526spp.local',
			producer_warehouse=test_warehouse,
			item_group=', '.join(test_item_groups)
		)
		print(f'Item Group Mapped Warehouse: {mapped_warehouse_ig}')
		
		# Test operations mapping (for Work Order/BOM)
		print("\nTesting Operations Mapping (Work Order/BOM):")
		mapped_warehouse_op = get_warehouse_mapping_for_sites(
			producer_site='sppmaster.local',
			consumer_site='2526spp.local',
			producer_warehouse=test_warehouse,
			operations=', '.join(test_operations)
		)
		print(f'Operations Mapped Warehouse: {mapped_warehouse_op}')
		
		print("✓ Test completed successfully!")
		return {"success": True, "item_group_mapping": mapped_warehouse_ig, "operations_mapping": mapped_warehouse_op}
		
	except Exception as e:
		print(f"✗ Test failed with error: {str(e)}")
		import traceback
		traceback.print_exc()
		return {"success": False, "error": str(e)}


@frappe.whitelist() 
def test_multiple_item_groups():
	"""Legacy test function - calls the new comprehensive test"""
	return test_warehouse_mapping_functionality()