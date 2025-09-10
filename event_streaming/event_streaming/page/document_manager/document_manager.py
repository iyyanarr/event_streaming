import frappe
from frappe import _
import json
from collections import defaultdict
import re

@frappe.whitelist()
def get_available_doctypes():
    """Get list of doctypes that have migrated documents"""
    # Get doctypes that are commonly migrated
    common_doctypes = ['Purchase Order', 'Sales Order', 'Purchase Invoice', 'Sales Invoice', 
                      'Supplier', 'Customer', 'Item', 'Delivery Note', 'Purchase Receipt','Quality Inspection']
    
    available_doctypes = []
    for doctype in common_doctypes:
        if frappe.db.exists("DocType", doctype):
            count = frappe.db.count(doctype)
            if count > 0:
                available_doctypes.append(doctype)
    
    return available_doctypes

@frappe.whitelist()
def get_documents_data(filters):
    """Get documents data with migration status and error analysis"""
    try:
        filters = json.loads(filters) if isinstance(filters, str) else filters
        
        # Require Document Type to be selected - don't load on status/migration filters alone
        if not filters.get('doctype'):
            # No doctype selected - return empty result with message
            return {
                "summary": {
                    'total': 0,
                    'success': 0,
                    'failed': 0,
                    'draft': 0,
                    'submitted': 0,
                    'mapping_errors': 0
                },
                "documents": [],
                "message": "Please select a Document Type to load documents"
            }
        
        # For specific doctype, query that table directly
        doctype = filters['doctype']
        return get_doctype_specific_data(doctype, filters)
            
    except Exception as e:
        frappe.log_error(message=frappe.get_traceback(), title="Get documents data failed")
        return {"summary": {}, "documents": []}

def get_doctype_specific_data(doctype, filters):
    """Get data for a specific doctype - only draft and cancelled documents"""
    try:
        # Base query for the doctype - ONLY draft and cancelled documents
        conditions = ["docstatus IN (0, 2)"]  # 0=Draft, 2=Cancelled (NO submitted documents)
        params = {}
        
        # Status filter - further restrict to specific statuses within draft/cancelled
        if filters.get('status'):
            if filters['status'] == 'draft':
                conditions = ["docstatus = 0"]  # Only drafts
            elif filters['status'] == 'cancelled':
                conditions = ["docstatus = 2"]  # Only cancelled
            elif filters['status'] == 'failed':
                # Look for draft documents that might have failed submission
                conditions = ["docstatus = 0"]
            # Remove 'submitted' option handling since we never want submitted docs
        
        # Get documents
        query = f"""
            SELECT 
                name,
                '{doctype}' as doctype,
                docstatus,
                status,
                creation,
                modified,
                owner
            FROM `tab{doctype}`
            WHERE {' AND '.join(conditions)}
            ORDER BY creation DESC
            LIMIT 1000
        """
        
        documents = frappe.db.sql(query, params, as_dict=True)
        
        # Enhance documents with migration status and error analysis
        enhanced_documents = []
        for doc in documents:
            # Simulate migration status based on various factors
            migration_status = analyze_document_migration_status(doctype, doc)
            # DISABLE error analysis during document loading to prevent any submission issues
            # error_details = get_document_error_details(doctype, doc)
            error_details = None  # Skip error analysis during loading
            
            doc.update({
                'migration_status': migration_status,
                'error_details': error_details
            })
            enhanced_documents.append(doc)
        
        # Calculate summary
        summary = calculate_summary(enhanced_documents)
        
        return {
            "summary": summary,
            "documents": enhanced_documents
        }
        
    except Exception as e:
        frappe.log_error(message=frappe.get_traceback(), title=f"Get {doctype} data failed")
        return {"summary": {}, "documents": []}

