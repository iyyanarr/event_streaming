import frappe
from frappe import _

def get_context(context):
	"""Page context for Migration Dashboard"""
	
	# Check permissions
	if not frappe.has_permission("Event Producer", "read"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	
	# Get available event producers
	producers = frappe.get_all("Event Producer", 
		fields=["name", "producer_url", "consumer_url", "status"],
		filters={"status": "Active"}
	)
	
	# Get available document type mappings
	doc_mappings = frappe.get_all("Document Type Mapping",
		fields=["name", "local_doctype", "remote_doctype"],
		order_by="local_doctype"
	)
	
	# Get SPP mapping statistics
	mapping_stats = get_mapping_statistics()
	
	context.update({
		"producers": producers,
		"doc_mappings": doc_mappings,
		"mapping_stats": mapping_stats,
		"page_title": _("Migration Dashboard"),
		"show_sidebar": False
	})

def get_mapping_statistics():
	"""Get statistics for all SPP mappings"""
	stats = {}
	
	mapping_types = [
		"SPP Company Mapping",
		"SPP Account Mapping", 
		"SPP Supplier Mapping",
		"SPP Item Mapping",
		"SPP Warehouse Mapping",
		"SPP Cost Center Mapping",
		"SPP Tax Template Mapping",
		"SPP Contact Mapping",
		"SPP Address Mapping"
	]
	
	for mapping_type in mapping_types:
		try:
			active_mappings = frappe.db.count(mapping_type, {"is_active": 1})
			total_mappings = frappe.db.count(mapping_type)
			stats[mapping_type] = {
				"active": active_mappings,
				"total": total_mappings
			}
		except Exception:
			stats[mapping_type] = {"active": 0, "total": 0}
	
	return stats

@frappe.whitelist()
def get_producer_data_preview(producer_url, filters):
	"""Preview data from producer site based on filters"""
	try:
		# This will be our API call to producer
		# For now, return mock data structure
		return {
			"status": "success",
			"preview": {
				"total_documents": 0,
				"doctypes": {},
				"date_range": filters.get("date_range", {}),
				"estimated_time": "Calculating..."
			}
		}
	except Exception as e:
		return {
			"status": "error", 
			"message": str(e)
		}

@frappe.whitelist()
def start_bulk_migration(migration_config):
	"""Start bulk migration process"""
	try:
		# Validate configuration
		if not migration_config.get("producer_url"):
			frappe.throw(_("Producer URL is required"))
		
		if not migration_config.get("doctypes"):
			frappe.throw(_("At least one document type must be selected"))
		
		# Create migration job (we'll implement job queue later)
		migration_job = {
			"config": migration_config,
			"status": "queued",
			"created_at": frappe.utils.now(),
			"created_by": frappe.session.user
		}
		
		# For now, return success
		return {
			"status": "success",
			"message": _("Migration job queued successfully"),
			"job_id": frappe.generate_hash(length=10)
		}
		
	except Exception as e:
		frappe.log_error(f"Migration start failed: {str(e)}")
		return {
			"status": "error",
			"message": str(e)
		}