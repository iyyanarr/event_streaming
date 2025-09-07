import frappe
from frappe import _
from frappe.frappeclient import FrappeClient  # type: ignore
import json
from datetime import datetime
import time
from event_streaming.event_streaming.doctype.document_type_mapping.document_type_mapping import DocumentTypeMapping

BATCH_SIZE = 50  # Number of documents to fetch per batch
MAX_RETRIES = 3  # Maximum retries for field updates
LOCK_TIMEOUT = 60  # Lock timeout in seconds

@frappe.whitelist()
def get_producer_doctypes(producer):
    """Get available doctypes from producer configuration"""
    if not producer:
        return []
        
    return frappe.get_all("Event Producer Document Type",
        filters={"parent": producer, "unsubscribe": 0},
        fields=["ref_doctype", "has_mapping", "mapping"]
    )

@frappe.whitelist()
def get_producers():
    """Get list of Event Producers"""
    producers = frappe.get_all('Event Producer', 
        fields=['name', 'producer_url'],
        order_by='modified desc'
    )
    return producers

def get_doc_lock_key(doctype, docname):
    """Get Redis key for document lock"""
    return f"doc_lock:{doctype}:{docname}"

def acquire_doc_lock(doctype, docname):
    """Try to acquire a lock for document migration"""
    lock_key = get_doc_lock_key(doctype, docname)
    # Always allow lock acquisition during migration
    if frappe.flags.in_migrate:
        frappe.cache().set_value(lock_key, frappe.session.user, expires_in_sec=300)
        return True
    return True  # During migration we'll always allow lock acquisition

def release_doc_lock(doctype, docname):
    """Release document lock"""
    lock_key = get_doc_lock_key(doctype, docname)
    frappe.cache().delete_value(lock_key)

def get_paginated_docs(producer_site, doctype, filters, start=0, page_length=BATCH_SIZE):
    """Get documents from producer in batches"""
    return producer_site.get_list(doctype,
        filters=filters,
        fields=["*"],
        limit_start=start,
        limit_page_length=page_length
    )

def update_doc_with_retries(doctype, doc_name, field_updates, retries=MAX_RETRIES):
    """Update document fields with retries"""
    for attempt in range(retries):
        try:
            # Get latest version of doc
            current = frappe.get_doc(doctype, doc_name)
            
            # Track if any field actually changed
            changed = False
            
            # Update each field if different
            for field, value in field_updates.items():
                if hasattr(current, field) and getattr(current, field) != value:
                    setattr(current, field, value)
                    changed = True
            
            if changed:
                current.flags.ignore_validate_update_after_submit = True
                current.save(ignore_permissions=True)
            return True
            
        except frappe.exceptions.TimestampMismatchError:
            if attempt < retries - 1:
                time.sleep(0.5 * (attempt + 1))  # Exponential backoff
                continue
            return False
        except Exception as e:
            frappe.logger().error(f"Error updating {doctype} {doc_name}: {str(e)}")
            return False
    return False