def get_aggregated_documents_data(filters):
    """Get aggregated data from multiple doctypes - only draft and cancelled documents"""
    try:
        all_documents = []
        doctypes = get_available_doctypes()
        
        for doctype in doctypes:
            try:
                # Get sample documents from each doctype - ONLY draft and cancelled
                query = f"""
                    SELECT 
                        name,
                        '{doctype}' as doctype,
                        docstatus,
                        status,
                        creation,
                        modified,
                        owner
                    FROM `tab{doctype}`
                    WHERE docstatus IN (0, 2)
                    ORDER BY creation DESC
                    LIMIT 100
                """
                
                documents = frappe.db.sql(query, as_dict=True)
                
                for doc in documents:
                    migration_status = analyze_document_migration_status(doctype, doc)
                    error_details = get_document_error_details(doctype, doc)
                    
                    doc.update({
                        'migration_status': migration_status,
                        'error_details': error_details
                    })
                    all_documents.append(doc)
                    
            except Exception as e:
                frappe.logger().error(f"Error processing {doctype}: {str(e)}")
                continue
        
        # Apply filters to aggregated data
        filtered_documents = apply_filters_to_documents(all_documents, filters)
        
        # Calculate summary
        summary = calculate_summary(filtered_documents)
        
        return {
            "summary": summary,
            "documents": filtered_documents[:500]  # Limit for performance
        }
        
    except Exception as e:
        frappe.log_error(message=frappe.get_traceback(), title="Get aggregated documents data failed")
        return {"summary": {}, "documents": []}

def analyze_document_migration_status(doctype, doc):
    """Analyze if a document was successfully migrated"""
    try:
        # Check if document has remote_docname field (indicates it was migrated)
        if frappe.db.has_column(f"tab{doctype}", "remote_docname"):
            remote_docname = frappe.db.get_value(doctype, doc['name'], 'remote_docname')
            if (remote_docname):
                return "Success"
        
        # Check creation date - if very recent, likely migrated
        from datetime import datetime, timedelta
        creation_date = doc.get('creation')
        if (creation_date):
            if isinstance(creation_date, str):
                creation_date = frappe.utils.get_datetime(creation_date)
            
            # If created in last 24 hours, likely migrated
            if creation_date > datetime.now() - timedelta(days=1):
                return "Success"
        
        # Check for signs of failed migration
        if doc.get('docstatus') == 0 and doc.get('status') in ['', None]:
            return "Failed"
        
        return "Success"
        
    except Exception as e:
        return "Unknown"

def get_document_error_details(doctype, doc):
    """Get error details for a document using validation only - NO SUBMISSION TESTING"""
    try:
        errors = []
        
        # For draft documents, ONLY do validation - NEVER attempt submission
        if doc.get('docstatus') == 0:
            try:
                test_doc = frappe.get_doc(doctype, doc['name'])
                test_doc.flags.ignore_permissions = True
                
                # ONLY do validation - DO NOT submit under any circumstances
                test_doc.validate()
                
                # If validation passes, return None (no errors detected)
                return None
                
            except Exception as validation_error:
                error_msg = str(validation_error)
                
                # Extract and categorize meaningful error messages
                if "Could not find" in error_msg:
                    errors.append(f"Missing mapping: {error_msg}")
                elif "mandatory" in error_msg.lower():
                    errors.append(f"Mandatory field: {error_msg}")
                elif "Tax Category" in error_msg:
                    errors.append(f"Tax configuration: {error_msg}")
                elif "Address" in error_msg and "not found" in error_msg:
                    errors.append(f"Address mapping: {error_msg}")
                elif "Warehouse" in error_msg:
                    errors.append(f"Warehouse mapping: {error_msg}")
                elif "Contact" in error_msg:
                    errors.append(f"Contact mapping: {error_msg}")
                elif "UOM" in error_msg:
                    errors.append(f"UOM issue: {error_msg}")
                elif "Supplier" in error_msg:
                    errors.append(f"Supplier mapping: {error_msg}")
                elif "Purchase Taxes and Charges Template" in error_msg:
                    errors.append(f"Tax template mapping: {error_msg}")
                elif "Item Tax Template" in error_msg:
                    errors.append(f"Item tax template: {error_msg}")
                else:
                    errors.append(f"Validation error: {error_msg}")
        
        # Additional checks for Purchase Orders (without loading the document)
        if doctype == "Purchase Order":
            # Check if document has items
            items_count = frappe.db.count("Purchase Order Item", {"parent": doc['name']})
            if items_count == 0:
                errors.append("No items found in Purchase Order")
            
            # Check for essential fields using database queries (avoid loading full document)
            po_data = frappe.db.get_value("Purchase Order", doc['name'], 
                ['supplier', 'status', 'company'], as_dict=True)
            
            if po_data:
                if not po_data.get('supplier'):
                    errors.append("Missing supplier")
                if not po_data.get('status'):
                    errors.append("Missing status field")
                if not po_data.get('company'):
                    errors.append("Missing company")
        
        return "; ".join(errors) if errors else None
        
    except Exception as e:
        frappe.logger().error(f"Error checking document {doc['name']}: {str(e)}")
        return f"Error checking document: {str(e)}"

