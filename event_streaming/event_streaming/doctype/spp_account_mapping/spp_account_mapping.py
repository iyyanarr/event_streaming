# Copyright (c) 2025, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document


class SPPAccountMapping(Document):
	def validate(self):
		self.validate_duplicate_source_accounts()
		self.validate_sites()
	
	def validate_duplicate_source_accounts(self):
		"""Ensure no duplicate source account names in the mapping"""
		source_accounts = []
		for account in self.account_mappings:
			if account.source_account in source_accounts:
				frappe.throw(_("Row #{0}: Duplicate source account {1}").format(
					account.idx, frappe.bold(account.source_account)
				))
			source_accounts.append(account.source_account)
	
	def validate_sites(self):
		"""Validate source and target sites"""
		if self.source_site == self.target_site:
			frappe.throw(_("Source site and target site cannot be the same"))
	
	def get_target_account(self, source_account):
		"""Get target account for a given source account"""
		if not self.is_active:
			return source_account
			
		for account in self.account_mappings:
			if account.source_account == source_account and account.is_active:
				return account.target_account
		
		# Return source account if no mapping found
		return source_account
	
	def get_source_account(self, target_account):
		"""Get source account for a given target account (reverse mapping)"""
		if not self.is_active:
			return target_account
			
		for account in self.account_mappings:
			if account.target_account == target_account and account.is_active:
				return account.source_account
		
		# Return target account if no mapping found
		return target_account

	@frappe.whitelist()
	def import_csv_mapping(self, csv_file_url):
		"""Import account mappings from uploaded CSV file using standard producer/consumer-like logic.
		Returns debug info about detected columns."""
		import csv
		import os
		
		try:
			file_doc = frappe.get_doc("File", {"file_url": csv_file_url})
			file_path = file_doc.get_full_path()
			if not os.path.exists(file_path):
				frappe.throw(_("File not found: {0}").format(csv_file_url))
				
			# Clear existing
			self.account_mappings = []
			
			with open(file_path, 'r', encoding='utf-8') as csvfile:
				reader = csv.DictReader(csvfile)
				fieldnames = reader.fieldnames
				if not fieldnames:
					frappe.throw(_("CSV file is empty or invalid"))
				
				# Detect columns
				source_col = None
				target_col = None
				for field in fieldnames:
					f = field.lower().strip().replace('\ufeff', '')
					if f in ['source_account', 'source account', 'old_account', 'producer_account']:
						if not source_col:
							source_col = field
					elif f in ['target_account', 'target account', 'new_account', 'consumer_account']:
						if not target_col:
							target_col = field
							
				# Fallback by position
				if (not source_col or not target_col) and len(fieldnames) >= 2:
					if not source_col: source_col = fieldnames[0]
					if not target_col: target_col = fieldnames[1]
					
				if not source_col or not target_col:
					frappe.throw(_("CSV must have columns for source and target account"))
					
				imported = 0
				for row in reader:
					src = (row.get(source_col) or '').strip()
					tgt = (row.get(target_col) or '').strip()
					if src and tgt:
						self.append('account_mappings', {
							'source_account': src,
							'target_account': tgt,
							'account_type': (row.get('account_type') or row.get('Account Type') or '').strip() or None,
							'is_active': 1
						})
						imported += 1
						
			self.save()
			frappe.db.commit()
			
			return {
				"message": _("Successfully imported {0} account mappings").format(imported),
				"count": imported,
				"source_col": source_col,
				"target_col": target_col
			}
		except Exception as e:
			frappe.log_error(frappe.get_traceback(), "CSV Import Error")
			frappe.throw(_("Error importing CSV: {0}").format(str(e)))


@frappe.whitelist()
def get_account_mapping_for_sites(source_site, target_site, source_account):
	"""Get account mapping between two sites for a specific account"""
	mapping = frappe.db.get_value(
		"SPP Account Mapping",
		{"source_site": source_site, "target_site": target_site, "is_active": 1},
		"name"
	)
	
	if mapping:
		doc = frappe.get_doc("SPP Account Mapping", mapping)
		return doc.get_target_account(source_account)
	
	return source_account


@frappe.whitelist()
def bulk_create_account_mappings_from_csv(file_path, mapping_name, source_site, target_site):
	"""Create account mappings from CSV file"""
	try:
		# Check if mapping already exists
		if frappe.db.exists("SPP Account Mapping", mapping_name):
			frappe.throw(_("Mapping with name {0} already exists").format(mapping_name))
		
		# Create new mapping document
		doc = frappe.new_doc("SPP Account Mapping")
		doc.mapping_name = mapping_name
		doc.source_site = source_site
		doc.target_site = target_site
		doc.is_active = 1
		
		# Read CSV file and create mappings
		import csv
		with open(file_path, 'r') as file:
			reader = csv.DictReader(file)
			for row in reader:
				# Handle different CSV column names
				source_account = row.get('source_account') or row.get('Source Account') or row.get('old_account')
				target_account = row.get('target_account') or row.get('Target Account') or row.get('new_account')
				
				if source_account and target_account:
					doc.append('account_mappings', {
						'source_account': source_account.strip(),
						'target_account': target_account.strip(),
						'account_type': row.get('account_type', '').strip() if row.get('account_type') else None,
						'is_active': 1
					})
		
		doc.save()
		frappe.db.commit()
		
		return {
			"status": "success",
			"message": _("Successfully created mapping {0} with {1} accounts").format(
				mapping_name, len(doc.account_mappings)
			),
			"mapping_name": mapping_name
		}
		
	except Exception as e:
		frappe.log_error(f"Error creating account mapping: {str(e)}")
		return {
			"status": "error", 
			"message": str(e)
		}