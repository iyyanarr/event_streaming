# Copyright (c) 2025, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document


class SPPCompanyMapping(Document):
	def validate(self):
		self.validate_duplicate_source_companies()
		self.validate_sites()
	
	def validate_duplicate_source_companies(self):
		"""Ensure no duplicate source company names in the mapping"""
		source_companies = []
		for company in self.company_mappings:
			if company.source_company in source_companies:
				frappe.throw(_("Row #{0}: Duplicate source company {1}").format(
					company.idx, frappe.bold(company.source_company)
				))
			source_companies.append(company.source_company)
	
	def validate_sites(self):
		"""Validate source and target sites"""
		if self.source_site == self.target_site:
			frappe.throw(_("Source site and target site cannot be the same"))
	
	def get_target_company(self, source_company):
		"""Get target company for a given source company"""
		if not self.is_active:
			return source_company
			
		for company in self.company_mappings:
			if company.source_company == source_company and company.is_active:
				return company.target_company
		
		# Return source company if no mapping found
		return source_company
	
	def get_source_company(self, target_company):
		"""Get source company for a given target company (reverse mapping)"""
		if not self.is_active:
			return target_company
			
		for company in self.company_mappings:
			if company.target_company == target_company and company.is_active:
				return company.source_company
		
		# Return target company if no mapping found
		return target_company


@frappe.whitelist()
def get_company_mapping_for_sites(source_site, target_site, source_company):
	"""Get company mapping between two sites for a specific company"""
	mapping = frappe.db.get_value(
		"SPP Company Mapping",
		{"source_site": source_site, "target_site": target_site, "is_active": 1},
		"name"
	)
	
	if mapping:
		doc = frappe.get_doc("SPP Company Mapping", mapping)
		return doc.get_target_company(source_company)
	
	return source_company