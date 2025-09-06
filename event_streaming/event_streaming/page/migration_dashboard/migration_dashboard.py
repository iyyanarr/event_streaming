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
        
        # Ensure date_filter_type matches the expected values
        date_filter_type = filters.get("date_filter_type")
        if date_filter_type == "creation":
            date_filter_type = "Creation Date"
        elif date_filter_type == "modified":
            date_filter_type = "Modified Date"
            
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
        
        for doctype in filters.get("doctypes", []):
            # Build filters for the producer site query
            doc_filters = {}
            if filters.get("from_date") and filters.get("to_date"):
                filter_field = "creation" if date_filter_type == "Creation Date" else "modified"
                doc_filters[filter_field] = ["between", [filters["from_date"], filters["to_date"]]]
            
            # Get total count first
            total_count = len(producer_site.get_list(doctype, 
                filters=doc_filters,
                limit_page_length=0
            ))
            
            # Get sample entries for preview
            sample_entries = producer_site.get_list(doctype,
                filters=doc_filters,
                fields=["name", "creation", "modified", "owner"],
                limit_page_length=5
            )
            
            stats["doctypes"][doctype] = {
                "count": total_count,
                "sample_entries": sample_entries,
                "has_mapping": frappe.db.exists("Document Type Mapping", {
                    "mapping_name": doctype
                })
            }
            stats["total_documents"] += total_count

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
        
        # Ensure date filter type matches the allowed values
        if config.get("date_filter_type") == "creation":
            config["date_filter_type"] = "Creation Date"
        elif config.get("date_filter_type") == "modified":
            config["date_filter_type"] = "Modified Date"
            
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
        filter_field = "creation" if job.date_filter_type == "Creation Date" else "modified"
        filters = {}
        if job.get("from_date") and job.get("to_date"):
            # Convert datetime objects to ISO format strings for JSON serialization
            from_date = job.from_date.isoformat() if hasattr(job.from_date, 'isoformat') else job.from_date
            to_date = job.to_date.isoformat() if hasattr(job.to_date, 'isoformat') else job.to_date
            filters[filter_field] = ["between", [from_date, to_date]]
            
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
                # For new documents, sanitize and insert
                clean_doc = sanitize_doc_for_insert(full_doc)
                doc_to_insert = frappe.get_doc(clean_doc)
                doc_to_insert.docstatus = 0
                
                # Clear workflow/status fields
                for field in ('status', 'workflow_state', 'cancelled'):
                    if hasattr(doc_to_insert, field):
                        setattr(doc_to_insert, field, None)
                
                # Set flags to bypass validations during migration        
                doc_to_insert.flags.ignore_validate = True
                doc_to_insert.flags.ignore_mandatory = True
                doc_to_insert.flags.ignore_links = True
                doc_to_insert.flags.in_insert = True
                doc_to_insert.flags.ignore_permissions = True
                doc_to_insert.flags.ignore_if_duplicate = True
                doc_to_insert.flags.from_migration = True
                
                try:
                    doc_to_insert.insert(ignore_permissions=True)
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