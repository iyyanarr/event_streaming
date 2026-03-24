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
			
		if self.producer_site == self.consumer_site:
			frappe.throw(_("Producer site and consumer site cannot be the same"))
	
	def get_consumer_company(self, producer_company):
		"""Get the consumer company for a given producer company"""
		for mapping in self.company_mappings:
			if mapping.producer_company == producer_company and mapping.is_active:
				return mapping.consumer_company
		return producer_company

	@frappe.whitelist()
	def import_csv_mapping(self, csv_file_url):
		"""Import company mappings from uploaded CSV file."""
		import csv
		import os
		
		try:
			file_doc = frappe.get_doc("File", {"file_url": csv_file_url})
			file_path = file_doc.get_full_path()
			if not os.path.exists(file_path):
				frappe.throw(_("File not found: {0}").format(csv_file_url))
				
			self.company_mappings = []
			
			with open(file_path, 'r', encoding='utf-8') as csvfile:
				reader = csv.DictReader(csvfile)
				fieldnames = reader.fieldnames
				if not fieldnames:
					frappe.throw(_("CSV file is empty or invalid"))
				
				producer_col = None
				consumer_col = None
				for field in fieldnames:
					f = field.lower().strip().replace('\ufeff', '')
					if f in ['producer_company', 'producer company', 'old_company', 'source_company']:
						if not producer_col: producer_col = field
					elif f in ['consumer_company', 'consumer company', 'new_company', 'target_company']:
						if not consumer_col: consumer_col = field
				
				if (not producer_col or not consumer_col) and len(fieldnames) >= 2:
					if not producer_col: producer_col = fieldnames[0]
					if not consumer_col: consumer_col = fieldnames[1]
					
				if not producer_col or not consumer_col:
					frappe.throw(_("CSV must have columns for producer and consumer company"))
					
				imported = 0
				for row in reader:
					p = (row.get(producer_col) or '').strip()
					c = (row.get(consumer_col) or '').strip()
					if p and c:
						self.append('company_mappings', {
							'producer_company': p,
							'consumer_company': c,
							'is_active': 1
						})
						imported += 1
						
			self.save()
			frappe.db.commit()
			return {"message": _("Successfully imported {0} company mappings").format(imported), "count": imported}
		except Exception as e:
			frappe.log_error(frappe.get_traceback(), "CSV Import Error")
			frappe.throw(_("Error importing CSV: {0}").format(str(e)))


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