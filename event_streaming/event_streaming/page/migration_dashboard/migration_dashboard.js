frappe.provide('frappe.event_streaming');

frappe.pages['migration-dashboard'].on_page_load = function(wrapper) {
    frappe.ui.make_app_page({
        parent: wrapper,
        title: __('Historical Data Migration'),
        single_column: true
    });

    wrapper.migration_dashboard = new MigrationDashboard(wrapper);

    // Add custom styles
    const style = document.createElement('style');
    style.textContent = `
        .migration-preview {
            padding: 15px;
            background: #fff;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        
        .preview-header {
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 1px solid #eee;
        }
        
        .date-range {
            margin: 15px 0;
            padding: 10px;
            background: #f8f9fa;
            border-radius: 4px;
        }
        
        .date-range p {
            margin: 5px 0;
        }
        
        .summary {
            font-size: 1.1em;
            margin: 15px 0;
        }
        
        .doctype-section {
            margin: 20px 0;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 6px;
        }
        
        .doctype-section h5 {
            color: #1a73e8;
            margin-bottom: 10px;
        }
        
        .sample-entries {
            margin-top: 15px;
        }
        
        .sample-entries table {
            width: 100%;
            margin-top: 10px;
            background: white;
        }
        
        .sample-entries th {
            background: #f1f5f9;
            font-weight: 600;
        }
        
        .sample-entries td, .sample-entries th {
            padding: 8px 12px;
            border: 1px solid #e2e8f0;
        }
    `;
    document.head.appendChild(style);

    let date_filter_types = [
        { value: 'Creation Date', label: 'Creation Date' },
        { value: 'Modified Date', label: 'Modified Date' }
    ];
    
    // Set up date filter type dropdown
    wrapper.page.date_filter_type = wrapper.page.add_field({
        fieldname: 'date_filter_type',
        label: 'Filter By',
        fieldtype: 'Select',
        options: date_filter_types,
        default: 'Creation Date',
        change: () => {
            // Handle filter type change
            wrapper.migration_dashboard.preview_migration();
        }
    });
};

class MigrationDashboard {
    constructor(wrapper) {
        this.page = wrapper.page;
        this.wrapper = $(wrapper).find('.page-content');
        this.filters = {};
        this.doctypes = [];
        this.setup();
    }

    setup() {
        // Add the HTML template to the page
        $(frappe.render_template('migration_dashboard')).appendTo(this.wrapper);
        this.load_producers();
        this.setup_event_handlers();
        
        // Add help link
        this.page.add_help_button('Historical Data Migration');
        
        // Add menu items
        this.page.add_menu_item(__('View Migration Jobs'), () => {
            frappe.set_route('List', 'Event Migration Job');
        });
    }

    load_producers() {
        frappe.call({
            method: 'event_streaming.event_streaming.page.migration_dashboard.migration_dashboard.get_producers',
            callback: (r) => {
                const $select = $('#event-producer');
                $select.empty().append(`<option value="">${__("Select Producer")}</option>`);
                
                (r.message || []).forEach(producer => {
                    $select.append(`<option value="${producer.name}">${producer.producer_url}</option>`);
                });
            }
        });
    }

    setup_event_handlers() {
        // Event Producer selection
        $('#event-producer').on('change', () => {
            this.load_doctypes();
        });

        // Select All doctypes
        $('#select-all-doctypes').on('change', (e) => {
            $('.doctype-checkbox').prop('checked', e.target.checked);
        });

        // Preview button
        $('#btn-preview').on('click', () => {
            this.preview_migration();
        });

        // Start migration button
        $('#btn-start').on('click', () => {
            this.start_migration();
        });

        // Date filter changes
        $('#from-date, #to-date').on('change', () => {
            this.validate_dates();
            // Reset preview when dates change
            $('#preview-stats').addClass('hidden');
            $('#btn-start').prop('disabled', true);
        });

        // Reset preview when filter type changes
        $('#date-filter-type').on('change', () => {
            $('#preview-stats').addClass('hidden');
            $('#btn-start').prop('disabled', true);
        });
    }

