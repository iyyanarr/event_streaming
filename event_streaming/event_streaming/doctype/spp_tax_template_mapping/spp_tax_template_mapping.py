# Copyright (c) 2025, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document


class SPPTaxTemplateMapping(Document):
	def validate(self):
		"""Validate tax template mapping entries"""
		if not self.tax_template_mappings:
			frappe.throw(_("Please add at least one tax template mapping"))
		
		# Prevent duplicate producer tax templates
		producer_tax_templates = []
		for mapping in self.tax_template_mappings:
			if mapping.producer_tax_template in producer_tax_templates:
				frappe.throw(_("Duplicate producer tax template: {0}").format(mapping.producer_tax_template))
			producer_tax_templates.append(mapping.producer_tax_template)

		if self.producer_site == self.consumer_site:
			frappe.throw(_("Producer site and consumer site cannot be the same"))

	def get_target_tax_template(self, producer_tax_template):
		"""Return consumer tax template for a given producer tax template (falls back to original)"""
		for mapping in self.tax_template_mappings:
			if (
				mapping.producer_tax_template == producer_tax_template
				and mapping.is_active
			):
				return mapping.consumer_tax_template
		return producer_tax_template

	@frappe.whitelist()
	def import_csv_mapping(self, csv_file_url):
		"""Import tax template mappings from uploaded CSV file."""
		import csv
		import os
		
		try:
			file_doc = frappe.get_doc("File", {"file_url": csv_file_url})
			file_path = file_doc.get_full_path()
			if not os.path.exists(file_path):
				frappe.throw(_("File not found: {0}").format(csv_file_url))
				
			self.tax_template_mappings = []
			
			with open(file_path, 'r', encoding='utf-8') as csvfile:
				reader = csv.DictReader(csvfile)
				fieldnames = reader.fieldnames
				if not fieldnames:
					frappe.throw(_("CSV file is empty or invalid"))
				
				producer_col = None
				consumer_col = None
				for field in fieldnames:
					f = field.lower().strip().replace('\ufeff', '')
					if f in ['producer_tax_template', 'producer tax template', 'old_tax_template', 'source_tax_template']:
						if not producer_col: producer_col = field
					elif f in ['consumer_tax_template', 'consumer tax template', 'new_tax_template', 'target_tax_template']:
						if not consumer_col: consumer_col = field
				
				if (not producer_col or not consumer_col) and len(fieldnames) >= 2:
					if not producer_col: producer_col = fieldnames[0]
					if not consumer_col: consumer_col = fieldnames[1]
					
				if not producer_col or not consumer_col:
					frappe.throw(_("CSV must have columns for producer and consumer tax template"))
					
				imported = 0
				for row in reader:
					p = (row.get(producer_col) or '').strip()
					c = (row.get(consumer_col) or '').strip()
					if p and c:
						self.append('tax_template_mappings', {
							'producer_tax_template': p,
							'consumer_tax_template': c,
							'is_active': 1
						})
						imported += 1
						
			self.save()
			frappe.db.commit()
			return {"message": _("Successfully imported {0} tax template mappings").format(imported), "count": imported}
		except Exception as e:
			frappe.log_error(frappe.get_traceback(), "CSV Import Error")
			frappe.throw(_("Error importing CSV: {0}").format(str(e)))


@frappe.whitelist()
def get_tax_template_mapping_for_sites(producer_site, consumer_site, producer_tax_template):
	"""Get tax template mapping between two sites for a specific tax template"""
	mapping = frappe.db.get_value(
		"SPP Tax Template Mapping",
		{"producer_site": producer_site, "consumer_site": consumer_site, "is_active": 1},
		"name"
	)
	
	if mapping:
		doc = frappe.get_doc("SPP Tax Template Mapping", mapping)
		return doc.get_target_tax_template(producer_tax_template)
	
	return producer_tax_template