def apply_filters_to_documents(documents, filters):
    """Apply filters to document list"""
    filtered = documents
    
    # Status filter
    if filters.get('status'):
        if filters['status'] == 'draft':
            filtered = [d for d in filtered if d.get('docstatus') == 0]
        elif filters['status'] == 'submitted':
            filtered = [d for d in filtered if d.get('docstatus') == 1]
        elif filters['status'] == 'failed':
            filtered = [d for d in filtered if d.get('error_details')]
        elif filters['status'] == 'success':
            filtered = [d for d in filtered if not d.get('error_details')]
    
    # Migration status filter
    if filters.get('migration_status'):
        if filters['migration_status'] == 'migrated':
            filtered = [d for d in filtered if d.get('migration_status') == 'Success']
        elif filters['migration_status'] == 'failed_migration':
            filtered = [d for d in filtered if d.get('migration_status') == 'Failed']
    
    return filtered

def calculate_summary(documents):
    """Calculate summary statistics for documents"""
    summary = {
        'total': len(documents),
        'success': 0,
        'failed': 0,
        'draft': 0,
        'submitted': 0,
        'mapping_errors': 0
    }
    
    for doc in documents:
        # Count by docstatus
        if doc.get('docstatus') == 0:
            summary['draft'] += 1
        elif doc.get('docstatus') == 1:
            summary['submitted'] += 1
        
        # Count by error status
        if doc.get('error_details'):
            summary['failed'] += 1
            if 'Could not find' in doc.get('error_details', ''):
                summary['mapping_errors'] += 1
        else:
            summary['success'] += 1
    
    return summary

@frappe.whitelist()
def bulk_submit_documents(documents):
    """Submit multiple documents in bulk"""
    try:
        documents = json.loads(documents) if isinstance(documents, str) else documents
        
        success_count = 0
        failed_count = 0
        errors = []
        
        for doc_info in documents:
            try:
                doctype = doc_info['doctype']
                docname = doc_info['name']
                
                # Get and submit the document
                doc = frappe.get_doc(doctype, docname)
                if doc.docstatus == 0:  # Only submit draft documents
                    doc.flags.ignore_permissions = True
                    doc.submit()
                    success_count += 1
                
            except Exception as e:
                failed_count += 1
                errors.append(f"{doc_info.get('name', 'Unknown')}: {str(e)}")
                continue
        
        frappe.db.commit()
        
        return {
            "success_count": success_count,
            "failed_count": failed_count,
            "errors": errors
        }
        
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(message=frappe.get_traceback(), title="Bulk submit documents failed")
        return {"success_count": 0, "failed_count": 0, "errors": [str(e)]}