    load_doctypes() {
        const producer = $('#event-producer').val();
        if (!producer) {
            $('#doctype-list').html('');
            $('#select-all-doctypes').prop('checked', false);
            return;
        }

        frappe.call({
            method: 'event_streaming.event_streaming.page.migration_dashboard.migration_dashboard.get_producer_doctypes',
            args: { producer: producer },
            callback: (r) => {
                if (r.message) {
                    this.render_doctypes(r.message);
                }
            }
        });
    }

    render_doctypes(doctypes) {
        const $container = $('#doctype-list');
        $container.empty();
        $('#select-all-doctypes').prop('checked', false);

        if (!doctypes.length) {
            $container.html(`<div class="text-muted p-3">${__("No document types configured for this producer")}</div>`);
            return;
        }

        doctypes.forEach(dt => {
            const $item = $(`
                <div class="doctype-item">
                    <div class="checkbox">
                        <label>
                            <input type="checkbox" class="doctype-checkbox" value="${dt.ref_doctype}">
                            ${dt.ref_doctype}
                            ${dt.has_mapping ? `<span class="text-muted">(${__("Has Mapping")})</span>` : ''}
                        </label>
                    </div>
                </div>
            `);
            $container.append($item);
        });

        // Reset preview when doctypes change
        $('#preview-stats').addClass('hidden');
        $('#btn-start').prop('disabled', true);

        // Handle individual checkbox changes
        $('.doctype-checkbox').on('change', () => {
            const allChecked = $('.doctype-checkbox:checked').length === $('.doctype-checkbox').length;
            $('#select-all-doctypes').prop('checked', allChecked);
        });
    }

    validate_dates() {
        const from_date = $('#from-date').val();
        const to_date = $('#to-date').val();

        if (from_date && to_date && from_date > to_date) {
            frappe.throw(__('From Date cannot be after To Date'));
            return false;
        }
        return true;
    }

    get_selected_doctypes() {
        return $('.doctype-checkbox:checked').map(function() {
            return $(this).val();
        }).get();
    }

    get_filters() {
        return {
            producer: $('#event-producer').val(),
            doctypes: this.get_selected_doctypes(),
            date_filter_type: $('#date-filter-type').val(),
            from_date: $('#from-date').val(),
            to_date: $('#to-date').val()
        };
    }

    preview_migration() {
        if (!this.validate_dates()) return;

        const filters = this.get_filters();
        if (!filters.producer) {
            frappe.throw(__('Please select an Event Producer'));
            return;
        }
        if (!filters.doctypes.length) {
            frappe.throw(__('Please select at least one Document Type'));
            return;
        }

        frappe.call({
            method: 'event_streaming.event_streaming.page.migration_dashboard.migration_dashboard.get_producer_data_preview',
            args: {
                producer_url: filters.producer,
                filters: filters
            },
            callback: (r) => {
                if (r.message && r.message.status === 'success') {
                    this.render_preview(r.message.preview);
                    $('#btn-start').prop('disabled', false);
                } else {
                    frappe.msgprint(r.message.message || __('Failed to get preview'));
                }
            }
        });
    }

    render_preview(preview) {
        const $stats = $('#preview-stats').removeClass('hidden');
        let html = `
            <div class="preview-info">
                <p><strong>${__('Total Documents')}:</strong> ${preview.total_documents}</p>
                <p><strong>${__('Estimated Time')}:</strong> ${preview.estimated_time}</p>
            </div>
            <div class="doctype-breakdown">
                <h4>${__('Document Type Breakdown')}</h4>
                <ul>
        `;

        Object.entries(preview.doctypes).forEach(([dt, data]) => {
            html += `<li>${dt}: ${data.count} ${__('documents')}</li>`;
        });

        html += '</ul></div>';
        
        if (preview.formatted_html) {
            html += preview.formatted_html;
        }
        
        $stats.html(html);
    }

    start_migration() {
        if (!this.validate_dates()) return;

        const filters = this.get_filters();
        frappe.confirm(
            __('Are you sure you want to start the migration? This process cannot be interrupted once started.'),
            () => {
                frappe.call({
                    method: 'event_streaming.event_streaming.page.migration_dashboard.migration_dashboard.start_bulk_migration',
                    args: {
                        migration_config: filters
                    },
                    callback: (r) => {
                        if (r.message && r.message.status === 'success') {
                            this.show_progress_section(r.message.job_id);
                            frappe.show_alert({
                                message: __('Migration started successfully'),
                                indicator: 'green'
                            });
                        } else {
                            frappe.msgprint(r.message.message || __('Failed to start migration'));
                        }
                    }
                });
            }
        );
    }

