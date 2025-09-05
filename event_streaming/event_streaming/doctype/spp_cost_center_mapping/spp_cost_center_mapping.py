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
				frappe.throw(_("Duplicate producer cost center: {0}").format(mapping.producer_cost_center))
			producer_cost_centers.append(mapping.producer_cost_center)

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