@frappe.whitelist()
def bulk_delete_documents(documents):
    """Delete multiple documents in bulk"""
    try:
        documents = json.loads(documents) if isinstance(documents, str) else documents
        
        success_count = 0
        failed_count = 0
        errors = []
        
        for doc_info in documents:
            try:
                doctype = doc_info['doctype']
                docname = doc_info['name']
                
                # Release any locks and delete
                from event_streaming.event_streaming.page.migration_dashboard.migration_dashboard import release_doc_lock
                release_doc_lock(doctype, docname)
                
                doc = frappe.get_doc(doctype, docname)
                doc.flags.ignore_permissions = True
                doc.delete()
                success_count += 1
                
            except Exception as e:
                failed_count += 1
                errors.append(f"{doc_info.get('name', 'Unknown')}: {str(e)}")
                continue
        
        frappe.db.commit()
        
        return {
            "success_count": success_count,
            "failed_count": failed_count,
            "errors": errors
        }
        
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(message=frappe.get_traceback(), title="Bulk delete documents failed")
        return {"success_count": 0, "failed_count": 0, "errors": [str(e)]}

@frappe.whitelist()
def submit_single_document(doctype, docname):
    """Submit a single document"""
    try:
        doc = frappe.get_doc(doctype, docname)
        if doc.docstatus == 0:
            doc.flags.ignore_permissions = True
            doc.submit()
            frappe.db.commit()
            return {"success": True}
        else:
            return {"success": False, "error": "Document is not in draft status"}
            
    except Exception as e:
        frappe.db.rollback()
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def delete_single_document(doctype, docname):
    """Delete a single document"""
    try:
        # Release any locks first
        from event_streaming.event_streaming.page.migration_dashboard.migration_dashboard import release_doc_lock
        release_doc_lock(doctype, docname)
        
        doc = frappe.get_doc(doctype, docname)
        doc.flags.ignore_permissions = True
        doc.delete()
        frappe.db.commit()
        return {"success": True}
        
    except Exception as e:
        frappe.db.rollback()
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def get_failure_analysis(filters):
    """Get detailed failure analysis for documents with real error testing"""
    try:
        filters = json.loads(filters) if isinstance(filters, str) else filters
        
        # Focus on Purchase Orders first since that's where you're seeing errors
        if not filters.get('doctype'):
            filters['doctype'] = 'Purchase Order'
        
        # Get documents data
        documents_data = get_doctype_specific_data(filters['doctype'], filters)
        documents = documents_data.get('documents', [])
        
        # Test each document for real errors
        failed_docs = []
        total_tested = 0
        
        for doc in documents:
            if doc.get('docstatus') == 0:  # Only test draft documents
                total_tested += 1
                error_details = get_document_error_details(filters['doctype'], doc)
                if error_details:
                    doc['error_details'] = error_details
                    failed_docs.append(doc)
        
        # Analyze error patterns with more detailed categorization
        error_groups = defaultdict(lambda: {'count': 0, 'documents': [], 'description': '', 'sample_errors': []})
        
        for doc in failed_docs:
            error_details = doc.get('error_details', '')
            
            # More specific categorization based on your actual errors
            if 'Tax Category' in error_details:
                category = 'Missing Tax Category Mappings'
                error_groups[category]['description'] = 'Tax categories from producer need mapping in SPP Tax Category Mapping'
                error_groups[category]['sample_errors'].append(error_details[:100])
            elif 'Purchase Taxes and Charges Template' in error_details:
                category = 'Missing Tax Template Mappings'
                error_groups[category]['description'] = 'Tax templates need mapping in SPP Tax Template Mapping'
                error_groups[category]['sample_errors'].append(error_details[:100])
            elif 'Address' in error_details and 'not found' in error_details:
                category = 'Missing Address Mappings'
                error_groups[category]['description'] = 'Addresses need mapping in SPP Address Mapping'
                error_groups[category]['sample_errors'].append(error_details[:100])
            elif 'Supplier Contact' in error_details:
                category = 'Missing Contact Mappings'
                error_groups[category]['description'] = 'Supplier contacts need mapping in SPP Contact Mapping'
                error_groups[category]['sample_errors'].append(error_details[:100])
            elif 'Warehouse' in error_details or 'set_warehouse' in error_details:
                category = 'Missing Warehouse Mappings'
                error_groups[category]['description'] = 'Warehouses need mapping in SPP Warehouse Mapping'
                error_groups[category]['sample_errors'].append(error_details[:100])
            elif 'UOM' in error_details:
                category = 'UOM Issues'
                error_groups[category]['description'] = 'Unit of Measure configuration problems'
                error_groups[category]['sample_errors'].append(error_details[:100])
            elif 'Item Tax Template' in error_details:
                category = 'Missing Item Tax Template Mappings'
                error_groups[category]['description'] = 'Item tax templates need configuration'
                error_groups[category]['sample_errors'].append(error_details[:100])
            elif 'mandatory' in error_details.lower():
                category = 'Mandatory Field Issues'
                error_groups[category]['description'] = 'Required fields are missing values'
                error_groups[category]['sample_errors'].append(error_details[:100])
            else:
                category = 'Other Validation Errors'
                error_groups[category]['description'] = 'Other business logic validation failures'
                error_groups[category]['sample_errors'].append(error_details[:100])
            
            error_groups[category]['count'] += 1
            error_groups[category]['documents'].append(doc['name'])
        
        # Generate specific mapping recommendations
        mapping_recommendations = []
        for error_type, data in error_groups.items():
            if 'Missing' in error_type and 'Mappings' in error_type:
                mapping_type = error_type.replace('Missing ', '').replace(' Mappings', '')
                mapping_recommendations.append(
                    f"Set up {mapping_type} mappings for {data['count']} affected documents"
                )
        
        # Calculate statistics
        total_docs = len(documents)
        total_errors = len(failed_docs)
        success_rate = round(((total_docs - total_errors) / total_docs * 100) if total_docs > 0 else 0, 1)
        
        most_common_error = max(error_groups.items(), key=lambda x: x[1]['count'])[0] if error_groups else 'None'
        
        # Add debugging information
        frappe.logger().info(f"Failure Analysis Results - Total docs: {total_docs}, Tested: {total_tested}, Failed: {total_errors}")
        
        return {
            "total_errors": total_errors,
            "total_tested": total_tested,
            "error_groups": dict(error_groups),
            "mapping_recommendations": mapping_recommendations,
            "success_rate": success_rate,
            "most_common_error": most_common_error,
            "debug_info": f"Analyzed {total_tested} draft documents, found {total_errors} with errors"
        }
        
    except Exception as e:
        frappe.log_error(message=frappe.get_traceback(), title="Get failure analysis failed")
        return {
            "total_errors": 0, 
            "error_groups": {}, 
            "mapping_recommendations": [], 
            "success_rate": 0,
            "debug_info": f"Analysis failed: {str(e)}"
        }

