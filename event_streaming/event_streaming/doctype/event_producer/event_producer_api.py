import frappe
from frappe import _
import json

@frappe.whitelist(allow_guest=True)
def get_filtered_documents_with_child_tables(doctype, filters=None, child_table_filters=None, date_filters=None, limit=None):
    """
    Special API endpoint to filter documents based on both parent and child table fields
    This overcomes the limitation of Frappe Client REST API not supporting child table filters
    
    Args:
        doctype: Parent doctype to filter
        filters: Standard parent table filters (same format as get_list)
        child_table_filters: List of child table filters in format:
            [
                {
                    "child_doctype": "Purchase Order Item", 
                    "fieldname": "item_code",
                    "operator": "=", 
                    "value": "ITEM-001"
                }
            ]
        date_filters: Standard date range filters
        limit: Maximum number of documents to return
        
    Returns:
        List of document names that match all criteria
    """
    try:
        # Verify API access
        if not frappe.has_permission(doctype, "read"):
            frappe.throw(_("Insufficient permissions to access {0}").format(doctype))
            
        # Parse filters if they're JSON strings
        if isinstance(filters, str):
            filters = json.loads(filters) if filters else []
        if isinstance(child_table_filters, str):
            child_table_filters = json.loads(child_table_filters) if child_table_filters else []
        if isinstance(date_filters, str):
            date_filters = json.loads(date_filters) if date_filters else []
            
        # Start building the SQL query
        meta = frappe.get_meta(doctype)
        parent_table = f"`tab{doctype}`"
        
        # Base query - select parent document names
        query = f"SELECT DISTINCT {parent_table}.name"
        
        # FROM clause
        from_clause = f"FROM {parent_table}"
        
        # WHERE clause components
        where_conditions = []
        
        # Add parent table filters
        if filters:
            parent_conditions = build_sql_conditions(filters, parent_table)
            where_conditions.extend(parent_conditions)
            
        # Add date filters
        if date_filters:
            date_conditions = build_sql_conditions(date_filters, parent_table)
            where_conditions.extend(date_conditions)
            
        # Add child table filters with JOINs
        if child_table_filters:
            child_joins = []
            child_conditions = []
            
            # Group child filters by child doctype
            child_filters_by_doctype = {}
            for child_filter in child_table_filters:
                child_doctype = child_filter.get("child_doctype")
                if child_doctype not in child_filters_by_doctype:
                    child_filters_by_doctype[child_doctype] = []
                child_filters_by_doctype[child_doctype].append(child_filter)
            
            # Create JOINs and conditions for each child doctype
            for child_doctype, filters_list in child_filters_by_doctype.items():
                child_table_alias = f"child_{child_doctype.lower().replace(' ', '_')}"
                child_table = f"`tab{child_doctype}`"
                
                # Add INNER JOIN for child table
                join_condition = f"INNER JOIN {child_table} AS {child_table_alias} ON {parent_table}.name = {child_table_alias}.parent"
                child_joins.append(join_condition)
                
                # Build conditions for this child table
                for child_filter in filters_list:
                    condition = build_child_table_condition(child_filter, child_table_alias)
                    if condition:
                        child_conditions.append(condition)
            
            # Add JOINs to FROM clause
            if child_joins:
                from_clause += " " + " ".join(child_joins)
                
            # Add child conditions to WHERE clause
            if child_conditions:
                where_conditions.extend(child_conditions)
        
        # Combine WHERE conditions
        if where_conditions:
            where_clause = "WHERE " + " AND ".join(where_conditions)
        else:
            where_clause = ""
            
        # Add default filter to exclude cancelled documents
        if where_clause:
            where_clause += f" AND {parent_table}.docstatus < 2"
        else:
            where_clause = f"WHERE {parent_table}.docstatus < 2"
        
        # Complete query
        complete_query = f"{query} {from_clause} {where_clause}"
        
        # Add ORDER BY
        complete_query += f" ORDER BY {parent_table}.creation DESC"
        
        # Add LIMIT if specified
        if limit:
            complete_query += f" LIMIT {int(limit)}"
            
        frappe.logger().info(f"Child table filter query: {complete_query}")
        
        # Execute query
        result = frappe.db.sql(complete_query, as_dict=True)
        
        # Extract document names
        document_names = [row['name'] for row in result]
        
        frappe.logger().info(f"Found {len(document_names)} documents matching child table filters")
        
        return {
            "status": "success",
            "document_names": document_names,
            "total_count": len(document_names),
            "query_executed": complete_query
        }
        
    except Exception as e:
        frappe.log_error(f"Child table filter API error: {str(e)}", "Child Table Filter API")
        return {
            "status": "error",
            "message": str(e)
        }

