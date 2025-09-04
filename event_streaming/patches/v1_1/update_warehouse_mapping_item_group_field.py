# Migration patch to update warehouse mapping item_group field to support multiple item groups
# This patch changes the item_group field from Link to Data type to support comma-separated values

import frappe
from frappe import _

def execute():
	"""Execute the migration patch"""
	
	# Check if the field already exists and is the correct type
	if frappe.db.has_column("SPP Warehouse Mapping Detail", "item_group"):
		# Get current field type
		current_field_type = frappe.db.sql("""
			SELECT fieldtype 
			FROM `tabDocField` 
			WHERE parent = 'SPP Warehouse Mapping Detail' 
			AND fieldname = 'item_group'
		""", as_dict=True)
		
		if current_field_type and current_field_type[0].get('fieldtype') == 'Link':
			# Update the field type from Link to Data
			frappe.db.sql("""
				UPDATE `tabDocField` 
				SET fieldtype = 'Data', 
					options = NULL,
					description = 'Comma-separated item groups (e.g., Raw Material,Chemical). Leave empty for general mappings.'
				WHERE parent = 'SPP Warehouse Mapping Detail' 
				AND fieldname = 'item_group'
			""")
			
			# Clear any invalid item group references that might exist
			frappe.db.sql("""
				UPDATE `tabSPP Warehouse Mapping Detail` 
				SET item_group = NULL 
				WHERE item_group NOT IN (SELECT name FROM `tabItem Group`)
				AND item_group IS NOT NULL
			""")
			
			# Log the migration
			frappe.logger().info("Updated SPP Warehouse Mapping Detail item_group field from Link to Data type")
			
			# Clear cache to ensure the changes take effect
			frappe.clear_cache(doctype="SPP Warehouse Mapping Detail")
			
			return _("Successfully updated warehouse mapping item_group field to support multiple item groups")
	
	return _("Migration not needed - field already supports multiple item groups")