import frappe

def update_producer_doctypes():
    frappe.init(site='spp15.local')
    frappe.connect()
    
    producer_name = 'http://2526spp.local:8001'
    
    if not frappe.db.exists('Event Producer', producer_name):
        print(f'Event Producer {producer_name} does not exist')
        frappe.destroy()
        return
    
    # Delete existing producer doctypes
    frappe.db.sql(f"DELETE FROM `tabEvent Producer Document Type` WHERE parent = %s", (producer_name,))
    
    # Add new producer doctypes with mappings
    doctypes_to_sync = [
        {'ref_doctype': 'Purchase Order', 'mapping': 'PO', 'use_same_name': 1},
        {'ref_doctype': 'Purchase Receipt', 'mapping': 'Purchase Receipt', 'use_same_name': 1},
        {'ref_doctype': 'Quality Inspection', 'mapping': 'Quality Inspection', 'use_same_name': 1},
        {'ref_doctype': 'Batch', 'mapping': 'Batch', 'use_same_name': 1},
        {'ref_doctype': 'Serial and Batch Bundle', 'mapping': 'Serial and Batch Bundle', 'use_same_name': 1},
        {'ref_doctype': 'Item', 'mapping': 'Item', 'use_same_name': 1},
        {'ref_doctype': 'Supplier', 'mapping': None, 'use_same_name': 1},
        {'ref_doctype': 'Stock Entry', 'mapping': 'Stock Entry', 'use_same_name': 0},
    ]
    
    for idx, dt in enumerate(doctypes_to_sync, 1):
        frappe.db.sql(f"""
            INSERT INTO `tabEvent Producer Document Type` 
            (name, parent, parenttype, parentfield, idx, ref_doctype, has_mapping, mapping, use_same_name, status, unsubscribe)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            f"{producer_name}-{idx}",
            producer_name,
            'Event Producer',
            'producer_doctypes',
            idx,
            dt['ref_doctype'],
            1 if dt['mapping'] else 0,
            dt['mapping'],
            dt['use_same_name'],
            'Approved',
            1 if dt['ref_doctype'] == 'Stock Entry' else 0
        ))
    
    frappe.db.commit()
    print(f'Updated Event Producer: {producer_name}')
    print(f'Added {len(doctypes_to_sync)} doctypes with mappings')
    
    frappe.destroy()

update_producer_doctypes()
