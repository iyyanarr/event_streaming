# Copyright (c) 2025, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document


class SPPCostCenterMapping(Document):
	def validate(self):
		"""Validate cost center mapping entries"""
		if not self.cost_center_mappings:
			frappe.throw(_("Please add at least one cost center mapping"))
		
		# Prevent duplicate producer cost centers
		producer_cost_centers = []
		for mapping in self.cost_center_mappings:
			if mapping.producer_cost_center in producer_cost_centers:
				frappe.throw(_("Row #{0}: Duplicate producer cost center: {1}").format(
					mapping.idx, mapping.producer_cost_center
				))
			producer_cost_centers.append(mapping.producer_cost_center)

		if self.producer_site == self.consumer_site:
			frappe.throw(_("Producer site and consumer site cannot be the same"))

	def get_target_cost_center(self, producer_cost_center):
		"""Return consumer cost center for a given producer cost center (falls back to original)"""
		for mapping in self.cost_center_mappings:
			if (
				mapping.producer_cost_center == producer_cost_center
				and mapping.is_active
			):
				return mapping.consumer_cost_center
		return producer_cost_center

	@frappe.whitelist()
	def import_csv_mapping(self, csv_file_url):
		"""Import cost center mappings from uploaded CSV file."""
		import csv
		import os
		
		try:
			file_doc = frappe.get_doc("File", {"file_url": csv_file_url})
			file_path = file_doc.get_full_path()
			if not os.path.exists(file_path):
				frappe.throw(_("File not found: {0}").format(csv_file_url))
				
			self.cost_center_mappings = []
			
			with open(file_path, 'r', encoding='utf-8') as csvfile:
				reader = csv.DictReader(csvfile)
				fieldnames = reader.fieldnames
				if not fieldnames:
					frappe.throw(_("CSV file is empty or invalid"))
				
				producer_col = None
				consumer_col = None
				for field in fieldnames:
					f = field.lower().strip().replace('\ufeff', '')
					if f in ['producer_cost_center', 'producer cost center', 'old_cost_center', 'source_cost_center']:
						if not producer_col: producer_col = field
					elif f in ['consumer_cost_center', 'consumer cost center', 'new_cost_center', 'target_cost_center']:
						if not consumer_col: consumer_col = field
				
				if (not producer_col or not consumer_col) and len(fieldnames) >= 2:
					if not producer_col: producer_col = fieldnames[0]
					if not consumer_col: consumer_col = fieldnames[1]
					
				if not producer_col or not consumer_col:
					frappe.throw(_("CSV must have columns for producer and consumer cost center"))
					
				imported = 0
				for row in reader:
					p = (row.get(producer_col) or '').strip()
					c = (row.get(consumer_col) or '').strip()
					if p and c:
						self.append('cost_center_mappings', {
							'producer_cost_center': p,
							'consumer_cost_center': c,
							'is_active': 1
						})
						imported += 1
						
			self.flags.ignore_links = True
			self.save()
			frappe.db.commit()
			return {"message": _("Successfully imported {0} cost center mappings").format(imported), "count": imported}
		except Exception as e:
			frappe.log_error(frappe.get_traceback(), "CSV Import Error")
			frappe.throw(_("Error importing CSV: {0}").format(str(e)))


@frappe.whitelist()
def get_cost_center_mapping_for_sites(producer_site, consumer_site, producer_cost_center):
	"""Get cost center mapping between two sites for a specific cost center"""
	mapping = frappe.db.get_value(
		"SPP Cost Center Mapping",
		{"producer_site": producer_site, "consumer_site": consumer_site, "is_active": 1},
		"name"
	)
	
	if mapping:
		doc = frappe.get_doc("SPP Cost Center Mapping", mapping)
		return doc.get_target_cost_center(producer_cost_center)
	
	return producer_cost_center