def build_sql_conditions(filters, table_alias):
    """Build SQL WHERE conditions from Frappe filters format"""
    conditions = []
    
    for filter_condition in filters:
        if isinstance(filter_condition, list) and len(filter_condition) >= 3:
            fieldname = filter_condition[0]
            operator = filter_condition[1]
            value = filter_condition[2]
            
            # Build condition based on operator
            if operator.lower() == "=":
                conditions.append(f"{table_alias}.{fieldname} = {frappe.db.escape(value)}")
            elif operator.lower() == "!=":
                conditions.append(f"{table_alias}.{fieldname} != {frappe.db.escape(value)}")
            elif operator.lower() == "like":
                conditions.append(f"{table_alias}.{fieldname} LIKE {frappe.db.escape(f'%{value}%')}")
            elif operator.lower() == "not like":
                conditions.append(f"{table_alias}.{fieldname} NOT LIKE {frappe.db.escape(f'%{value}%')}")
            elif operator.lower() == "in":
                if isinstance(value, list):
                    escaped_values = [frappe.db.escape(v) for v in value]
                    conditions.append(f"{table_alias}.{fieldname} IN ({','.join(escaped_values)})")
            elif operator.lower() == "not in":
                if isinstance(value, list):
                    escaped_values = [frappe.db.escape(v) for v in value]
                    conditions.append(f"{table_alias}.{fieldname} NOT IN ({','.join(escaped_values)})")
            elif operator.lower() == ">":
                conditions.append(f"{table_alias}.{fieldname} > {frappe.db.escape(value)}")
            elif operator.lower() == ">=":
                conditions.append(f"{table_alias}.{fieldname} >= {frappe.db.escape(value)}")
            elif operator.lower() == "<":
                conditions.append(f"{table_alias}.{fieldname} < {frappe.db.escape(value)}")
            elif operator.lower() == "<=":
                conditions.append(f"{table_alias}.{fieldname} <= {frappe.db.escape(value)}")
            elif operator.lower() == "between":
                if isinstance(value, list) and len(value) == 2:
                    conditions.append(f"{table_alias}.{fieldname} BETWEEN {frappe.db.escape(value[0])} AND {frappe.db.escape(value[1])}")
                    
    return conditions

def build_child_table_condition(child_filter, table_alias):
    """Build SQL condition for child table filter"""
    fieldname = child_filter.get("fieldname")
    operator = child_filter.get("operator", "=")
    value = child_filter.get("value")
    
    if not fieldname or value is None:
        return None
        
    # Build condition based on operator
    if operator == "=":
        return f"{table_alias}.{fieldname} = {frappe.db.escape(value)}"
    elif operator == "!=":
        return f"{table_alias}.{fieldname} != {frappe.db.escape(value)}"
    elif operator == "like":
        return f"{table_alias}.{fieldname} LIKE {frappe.db.escape(f'%{value}%')}"
    elif operator == "not like":
        return f"{table_alias}.{fieldname} NOT LIKE {frappe.db.escape(f'%{value}%')}"
    elif operator == "in":
        if isinstance(value, str):
            value = [v.strip() for v in value.split(',')]
        if isinstance(value, list):
            escaped_values = [frappe.db.escape(v) for v in value]
            return f"{table_alias}.{fieldname} IN ({','.join(escaped_values)})"
    elif operator == "not in":
        if isinstance(value, str):
            value = [v.strip() for v in value.split(',')]
        if isinstance(value, list):
            escaped_values = [frappe.db.escape(v) for v in value]
            return f"{table_alias}.{fieldname} NOT IN ({','.join(escaped_values)})"
    elif operator == ">":
        return f"{table_alias}.{fieldname} > {frappe.db.escape(value)}"
    elif operator == ">=":
        return f"{table_alias}.{fieldname} >= {frappe.db.escape(value)}"
    elif operator == "<":
        return f"{table_alias}.{fieldname} < {frappe.db.escape(value)}"
    elif operator == "<=":
        return f"{table_alias}.{fieldname} <= {frappe.db.escape(value)}"
        
    return None

@frappe.whitelist(allow_guest=True) 
def get_doctype_child_tables(doctype):
    """Get child table information for a doctype including field details"""
    try:
        if not frappe.has_permission(doctype, "read"):
            frappe.throw(_("Insufficient permissions to access {0}").format(doctype))
            
        meta = frappe.get_meta(doctype)
        child_tables = {}
        
        for field in meta.fields:
            if field.fieldtype == "Table" and field.options:
                child_doctype = field.options
                try:
                    child_meta = frappe.get_meta(child_doctype)
                    
                    # Get filterable fields from child table
                    child_fields = []
                    for child_field in child_meta.fields:
                        if child_field.fieldtype in [
                            'Data', 'Select', 'Link', 'Int', 'Float', 'Currency', 
                            'Date', 'Datetime', 'Check', 'Text', 'Small Text'
                        ] and not child_field.hidden and not child_field.read_only:
                            child_fields.append({
                                'fieldname': child_field.fieldname,
                                'label': child_field.label or child_field.fieldname,
                                'fieldtype': child_field.fieldtype,
                                'options': child_field.options
                            })
                    
                    child_tables[field.fieldname] = {
                        'label': field.label or field.fieldname,
                        'child_doctype': child_doctype,
                        'fields': child_fields
                    }
                except Exception as e:
                    frappe.logger().error(f"Error getting meta for child doctype {child_doctype}: {str(e)}")
                    continue
        
        return {
            "status": "success",
            "child_tables": child_tables
        }
        
    except Exception as e:
        frappe.log_error(f"Get child tables API error: {str(e)}", "Get Child Tables API")
        return {
            "status": "error", 
            "message": str(e)
        }
