# Migration patch to add operations field to SPP Warehouse Mapping Detail
# This patch adds the operations field to support Work Order and BOM warehouse mapping

import frappe
from frappe import _

def execute():
	"""Execute the migration patch"""
	
	# Check if the operations field already exists
	if not frappe.db.has_column("SPP Warehouse Mapping Detail", "operations"):
		# Add the operations column to the table
		frappe.db.sql("""
			ALTER TABLE `tabSPP Warehouse Mapping Detail` 
			ADD COLUMN `operations` TEXT NULL
			AFTER `item_group`
		""")
		
		# Update the DocField record
		if not frappe.db.exists("DocField", {"parent": "SPP Warehouse Mapping Detail", "fieldname": "operations"}):
			doc_field = frappe.new_doc("DocField")
			doc_field.update({
				"parent": "SPP Warehouse Mapping Detail",
				"parenttype": "DocType",
				"parentfield": "fields",
				"fieldname": "operations",
				"fieldtype": "Data",
				"label": "Operations",
				"description": "Comma-separated operations (e.g., Mixing,Extrusion,Packing). Used for Work Order and BOM warehouse mapping.",
				"idx": 5  # Position after item_group
			})
			doc_field.insert()
		
		# Log the migration
		frappe.logger().info("Added operations field to SPP Warehouse Mapping Detail")
		
		# Clear cache to ensure the changes take effect
		frappe.clear_cache(doctype="SPP Warehouse Mapping Detail")
		
		return _("Successfully added operations field to SPP Warehouse Mapping Detail")
	
	return _("Migration not needed - operations field already exists")
