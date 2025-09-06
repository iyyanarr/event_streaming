# Event Streaming App with SPP Mapping Integration
## User Manual & Complete Documentation

**Version:** 1.0  
**Date:** September 5, 2025  
**Authors:** Development Team  

---

## Table of Contents

1. [Overview](#overview)
2. [User Manual](#user-manual)
3. [Technical Documentation](#technical-documentation)
4. [Configuration Guide](#configuration-guide)
5. [Troubleshooting](#troubleshooting)
6. [API Reference](#api-reference)

---

## Overview

The Event Streaming App with SPP Mapping Integration is a comprehensive solution for real-time data synchronization between multiple Frappe/ERPNext sites. It enables seamless data flow from a producer site (master) to consumer sites (branches) with intelligent value mapping to handle differences in company structures, accounts, and other master data.

### Key Features

- **Real-time Data Sync**: Automatic synchronization of documents between sites
- **Intelligent Value Mapping**: Smart transformation of values during sync
- **Multi-company Support**: Handle different company structures seamlessly
- **Error Recovery**: Robust error handling and recovery mechanisms
- **Comprehensive Logging**: Detailed logs for monitoring and debugging

### Supported Scenarios

- **Multi-branch Operations**: Sync data from headquarters to branches
- **Company Mergers**: Map data between different company structures
- **Master Data Management**: Centralized control with distributed execution

---

## User Manual

### Getting Started

#### Prerequisites

- Frappe Framework v14+
- ERPNext installed on all sites
- Network connectivity between producer and consumer sites
- Administrator access to both sites

#### Installation

1. **Install the Event Streaming App**
   ```bash
   bench get-app event_streaming
   bench --site [site-name] install-app event_streaming
   ```

2. **Run Migrations**
   ```bash
   bench --site [site-name] migrate
   ```

### Setting Up Event Streaming

#### Step 1: Configure Producer Site

1. **Navigate to Event Streaming**
   - Go to `Event Streaming > Event Producer`
   - Create a new Event Producer document

2. **Basic Configuration**
   - **Producer URL**: `https://producer-site.com`
   - **Consumer URL**: `https://consumer-site.com`
   - **Status**: Active
   - **Doctypes to Sync**: Select documents (e.g., Purchase Order, Sales Order)

3. **Authentication Setup**
   - Set API Key and Secret
   - Configure user permissions

#### Step 2: Configure Document Type Mapping

1. **Create Purchase Order Mapping**
   - Go to `Event Streaming > Document Type Mapping`
   - Name: "Purchase Order"
   - Local DocType: "Purchase Order"
   - Remote DocType: "Purchase Order"

2. **Field Mappings Configuration**
   ```
   Field Mappings:
   - supplier → supplier
   - company → company
   - items → items (Child Table: "Purchase Order Items")
   - taxes → taxes (Child Table: "Purchase Order Tax")
   - contact_person → contact_person
   - shipping_address → shipping_address
   - taxes_and_charges → taxes_and_charges
   ```

3. **Child Table Mappings**
   
   **Purchase Order Items:**
   - item_code → item_code
   - warehouse → warehouse
   - expense_account → expense_account
   - cost_center → cost_center
   
   **Purchase Order Tax:**
   - account_head → account_head
   - cost_center → cost_center

### Setting Up SPP Mapping Integration

#### Step 1: Company Mapping

1. **Navigate to SPP Company Mapping**
   - Create new document
   - Mapping Name: "Company Mapping - Consumer"
   - Is Active: ✓

2. **Add Company Mappings**
   ```
   Producer Company → Consumer Company
   SPP INDIA → Shree Polymer Products
   ```

#### Step 2: Account Mapping

1. **Navigate to SPP Account Mapping**
   - Create new document
   - Mapping Name: "Account Mapping - Consumer"
   - Is Active: ✓

2. **Add Account Mappings**
   ```
   Source Account → Target Account
   Input Tax CGST - SPP INDIA → 3090100.001 - Input Tax CGST - SPP
   Input Tax SGST - SPP INDIA → 3090100.002 - Input Tax SGST - SPP
   Cost of Goods Sold - SPP INDIA → 6010100.001 - Cost of Goods Sold - SPP
   ```

#### Step 3: Additional Mappings

**Cost Center Mapping:**
```
Producer Cost Center → Consumer Cost Center
Main - SPP INDIA → Main - SPP
```

**Supplier Mapping:**
```
Producer Supplier → Consumer Supplier
B P Chemicals - Maharashtra → B P Chemicals - Tamil Nadu
```

**Contact & Address Mapping:**
```
Producer Contact → Consumer Contact
Ronak Vaghani-B P CHEMICALS → [Existing Contact in Consumer]

Producer Address → Consumer Address
Shree Polymer Products; Unit - 2 → Shree Polymer Products; Unit - 2
```

### Daily Operations

#### Monitoring Sync Status

1. **Event Producer Dashboard**
   - Check sync status
   - View last sync time
   - Monitor error counts

2. **Event Consumer Logs**
   - Review successful syncs
   - Identify failed documents
   - Track mapping applications

#### Handling Sync Errors

1. **LinkValidationError**
   - Check if mapped values exist in consumer
   - Update mapping configurations
   - Retry sync

2. **ValidationError**
   - Review document validation rules
   - Check company/account mappings
   - Verify target accounts exist

#### Adding New Mappings

1. **When New Values Appear**
   - Check error logs for unmapped values
   - Add entries to relevant SPP mapping documents
   - Test sync with new mappings

2. **Best Practices**
   - Always test mappings in development first
   - Keep mapping documents organized
   - Document mapping decisions

---

## Technical Documentation

### Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐
│  Producer Site  │    │  Consumer Site  │
│                 │    │                 │
│ ┌─────────────┐ │    │ ┌─────────────┐ │
│ │Event Producer│ │    │ │Event Consumer│ │
│ └─────────────┘ │    │ └─────────────┘ │
│        │        │    │        │        │
│        v        │    │        v        │
│ ┌─────────────┐ │    │ ┌─────────────┐ │
│ │  Document   │ │    │ │  Document   │ │
│ │Type Mapping │ │────┼─│Type Mapping │ │
│ └─────────────┘ │    │ └─────────────┘ │
│                 │    │        │        │
│                 │    │        v        │
│                 │    │ ┌─────────────┐ │
│                 │    │ │SPP Mappings │ │
│                 │    │ └─────────────┘ │
└─────────────────┘    └─────────────────┘
```

### Core Components

#### 1. Event Producer (`event_producer.py`)

**Key Methods:**
- `sync()`: Main synchronization method
- `pull_from_node()`: Pull updates from producer
- `get_mapped_update()`: Apply mapping transformations

**Data Flow:**
```python
def sync(self):
    # 1. Pull updates from producer site
    updates = self.pull_from_node()
    
    # 2. Apply document type mapping
    for update in updates:
        mapped_update = get_mapped_update(update, producer_site)
        
        # 3. Insert/update in consumer site
        set_insert(mapped_update, producer_site, self.name)
```

#### 2. Document Type Mapping (`document_type_mapping.py`)

**Enhanced Features:**
- **Value Mapping Logic**: Automatically applies SPP mappings
- **Child Table Support**: Maps nested table records
- **Field Detection**: Smart identification of field types
- **Error Handling**: Graceful handling of missing mappings

**Key Methods:**

```python
def apply_value_mappings(self, doc):
    """Apply value mappings using SPP mapping DocTypes"""
    mapped_fields = [fm.local_fieldname for fm in self.field_mapping]
    
    # Apply to parent fields
    for field_name in mapped_fields:
        if doc.get(field_name):
            doc[field_name] = self.get_mapped_value(field_name, doc[field_name])
    
    # Apply to child tables
    child_table_fields = [fm.local_fieldname for fm in self.field_mapping 
                         if fm.mapping_type == "Child Table"]
    for table_field in child_table_fields:
        if doc.get(table_field):
            for row in doc[table_field]:
                # Apply mappings to each row
                child_mapping = self.get_child_table_mapping(table_field)
                if child_mapping:
                    for child_field in child_mapping.field_mapping:
                        if row.get(child_field.local_fieldname):
                            row[child_field.local_fieldname] = self.get_mapped_value(
                                child_field.local_fieldname, 
                                row[child_field.local_fieldname]
                            )
```

#### 3. SPP Mapping System

**Mapping Types:**

1. **Company Mapping**
   ```python
   def get_company_mapping(self, company):
       mapping_doc = frappe.db.get_value("SPP Company Mapping", {"is_active": 1}, "name")
       if mapping_doc:
           return frappe.db.get_value("SPP Company Mapping Detail",
               {"parent": mapping_doc, "producer_company": company}, "consumer_company")
       return company
   ```

2. **Account Mapping**
   ```python
   def get_account_mapping(self, account):
       mapping_doc = frappe.db.get_value("SPP Account Mapping", {"is_active": 1}, "name")
       if mapping_doc:
           return frappe.db.get_value("SPP Account Mapping Detail",
               {"parent": mapping_doc, "source_account": account}, "target_account")
       return account
   ```

**Field Detection Logic:**
```python
def field_maps_to_account(self, field_name):
    """Check if field should use account mapping"""
    return field_name in ['expense_account', 'income_account', 'account', 
                         'debit_to', 'credit_to', 'account_head']

def field_maps_to_company(self, field_name):
    """Check if field should use company mapping"""
    return field_name in ['company']
```

### Database Schema

#### SPP Mapping Documents

**SPP Company Mapping:**
```sql
-- Parent Document
SPP Company Mapping:
- mapping_name (Data)
- is_active (Check)

-- Child Table
SPP Company Mapping Detail:
- producer_company (Data)
- consumer_company (Link: Company)
```

**SPP Account Mapping:**
```sql
-- Parent Document
SPP Account Mapping:
- source_site (Data)
- target_site (Data)
- is_active (Check)

-- Child Table
SPP Account Mapping Detail:
- source_account (Data)
- target_account (Link: Account)
- is_active (Check)
```

#### Document Type Mapping

```sql
-- Parent Document
Document Type Mapping:
- mapping_name (Data)
- local_doctype (Link: DocType)
- remote_doctype (Data)

-- Child Table
Document Type Field Mapping:
- local_fieldname (Data)
- remote_fieldname (Data)
- mapping_type (Select: "", "Child Table", "Document")
- mapping (Data)
- default_value (Data)
```

### Error Handling

#### Common Error Types

1. **LinkValidationError**
   ```python
   # Cause: Mapped value doesn't exist in target system
   # Solution: Create target record or update mapping
   
   try:
       doc.insert()
   except frappe.LinkValidationError as e:
       frappe.logger().error(f"Link validation failed: {str(e)}")
       # Handle gracefully
   ```

2. **ValidationError**
   ```python
   # Cause: Business rule validation failure
   # Solution: Check mapping configuration
   
   try:
       doc.validate()
   except frappe.ValidationError as e:
       frappe.logger().error(f"Validation failed: {str(e)}")
       # Handle gracefully
   ```

3. **DoesNotExistError**
   ```python
   # Cause: Document Type Mapping not found
   # Solution: Create missing mapping or add null check
   
   if not table_map:
       frappe.logger().warning(f"No mapping found for table '{tablename}'")
       mapping.get(operation)[local_table_name or tablename] = entries
       continue
   ```

---

## Configuration Guide

### Environment Setup

#### Development Environment

```bash
# 1. Create development sites
bench new-site dev-producer.local
bench new-site dev-consumer.local

# 2. Install apps
bench --site dev-producer.local install-app erpnext
bench --site dev-producer.local install-app event_streaming

bench --site dev-consumer.local install-app erpnext
bench --site dev-consumer.local install-app event_streaming

# 3. Create test data
bench --site dev-producer.local console
```

#### Production Environment

```bash
# 1. Backup before deployment
bench --site production-site backup

# 2. Update apps
bench update --app event_streaming

# 3. Run migrations
bench --site production-site migrate

# 4. Restart services
bench restart
```

### Security Configuration

#### API Access

1. **Create API User**
   ```python
   # In producer site
   user = frappe.get_doc({
       "doctype": "User",
       "email": "event_streaming@producer.local",
       "first_name": "Event Streaming",
       "role_profile_name": "Event Streaming User"
   })
   user.insert()
   ```

2. **Generate API Keys**
   ```python
   api_key = frappe.generate_hash(length=15)
   api_secret = frappe.generate_hash(length=15)
   
   user.api_key = api_key
   user.api_secret = api_secret
   user.save()
   ```

#### Network Security

```bash
# Firewall configuration
sudo ufw allow from [consumer-ip] to any port 443
sudo ufw allow from [consumer-ip] to any port 80

# SSL/TLS configuration
sudo certbot --nginx -d producer-site.com
```

### Performance Optimization

#### Database Indexing

```sql
-- Add indexes for mapping queries
CREATE INDEX idx_spp_account_mapping_source 
ON `tabSPP Account Mapping Detail` (source_account);

CREATE INDEX idx_spp_company_mapping_producer 
ON `tabSPP Company Mapping Detail` (producer_company);

CREATE INDEX idx_document_type_field_mapping 
ON `tabDocument Type Field Mapping` (local_fieldname, parent);
```

#### Caching Strategy

```python
# Implement caching for mapping lookups
@frappe.cache()
def get_cached_account_mapping(account):
    return get_account_mapping_from_db(account)
```

---

## Troubleshooting

### Common Issues and Solutions

#### 1. Sync Failures

**Issue:** Documents not syncing
```
Error: Connection timeout to producer site
```

**Solution:**
```bash
# Check network connectivity
ping producer-site.com

# Verify SSL certificates
curl -I https://producer-site.com

# Check API credentials
bench --site consumer-site console
frappe.get_doc("Event Producer", "producer-url").test_connection()
```

#### 2. Mapping Errors

**Issue:** LinkValidationError
```
Error: Could not find Account: Input Tax CGST - SPP INDIA
```

**Solution:**
1. Check if mapping exists:
   ```python
   frappe.db.exists("SPP Account Mapping Detail", 
       {"source_account": "Input Tax CGST - SPP INDIA"})
   ```

2. Add missing mapping:
   ```python
   doc = frappe.get_doc("SPP Account Mapping", "mapping-name")
   doc.append("account_mappings", {
       "source_account": "Input Tax CGST - SPP INDIA",
       "target_account": "Input Tax CGST - SPP"
   })
   doc.save()
   ```

#### 3. Performance Issues

**Issue:** Slow sync processing

**Solution:**
```python
# Enable bulk operations
frappe.flags.in_migrate = True

# Use bulk insert
frappe.db.bulk_insert(doctype, records)

# Disable notifications
frappe.flags.ignore_links = True
```

### Debugging Tools

#### 1. Logging Configuration

```python
# Enable debug logging
import logging
frappe.logger().setLevel(logging.DEBUG)

# Custom log messages
frappe.logger().info(f"Processing mapping for {field_name}: {field_value}")
```

#### 2. Mapping Validation Script

```python
def validate_all_mappings():
    """Validate all SPP mappings"""
    
    mapping_types = [
        "SPP Company Mapping",
        "SPP Account Mapping", 
        "SPP Supplier Mapping",
        "SPP Item Mapping"
    ]
    
    for mapping_type in mapping_types:
        docs = frappe.get_all(mapping_type, {"is_active": 1})
        for doc_name in docs:
            validate_mapping_doc(mapping_type, doc_name)
```

#### 3. Sync Status Monitor

```python
def monitor_sync_status():
    """Monitor sync status and errors"""
    
    producers = frappe.get_all("Event Producer", {"status": "Active"})
    
    for producer in producers:
        doc = frappe.get_doc("Event Producer", producer.name)
        
        print(f"Producer: {doc.producer_url}")
        print(f"Last Sync: {doc.last_update}")
        print(f"Status: {doc.status}")
        print(f"Errors: {len(doc.get('error_log', []))}")
```

---

## API Reference

### Event Producer API

#### Endpoints

**1. Get Updates**
```
GET /api/method/event_streaming.get_updates
Parameters:
- doctype: Document type to sync
- last_update: Last sync timestamp
- limit: Number of records to fetch
```

**2. Test Connection**
```
POST /api/method/event_streaming.test_connection
Parameters:
- producer_url: Producer site URL
- api_key: API key
- api_secret: API secret
```

#### Response Format

```json
{
  "message": {
    "updates": [
      {
        "update_type": "Insert|Update|Delete",
        "doctype": "Purchase Order",
        "docname": "PO-2025-00001",
        "data": "{...document_data...}"
      }
    ],
    "last_update": "2025-09-05 12:00:00"
  }
}
```

### Document Type Mapping API

#### Methods

**1. Apply Mapping**
```python
mapping = frappe.get_doc("Document Type Mapping", "Purchase Order")
result = mapping.get_mapping(doc, producer_site, "Insert")
```

**2. Validate Mapping**
```python
mapping.validate_mapping_configuration()
```

### SPP Mapping API

#### Methods

**1. Get Mapped Value**
```python
def get_mapped_value(mapping_type, source_value):
    """
    Get mapped value from SPP mapping tables
    
    Args:
        mapping_type: Type of mapping (company, account, etc.)
        source_value: Original value from producer
        
    Returns:
        str: Mapped value or original if no mapping found
    """
    pass
```

**2. Add Mapping Entry**
```python
def add_mapping_entry(mapping_doc, source_value, target_value):
    """
    Add new mapping entry to SPP mapping document
    
    Args:
        mapping_doc: SPP mapping document name
        source_value: Producer value
        target_value: Consumer value
    """
    pass
```

---

## Appendices

### A. Sample Configuration Files

#### Event Producer Configuration
```json
{
  "producer_url": "https://sppmaster.frappe.cloud",
  "consumer_url": "https://2526spp.frappe.cloud", 
  "doctypes": ["Purchase Order", "Sales Order"],
  "sync_interval": 300,
  "retry_attempts": 3,
  "timeout": 30
}
```

#### Document Type Mapping Configuration
```json
{
  "name": "Purchase Order",
  "local_doctype": "Purchase Order",
  "remote_doctype": "Purchase Order",
  "field_mapping": [
    {
      "local_fieldname": "supplier",
      "remote_fieldname": "supplier",
      "mapping_type": "",
      "default_value": ""
    },
    {
      "local_fieldname": "taxes", 
      "remote_fieldname": "taxes",
      "mapping_type": "Child Table",
      "mapping": "Purchase Order Tax"
    }
  ]
}
```

### B. Migration Scripts

#### Data Migration Script
```python
def migrate_existing_data():
    """Migrate existing producer data to consumer"""
    
    # Get all Purchase Orders from producer
    po_list = producer_site.get_list("Purchase Order", 
        fields=["name"], limit_page_length=0)
    
    for po in po_list:
        # Get full document
        doc = producer_site.get_doc("Purchase Order", po.name)
        
        # Apply mapping
        mapping = frappe.get_doc("Document Type Mapping", "Purchase Order")
        mapped_doc = mapping.get_mapping(doc, producer_site, "Insert")
        
        # Insert in consumer
        consumer_doc = frappe.get_doc(json.loads(mapped_doc["doc"]))
        consumer_doc.insert()
```

### C. Monitoring Scripts

#### Health Check Script
```python
def health_check():
    """Comprehensive health check for event streaming"""
    
    checks = {
        "producer_connectivity": test_producer_connection(),
        "mapping_validation": validate_all_mappings(), 
        "database_integrity": check_database_consistency(),
        "sync_status": get_sync_status()
    }
    
    return checks
```

---

**End of Documentation**

For additional support or questions, please contact the development team or refer to the project repository.

**Last Updated:** September 5, 2025  
**Version:** 1.0  
**License:** MIT