# ID-Based Migration Feature

## Overview
The ID-based migration feature allows you to migrate specific documents by uploading a JSON file containing their document IDs. This bypasses the 1000-character textarea limit and processes documents in configurable batches.

## Features
✅ **No Character Limits** - Upload thousands of document IDs via JSON file
✅ **Batch Processing** - Configure batch size for optimal performance
✅ **Validation** - Validates IDs against producer site before migration
✅ **Progress Tracking** - Real-time progress updates with success/failure counts
✅ **Error Handling** - Continues processing even if some documents fail

## How to Use

### Step 1: Prepare Your JSON File
Create a JSON file containing an array of document IDs:

```json
[
  "PO-2024-001",
  "PO-2024-002",
  "PO-2024-003",
  "PO-2024-004",
  "PO-2024-005"
]
```

**Important Notes:**
- Must be a valid JSON array
- Each element should be a document ID (string)
- No limit on the number of IDs
- File must have `.json` extension

### Step 2: Access Migration Dashboard
1. Open **Migration Dashboard** page
2. Locate the **"2B. Migrate Specific Documents by ID"** section (highlighted in blue)

### Step 3: Configure Migration
1. **Select Event Producer** - Choose the producer site from section 1
2. **Select Document Type** - Choose the DocType (e.g., Purchase Order)
3. **Upload JSON File** - Click "Choose File" and select your JSON file
4. **Set Batch Size** - Default is 50 (recommended: 50-100 documents per batch)

### Step 4: Validate IDs
1. Click **"Validate IDs"** button
2. Review the validation results:
   - ✅ **Valid IDs** - Documents found on producer site
   - ❌ **Invalid IDs** - Documents not found (will be skipped)
   - 📊 **Total Count** - Total IDs in your file
   - 🔢 **Estimated Batches** - Number of batches based on batch size
3. Check the **sample documents** table to preview

### Step 5: Start Migration
1. Click **"Start ID Migration"** button
2. Confirm the migration in the dialog
3. Monitor progress in the **"ID Migration Progress"** section

## Progress Monitoring
The progress section shows:
- **Status** - Queued → In Progress → Completed/Failed
- **Progress Bar** - Visual progress with percentage
- **Document Count** - Processed / Total documents
- **Failed Count** - Number of failed migrations
- **Start/End Time** - Migration timestamps

## Example JSON Files

### Small Migration (5 documents)
```json
[
  "PO-2024-001",
  "PO-2024-002",
  "PO-2024-003",
  "PO-2024-004",
  "PO-2024-005"
]
```

### Large Migration (1000+ documents)
```json
[
  "PO-2024-001",
  "PO-2024-002",
  "PO-2024-003",
  ...
  "PO-2024-999",
  "PO-2024-1000"
]
```

## Best Practices

### Batch Size Recommendations
- **Small datasets (<100 docs)**: Use batch size 20-30
- **Medium datasets (100-500 docs)**: Use batch size 50 (default)
- **Large datasets (>500 docs)**: Use batch size 75-100
- **Very large datasets (>1000 docs)**: Use batch size 100

### Performance Tips
1. **Pre-validation** - Always validate IDs before migration
2. **Off-peak hours** - Run large migrations during low-traffic times
3. **Batch optimization** - Adjust batch size based on document complexity
4. **Monitor logs** - Check Frappe logs for detailed migration status

### Error Handling
- Invalid IDs are automatically skipped
- Failed migrations don't stop the entire process
- Check the "Failed Documents" count in progress section
- Review Frappe error logs for specific failure reasons

## Troubleshooting

### Common Issues

**1. JSON Parse Error**
```
Error: Failed to parse JSON file: Unexpected token
```
**Solution:** Ensure your JSON file is valid. Use a JSON validator or check:
- All strings are in double quotes
- Commas between elements
- Square brackets at start and end

**2. No Documents Found**
```
Error: 0 valid IDs found
```
**Solution:** 
- Verify document IDs are correct
- Check that documents exist on producer site
- Ensure correct Document Type is selected

**3. Migration Fails to Start**
```
Error: Please validate the IDs first
```
**Solution:** Click "Validate IDs" button before starting migration

**4. Upload Failed**
```
Error: Please upload a JSON file
```
**Solution:** 
- File must have `.json` extension
- File size should be reasonable (<10MB)

## API Reference

### Backend Methods

#### `validate_document_ids(producer, doctype, document_ids)`
Validates document IDs against producer site
- **Parameters:**
  - `producer`: Event Producer name
  - `doctype`: Document Type
  - `document_ids`: Array of document IDs
- **Returns:** Validation results with valid/invalid counts

#### `start_id_based_migration(producer, doctype, document_ids, batch_size)`
Starts ID-based migration job
- **Parameters:**
  - `producer`: Event Producer name
  - `doctype`: Document Type
  - `document_ids`: Array of document IDs
  - `batch_size`: Number of documents per batch (default: 50)
- **Returns:** Job ID for progress tracking

#### `process_id_based_migration_job(job_args)`
Background job that processes the migration
- **Parameters:**
  - `job_args`: Dictionary with job configuration
- **Processes:** Documents in batches with progress updates

## Advantages Over Textarea Input

| Feature | Textarea | JSON File |
|---------|----------|-----------|
| Character Limit | ❌ 1000 chars | ✅ Unlimited |
| Documents | ~50 IDs | ✅ Thousands |
| Validation | ❌ None | ✅ Pre-validation |
| Reusability | ❌ Hard to save | ✅ Easy to reuse |
| Tracking | ❌ Basic | ✅ Detailed progress |
| Error Handling | ❌ Stops on error | ✅ Continues processing |

## Sample Use Cases

### 1. Migrate Specific Month's Orders
```json
[
  "PO-2024-01-001",
  "PO-2024-01-002",
  ...
  "PO-2024-01-150"
]
```

### 2. Migrate Failed Documents
After reviewing error logs, create JSON with failed IDs:
```json
[
  "PO-2024-123",
  "PO-2024-456",
  "PO-2024-789"
]
```

### 3. Selective Migration by Customer
Export IDs from a filtered list view and migrate:
```json
[
  "SO-2024-001",
  "SO-2024-005",
  "SO-2024-012",
  "SO-2024-023"
]
```

## Notes
- Migration uses existing Document Type Mappings
- All SPP mappings (Company, Item, Warehouse, etc.) are applied
- Documents are created with draft status (docstatus=0)
- Use the regular "Submit Draft Purchase Orders" utility to submit them
- Background job timeout is 1500 seconds (25 minutes)

## Support
For issues or questions:
1. Check Frappe error logs
2. Review migration job status in "Event Migration Job" DocType
3. Verify Document Type Mapping configuration
4. Check SPP mapping configurations
