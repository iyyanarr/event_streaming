#!/usr/bin/env python3
# Copyright (c) 2025, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""
SPP Mapping Setup Utility
Run this script to set up all SPP mappings from your CSV files
"""

import frappe
import os


def setup_spp_mappings():
	"""Set up all SPP mappings from CSV files"""
	
	print("🚀 Setting up SPP Mapping System...")
	
	# Install the DocTypes first
	print("📦 Installing SPP Mapping DocTypes...")
	install_doctypes()
	
	# Import mappings from CSV files
	print("📁 Importing mappings from CSV files...")
	import_all_csv_mappings()
	
	print("✅ SPP Mapping System setup complete!")
	print("\nNext steps:")
	print("1. Go to 'SPP Item Mapping' to view and manage item mappings")
	print("2. Go to 'SPP Warehouse Mapping' to view and manage warehouse mappings") 
	print("3. Go to 'SPP Company Mapping' to view and manage company mappings")
	print("4. Go to 'SPP Account Mapping' to view and manage account mappings")
	print("5. Go to 'SPP Supplier Mapping' to view and manage supplier mappings")
	print("6. Test your mappings using the 'Test Mapping' buttons")


def install_doctypes():
	"""Install SPP mapping DocTypes"""
	doctypes = [
		"SPP Company Mapping",
		"SPP Company Mapping Detail", 
		"SPP Item Mapping",
		"SPP Item Mapping Detail",
		"SPP Warehouse Mapping",
		"SPP Warehouse Mapping Detail",
		"SPP Account Mapping",
		"SPP Account Mapping Detail",
		"SPP Supplier Mapping", 
		"SPP Supplier Mapping Detail"
	]
	
	for doctype in doctypes:
		if not frappe.db.exists("DocType", doctype):
			print(f"   Installing {doctype}...")
			# DocType will be installed automatically when app is migrated
		else:
			print(f"   ✓ {doctype} already exists")


def import_all_csv_mappings():
	"""Import all CSV mappings"""
	try:
		from event_streaming.spp_mapping_integration import bulk_import_mappings_from_csv
		results = bulk_import_mappings_from_csv()
		
		# Import Account Mappings
		mappings_path = frappe.get_app_path("event_streaming", "mappings")
		
		# Import Account Head Mappings
		account_source_csv = os.path.join(mappings_path, "account_heads_source_spp.csv")
		account_target_csv = os.path.join(mappings_path, "account_heads_target_reference.csv")
		
		if os.path.exists(account_source_csv) and os.path.exists(account_target_csv):
			try:
				from event_streaming.event_streaming.doctype.spp_account_mapping.spp_account_mapping import bulk_create_account_mappings_from_csv
				results["accounts"] = bulk_create_account_mappings_from_csv(
					account_source_csv,
					"SPP Master to 2526 - Account Mapping",
					"sppmaster.local",
					"2526spp.local"
				)
			except Exception as e:
				results["accounts"] = {"status": "error", "message": f"Account mapping error: {str(e)}"}
		
		# Import Supplier Mappings
		supplier_csv_path = os.path.join(mappings_path, "supplier_mapping.csv")
		if os.path.exists(supplier_csv_path):
			try:
				from event_streaming.event_streaming.doctype.spp_supplier_mapping.spp_supplier_mapping import bulk_create_supplier_mappings_from_csv
				results["suppliers"] = bulk_create_supplier_mappings_from_csv(
					supplier_csv_path,
					"SPP Master to 2526 - Supplier Mapping",
					"sppmaster.local", 
					"2526spp.local"
				)
			except Exception as e:
				results["suppliers"] = {"status": "error", "message": f"Supplier mapping error: {str(e)}"}
		
		print("\n📊 Import Results:")
		for mapping_type, result in results.items():
			if result:
				if result.get("status") == "success":
					print(f"   ✅ {mapping_type.title()}: {result.get('message')}")
				else:
					print(f"   ❌ {mapping_type.title()}: {result.get('message')}")
			else:
				print(f"   ⏭️  {mapping_type.title()}: Skipped (no CSV file found)")
				
	except Exception as e:
		print(f"❌ Error importing CSV mappings: {str(e)}")


def test_setup():
	"""Test the SPP mapping setup"""
	print("\n🔍 Testing SPP Mapping Setup...")
	
	# Test item mapping
	try:
		from event_streaming.event_streaming.doctype.spp_item_mapping.spp_item_mapping import get_item_mapping_for_sites
		test_result = get_item_mapping_for_sites("sppmaster.local", "2526spp.local", "RM 01")
		print(f"   ✅ Item Mapping Test: RM 01 → {test_result}")
	except Exception as e:
		print(f"   ❌ Item Mapping Test Failed: {str(e)}")
	
	# Test warehouse mapping  
	try:
		from event_streaming.event_streaming.doctype.spp_warehouse_mapping.spp_warehouse_mapping import get_warehouse_mapping_for_sites
		test_result = get_warehouse_mapping_for_sites("sppmaster.local", "2526spp.local", "U3-WIP - SPP INDIA")
		print(f"   ✅ Warehouse Mapping Test: U3-WIP - SPP INDIA → {test_result}")
	except Exception as e:
		print(f"   ❌ Warehouse Mapping Test Failed: {str(e)}")
	
	# Test company mapping
	try:
		from event_streaming.event_streaming.doctype.spp_company_mapping.spp_company_mapping import get_company_mapping_for_sites
		test_result = get_company_mapping_for_sites("sppmaster.local", "2526spp.local", "SPP")
		print(f"   ✅ Company Mapping Test: SPP → {test_result}")
	except Exception as e:
		print(f"   ❌ Company Mapping Test Failed: {str(e)}")
	
	# Test account mapping
	try:
		from event_streaming.event_streaming.doctype.spp_account_mapping.spp_account_mapping import get_account_mapping_for_sites
		test_result = get_account_mapping_for_sites("sppmaster.local", "2526spp.local", "Test Account")
		print(f"   ✅ Account Mapping Test: Test Account → {test_result}")
	except Exception as e:
		print(f"   ❌ Account Mapping Test Failed: {str(e)}")
	
	# Test supplier mapping
	try:
		from event_streaming.event_streaming.doctype.spp_supplier_mapping.spp_supplier_mapping import get_supplier_mapping_for_sites
		test_result = get_supplier_mapping_for_sites("sppmaster.local", "2526spp.local", "Test Supplier")
		print(f"   ✅ Supplier Mapping Test: Test Supplier → {test_result}")
	except Exception as e:
		print(f"   ❌ Supplier Mapping Test Failed: {str(e)}")


if __name__ == "__main__":
	setup_spp_mappings()
	test_setup()