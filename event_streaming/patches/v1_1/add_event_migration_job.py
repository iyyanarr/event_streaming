import frappe

def execute():
    """Add Event Migration Job doctype"""
    if not frappe.db.exists('DocType', 'Event Migration Job'):
        # Create new doctype
        job_doctype = frappe.new_doc('DocType')
        job_doctype.name = 'Event Migration Job'
        job_doctype.module = 'Event Streaming'
        job_doctype.custom = 0
        job_doctype.fields = [
            {
                "fieldname": "producer",
                "fieldtype": "Link",
                "in_list_view": 1,
                "label": "Event Producer",
                "options": "Event Producer",
                "reqd": 1
            },
            {
                "default": "Queued",
                "fieldname": "status",
                "fieldtype": "Select",
                "in_list_view": 1,
                "label": "Status",
                "options": "Queued\nIn Progress\nCompleted\nFailed",
                "read_only": 1
            },
            {
                "default": "Creation Date",
                "fieldname": "date_filter_type",
                "fieldtype": "Select",
                "label": "Filter By",
                "options": "Creation Date\nModified Date\nTransaction Date\nPosting Date"
            },
            {
                "fieldname": "from_date",
                "fieldtype": "Datetime",
                "label": "From Date"
            },
            {
                "fieldname": "to_date",
                "fieldtype": "Datetime",
                "label": "To Date"
            },
            {
                "fieldname": "selected_doctypes",
                "fieldtype": "Code",
                "label": "Selected Document Types",
                "options": "JSON"
            },
            {
                "default": "0",
                "fieldname": "total_docs",
                "fieldtype": "Int",
                "label": "Total Documents",
                "read_only": 1
            },
            {
                "default": "0",
                "fieldname": "processed_docs",
                "fieldtype": "Int",
                "label": "Processed Documents",
                "read_only": 1
            },
            {
                "default": "{}",
                "fieldname": "processed_doctypes",
                "fieldtype": "Code",
                "label": "Processed Document Types",
                "options": "JSON",
                "read_only": 1
            },
            {
                "fieldname": "start_time",
                "fieldtype": "Datetime",
                "label": "Start Time",
                "read_only": 1
            },
            {
                "fieldname": "end_time",
                "fieldtype": "Datetime",
                "label": "End Time",
                "read_only": 1
            },
            {
                "fieldname": "error_log",
                "fieldtype": "Text",
                "label": "Error Log",
                "read_only": 1
            }
        ]
        job_doctype.permissions = [{
            "role": "System Manager",
            "read": 1,
            "write": 1,
            "create": 1,
            "delete": 1,
            "export": 1
        }]
        job_doctype.insert()