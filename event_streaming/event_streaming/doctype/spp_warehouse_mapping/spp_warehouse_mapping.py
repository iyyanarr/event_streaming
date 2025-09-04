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
			key = f"{mapping.producer_warehouse}|{mapping.item_group or 'All'}"
			if key in producer_warehouses:
				frappe.throw(_("Duplicate producer warehouse '{0}' for item group '{1}'").format(
					mapping.producer_warehouse, mapping.item_group or 'All'
				))
			producer_warehouses[key] = True
	
	def get_consumer_warehouse(self, producer_warehouse, item_group=None):
		"""Get the consumer warehouse for a given producer warehouse"""
		# First try to find specific item group mapping
		if item_group:
			for mapping in self.warehouse_mappings:
				if mapping.producer_warehouse == producer_warehouse and mapping.item_group == item_group:
					return mapping.consumer_warehouse
		
		# Fallback to general mapping (no item group specified)
		for mapping in self.warehouse_mappings:
			if mapping.producer_warehouse == producer_warehouse and not mapping.item_group:
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
def get_warehouse_mapping_for_sites(producer_site, consumer_site, producer_warehouse, item_group=None):
	"""Get warehouse mapping between two sites for a specific warehouse"""
	# Try new field names first
	mapping = frappe.db.get_value(
		"SPP Warehouse Mapping",
		{"producer_site": producer_site, "consumer_site": consumer_site, "is_active": 1},
		"name"
	)
	if not mapping:
		# Fallback to legacy source/target field names
		mapping = frappe.db.get_value(
			"SPP Warehouse Mapping",
			{"source_site": producer_site, "target_site": consumer_site, "is_active": 1},
			"name"
		)
	if mapping:
		doc = frappe.get_doc("SPP Warehouse Mapping", mapping)
		return doc.get_consumer_warehouse(producer_warehouse, item_group)
	
	return producer_warehouse


@frappe.whitelist()
def bulk_create_warehouse_mappings_from_csv(file_path, mapping_name, producer_site, consumer_site):
	"""Create warehouse mappings from CSV file"""
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
				doc.append("warehouse_mappings", {
					"producer_warehouse": row['Producer Warehouse'].strip(),
					"consumer_warehouse": row['Consumer Warehouse'].strip(),
					"item_group": row.get('Item Group', '').strip() if row.get('Item Group') else None
				})
	
	doc.save()
	frappe.db.commit()
	
	return f"Created warehouse mapping '{mapping_name}' with {len(doc.warehouse_mappings)} entries"