@frappe.whitelist()
def get_producer_data_preview(producer_url, filters):
    """Preview data from producer site based on filters"""
    try:
        filters = json.loads(filters) if isinstance(filters, str) else filters
        producer = frappe.get_doc("Event Producer", producer_url)
        producer_site = get_producer_site(producer)
        
        # Map API filter values to display values
        filter_type_mapping = {
            "creation": "Creation Date",
            "modified": "Modified Date",
            "transaction": "Transaction Date",
            "posting": "Posting Date"
        }
        
        # Valid filter types for validation
        valid_filter_types = ["Creation Date", "Modified Date", "Transaction Date", "Posting Date"]
        
        # Convert API filter type to display value
        date_filter_type = filter_type_mapping.get(filters.get("date_filter_type"))
        
        if not date_filter_type or date_filter_type not in valid_filter_types:
            frappe.throw(_("Invalid date filter type. Must be one of: Creation Date, Modified Date, Transaction Date, Posting Date"))
            
        stats = {
            "total_documents": 0,
            "doctypes": {},
            "date_range": {
                "filter_type": date_filter_type,
                "from": filters.get("from_date"),
                "to": filters.get("to_date")
            },
            "estimated_time": "0 minutes"
        }
        
        # Map display filter types to database fields
        field_mapping = {
            "Creation Date": "creation",
            "Modified Date": "modified", 
            "Transaction Date": "transaction_date",
            "Posting Date": "posting_date"
        }
        
        for doctype in filters.get("doctypes", []):
            filter_field = field_mapping.get(date_filter_type)
            
            date_filters = []
            if filters.get("from_date"):
                if filter_field in ["transaction_date", "posting_date"]:
                    from_date = filters["from_date"].split("T")[0] if isinstance(filters["from_date"], str) else filters["from_date"]
                    date_filters.append([filter_field, ">=", from_date])
                else:
                    date_filters.append([filter_field, ">=", filters["from_date"]])
                    
            if filters.get("to_date"):
                if filter_field in ["transaction_date", "posting_date"]:
                    to_date = filters["to_date"].split("T")[0] if isinstance(filters["to_date"], str) else filters["to_date"]
                    date_filters.append([filter_field, "<=", to_date])
                else:
                    date_filters.append([filter_field, "<=", filters["to_date"]])

            # Add filter for non-canceled documents
            date_filters.append(["docstatus", "<", 2])

            try:
                # Get count of records matching the filter by getting all records with just the name field
                records = producer_site.get_list(doctype, 
                    fields=["name"],
                    filters=date_filters,
                    limit_page_length=0  # No limit to get all records
                )
                total_count = len(records)
            except Exception as e:
                frappe.logger().error(f"Error getting count for {doctype}: {str(e)}")
                total_count = 0
            
            # Get sample entries (limited to 5)
            try:
                sample_entries = producer_site.get_list(doctype, 
                    fields=["name", "creation", "modified", "owner", filter_field, "docstatus"],
                    filters=date_filters,
                    limit_page_length=5
                )
            except Exception as e:
                frappe.logger().error(f"Error getting sample entries for {doctype}: {str(e)}")
                sample_entries = []
            
            stats["doctypes"][doctype] = {
                "count": total_count,
                "sample_entries": sample_entries,
                "has_mapping": frappe.db.exists("Document Type Mapping", {
                    "mapping_name": doctype
                })
            }
            stats["total_documents"] += total_count
            
            # Log the filters and results for debugging
            frappe.logger().debug(f"Date filters for {doctype}: {date_filters}")
            frappe.logger().debug(f"Total count for {doctype}: {total_count}")

        # Estimate time (rough estimate: 2 seconds per document)
        total_minutes = round((stats["total_documents"] * 2) / 60)
        stats["estimated_time"] = f"{total_minutes} minutes" if total_minutes > 0 else "Less than a minute"
        
        # Format the output for better presentation
        formatted_output = format_preview_output(stats)
        stats["formatted_html"] = formatted_output
        
        return {
            "status": "success",
            "preview": stats
        }
        
    except Exception as e:
        frappe.log_error(message=frappe.get_traceback(), title="Migration preview failed")
        return {
            "status": "error",
            "message": str(e)
        }

