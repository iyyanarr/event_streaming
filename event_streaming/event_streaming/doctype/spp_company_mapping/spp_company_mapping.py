# Copyright (c) 2025, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document


class SPPCompanyMapping(Document):
	def validate(self):
		"""Validate company mapping entries"""
		if not self.company_mappings:
			frappe.throw(_("Please add at least one company mapping"))
		
		# Check for duplicate producer companies
		producer_companies = []
		for mapping in self.company_mappings:
			if mapping.producer_company in producer_companies:
				frappe.throw(_("Duplicate producer company: {0}").format(mapping.producer_company))
			producer_companies.append(mapping.producer_company)
	
	def get_consumer_company(self, producer_company):
		"""Get the consumer company for a given producer company"""
		for mapping in self.company_mappings:
			if mapping.producer_company == producer_company:
				return mapping.consumer_company
		return producer_company  # Return original if no mapping found


@frappe.whitelist()
def get_company_mapping_for_sites(producer_site, consumer_site, producer_company):
	"""Get company mapping between two sites for a specific company"""
	mapping = frappe.db.get_value(
		"SPP Company Mapping",
		{"producer_site": producer_site, "consumer_site": consumer_site, "is_active": 1},
		"name"
	)
	
	if mapping:
		doc = frappe.get_doc("SPP Company Mapping", mapping)
		return doc.get_consumer_company(producer_company)
	
	return producer_company


@frappe.whitelist()
def bulk_create_company_mappings_from_csv(file_path, mapping_name, producer_site, consumer_site):
	"""Create company mappings from CSV file"""
	import csv
	
	# Create or get existing mapping document
	existing_mapping = frappe.db.get_value(
		"SPP Company Mapping", 
		{"mapping_name": mapping_name}
	)
	
	if existing_mapping:
		doc = frappe.get_doc("SPP Company Mapping", existing_mapping)
		doc.company_mappings = []  # Clear existing mappings
	else:
		doc = frappe.new_doc("SPP Company Mapping")
		doc.mapping_name = mapping_name
		doc.producer_site = producer_site
		doc.consumer_site = consumer_site
	
	# Read CSV and create mappings
	with open(file_path, 'r', encoding='utf-8') as csvfile:
		reader = csv.DictReader(csvfile)
		for row in reader:
			if row.get('Producer Company') and row.get('Consumer Company'):
				doc.append("company_mappings", {
					"producer_company": row['Producer Company'].strip(),
					"consumer_company": row['Consumer Company'].strip()
				})
	
	doc.save()
	frappe.db.commit()
	
	return f"Created company mapping '{mapping_name}' with {len(doc.company_mappings)} entries"