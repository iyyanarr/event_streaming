frappe.provide('frappe.document_manager');

frappe.pages['document-manager'].on_page_load = function(wrapper) {
    frappe.ui.make_app_page({
        parent: wrapper,
        title: __('Document Manager'),
        single_column: true
    });

    wrapper.document_manager = new DocumentManager(wrapper);
};

class DocumentManager {
    constructor(wrapper) {
        this.page = wrapper.page;
        this.wrapper = $(wrapper).find('.page-content');
        this.filters = {};
        this.selected_documents = new Set();
        this.setup();
    }

    setup() {
        // Add the HTML template to the page
        $(frappe.render_template('document_manager')).appendTo(this.wrapper);
        this.setup_event_handlers();
        this.load_document_types();
        // Remove automatic document loading on page load
        // this.load_documents(); // Commented out - only load when user selects filters
        
        // Show initial message instead
        this.show_initial_message();
        
        // Add menu items
        this.page.add_menu_item(__('Migration Dashboard'), () => {
            frappe.set_route('page', 'migration-dashboard');
        });

        this.page.add_menu_item(__('Refresh Data'), () => {
            this.load_documents();
        });
    }

    setup_event_handlers() {
        // Document Type filter - primary filter that enables others
        $('#doctype-filter').on('change', () => {
            const doctype = $('#doctype-filter').val();
            if (doctype) {
                // Enable other filters when doctype is selected
                $('#status-filter, #migration-status-filter').prop('disabled', false);
                // Show message that user can now select additional filters
                this.show_filter_message();
            } else {
                // Disable other filters when no doctype selected
                $('#status-filter, #migration-status-filter').prop('disabled', true).val('');
                this.show_initial_message();
            }
        });

        // Secondary filters - only work after doctype is selected
        $('#status-filter, #migration-status-filter').on('change', () => {
            const doctype = $('#doctype-filter').val();
            if (doctype) {
                // Show message that user can now click Refresh
                this.show_ready_message();
            }
        });

        // Refresh button - only loads data when explicitly clicked
        $('#btn-refresh').on('click', () => {
            const doctype = $('#doctype-filter').val();
            if (doctype) {
                this.load_documents();
            } else {
                frappe.msgprint(__('Please select a Document Type first'));
            }
        });

        // Select all checkbox
        $('#select-all-docs, .select-all-header').on('change', (e) => {
            const isChecked = e.target.checked;
            $('.doc-checkbox').prop('checked', isChecked);
            this.update_selection();
        });

        // Individual document selection
        $(document).on('change', '.doc-checkbox', () => {
            this.update_selection();
        });

        // Bulk action buttons - add confirmation and prevent accidental clicks
        $('#btn-submit-selected').on('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.submit_selected_documents();
        });

