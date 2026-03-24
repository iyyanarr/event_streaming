import frappe
import json
import csv
import os

def export_mappings_reversed():
    frappe.init(site='2526spp.local')
    frappe.connect()
    
    output_dir = '/home/friday/Desktop/spp-bench/mappings_for_spp15'
    os.makedirs(output_dir, exist_ok=True)
    
    # SPP Mapping DocTypes to export and reverse
    mapping_doctypes = [
        'SPP Item Mapping',
        'SPP Warehouse Mapping', 
        'SPP Supplier Mapping',
        'SPP Company Mapping',
        'SPP Account Mapping',
        'SPP Address Mapping',
        'SPP Contact Mapping',
        'SPP Cost Center Mapping',
        'SPP Tax Template Mapping'
    ]
    
    for doctype in mapping_doctypes:
        try:
            # Get all records of this mapping type
            records = frappe.get_all(doctype, fields=['*'])
            
            for record in records:
                # Get the child mappings
                child_field = record.item_mappings._meta_.get_json().get('fieldname') if hasattr(record, 'item_mappings') else None
                
                if 'Item' in doctype:
                    child_table = 'item_mappings'
                    producer_field = 'producer_item_code'
                    consumer_field = 'consumer_item_code'
                elif 'Warehouse' in doctype:
                    child_table = 'warehouse_mappings'
                    producer_field = 'producer_warehouse'
                    consumer_field = 'consumer_warehouse'
                elif 'Supplier' in doctype:
                    child_table = 'supplier_mappings'
                    producer_field = 'producer_supplier'
                    consumer_field = 'consumer_supplier'
                elif 'Company' in doctype:
                    child_table = 'company_mappings'
                    producer_field = 'producer_company'
                    consumer_field = 'consumer_company'
                elif 'Account' in doctype:
                    child_table = 'account_mappings'
                    producer_field = 'producer_account'
                    consumer_field = 'consumer_account'
                elif 'Address' in doctype:
                    child_table = 'address_mappings'
                    producer_field = 'producer_address'
                    consumer_field = 'consumer_address'
                elif 'Contact' in doctype:
                    child_table = 'contact_mappings'
                    producer_field = 'producer_contact'
                    consumer_field = 'consumer_contact'
                elif 'Cost Center' in doctype:
                    child_table = 'cost_center_mappings'
                    producer_field = 'producer_cost_center'
                    consumer_field = 'consumer_cost_center'
                elif 'Tax Template' in doctype:
                    child_table = 'tax_template_mappings'
                    producer_field = 'producer_tax_template'
                    consumer_field = 'consumer_tax_template'
                else:
                    continue
                
                # Get child table data
                child_data = frappe.db.sql(f"""
                    SELECT * FROM `tab{doctype} {doctype.replace('SPP ', '')} {child_table.capitalize()}` 
                    WHERE parent = %s
                """, (record.name,), as_dict=True) if record.name else []
                
                if not child_data:
                    # Try alternative query
                    child_data = frappe.get_all(doctype, filters={'parent': record.name}, 
                        fields=['*'], order_by='idx') if hasattr(record, child_table) else []
                
                reversed_data = []
                for row in child_data:
                    # REVERSE: producer -> consumer, consumer -> producer
                    reversed_row = {
                        f'producer_{producer_field.split("_", 1)[1]}': row.get(consumer_field),
                        f'consumer_{consumer_field.split("_", 1)[1]}': row.get(producer_field),
                        'item_group': row.get('item_group'),
                        'is_active': row.get('is_active'),
                        'notes': row.get('notes')
                    }
                    reversed_data.append(reversed_row)
                
                # Save as CSV
                if reversed_data:
                    csv_file = os.path.join(output_dir, f'{doctype}_reversed.csv')
                    with open(csv_file, 'w') as f:
                        headers = list(reversed_data[0].keys())
                        f.write(','.join(headers) + '\n')
                        for row in reversed_data:
                            values = [str(row.get(h, '')).replace(',', ';') for h in headers]
                            f.write(','.join(values) + '\n')
                    print(f'Exported: {csv_file} ({len(reversed_data)} records)')
                    
        except Exception as e:
            print(f'Error with {doctype}: {e}')
            import traceback
            traceback.print_exc()
    
    frappe.destroy()
    print(f'\n✅ All mappings exported to: {output_dir}')

export_mappings_reversed()
