# Copyright (c) 2025, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document
import csv
import os


class SPPItemMapping(Document):
	def validate(self):
		"""Validate item mapping entries"""
		if not self.item_mappings:
			frappe.throw(_("Please add at least one item mapping"))
		# Prevent duplicate producer item codes
		producer_items = []
		for mapping in self.item_mappings:
			if mapping.producer_item_code in producer_items:
				frappe.throw(_("Duplicate producer item code: {0}").format(mapping.producer_item_code))
			producer_items.append(mapping.producer_item_code)

	def get_target_item_code(self, producer_item_code):  # kept name for backward compatibility
		"""Return consumer item code for a given producer item code (falls back to original)"""
		for mapping in self.item_mappings:
			if (
				mapping.producer_item_code == producer_item_code
				and mapping.is_active
			):
				return mapping.consumer_item_code
		return producer_item_code

	@frappe.whitelist()
	def import_csv_mapping(self, csv_file_url):
		"""Import item mappings from uploaded CSV file using new producer/consumer terminology (accepts legacy headers).
		Adds safeguards so producer and consumer columns are not accidentally mapped from the same CSV column.
		Returns debug info about detected columns."""
		try:
			file_doc = frappe.get_doc("File", {"file_url": csv_file_url})
			file_path = file_doc.get_full_path()
			if not os.path.exists(file_path):
				frappe.throw(_("File not found: {0}").format(csv_file_url))
			# Clear existing
			self.item_mappings = []
			with open(file_path, 'r', encoding='utf-8') as csvfile:
				reader = csv.DictReader(csvfile)
				fieldnames = reader.fieldnames
				if not fieldnames:
					frappe.throw(_("CSV file is empty or invalid"))
				original_fieldnames = list(fieldnames)  # keep for debugging
				producer_col = None
				consumer_col = None
				for field in fieldnames:
					f = field.lower().strip().replace('\ufeff', '')  # strip BOM if present
					if f in ['old_item_code', 'source_item_code', 'producer_item_code', 'producer item code']:
						if not producer_col:
							producer_col = field
					elif f in ['new_item_code', 'target_item_code', 'consumer_item_code', 'consumer item code']:
						if not consumer_col:
							consumer_col = field
				# Fallback: If one of the columns was not detected but there are exactly 2 columns, assign by position
				if (not producer_col or not consumer_col) and len(fieldnames) >= 2:
					if not producer_col:
						producer_col = fieldnames[0]
					if not consumer_col and len(fieldnames) > 1:
						consumer_col = fieldnames[1]
				# Guard: prevent both pointing to same field if multiple columns exist
				if producer_col == consumer_col:
					if len(fieldnames) > 1:
						# try to pick a different second column
						for fn in fieldnames:
							if fn != producer_col:
								consumer_col = fn
								break
					if producer_col == consumer_col:
						frappe.throw(_("Could not distinctly identify producer and consumer item code columns. Detected only one usable column: {0}. Please ensure headers like 'old_item_code,new_item_code' or 'Producer Item Code,Consumer Item Code'.").format(producer_col))
				if not producer_col or not consumer_col:
					frappe.throw(_("CSV must have columns for producer/source item code and consumer/target item code"))
				imported = 0
				for row in reader:
					producer_code = (row.get(producer_col) or '').strip()
					consumer_code = (row.get(consumer_col) or '').strip()
					if producer_code and consumer_code:
						self.append('item_mappings', {
							'producer_item_code': producer_code,
							'consumer_item_code': consumer_code,
							'item_group': (row.get('item_group') or row.get('Item Group') or '').strip() or None,
							'is_active': 1,
							'notes': (row.get('notes') or '').strip() or None
						})
						imported += 1
			self.flags.ignore_links = True
			self.save()
			frappe.db.commit()
			# Log for diagnostics
			frappe.logger().info({
				"event": "spp_item_mapping_import",
				"mapping": self.name,
				"producer_col": producer_col,
				"consumer_col": consumer_col,
				"fieldnames": original_fieldnames,
				"imported_count": imported
			})
			return {
				"message": _("Successfully imported {0} item mappings").format(imported),
				"count": imported,
				"producer_col": producer_col,
				"consumer_col": consumer_col
			}
		except Exception as e:
			frappe.log_error(frappe.get_traceback(), "CSV Import Error")
			frappe.throw(_("Error importing CSV: {0}").format(str(e)))


@frappe.whitelist()
def get_item_mapping_for_sites(producer_site, consumer_site, producer_item_code):
	"""Get item mapping between two sites for a specific item"""
	mapping = frappe.db.get_value(
		"SPP Item Mapping",
		{"producer_site": producer_site, "consumer_site": consumer_site, "is_active": 1},
		"name"
	)
	if mapping:
		doc = frappe.get_doc("SPP Item Mapping", mapping)
		return doc.get_target_item_code(producer_item_code)
	return producer_item_code


@frappe.whitelist()
def bulk_create_mappings_from_csv(file_path, mapping_name, producer_site, consumer_site):
	"""Create item mappings from CSV file (expects headers: Producer Item Code, Consumer Item Code, Item Group)"""
	import csv
	existing_mapping = frappe.db.get_value("SPP Item Mapping", {"mapping_name": mapping_name})
	if existing_mapping:
		doc = frappe.get_doc("SPP Item Mapping", existing_mapping)
		doc.item_mappings = []
	else:
		doc = frappe.new_doc("SPP Item Mapping")
		doc.mapping_name = mapping_name
		doc.producer_site = producer_site
		doc.consumer_site = consumer_site
	with open(file_path, 'r', encoding='utf-8') as csvfile:
		reader = csv.DictReader(csvfile)
		for row in reader:
			p = row.get('Producer Item Code') or row.get('producer_item_code') or row.get('old_item_code')
			c = row.get('Consumer Item Code') or row.get('consumer_item_code') or row.get('new_item_code')
			if p and c:
				doc.append('item_mappings', {
					'producer_item_code': p.strip(),
					'consumer_item_code': c.strip(),
					'item_group': (row.get('Item Group') or row.get('item_group') or '').strip() or None,
					'is_active': 1
				})
	doc.save()
	frappe.db.commit()
	return f"Created item mapping '{mapping_name}' with {len(doc.item_mappings)} entries"