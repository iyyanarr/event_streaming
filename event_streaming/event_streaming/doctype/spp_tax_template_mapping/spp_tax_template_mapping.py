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