        $('#btn-delete-selected').on('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.delete_selected_documents();
        });

        $('#btn-analyze-failures').on('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.show_failure_analysis();
        });

        $('#btn-export-report').on('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.export_report();
        });

        // Individual document actions with event prevention
        $(document).on('click', '.btn-submit-doc', (e) => {
            e.preventDefault();
            e.stopPropagation();
            const doctype = $(e.target).data('doctype');
            const docname = $(e.target).data('docname');
            this.submit_single_document(doctype, docname);
        });

        $(document).on('click', '.btn-delete-doc', (e) => {
            e.preventDefault();
            e.stopPropagation();
            const doctype = $(e.target).data('doctype');
            const docname = $(e.target).data('docname');
            this.delete_single_document(doctype, docname);
        });

        $(document).on('click', '.btn-view-error', (e) => {
            e.preventDefault();
            e.stopPropagation();
            const error = $(e.target).data('error');
            this.show_error_details(error);
        });
    }

    load_document_types() {
        frappe.call({
            method: 'event_streaming.event_streaming.page.document_manager.document_manager.get_available_doctypes',
            callback: (r) => {
                const $select = $('#doctype-filter');
                $select.empty().append(`<option value="">${__("All Document Types")}</option>`);
                
                (r.message || []).forEach(doctype => {
                    $select.append(`<option value="${doctype}">${doctype}</option>`);
                });
            }
        });
    }

    load_documents() {
        const filters = this.get_filters();
        
        frappe.call({
            method: 'event_streaming.event_streaming.page.document_manager.document_manager.get_documents_data',
            args: { filters: filters },
            callback: (r) => {
                if (r.message) {
                    this.render_summary(r.message.summary);
                    this.render_documents(r.message.documents);
                }
            }
        });
    }

    get_filters() {
        return {
            doctype: $('#doctype-filter').val(),
            status: $('#status-filter').val(),
            migration_status: $('#migration-status-filter').val()
        };
    }

    render_summary(summary) {
        $('#success-count').text(summary.success || 0);
        $('#failed-count').text(summary.failed || 0);
        $('#draft-count').text(summary.draft || 0);
        $('#submitted-count').text(summary.submitted || 0);
        $('#total-count').text(summary.total || 0);
        $('#mapping-errors-count').text(summary.mapping_errors || 0);
    }

    render_documents(documents) {
        const $tbody = $('#documents-tbody');
        $tbody.empty();
        
        if (!documents || !documents.length) {
            $tbody.append(`
                <tr>
                    <td colspan="8" class="text-center text-muted">
                        ${__('No documents found matching the criteria')}
                    </td>
                </tr>
            `);
            return;
        }

        documents.forEach(doc => {
            const statusClass = this.get_status_class(doc.docstatus);
            const migrationStatusClass = this.get_migration_status_class(doc.migration_status);
            const errorPreview = doc.error_details ? 
                (doc.error_details.length > 50 ? 
                    doc.error_details.substring(0, 50) + '...' : 
                    doc.error_details) : '';

            const row = $(`
                <tr>
                    <td>
                        <input type="checkbox" class="doc-checkbox" 
                               data-doctype="${doc.doctype}" 
                               data-docname="${doc.name}">
                    </td>
                    <td>
                        <a href="/app/${doc.doctype.toLowerCase().replace(' ', '-')}/${doc.name}" 
                           target="_blank">${doc.name}</a>
                    </td>
                    <td>${doc.doctype}</td>
                    <td>
                        <span class="status-badge ${statusClass}">
                            ${this.get_status_text(doc.docstatus, doc.status)}
                        </span>
                    </td>
                    <td>
                        <span class="migration-status-badge ${migrationStatusClass}">
                            ${doc.migration_status || 'Unknown'}
                        </span>
                    </td>
                    <td>${frappe.datetime.str_to_user(doc.creation)}</td>
                    <td>
                        ${doc.error_details ? `
                            <span class="error-details" title="${doc.error_details}">
                                ${errorPreview}
                                <button class="btn btn-xs btn-warning btn-view-error" 
                                        data-error="${frappe.utils.escape_html(doc.error_details)}">
                                    <i class="fa fa-eye"></i>
                                </button>
                            </span>
                        ` : '<span class="text-muted">No errors</span>'}
                    </td>
                    <td>
                        ${doc.docstatus === 0 ? `
                            <button class="btn btn-xs btn-success btn-submit-doc" 
                                    data-doctype="${doc.doctype}" 
                                    data-docname="${doc.name}">
                                <i class="fa fa-check"></i> Submit
                            </button>
                        ` : ''}
                        <button class="btn btn-xs btn-danger btn-delete-doc" 
                                data-doctype="${doc.doctype}" 
                                data-docname="${doc.name}">
                            <i class="fa fa-trash"></i> Delete
                        </button>
                    </td>
                </tr>
            `);
            $tbody.append(row);
        });

        this.update_selection();
    }

    get_status_class(docstatus) {
        switch(docstatus) {
            case 0: return 'status-draft';
            case 1: return 'status-submitted';
            case 2: return 'status-cancelled';
            default: return 'status-draft';
        }
    }

    get_status_text(docstatus, status) {
        switch(docstatus) {
            case 0: return status || 'Draft';
            case 1: return 'Submitted';
            case 2: return 'Cancelled';
            default: return status || 'Unknown';
        }
    }

    get_migration_status_class(migration_status) {
        switch(migration_status) {
            case 'Success': return 'migration-success';
            case 'Failed': return 'migration-failed';
            case 'Partial': return 'migration-warning';
            default: return 'migration-success';
        }
    }

    update_selection() {
        const $checkboxes = $('.doc-checkbox:checked');
        const count = $checkboxes.length;
        
        $('#selection-info').text(`${count} documents selected`);
        $('#btn-submit-selected, #btn-delete-selected').prop('disabled', count === 0);
        
        // Update select all checkbox state
        const totalCheckboxes = $('.doc-checkbox').length;
        const allChecked = count === totalCheckboxes && totalCheckboxes > 0;
        $('#select-all-docs, .select-all-header').prop('checked', allChecked);
    }

    get_selected_documents() {
        const selected = [];
        $('.doc-checkbox:checked').each(function() {
            selected.push({
                doctype: $(this).data('doctype'),
                name: $(this).data('docname')
            });
        });
        return selected;
    }

    submit_selected_documents() {
        const selected = this.get_selected_documents();
        if (!selected.length) return;

        frappe.confirm(
            __(`Are you sure you want to submit ${selected.length} selected documents?`),
            () => {
                this.show_progress_modal('Submitting Documents');
                
                frappe.call({
                    method: 'event_streaming.event_streaming.page.document_manager.document_manager.bulk_submit_documents',
                    args: { documents: selected },
                    callback: (r) => {
                        this.hide_progress_modal();
                        if (r.message) {
                            frappe.show_alert({
                                message: __(`Successfully submitted ${r.message.success_count} documents`),
                                indicator: 'green'
                            });
                            this.load_documents();
                        }
                    }
                });
            }
        );
    }

    delete_selected_documents() {
        const selected = this.get_selected_documents();
        if (!selected.length) return;

        frappe.confirm(
            __(`Are you sure you want to delete ${selected.length} selected documents? This action cannot be undone.`),
            () => {
                this.show_progress_modal('Deleting Documents');
                
                frappe.call({
                    method: 'event_streaming.event_streaming.page.document_manager.document_manager.bulk_delete_documents',
                    args: { documents: selected },
                    callback: (r) => {
                        this.hide_progress_modal();
                        if (r.message) {
                            frappe.show_alert({
                                message: __(`Successfully deleted ${r.message.success_count} documents`),
                                indicator: 'green'
                            });
                            this.load_documents();
                        }
                    }
                });
            }
        );
    }

    submit_single_document(doctype, docname) {
        frappe.call({
            method: 'event_streaming.event_streaming.page.document_manager.document_manager.submit_single_document',
            args: { doctype: doctype, docname: docname },
            callback: (r) => {
                if (r.message && r.message.success) {
                    frappe.show_alert({
                        message: __('Document submitted successfully'),
                        indicator: 'green'
                    });
                    this.load_documents();
                } else {
                    frappe.msgprint({
                        title: __('Submission Failed'),
                        message: r.message.error || __('Failed to submit document'),
                        indicator: 'red'
                    });
                }
            }
        });
    }

    delete_single_document(doctype, docname) {
        frappe.confirm(
            __(`Are you sure you want to delete ${docname}? This action cannot be undone.`),
            () => {
                frappe.call({
                    method: 'event_streaming.event_streaming.page.document_manager.document_manager.delete_single_document',
                    args: { doctype: doctype, docname: docname },
                    callback: (r) => {
                        if (r.message && r.message.success) {
                            frappe.show_alert({
                                message: __('Document deleted successfully'),
                                indicator: 'green'
                            });
                            this.load_documents();
                        } else {
                            frappe.msgprint({
                                title: __('Deletion Failed'),
                                message: r.message.error || __('Failed to delete document'),
                                indicator: 'red'
                            });
                        }
                    }
                });
            }
        );
    }

    show_failure_analysis() {
        frappe.call({
            method: 'event_streaming.event_streaming.page.document_manager.document_manager.get_failure_analysis',
            args: { filters: this.get_filters() },
            callback: (r) => {
                if (r.message) {
                    this.render_failure_analysis(r.message);
                    $('#failure-analysis-modal').modal('show');
                }
            }
        });
    }

    render_failure_analysis(analysis) {
        const $content = $('#failure-analysis-content');
        let html = '';

        // Debug information first
        if (analysis.debug_info) {
            html += `
                <div class="analysis-section">
                    <h5>Analysis Details</h5>
                    <p class="text-info"><i class="fa fa-info-circle"></i> ${analysis.debug_info}</p>
                </div>
            `;
        }

        // Overall statistics
        html += `
            <div class="analysis-section">
                <h5>Overall Statistics</h5>
                <div class="row">
                    <div class="col-md-3">
                        <strong>Total Documents:</strong> ${analysis.total_tested || 0}
                    </div>
                    <div class="col-md-3">
                        <strong>Documents with Errors:</strong> ${analysis.total_errors || 0}
                    </div>
                    <div class="col-md-3">
                        <strong>Unique Error Types:</strong> ${Object.keys(analysis.error_groups || {}).length}
                    </div>
                    <div class="col-md-3">
                        <strong>Success Rate:</strong> ${analysis.success_rate || 0}%
                    </div>
                </div>
                ${analysis.most_common_error !== 'None' ? `
                    <p class="margin-top"><strong>Most Common Issue:</strong> ${analysis.most_common_error}</p>
                ` : ''}
            </div>
        `;

        // Error groups with enhanced information
        if (analysis.error_groups && Object.keys(analysis.error_groups).length > 0) {
            html += `
                <div class="analysis-section">
                    <h5>Detailed Error Breakdown</h5>
            `;
            
            Object.entries(analysis.error_groups).forEach(([error_type, data]) => {
                html += `
                    <div class="error-group">
                        <h6>${error_type} <span class="error-count">(${data.count} affected documents)</span></h6>
                        <p><strong>Description:</strong> ${data.description || 'No description available'}</p>
                        
                        ${data.sample_errors && data.sample_errors.length > 0 ? `
                            <div class="sample-errors" style="margin-top: 10px;">
                                <strong>Sample Errors:</strong>
                                <ul style="margin-top: 5px;">
                                    ${data.sample_errors.slice(0, 3).map(error => `<li><code style="font-size: 0.85em;">${error}...</code></li>`).join('')}
                                </ul>
                            </div>
                        ` : ''}
                        
                        <details style="margin-top: 10px;">
                            <summary><strong>Affected Documents (${data.count})</strong></summary>
                            <div style="margin-top: 5px; font-family: monospace; font-size: 0.9em;">
                                ${data.documents.slice(0, 20).join(', ')}
                                ${data.documents.length > 20 ? ` and ${data.documents.length - 20} more...` : ''}
                            </div>
                        </details>
                    </div>
                `;
            });
            
            html += '</div>';
        } else {
            html += `
                <div class="analysis-section">
                    <div class="alert alert-info">
                        <i class="fa fa-info-circle"></i> 
                        No errors found in the tested documents, or analysis could not detect specific error patterns.
                        ${analysis.total_tested === 0 ? 'Try selecting "Purchase Order" from the Document Type filter first.' : ''}
                    </div>
                </div>
            `;
        }

        // Mapping recommendations with priority
        if (analysis.mapping_recommendations && analysis.mapping_recommendations.length > 0) {
            html += `
                <div class="analysis-section">
                    <h5>Priority Actions Required</h5>
                    <div class="alert alert-warning">
                        <i class="fa fa-exclamation-triangle"></i> 
                        <strong>Immediate Steps to Fix Issues:</strong>
                    </div>
                    <ol style="margin-top: 10px;">
            `;
            
            analysis.mapping_recommendations.forEach(rec => {
                html += `<li style="margin-bottom: 8px;"><strong>${rec}</strong></li>`;
            });
            
            html += `
                    </ol>
                    <div class="alert alert-info" style="margin-top: 15px;">
                        <strong>How to set up mappings:</strong><br>
                        1. Go to the respective SPP mapping doctypes (e.g., SPP Address Mapping)<br>
                        2. Create new mapping records linking producer values to consumer values<br>
                        3. Test submission again after creating mappings
                    </div>
                </div>
            `;
        }

        $content.html(html);
    }

    show_error_details(error) {
        frappe.msgprint({
            title: __('Error Details'),
            message: `<pre style="white-space: pre-wrap; word-wrap: break-word;">${error}</pre>`,
            wide: true
        });
    }

    export_report() {
        const filters = this.get_filters();
        frappe.call({
            method: 'event_streaming.event_streaming.page.document_manager.document_manager.export_documents_report',
            args: { filters: filters },
            callback: (r) => {
                if (r.message && r.message.file_url) {
                    window.open(r.message.file_url, '_blank');
                }
            }
        });
    }

    show_progress_modal(title) {
        $('#progress-modal .modal-title').text(title);
        $('#progress-content').html(`
            <div class="text-center">
                <i class="fa fa-spinner fa-spin fa-3x"></i>
                <p class="margin-top">${__('Processing...')}</p>
            </div>
        `);
        $('#progress-modal').modal('show');
    }

    hide_progress_modal() {
        $('#progress-modal').modal('hide');
    }

    show_initial_message() {
        const $tbody = $('#documents-tbody');
        $tbody.empty();
        $tbody.append(`
            <tr>
                <td colspan="8" class="text-center text-muted">
                    <div style="padding: 20px;">
                        <i class="fa fa-info-circle" style="font-size: 2em; color: #6c757d; margin-bottom: 10px;"></i>
                        <h5>Step 1: Select Document Type</h5>
                        <p>Please choose a Document Type from the dropdown above to begin.</p>
                    </div>
                </td>
            </tr>
        `);
        
        // Reset summary
        this.render_summary({
            total: 0, success: 0, failed: 0, draft: 0, submitted: 0, mapping_errors: 0
        });
    }

    show_filter_message() {
        const $tbody = $('#documents-tbody');
        $tbody.empty();
        $tbody.append(`
            <tr>
                <td colspan="8" class="text-center text-muted">
                    <div style="padding: 20px;">
                        <i class="fa fa-filter" style="font-size: 2em; color: #17a2b8; margin-bottom: 10px;"></i>
                        <h5>Step 2: Apply Filters (Optional)</h5>
                        <p>You can now select additional filters like Status or Migration Status, then click <strong>Refresh</strong> to load documents.</p>
                        <p><em>Or click Refresh now to load all documents of the selected type.</em></p>
                    </div>
                </td>
            </tr>
        `);
    }

    show_ready_message() {
        const $tbody = $('#documents-tbody');
        $tbody.empty();
        $tbody.append(`
            <tr>
                <td colspan="8" class="text-center text-muted">
                    <div style="padding: 20px;">
                        <i class="fa fa-refresh" style="font-size: 2em; color: #28a745; margin-bottom: 10px;"></i>
                        <h5>Step 3: Load Documents</h5>
                        <p>Filters are ready! Click the <strong>Refresh</strong> button above to load documents.</p>
                    </div>
                </td>
            </tr>
        `);
    }
}