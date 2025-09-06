import frappe

def execute():
    """Add processed_docs field to Event Migration Job doctype"""
    if not frappe.db.has_column("Event Migration Job", "processed_docs"):
        frappe.db.add_column("Event Migration Job", "processed_docs", "Int")
        frappe.db.sql("""UPDATE `tabEvent Migration Job` SET processed_docs = 0""")
        frappe.db.commit()