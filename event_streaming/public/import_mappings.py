import frappe
import csv
import os

def import_mappings_to_spp15():
    frappe.init(site='spp15.local')
    frappe.connect()
    
    files_dir = '/home/friday/Desktop/spp-bench/sites/spp15.local/private/files'
    
    mappings = [
        {
            'csv': 'SPP Item Mapping_reversed.csv',
            'doctype': 'SPP Item Mapping',
            'child_table': 'tabSPP Item Mapping Detail',
            'prod_col': 'producer_item_code',
            'cons_col': 'consumer_item_code',
            'group_col': 'item_group'
        },
        {
            'csv': 'SPP Warehouse Mapping_reversed.csv',
            'doctype': 'SPP Warehouse Mapping',
            'child_table': 'tabSPP Warehouse Mapping Detail',
            'prod_col': 'producer_warehouse',
            'cons_col': 'consumer_warehouse',
            'group_col': 'item_group'
        },
        {
            'csv': 'SPP Supplier Mapping_reversed.csv',
            'doctype': 'SPP Supplier Mapping',
            'child_table': 'tabSPP Supplier Mapping Detail',
            'prod_col': 'producer_supplier',
            'cons_col': 'consumer_supplier',
            'group_col': 'supplier_group'
        },
    ]
    
    for mapping in mappings:
        csv_path = os.path.join(files_dir, mapping['csv'])
        if not os.path.exists(csv_path):
            print(f'Skipping: {csv_path} not found')
            continue
        
        main_name = 'Reverse_2526_to_spp15'
        
        # Delete existing
        frappe.db.sql(f"DELETE FROM `{mapping['child_table']}` WHERE parent = %s", (main_name,))
        frappe.db.sql(f"DELETE FROM `tab{mapping['doctype']}` WHERE name = %s", (main_name,))
        
        # Insert main record
        frappe.db.sql(f"""
            INSERT INTO `tab{mapping['doctype']}` 
            (name, mapping_name, producer_site, consumer_site, is_active, docstatus, owner, creation, modified, modified_by)
            VALUES (%s, %s, %s, %s, 1, 0, 'Administrator', NOW(), NOW(), 'Administrator')
        """, (main_name, main_name, 'http://2526spp.local:8001', 'http://spp15.local:8001'))
        
        # Read CSV and insert child records
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for idx, row in enumerate(reader, 1):
                child_name = f"{main_name}-{idx}"
                prod_field = mapping['prod_col']
                cons_field = mapping['cons_col']
                group_field = mapping['group_col']
                
                # Handle "None" string values
                item_group_val = row.get(group_field, '')
                if item_group_val == 'None':
                    item_group_val = None
                
                is_active_val = row.get('is_active', '1')
                if is_active_val == 'None' or is_active_val == '':
                    is_active_val = '1'
                
                frappe.db.sql(f"""
                    INSERT INTO `{mapping['child_table']}` 
                    (name, parent, parenttype, parentfield, idx, {prod_field}, {cons_field}, {group_field}, is_active, notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    child_name, main_name, mapping['doctype'], 
                    mapping['doctype'].lower().replace(' ', '_') + 's',
                    idx,
                    row.get(prod_field, ''),
                    row.get(cons_field, ''),
                    item_group_val,
                    is_active_val,
                    row.get('notes') or None
                ))
        
        # Verify
        count = frappe.db.sql(f"SELECT COUNT(*) as cnt FROM `{mapping['child_table']}` WHERE parent = %s", (main_name,))[0][0]
        print(f'Imported: {mapping["doctype"]} - {count} child records')
    
    frappe.db.commit()
    frappe.destroy()
    print('\n✅ All mappings imported to spp15.local!')

import_mappings_to_spp15()