    show_progress_section(job_id) {
        $('.progress-section').removeClass('hidden');
        this.setup_progress_tracking(job_id);
    }

    setup_progress_tracking(job_id) {
        const $progress = $('.progress-stats');
        this.progress_interval = setInterval(() => {
            frappe.call({
                method: 'event_streaming.event_streaming.page.migration_dashboard.migration_dashboard.get_migration_job_progress',
                args: {
                    job_name: job_id
                },
                callback: (r) => {
                    if (r.message) {
                        const progress = r.message;
                        this.update_progress_ui(progress);

                        // Stop tracking if job is complete or failed
                        if (progress.status === 'Completed' || progress.status === 'Failed') {
                            clearInterval(this.progress_interval);
                        }
                    }
                }
            });
        }, 5000); // Update every 5 seconds
    }

    update_progress_ui(progress) {
        const $progress = $('.progress-stats');
        const start_time = progress.start_time ? frappe.datetime.str_to_user(progress.start_time) : '';
        const end_time = progress.end_time ? frappe.datetime.str_to_user(progress.end_time) : '';
        
        let html = `
            <div class="progress-info">
                <div class="row">
                    <div class="col-md-6">
                        <p><strong>${__('Status')}:</strong> 
                            <span class="status-${(progress.status || '').toLowerCase()}">${progress.status || ''}</span>
                        </p>
                        <p><strong>${__('Documents Processed')}:</strong> ${progress.processed_docs || 0} / ${progress.total_docs || 0}</p>
                        <p><strong>${__('Document Types')}:</strong> 
                            ${progress.completed_doctypes || 0} / ${progress.total_doctypes || 0}
                        </p>
                    </div>
                    <div class="col-md-6">
                        <p><strong>${__('Start Time')}:</strong> ${start_time}</p>
                        ${end_time ? 
                            `<p><strong>${__('End Time')}:</strong> ${end_time}</p>` 
                            : ''
                        }
                    </div>
                </div>
            </div>
        `;

        // Add per-doctype progress
        if (progress.processed_by_doctype) {
            html += `
                <div class="doctype-progress">
                    <h6>${__('Progress by Document Type')}</h6>
                    <div class="table-responsive">
                        <table class="table table-bordered">
                            <thead>
                                <tr>
                                    <th>${__('Document Type')}</th>
                                    <th>${__('Progress')}</th>
                                    <th>${__('Count')}</th>
                                </tr>
                            </thead>
                            <tbody>
            `;
            
            Object.entries(progress.processed_by_doctype).forEach(([doctype, stats]) => {
                const processed = stats.processed || 0;
                const total = stats.total || 0;
                const percent = total ? Math.round((processed / total) * 100) : 0;
                
                html += `
                    <tr>
                        <td>${doctype}</td>
                        <td>
                            <div class="progress" style="margin-bottom: 0;">
                                <div class="progress-bar" role="progressbar" 
                                    style="width: ${percent}%;"
                                    aria-valuenow="${percent}" aria-valuemin="0" aria-valuemax="100">
                                    ${percent}%
                                </div>
                            </div>
                        </td>
                        <td>${processed} / ${total}</td>
                    </tr>
                `;
            });
            
            html += `
                            </tbody>
                        </table>
                    </div>
                </div>
            `;
        }

        if (progress.error) {
            html += `
                <div class="error-section alert alert-danger">
                    <h5>${__('Error')}</h5>
                    <pre>${progress.error}</pre>
                </div>
            `;
        }

        $progress.html(html);

        // Update status colors
        $('.status-completed').css('color', 'var(--green-600)');
        $('.status-failed').css('color', 'var(--red-600)');
        $('.status-inprogress').css('color', 'var(--blue-600)');
        $('.status-queued').css('color', 'var(--orange-600)');
    }
}