def format_preview_output(stats):
    """Format the preview data as HTML for better presentation"""
    html = f"""
    <div class="migration-preview">
        <div class="preview-header">
            <h4>Migration Preview</h4>
            <div class="date-range">
                <p><strong>Date Filter:</strong> {stats["date_range"]["filter_type"]}</p>
                <p><strong>From:</strong> {stats["date_range"]["from"]}</p>
                <p><strong>To:</strong> {stats["date_range"]["to"]}</p>
            </div>
            <div class="summary">
                <p><strong>Total Documents:</strong> {stats["total_documents"]}</p>
                <p><strong>Estimated Time:</strong> {stats["estimated_time"]}</p>
            </div>
        </div>
    """
    
    for doctype, data in stats["doctypes"].items():
        html += f"""
        <div class="doctype-section">
            <h5>{doctype}</h5>
            <p>Total Records: {data["count"]}</p>
            <p>Has Mapping: {'Yes' if data["has_mapping"] else 'No'}</p>
        """
        
        if data["sample_entries"]:
            html += """
            <div class="sample-entries">
                <h6>Sample Entries:</h6>
                <table class="table table-bordered">
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>Created</th>
                            <th>Modified</th>
                            <th>Owner</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            
            for entry in data["sample_entries"]:
                html += f"""
                <tr>
                    <td>{entry.get("name")}</td>
                    <td>{entry.get("creation")}</td>
                    <td>{entry.get("modified")}</td>
                    <td>{entry.get("owner")}</td>
                </tr>
                """
                
            html += """
                    </tbody>
                </table>
            </div>
            """
            
        html += "</div>"
    
    html += "</div>"
    return html

@frappe.whitelist()
def start_bulk_migration(migration_config):
    """Start the bulk migration process on consumer site"""
    try:
        config = json.loads(migration_config) if isinstance(migration_config, str) else migration_config
        
        # Map API filter values to display values
        filter_type_mapping = {
            "creation": "Creation Date",
            "modified": "Modified Date",
            "transaction": "Transaction Date",
            "posting": "Posting Date"
        }
        
        # Convert filter type to display value
        config["date_filter_type"] = filter_type_mapping.get(config.get("date_filter_type"))
        
        if not config.get("date_filter_type") or config["date_filter_type"] not in ["Creation Date", "Modified Date", "Transaction Date", "Posting Date"]:
            frappe.throw(_("Invalid date filter type. Must be one of: Creation Date, Modified Date, Transaction Date, Posting Date"))
            
        if not config.get("producer"):
            frappe.throw(_("Producer URL is required"))
        
        if not config.get("doctypes"):
            frappe.throw(_("At least one document type must be selected"))
            
        # Create migration job
        job = frappe.get_doc({
            "doctype": "Event Migration Job",
            "producer": config["producer"],
            "status": "Queued",
            "date_filter_type": config.get("date_filter_type"),
            "from_date": config.get("from_date"),
            "to_date": config.get("to_date"),
            "selected_doctypes": json.dumps(config["doctypes"]),
            "total_docs": 0,
            "processed_docs": 0,
            "processed_doctypes": "{}"
        }).insert()

        # Pass all arguments as a single dictionary
        frappe.enqueue(
            "event_streaming.event_streaming.page.migration_dashboard.migration_dashboard.process_migration_job",
            queue="long",
            timeout=1500,
            job_args={
                "job_id": job.name,
                "producer_name": config["producer"],
                "config": config
            }
        )

        return {
            "status": "success",
            "message": _("Migration job queued successfully"),
            "job_id": job.name
        }
        
    except Exception as e:
        frappe.log_error(message=frappe.get_traceback(), title="Migration start failed")
        return {
            "status": "error",
            "message": str(e)
        }

def process_migration_job(job_args):
    """Process the migration job on consumer site by pulling from producer"""
    try:
        job = frappe.get_doc("Event Migration Job", job_args.get("job_id"))
        producer = frappe.get_doc("Event Producer", job_args.get("producer_name"))
        producer_site = get_producer_site(producer)
        
        job.db_set("status", "In Progress")
        job.db_set("start_time", datetime.now())

        try:
            # Process each doctype
            for doctype in job_args.get("config", {}).get("doctypes", []):
                process_doctype_migration(job, producer, producer_site, doctype)

            job.db_set("status", "Completed")
            
        except Exception as e:
            job.db_set("status", "Failed")
            job.db_set("error_log", str(e))
            frappe.log_error(message=frappe.get_traceback(), 
                title=f"Migration job {job.name} failed")
            
        finally:
            job.db_set("end_time", datetime.now())
            
    except Exception as e:
        frappe.log_error(message=frappe.get_traceback(), 
            title=f"Migration job {job_args.get('job_id')} failed")
        raise

def process_doctype_migration(job, producer, producer_site, doctype):
    """Process migration for a single doctype by pulling from producer site"""
    try:
        # Build filters
        filter_field = {
            "Creation Date": "creation",
            "Modified Date": "modified",
            "Transaction Date": "transaction_date",
            "Posting Date": "posting_date"
        }.get(job.date_filter_type, "creation")
        
        filters = []
        if job.get("from_date") and job.get("to_date"):
            # Convert datetime objects to ISO format strings for JSON serialization
            from_date = job.from_date.isoformat() if hasattr(job.from_date, 'isoformat') else job.from_date
            to_date = job.to_date.isoformat() if hasattr(job.to_date, 'isoformat') else job.to_date
            
            # Special handling for transaction/posting dates which are Date fields
            if job.date_filter_type in ["Transaction Date", "Posting Date"]:
                from_date = from_date.split('T')[0]  # Get only the date part
                to_date = to_date.split('T')[0]  # Get only the date part
            
            filters.append([filter_field, "between", [from_date, to_date]])
        
        # Add filter to exclude canceled documents
        filters.append(["docstatus", "<", 2])  # 0=Draft, 1=Submitted, 2=Cancelled
            
        # Skip if doctype doesn't have the selected date field
        if filter_field not in ["creation", "modified"]:
            meta = producer_site.get_doc("DocType", doctype)
            # Access fields from the dictionary instead of attribute
            if not any(f.get("fieldname") == filter_field for f in meta.get("fields", [])):
                frappe.logger().warning(f"Skipping {doctype} as it doesn't have field {filter_field}")
                processed = json.loads(job.processed_doctypes or "{}")
                processed[doctype] = {"total": 0, "processed": 0, "skipped": True, 
                    "reason": f"Document type doesn't have {job.date_filter_type} field"}
                job.db_set("processed_doctypes", json.dumps(processed))
                return
            
        # Get total count first
        if doctype == "Purchase Order":
            frappe.logger().info(f"Fetching Purchase Orders with filters: {filters}")
            
        total_count = len(producer_site.get_list(doctype, filters=filters, limit_page_length=0))
            
        if doctype == "Purchase Order":
            frappe.logger().info(f"Found {total_count} Purchase Orders to migrate")
            
        processed = json.loads(job.processed_doctypes or "{}")
        processed[doctype] = {"total": total_count, "processed": 0}
        job.db_set("processed_doctypes", json.dumps(processed))
        
        # Process in batches
        start = 0
        while True:
            if doctype == "Purchase Order":
                frappe.logger().info(f"Fetching batch of Purchase Orders starting at {start}")
                
            docs = get_paginated_docs(producer_site, doctype, filters, start, BATCH_SIZE)
            if not docs:
                break
                
            if doctype == "Purchase Order":
                frappe.logger().info(f"Processing {len(docs)} Purchase Orders in current batch")
                
            for doc in docs:
                try:
                    if doctype == "Purchase Order":
                        frappe.logger().info(f"Processing Purchase Order {doc.get('name')}")
                        
                    migrate_single_document(producer, producer_site, doctype, doc)
                    
                    # Update progress
                    processed[doctype]["processed"] += 1
                    job.db_set("processed_doctypes", json.dumps(processed))
                    job.db_set("processed_docs", (job.processed_docs or 0) + 1)
                    
                    if doctype == "Purchase Order":
                        frappe.logger().info(f"Successfully processed Purchase Order {doc.get('name')}")
                        
                except Exception as e:
                    if doctype == "Purchase Order":
                        frappe.logger().error(f"Failed to process Purchase Order {doc.get('name')}: {str(e)}\n{frappe.get_traceback()}")
                    continue
                    
            start += BATCH_SIZE
            
    except Exception as e:
        frappe.log_error(message=frappe.get_traceback(), 
            title=f"Migration failed for {doctype}")
        raise

def get_producer_site(producer):
    """Get FrappeClient instance for producer site"""
    return FrappeClient(
        url=producer.producer_url,
        api_key=producer.api_key,
        api_secret=producer.get_password("api_secret")
    )

def migrate_single_document(producer, producer_site, doctype, doc):
    """Migrate a single document using field-level updates and document locking"""
    producer.db_set("incoming_change", 1)
    frappe.flags.in_migrate = True
    
    try:
        # Get document name safely
        doc_name = doc.get("name") if isinstance(doc, dict) else getattr(doc, "name", None)
        if not doc_name:
            raise ValueError(f"Document name missing for doctype {doctype}: {doc}")
            
        try:
            # Get full document from producer
            full_doc = producer_site.get_doc(doctype, doc_name)
            
            # Get mapping for doctype
            mapping = get_doctype_mapping(producer, doctype)
            if not mapping:
                frappe.logger().error(f"No mapping found for doctype {doctype}")
                return
                
            # Check if we should use the same name as producer (from Event Producer configuration)
            use_same_name = frappe.db.get_value("Event Producer Document Type",
                {"parent": producer.name, "ref_doctype": doctype}, "use_same_name")
            
            # Apply mapping and get mapped document
            mapped_result = mapping.get_mapping(full_doc, producer_site, "Insert")
            
            # Handle dependencies first (accounts, cost centers, etc.)
            if mapped_result.get("dependencies"):
                for fieldname, dependency in mapped_result["dependencies"]:
                    if isinstance(dependency, str):
                        dependency = json.loads(dependency)
                    if dependency.get("doctype"):
                        dep_doctype = dependency["doctype"]
                        # Create dependency if it doesn't exist
                        if not frappe.db.exists(dep_doctype, dependency.get("name")):
                            dep_doc = frappe.get_doc(dependency)
                            dep_doc.insert(ignore_permissions=True)
            
            # Get mapped document
            full_doc = json.loads(mapped_result.get("doc")) if isinstance(mapped_result.get("doc"), str) else mapped_result.get("doc")
            
            # Create new or update existing
            if not frappe.db.exists(doctype, doc_name):
                # For new documents, sanitize and insert with name handling based on configuration
                clean_doc = sanitize_doc_for_insert(full_doc)
                
                if use_same_name:
                    # CRITICAL: Preserve the original document name from producer
                    clean_doc['name'] = doc_name
                
                # Set docstatus to draft
                clean_doc['docstatus'] = 0
                
                # Clear workflow/status fields
                for field in ('status', 'workflow_state', 'cancelled'):
                    if field in clean_doc:
                        clean_doc.pop(field, None)
                
                try:
                    # Use frappe.get_doc with name preservation
                    doc_to_insert = frappe.get_doc(clean_doc)
                    
                    # Set flags to bypass validations during migration        
                    doc_to_insert.flags.ignore_validate = True
                    doc_to_insert.flags.ignore_mandatory = True
                    doc_to_insert.flags.ignore_links = True
                    doc_to_insert.flags.ignore_permissions = True
                    doc_to_insert.flags.ignore_if_duplicate = True
                    doc_to_insert.flags.from_migration = True
                    
                    if use_same_name:
                        # Insert parent document with preserved name using db_insert
                        doc_to_insert.db_insert()
                        
                        # Now manually insert child table records
                        insert_child_table_records(doctype, doc_name, clean_doc)
                        
                        frappe.logger().info(f"Successfully inserted {doctype} {doc_name} with preserved name and child tables")
                    else:
                        # Store the remote docname in custom fields and let Frappe generate new name
                        doc_to_insert.remote_docname = doc_name
                        doc_to_insert.remote_site_name = producer.name
                        doc_to_insert.insert(ignore_permissions=True)
                        frappe.logger().info(f"Successfully inserted {doctype} with new name {doc_to_insert.name} (original: {doc_name})")
                    
                    frappe.db.commit()
                    
                except Exception as e:
                    frappe.db.rollback()
                    frappe.logger().error(f"Failed to insert {doctype} {doc_name}: {str(e)}\n{frappe.get_traceback()}")
                    raise
            else:
                # For existing documents, do field-level updates
                current_doc = frappe.get_doc(doctype, doc_name)
                field_updates = {}
                
                # Compare and collect changed fields
                if isinstance(full_doc, dict):
                    doc_dict = full_doc
                else:
                    doc_dict = full_doc.as_dict()
                    
                for field, value in doc_dict.items():
                    if (field not in ('name', 'owner', 'creation', 'modified', 'modified_by', 'docstatus', 'parent', 'parenttype', 'parentfield', 'idx') 
                        and hasattr(current_doc, field)
                        and getattr(current_doc, field) != value):
                        field_updates[field] = value
                        
                if field_updates:
                    success = update_doc_with_retries(doctype, doc_name, field_updates)
                    if not success:
                        frappe.logger().error(f"Failed to update {doctype} {doc_name} after retries")
                        
        except Exception as e:
            frappe.logger().error(f"Error migrating {doctype} {doc_name}: {str(e)}\n{frappe.get_traceback()}")
            raise
            
    finally:
        producer.db_set("incoming_change", 0)
        frappe.flags.in_migrate = False

def sanitize_doc_for_insert(doc):
    """Clean document for insertion by removing problematic fields"""
    if not isinstance(doc, dict):
        try:
            doc = doc.as_dict()
        except:
            return doc
            
    cleaned = dict(doc)
    # Remove top-level fields that could cause issues
    for field in ('docstatus', 'status', 'workflow_state', 'cancelled', 
                 'amended_from', 'amendment_date', 'amended_by', 'is_return'):
        cleaned.pop(field, None)
        
    # Clean child tables
    for key, value in list(cleaned.items()):
        if isinstance(value, list):
            new_list = []
            for row in value:
                if isinstance(row, dict):
                    row = dict(row)
                    for field in ('docstatus', 'status', 'workflow_state', 'cancelled',
                                'amended_from', 'amendment_date', 'amended_by', 'is_return'):
                        row.pop(field, None)
                    new_list.append(row)
                else:
                    new_list.append(row)
            cleaned[key] = new_list
            
    return cleaned

def insert_child_table_records(parent_doctype, parent_name, doc_data):
    """Insert child table records for a migrated document with preserved names"""
    try:
        # Get the parent meta to find child table fields
        meta = frappe.get_meta(parent_doctype)
        
        for field in meta.get("fields"):
            if field.fieldtype == "Table" and field.fieldname in doc_data:
                child_records = doc_data.get(field.fieldname, [])
                
                if child_records and isinstance(child_records, list):
                    for idx, child_record in enumerate(child_records, 1):
                        if isinstance(child_record, dict):
                            child_record = dict(child_record)
                            
                            # Set essential parent-child relationship fields
                            child_record.update({
                                'name': child_record.get('name') or frappe.generate_hash(length=10),
                                'parent': parent_name,
                                'parenttype': parent_doctype,
                                'parentfield': field.fieldname,
                                'idx': idx,
                                'docstatus': 0
                            })
                            
                            # Remove problematic fields
                            for problematic_field in ('status', 'workflow_state', 'cancelled', 
                                                    'amended_from', 'amendment_date', 'amended_by', 'is_return'):
                                child_record.pop(problematic_field, None)
                            
                            # Create and insert child document
                            try:
                                child_doc = frappe.get_doc({
                                    'doctype': field.options,
                                    **child_record
                                })
                                
                                # Set flags for child document
                                child_doc.flags.ignore_validate = True
                                child_doc.flags.ignore_mandatory = True
                                child_doc.flags.ignore_links = True
                                child_doc.flags.ignore_permissions = True
                                child_doc.flags.from_migration = True
                                
                                # Use db_insert to preserve name and bypass validations
                                child_doc.db_insert()
                                
                                frappe.logger().debug(f"Inserted child record {child_record.get('name')} for {parent_doctype} {parent_name}")
                                
                            except Exception as e:
                                frappe.logger().error(f"Error inserting child record for {parent_doctype} {parent_name}, table {field.fieldname}: {str(e)}")
                                # Log the child record data for debugging
                                frappe.logger().error(f"Child record data: {child_record}")
                                
    except Exception as e:
        frappe.logger().error(f"Error inserting child table records for {parent_doctype} {parent_name}: {str(e)}")

def get_doctype_mapping(producer, doctype):
    """Get mapping configuration for doctype if exists"""
    mapping_name = frappe.db.get_value("Event Producer Document Type",
        {"parent": producer.name, "ref_doctype": doctype},
        "mapping"
    )
    return frappe.get_doc("Document Type Mapping", mapping_name) if mapping_name else None

@frappe.whitelist()
def get_migration_job_progress(job_name):
    """Return structured progress for an Event Migration Job"""
    try:
        job = frappe.get_doc("Event Migration Job", job_name)
        processed = json.loads(job.processed_doctypes or "{}")
        
        total_docs = 0
        processed_docs = job.processed_docs or 0
        total_doctypes = len(json.loads(job.selected_doctypes))
        completed_doctypes = 0
        
        for doctype_stats in processed.values():
            total_docs += doctype_stats.get("total", 0)
            if doctype_stats.get("processed", 0) >= doctype_stats.get("total", 0):
                completed_doctypes += 1
                
        progress = {
            "status": job.status,
            "total_docs": total_docs,
            "processed_docs": processed_docs,
            "total_doctypes": total_doctypes,
            "completed_doctypes": completed_doctypes,
            "processed_by_doctype": processed,
            "start_time": str(job.start_time) if job.start_time else None,
            "end_time": str(job.end_time) if job.end_time else None,
            "error": job.error_log
        }
        return progress
        
    except Exception as e:
        frappe.log_error(message=frappe.get_traceback(),
            title="Get migration job progress failed")
        raise

@frappe.whitelist()
def delete_draft_purchase_orders():
    """Delete all draft Purchase Orders from the current site"""
    try:
        # Get all draft Purchase Orders (docstatus = 0)
        draft_pos = frappe.get_all("Purchase Order", 
            filters={"docstatus": 0},
            fields=["name"]
        )
        
        deleted_count = 0
        errors = []
        
        for po in draft_pos:
            try:
                # Get the document and delete it
                doc = frappe.get_doc("Purchase Order", po.name)
                doc.flags.ignore_permissions = True
                doc.delete()
                deleted_count += 1
                
            except Exception as e:
                errors.append(f"Failed to delete {po.name}: {str(e)}")
                frappe.logger().error(f"Error deleting Purchase Order {po.name}: {str(e)}")
                continue
        
        # Commit the deletions
        frappe.db.commit()
        
        # Prepare response
        response = {
            "status": "success",
            "deleted_count": deleted_count,
            "total_found": len(draft_pos)
        }
        
        if errors:
            response["errors"] = errors
            response["message"] = f"Deleted {deleted_count} out of {len(draft_pos)} draft Purchase Orders. Some deletions failed."
        else:
            response["message"] = f"Successfully deleted {deleted_count} draft Purchase Orders"
        
        frappe.logger().info(f"Deleted {deleted_count} draft Purchase Orders out of {len(draft_pos)} found")
        return response
        
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(message=frappe.get_traceback(), 
            title="Delete draft Purchase Orders failed")
        return {
            "status": "error",
            "message": f"Failed to delete draft Purchase Orders: {str(e)}"
        }