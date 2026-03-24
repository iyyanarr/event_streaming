import frappe
import json

@frappe.whitelist()
def get_mapping_samples():
    mappings = [
        'spp_item_mapping',
        'spp_warehouse_mapping', 
        'spp_supplier_mapping',
        'spp_company_mapping',
        'spp_account_mapping',
        'spp_address_mapping',
        'spp_contact_mapping',
        'spp_cost_center_mapping',
        'spp_tax_template_mapping'
    ]
    
    result = {}
    for md in mappings:
        try:
            data = frappe.db.sql(f'SELECT * FROM `{md}` LIMIT 3', as_dict=True)
            result[md] = [dict(row) for row in data] if data else []
        except Exception as e:
            result[md] = {'error': str(e)}
    
    return json.dumps(result, default=str)
