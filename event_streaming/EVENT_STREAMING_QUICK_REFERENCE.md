# Event Streaming - Quick Reference Guide

## Quick Setup Checklist

### ✅ Initial Setup
- [ ] Install event_streaming app on both sites
- [ ] Create Event Producer document
- [ ] Configure Document Type Mapping for Purchase Order
- [ ] Set up child table mappings (items, taxes)

### ✅ SPP Mappings Setup
- [ ] Create SPP Company Mapping (SPP INDIA → Shree Polymer Products)
- [ ] Create SPP Account Mapping (tax accounts, expense accounts)
- [ ] Create SPP Cost Center Mapping (Main - SPP INDIA → Main - SPP)
- [ ] Create SPP Contact Mapping
- [ ] Create SPP Address Mapping

### ✅ Common Account Mappings
```
Input Tax CGST - SPP INDIA → 3090100.001 - Input Tax CGST - SPP
Input Tax SGST - SPP INDIA → 3090100.002 - Input Tax SGST - SPP
Cost of Goods Sold - SPP INDIA → 6010100.001 - Cost of Goods Sold - SPP
Stock Assets - SPP INDIA → Stock Assets - SPP
Creditors - SPP INDIA → Creditors - SPP
```

## Quick Troubleshooting

### 🔍 Check Sync Status
```bash
# Check event producer status
frappe.get_doc("Event Producer", "producer-url").last_update

# Check for errors
frappe.get_all("Error Log", {"method": "event_streaming"}, limit=10)
```

### 🔧 Common Fixes

**LinkValidationError:**
1. Check mapping exists in SPP mapping documents
2. Verify target record exists in consumer
3. Add missing mapping entry

**ValidationError - Tax Accounts:**
1. Ensure SGST mapping exists in SPP Account Mapping
2. Check account belongs to correct company
3. Verify tax template mapping

**Document Type Mapping None not found:**
1. Check if child table mapping is configured
2. Add null check in mapping logic (already fixed)

### 📊 Monitor Health
```python
# Check all active mappings
for mapping_type in ["SPP Company Mapping", "SPP Account Mapping"]:
    docs = frappe.get_all(mapping_type, {"is_active": 1})
    print(f"{mapping_type}: {len(docs)} active")
```

## Emergency Contacts
- Development Team: [contact-info]
- System Administrator: [contact-info]
- Documentation: EVENT_STREAMING_DOCUMENTATION.md

---
**Last Updated:** September 5, 2025