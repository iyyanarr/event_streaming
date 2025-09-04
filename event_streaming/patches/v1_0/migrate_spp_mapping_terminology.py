# Copyright (c) 2025, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _


def execute():
	"""
	Data migration patch to update SPP mapping doctypes from source/target terminology 
	to producer/consumer terminology to align with existing event streaming framework
	"""
	
	frappe.log("Starting SPP mapping terminology migration...")
	
	try:
		# Migrate SPP Company Mapping
		migrate_company_mappings()
		
		# Migrate SPP Item Mapping
		migrate_item_mappings()
		
		# Migrate SPP Warehouse Mapping
		migrate_warehouse_mappings()
		
		frappe.db.commit()
		frappe.log("SPP mapping terminology migration completed successfully")
		
	except Exception as e:
		frappe.log_error(f"Error in SPP mapping migration: {str(e)}")
		frappe.throw(_("Migration failed. Please check error logs."))


def migrate_company_mappings():
	"""Migrate SPP Company Mapping from source/target to producer/consumer"""
	
	# Check if old fields exist in the database
	if frappe.db.has_column("SPP Company Mapping", "source_site"):
		# Update main doctype fields
		frappe.db.sql("""
			UPDATE `tabSPP Company Mapping` 
			SET producer_site = source_site, consumer_site = target_site
			WHERE source_site IS NOT NULL AND target_site IS NOT NULL
		""")
		
		frappe.log("Migrated SPP Company Mapping parent fields")
	
	# Check if old fields exist in child table
	if frappe.db.has_column("SPP Company Mapping Detail", "source_company"):
		# Update child table fields
		frappe.db.sql("""
			UPDATE `tabSPP Company Mapping Detail` 
			SET producer_company = source_company, consumer_company = target_company
			WHERE source_company IS NOT NULL AND target_company IS NOT NULL
		""")
		
		frappe.log("Migrated SPP Company Mapping Detail fields")


def migrate_item_mappings():
	"""Migrate SPP Item Mapping from source/target to producer/consumer"""
	
	# Check if old fields exist in the database
	if frappe.db.has_column("SPP Item Mapping", "source_site"):
		# Update main doctype fields
		frappe.db.sql("""
			UPDATE `tabSPP Item Mapping` 
			SET producer_site = source_site, consumer_site = target_site
			WHERE source_site IS NOT NULL AND target_site IS NOT NULL
		""")
		
		frappe.log("Migrated SPP Item Mapping parent fields")
	
	# Check if old fields exist in child table
	if frappe.db.has_column("SPP Item Mapping Detail", "source_item_code"):
		# Update child table fields
		frappe.db.sql("""
			UPDATE `tabSPP Item Mapping Detail` 
			SET producer_item_code = source_item_code, consumer_item_code = target_item_code
			WHERE source_item_code IS NOT NULL AND target_item_code IS NOT NULL
		""")
		
		frappe.log("Migrated SPP Item Mapping Detail fields")


def migrate_warehouse_mappings():
	"""Migrate SPP Warehouse Mapping from source/target to producer/consumer"""
	
	# Check if old fields exist in the database
	if frappe.db.has_column("SPP Warehouse Mapping", "source_site"):
		# Update main doctype fields
		frappe.db.sql("""
			UPDATE `tabSPP Warehouse Mapping` 
			SET producer_site = source_site, consumer_site = target_site
			WHERE source_site IS NOT NULL AND target_site IS NOT NULL
		""")
		
		frappe.log("Migrated SPP Warehouse Mapping parent fields")
	
	# Check if old fields exist in child table
	if frappe.db.has_column("SPP Warehouse Mapping Detail", "source_warehouse"):
		# Update child table fields
		frappe.db.sql("""
			UPDATE `tabSPP Warehouse Mapping Detail` 
			SET producer_warehouse = source_warehouse, consumer_warehouse = target_warehouse
			WHERE source_warehouse IS NOT NULL AND target_warehouse IS NOT NULL
		""")
		
		frappe.log("Migrated SPP Warehouse Mapping Detail fields")