@frappe.whitelist()
def export_documents_report(filters):
    """Export documents report as Excel file"""
    try:
        filters = json.loads(filters) if isinstance(filters, str) else filters
        
        # Get documents data
        if filters.get('doctype'):
            documents_data = get_doctype_specific_data(filters['doctype'], filters)
        else:
            documents_data = get_aggregated_documents_data(filters)
        
        documents = documents_data.get('documents', [])
        
        # Create Excel file
        from frappe.utils.xlsxutils import make_xlsx
        
        data = [['Document', 'Document Type', 'Status', 'Migration Status', 'Created', 'Error Details']]
        
        for doc in documents:
            status_text = 'Draft' if doc.get('docstatus') == 0 else 'Submitted' if doc.get('docstatus') == 1 else 'Cancelled'
            data.append([
                doc.get('name', ''),
                doc.get('doctype', ''),
                status_text,
                doc.get('migration_status', ''),
                str(doc.get('creation', '')),
                doc.get('error_details', '')
            ])
        
        xlsx_file = make_xlsx(data, "Documents Report")
        
        # Save file
        from frappe.utils.file_manager import save_file
        file_doc = save_file("documents_report.xlsx", xlsx_file.getvalue(), "Document Manager", is_private=1)
        
        return {"file_url": file_doc.file_url}
        
    except Exception as e:
        frappe.log_error(message=frappe.get_traceback(), title="Export documents report failed")
        return {"error": str(e)}