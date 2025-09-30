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

    const date_filter_types = [
        { value: 'creation', label: 'Creation Date' },
        { value: 'modified', label: 'Modified Date' },
        { value: 'transaction', label: 'Transaction Date' },
        { value: 'posting', label: 'Posting Date' }
    ];
    
    // Set up date filter type dropdown
    wrapper.page.date_filter_type = wrapper.page.add_field({
        fieldname: 'date_filter_type',
        label: 'Filter By',
        fieldtype: 'Select',
        options: date_filter_types,
        default: 'creation',
        change: () => {
            // Reset preview when filter type changes
            $('#preview-stats').addClass('hidden');
            $('#btn-start').prop('disabled', true);
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
        this.custom_filters = [];
        this.doctype_meta_cache = {};
        this.setup();
    }

    setup() {
        // Add the HTML template to the page
        $(frappe.render_template('migration_dashboard')).appendTo(this.wrapper);
        this.load_producers();
        this.setup_event_handlers();
        this.setup_advanced_filters();
        
        // Add help link
        this.page.add_help_button('Historical Data Migration');
        
        // Add menu items
        this.page.add_menu_item(__('View Migration Jobs'), () => {
            frappe.set_route('List', 'Event Migration Job');
        });

        this.page.add_menu_item(__('Document Manager'), () => {
            frappe.set_route('page', 'document-manager');
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
            this.populate_id_doctype_dropdown();
        });

        // Select All doctypes
        $('#select-all-doctypes').on('change', (e) => {
            $('.doctype-checkbox').prop('checked', e.target.checked);
            this.update_available_filter_fields();
        });

        // ID-based migration handlers
        $('#json-file-upload').on('change', (e) => {
            this.handle_json_file_upload(e);
        });

        $('#btn-validate-ids').on('click', () => {
            this.validate_json_ids();
        });

        $('#btn-start-id-migration').on('click', () => {
            this.start_id_migration();
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

        // Delete Draft Purchase Orders button
        $('#btn-delete-draft-pos').on('click', () => {
            this.delete_draft_purchase_orders();
        });

        // Submit Draft Purchase Orders button
        $('#btn-submit-draft-pos').on('click', () => {
            this.submit_draft_purchase_orders();
        });

        // Clear Document Locks button
        $('#btn-clear-locks').on('click', () => {
            this.clear_document_locks();
        });
    }

    setup_advanced_filters() {
        // Add filter button
        $('#btn-add-filter').on('click', () => {
            this.add_filter_row();
        });

        // Clear filters button
        $('#btn-clear-filters').on('click', () => {
            this.clear_all_filters();
        });

        // Filter mode change
        $('input[name="filter-mode"]').on('change', () => {
            this.update_filter_summary();
            // Reset preview when filter mode changes
            $('#preview-stats').addClass('hidden');
            $('#btn-start').prop('disabled', true);
        });

        // Initialize empty state
        this.show_empty_filters_state();
    }

    load_doctypes() {
        const producer = $('#event-producer').val();
        if (!producer) {
            $('#doctype-list').html('');
            $('#select-all-doctypes').prop('checked', false);
            this.clear_all_filters();
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
            this.clear_all_filters();
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
            this.update_available_filter_fields();
        });
    }

    async update_available_filter_fields() {
        const selected_doctypes = this.get_selected_doctypes();
        
        if (selected_doctypes.length === 0) {
            this.clear_all_filters();
            return;
        }

        // Load meta for all selected doctypes
        for (const doctype of selected_doctypes) {
            if (!this.doctype_meta_cache[doctype]) {
                try {
                    const meta = await this.get_doctype_meta(doctype);
                    this.doctype_meta_cache[doctype] = meta;
                } catch (error) {
                    console.error(`Failed to load meta for ${doctype}:`, error);
                }
            }
        }

        // Update existing filter dropdowns
        this.update_filter_field_options();
    }

    async get_doctype_meta(doctype) {
        return new Promise((resolve, reject) => {
            frappe.call({
                method: 'event_streaming.event_streaming.page.migration_dashboard.migration_dashboard.get_doctype_meta',
                args: { doctype: doctype },
                callback: (r) => {
                    if (r.message) {
                        resolve(r.message);
                    } else {
                        reject(new Error(`Failed to get meta for ${doctype}`));
                    }
                },
                error: reject
            });
        });
    }

    get_available_filter_fields() {
        const selected_doctypes = this.get_selected_doctypes();
        if (selected_doctypes.length === 0) return [];

        let common_fields = [];
        
        // Find fields that are common across all selected doctypes
        if (selected_doctypes.length === 1) {
            // For single doctype, show all filterable fields including child table fields
            const doctype = selected_doctypes[0];
            const meta = this.doctype_meta_cache[doctype];
            if (meta && meta.fields) {
                // Parent table fields
                const parent_fields = meta.fields.filter(field => 
                    this.is_field_filterable(field)
                ).map(field => ({
                    fieldname: field.fieldname,
                    label: field.label || field.fieldname,
                    fieldtype: field.fieldtype,
                    options: field.options,
                    doctype: doctype,
                    is_child_table: false
                }));

                // Child table fields
                const child_table_fields = [];
                if (meta.child_tables) {
                    Object.keys(meta.child_tables).forEach(table_field => {
                        const child_table = meta.child_tables[table_field];
                        child_table.fields.forEach(child_field => {
                            child_table_fields.push({
                                fieldname: `${table_field}.${child_field.fieldname}`,
                                label: `${child_table.label} → ${child_field.label || child_field.fieldname}`,
                                fieldtype: child_field.fieldtype,
                                options: child_field.options,
                                doctype: doctype,
                                is_child_table: true,
                                parent_table: table_field,
                                child_doctype: child_table.child_doctype
                            });
                        });
                    });
                }

                common_fields = [...parent_fields, ...child_table_fields];
            }
        } else {
            // For multiple doctypes, find common fields (parent table only for simplicity)
            const all_field_sets = selected_doctypes.map(doctype => {
                const meta = this.doctype_meta_cache[doctype];
                return meta && meta.fields ? meta.fields.filter(field => 
                    this.is_field_filterable(field)
                ) : [];
            });

            if (all_field_sets.length > 0) {
                const first_set = all_field_sets[0];
                common_fields = first_set.filter(field => 
                    all_field_sets.every(set => 
                        set.some(f => f.fieldname === field.fieldname && f.fieldtype === field.fieldtype)
                    )
                ).map(field => ({
                    fieldname: field.fieldname,
                    label: field.label || field.fieldname,
                    fieldtype: field.fieldtype,
                    options: field.options,
                    doctype: 'common',
                    is_child_table: false
                }));
            }
        }

        // Always include standard fields
        const standard_fields = [
            { fieldname: 'name', label: 'ID', fieldtype: 'Data', doctype: 'standard', is_child_table: false },
            { fieldname: 'owner', label: 'Created By', fieldtype: 'Link', options: 'User', doctype: 'standard', is_child_table: false },
            { fieldname: 'docstatus', label: 'Document Status', fieldtype: 'Select', 
              options: '0\n1\n2', doctype: 'standard', is_child_table: false },
            { fieldname: 'creation', label: 'Created On', fieldtype: 'Datetime', doctype: 'standard', is_child_table: false },
            { fieldname: 'modified', label: 'Last Modified', fieldtype: 'Datetime', doctype: 'standard', is_child_table: false }
        ];

        return [...standard_fields, ...common_fields];
    }

    is_field_filterable(field) {
        const filterable_types = [
            'Data', 'Select', 'Link', 'Int', 'Float', 'Currency', 'Date', 'Datetime', 
            'Check', 'Text', 'Small Text', 'Long Text', 'Time', 'Duration'
        ];
        
        return filterable_types.includes(field.fieldtype) && 
               !field.hidden && 
               !field.read_only &&
               field.fieldname !== 'amended_from';
    }

    add_filter_row() {
        const available_fields = this.get_available_filter_fields();
        
        if (available_fields.length === 0) {
            frappe.msgprint(__('Please select document types first to see available filter fields.'));
            return;
        }

        const filter_id = `filter_${Date.now()}`;
        const $container = $('#custom-filters-container');
        
        // Remove empty state
        $container.removeClass('empty-filters').addClass('has-filters');
        $container.find('.empty-filters-message').remove();

        const $filter_row = $(`
            <div class="filter-row" data-filter-id="${filter_id}">
                <div class="filter-field">
                    <select class="form-control filter-field-select">
                        <option value="">${__('Select Field')}</option>
                    </select>
                </div>
                <div class="filter-operator">
                    <select class="form-control filter-operator-select">
                        <option value="=">=</option>
                        <option value="!=">!=</option>
                        <option value="like">contains</option>
                        <option value="not like">not contains</option>
                        <option value="in">in</option>
                        <option value="not in">not in</option>
                        <option value=">">&gt;</option>
                        <option value=">=">&gt;=</option>
                        <option value="<">&lt;</option>
                        <option value="<=">&lt;=</option>
                        <option value="between">between</option>
                        <option value="is">is</option>
                        <option value="is not">is not</option>
                    </select>
                </div>
                <div class="filter-value">
                    <input type="text" class="form-control filter-value-input" placeholder="${__('Enter value')}">
                </div>
                <div class="filter-remove">
                    <button type="button" class="btn btn-danger btn-xs remove-filter" title="${__('Remove Filter')}">
                        <i class="fa fa-times"></i>
                    </button>
                </div>
            </div>
        `);

        // Populate field options
        const $field_select = $filter_row.find('.filter-field-select');
        available_fields.forEach(field => {
            let option_text;
            if (field.doctype === 'standard') {
                option_text = field.label;
            } else if (field.doctype === 'common') {
                option_text = `${field.label} (Common)`;
            } else if (field.is_child_table) {
                option_text = `${field.label} (Child Table)`;
            } else {
                option_text = `${field.label} (${field.doctype})`;
            }
            
            $field_select.append(`<option value="${field.fieldname}" 
                data-fieldtype="${field.fieldtype}" 
                data-options="${field.options || ''}"
                data-is-child-table="${field.is_child_table || false}"
                data-parent-table="${field.parent_table || ''}"
                data-child-doctype="${field.child_doctype || ''}">${option_text}</option>`);
        });

        $container.append($filter_row);

        // Setup event handlers for this filter row
        this.setup_filter_row_handlers($filter_row);
        this.update_filter_summary();
    }

    setup_filter_row_handlers($filter_row) {
        const $field_select = $filter_row.find('.filter-field-select');
        const $operator_select = $filter_row.find('.filter-operator-select');
        const $value_input = $filter_row.find('.filter-value-input');
        const $remove_btn = $filter_row.find('.remove-filter');

        // Field selection change
        $field_select.on('change', () => {
            const fieldtype = $field_select.find(':selected').data('fieldtype');
            const options = $field_select.find(':selected').data('options');
            this.update_operator_options($operator_select, fieldtype);
            this.update_value_input($value_input, fieldtype, options);
            this.update_filter_summary();
        });

        // Operator change
        $operator_select.on('change', () => {
            const operator = $operator_select.val();
            this.update_value_input_for_operator($value_input, operator);
            this.update_filter_summary();
        });

        // Value change
        $value_input.on('input change', () => {
            this.update_filter_summary();
        });

        // Remove filter
        $remove_btn.on('click', () => {
            $filter_row.remove();
            
            // Check if no filters left
            if ($('#custom-filters-container .filter-row').length === 0) {
                this.show_empty_filters_state();
            }
            
            this.update_filter_summary();
            // Reset preview when filters change
            $('#preview-stats').addClass('hidden');
            $('#btn-start').prop('disabled', true);
        });
    }

    update_operator_options($operator_select, fieldtype) {
        $operator_select.empty();
        
        const operators = this.get_operators_for_fieldtype(fieldtype);
        operators.forEach(op => {
            $operator_select.append(`<option value="${op.value}">${op.label}</option>`);
        });
    }

    get_operators_for_fieldtype(fieldtype) {
        const base_operators = [
            { value: '=', label: '=' },
            { value: '!=', label: '!=' }
        ];

        switch (fieldtype) {
            case 'Select':
            case 'Link':
                return [
                    ...base_operators,
                    { value: 'like', label: 'contains' },
                    { value: 'not like', label: 'not contains' },
                    { value: 'in', label: 'in' },
                    { value: 'not in', label: 'not in' },
                    { value: 'is', label: 'is' },
                    { value: 'is not', label: 'is not' }
                ];

            case 'Data':
            case 'Text':
            case 'Small Text':
            case 'Long Text':
                return [
                    ...base_operators,
                    { value: 'like', label: 'contains' },
                    { value: 'not like', label: 'not contains' },
                    { value: 'in', label: 'in' },
                    { value: 'not in', label: 'not in' }
                ];

            case 'Int':
            case 'Float':
            case 'Currency':
            case 'Date':
            case 'Datetime':
                return [
                    ...base_operators,
                    { value: 'like', label: 'contains' },
                    { value: 'not like', label: 'not contains' },
                    { value: '>', label: '>' },
                    { value: '>=', label: '>=' },
                    { value: '<', label: '<' },
                    { value: '<=', label: '<=' },
                    { value: 'between', label: 'between' }
                ];

            case 'Check':
                return [
                    { value: '=', label: '=' },
                    { value: 'like', label: 'contains' }
                ];

            default:
                return [
                    ...base_operators,
                    { value: 'like', label: 'contains' },
                    { value: 'not like', label: 'not contains' }
                ];
        }
    }

    update_value_input($value_input, fieldtype, options) {
        const operator = $value_input.closest('.filter-row').find('.filter-operator-select').val();
        
        // Remove existing enhanced inputs
        $value_input.siblings('.filter-value-enhanced').remove();
        $value_input.show();

        if (fieldtype === 'Select' && options) {
            // Create select dropdown for Select fields
            const select_options = options.split('\n').filter(opt => opt.trim());
            const $select = $(`<select class="form-control filter-value-enhanced"></select>`);
            $select.append('<option value="">Select...</option>');
            select_options.forEach(opt => {
                $select.append(`<option value="${opt.trim()}">${opt.trim()}</option>`);
            });
            $value_input.hide().after($select);
        } else if (fieldtype === 'Check') {
            // Create checkbox for Check fields
            const $select = $(`
                <select class="form-control filter-value-enhanced">
                    <option value="">Select...</option>
                    <option value="1">Yes</option>
                    <option value="0">No</option>
                </select>
            `);
            $value_input.hide().after($select);
        } else if (fieldtype === 'Date') {
            $value_input.attr('type', 'date');
        } else if (fieldtype === 'Datetime') {
            $value_input.attr('type', 'datetime-local');
        } else if (fieldtype === 'Time') {
            $value_input.attr('type', 'time');
        } else {
            $value_input.attr('type', 'text');
        }

        this.update_value_input_for_operator($value_input, operator);
    }

    update_value_input_for_operator($value_input, operator) {
        const $enhanced = $value_input.siblings('.filter-value-enhanced');
        const $active_input = $enhanced.length ? $enhanced : $value_input;

        if (operator === 'between') {
            // For between operator, create two inputs
            $active_input.attr('placeholder', 'From value');
            
            if (!$active_input.siblings('.between-to').length) {
                const $to_input = $active_input.clone().addClass('between-to').attr('placeholder', 'To value');
                $active_input.after($to_input);
            }
        } else if (operator === 'in' || operator === 'not in') {
            $active_input.attr('placeholder', 'Enter comma-separated values');
            $active_input.siblings('.between-to').remove();
        } else if (operator === 'is' || operator === 'is not') {
            $active_input.attr('placeholder', 'set, not set');
            $active_input.siblings('.between-to').remove();
        } else {
            $active_input.attr('placeholder', 'Enter value');
            $active_input.siblings('.between-to').remove();
        }
    }

    update_filter_field_options() {
        const available_fields = this.get_available_filter_fields();
        
        $('#custom-filters-container .filter-field-select').each(function() {
            const $select = $(this);
            const current_value = $select.val();
            
            $select.empty().append(`<option value="">${__('Select Field')}</option>`);
            
            available_fields.forEach(field => {
                let option_text;
                if (field.doctype === 'standard') {
                    option_text = field.label;
                } else if (field.doctype === 'common') {
                    option_text = `${field.label} (Common)`;
                } else if (field.is_child_table) {
                    option_text = `${field.label} (Child Table)`;
                } else {
                    option_text = `${field.label} (${field.doctype})`;
                }
                
                $select.append(`<option value="${field.fieldname}" 
                    data-fieldtype="${field.fieldtype}" 
                    data-options="${field.options || ''}"
                    data-is-child-table="${field.is_child_table || false}"
                    data-parent-table="${field.parent_table || ''}"
                    data-child-doctype="${field.child_doctype || ''}">${option_text}</option>`);
            });
            
            // Restore previous value if still available
            if (current_value && available_fields.some(f => f.fieldname === current_value)) {
                $select.val(current_value);
            }
        });
    }

    clear_all_filters() {
        $('#custom-filters-container').empty();
        this.show_empty_filters_state();
        this.update_filter_summary();
        // Reset preview when filters change
        $('#preview-stats').addClass('hidden');
        $('#btn-start').prop('disabled', true);
    }

    show_empty_filters_state() {
        const $container = $('#custom-filters-container');
        $container.removeClass('has-filters');
        $container.html(`
            <div class="empty-filters-message">
                <i class="fa fa-filter" style="font-size: 2em; color: #ccc; margin-bottom: 10px;"></i>
                <p>${__('No custom filters added yet.')}</p>
                <p class="text-muted">${__('Click "Add Filter" to create field-specific filters for precise document selection.')}</p>
            </div>
        `);
    }

    update_filter_summary() {
        const filters = this.get_custom_filters();
        const $summary = $('#filter-summary');
        const $tags = $summary.find('.filter-tags');
        
        if (filters.length === 0) {
            $summary.addClass('hidden');
            return;
        }

        $summary.removeClass('hidden');
        $tags.empty();

        const filter_mode = $('input[name="filter-mode"]:checked').val();
        
        filters.forEach((filter, index) => {
            if (filter.field && filter.operator && filter.value) {
                const $tag = $(`
                    <span class="filter-tag">
                        ${filter.field} ${filter.operator} ${filter.value}
                        <span class="remove-tag" data-filter-index="${index}">&times;</span>
                    </span>
                `);
                $tags.append($tag);
            }
        });

        // Add filter mode indicator
        if (filters.length > 1) {
            const $mode_tag = $(`
                <span class="filter-tag" style="background: #fff3cd; border-color: #ffeaa7; color: #856404;">
                    Mode: ${filter_mode}
                </span>
            `);
            $tags.prepend($mode_tag);
        }

        // Handle tag removal
        $tags.find('.remove-tag').on('click', function() {
            const index = $(this).data('filter-index');
            const $filter_rows = $('#custom-filters-container .filter-row');
            $filter_rows.eq(index).find('.remove-filter').click();
        });
    }

    get_custom_filters() {
        const filters = [];
        
        $('#custom-filters-container .filter-row').each(function() {
            const $row = $(this);
            const field = $row.find('.filter-field-select').val();
            const operator = $row.find('.filter-operator-select').val();
            
            let value;
            const $enhanced = $row.find('.filter-value-enhanced');
            if ($enhanced.length) {
                value = $enhanced.val();
            } else {
                value = $row.find('.filter-value-input').val();
                
                // Handle between operator
                const $between_to = $row.find('.between-to');
                if ($between_to.length && $between_to.val()) {
                    value = [value, $between_to.val()];
                }
            }
            
            if (field && operator && value) {
                filters.push({ field, operator, value });
            }
        });
        
        return filters;
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
            to_date: $('#to-date').val(),
            custom_filters: this.get_custom_filters(),
            filter_mode: $('input[name="filter-mode"]:checked').val()
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

    delete_draft_purchase_orders() {
        frappe.confirm(
            __('Are you sure you want to delete all draft Purchase Orders? This action cannot be undone.'),
            () => {
                const $progress = $('#utility-progress').removeClass('hidden');
                const $stats = $('.utility-stats');
                
                $stats.html(`
                    <div class="alert alert-info">
                        <i class="fa fa-spinner fa-spin"></i> Deleting draft Purchase Orders...
                    </div>
                `);

                frappe.call({
                    method: 'event_streaming.event_streaming.page.migration_dashboard.migration_dashboard.delete_draft_purchase_orders',
                    callback: (r) => {
                        if (r.message && r.message.status === 'success') {
                            $stats.html(`
                                <div class="alert alert-success">
                                    <i class="fa fa-check"></i> Successfully deleted ${r.message.deleted_count} draft Purchase Orders
                                </div>
                            `);
                            frappe.show_alert({
                                message: __('Draft Purchase Orders deleted successfully'),
                                indicator: 'green'
                            });
                        } else {
                            $stats.html(`
                                <div class="alert alert-danger">
                                    <i class="fa fa-times"></i> Error: ${r.message.message || 'Failed to delete draft Purchase Orders'}
                                </div>
                            `);
                            frappe.msgprint(r.message.message || __('Failed to delete draft Purchase Orders'));
                        }
                    },
                    error: (err) => {
                        $stats.html(`
                            <div class="alert alert-danger">
                                <i class="fa fa-times"></i> Error: ${err.message || 'Failed to delete draft Purchase Orders'}
                            </div>
                        `);
                    }
                });
            }
        );
    }

    submit_draft_purchase_orders() {
        frappe.confirm(
            __('Are you sure you want to submit all draft Purchase Orders? This action cannot be undone.'),
            () => {
                const $progress = $('#utility-progress').removeClass('hidden');
                const $stats = $('.utility-stats');
                
                $stats.html(`
                    <div class="alert alert-info">
                        <i class="fa fa-spinner fa-spin"></i> Submitting draft Purchase Orders...
                    </div>
                `);

                frappe.call({
                    method: 'event_streaming.event_streaming.page.migration_dashboard.migration_dashboard.submit_draft_purchase_orders',
                    callback: (r) => {
                        if (r.message && r.message.status === 'success') {
                            $stats.html(`
                                <div class="alert alert-success">
                                    <i class="fa fa-check"></i> Successfully submitted ${r.message.submitted_count} draft Purchase Orders
                                    ${r.message.errors && r.message.errors.length > 0 ? 
                                        `<br><small class="text-warning">Note: ${r.message.errors.length} submissions failed</small>` 
                                        : ''
                                    }
                                </div>
                            `);
                            frappe.show_alert({
                                message: __('Draft Purchase Orders submitted successfully'),
                                indicator: 'green'
                            });
                        } else {
                            $stats.html(`
                                <div class="alert alert-danger">
                                    <i class="fa fa-times"></i> Error: ${r.message.message || 'Failed to submit draft Purchase Orders'}
                                </div>
                            `);
                            frappe.msgprint(r.message.message || __('Failed to submit draft Purchase Orders'));
                        }
                    },
                    error: (err) => {
                        $stats.html(`
                            <div class="alert alert-danger">
                                <i class="fa fa-times"></i> Error: ${err.message || 'Failed to submit draft Purchase Orders'}
                            </div>
                        `);
                    }
                });
            }
        );
    }

    clear_document_locks() {
        frappe.confirm(
            __('Are you sure you want to clear all document locks? This will remove any existing locks that may be preventing document operations.'),
            () => {
                const $progress = $('#utility-progress').removeClass('hidden');
                const $stats = $('.utility-stats');
                
                $stats.html(`
                    <div class="alert alert-info">
                        <i class="fa fa-spinner fa-spin"></i> Clearing document locks...
                    </div>
                `);

                frappe.call({
                    method: 'event_streaming.event_streaming.page.migration_dashboard.migration_dashboard.clear_all_document_locks',
                    callback: (r) => {
                        if (r.message && r.message.status === 'success') {
                            $stats.html(`
                                <div class="alert alert-success">
                                    <i class="fa fa-check"></i> Successfully cleared ${r.message.cleared_count} document locks
                                </div>
                            `);
                            frappe.show_alert({
                                message: __('Document locks cleared successfully'),
                                indicator: 'green'
                            });
                        } else {
                            $stats.html(`
                                <div class="alert alert-danger">
                                    <i class="fa fa-times"></i> Error: ${r.message.message || 'Failed to clear document locks'}
                                </div>
                            `);
                            frappe.msgprint(r.message.message || __('Failed to clear document locks'));
                        }
                    },
                    error: (err) => {
                        $stats.html(`
                            <div class="alert alert-danger">
                                <i class="fa fa-times"></i> Error: ${err.message || 'Failed to clear document locks'}
                            </div>
                        `);
                    }
                });
            }
        );
    }

    // ============================================
    // ID-Based Migration Methods
    // ============================================

    populate_id_doctype_dropdown() {
        const producer = $('#event-producer').val();
        const $select = $('#id-doctype');
        
        $select.empty().append(`<option value="">${__("Select Document Type")}</option>`);
        
        if (!producer) {
            return;
        }

        frappe.call({
            method: 'event_streaming.event_streaming.page.migration_dashboard.migration_dashboard.get_producer_doctypes',
            args: { producer: producer },
            callback: (r) => {
                if (r.message) {
                    r.message.forEach(dt => {
                        $select.append(`<option value="${dt.ref_doctype}">${dt.ref_doctype}</option>`);
                    });
                }
            }
        });
    }

    handle_json_file_upload(event) {
        const file = event.target.files[0];
        
        if (!file) {
            return;
        }

        // Validate file type
        if (!file.name.endsWith('.json')) {
            frappe.msgprint({
                title: __('Invalid File'),
                message: __('Please upload a JSON file'),
                indicator: 'red'
            });
            $('#json-file-upload').val('');
            return;
        }

        // Read and parse JSON file
        const reader = new FileReader();
        reader.onload = (e) => {
            try {
                const content = e.target.result;
                const data = JSON.parse(content);
                
                // Validate that it's an array
                if (!Array.isArray(data)) {
                    frappe.msgprint({
                        title: __('Invalid JSON Format'),
                        message: __('JSON file must contain an array of document IDs. Example: ["PO-001", "PO-002"]'),
                        indicator: 'red'
                    });
                    $('#json-file-upload').val('');
                    return;
                }

                // Store the IDs
                this.json_document_ids = data;
                
                frappe.show_alert({
                    message: __('JSON file loaded: {0} IDs found', [data.length]),
                    indicator: 'green'
                });

                // Reset validation results
                $('#id-validation-results').addClass('hidden');
                $('#btn-start-id-migration').prop('disabled', true);

            } catch (error) {
                frappe.msgprint({
                    title: __('JSON Parse Error'),
                    message: __('Failed to parse JSON file: {0}', [error.message]),
                    indicator: 'red'
                });
                $('#json-file-upload').val('');
            }
        };

        reader.onerror = () => {
            frappe.msgprint({
                title: __('File Read Error'),
                message: __('Failed to read the file'),
                indicator: 'red'
            });
            $('#json-file-upload').val('');
        };

        reader.readAsText(file);
    }

    validate_json_ids() {
        const producer = $('#event-producer').val();
        const doctype = $('#id-doctype').val();
        const document_ids = this.json_document_ids;

        // Validation
        if (!producer) {
            frappe.msgprint(__('Please select an Event Producer'));
            return;
        }

        if (!doctype) {
            frappe.msgprint(__('Please select a Document Type'));
            return;
        }

        if (!document_ids || document_ids.length === 0) {
            frappe.msgprint(__('Please upload a JSON file with document IDs'));
            return;
        }

        // Show loading state
        const $results = $('#id-validation-results').removeClass('hidden');
        $results.html(`
            <div class="alert alert-info">
                <i class="fa fa-spinner fa-spin"></i> Validating ${document_ids.length} document IDs...
            </div>
        `);

        // Call backend to validate IDs
        frappe.call({
            method: 'event_streaming.event_streaming.page.migration_dashboard.migration_dashboard.validate_document_ids',
            args: {
                producer: producer,
                doctype: doctype,
                document_ids: document_ids
            },
            callback: (r) => {
                if (r.message && r.message.status === 'success') {
                    this.render_validation_results(r.message.validation);
                    $('#btn-start-id-migration').prop('disabled', false);
                } else {
                    $results.html(`
                        <div class="alert alert-danger">
                            <i class="fa fa-times"></i> ${r.message.message || __('Validation failed')}
                        </div>
                    `);
                }
            },
            error: (err) => {
                $results.html(`
                    <div class="alert alert-danger">
                        <i class="fa fa-times"></i> ${err.message || __('Validation failed')}
                    </div>
                `);
            }
        });
    }

    render_validation_results(validation) {
        const $results = $('#id-validation-results');
        
        let html = `
            <div class="alert alert-success">
                <i class="fa fa-check-circle"></i> <strong>${__('Validation Complete')}</strong>
            </div>
            
            <div class="validation-summary">
                <div class="validation-card success">
                    <div class="value">${validation.valid_count}</div>
                    <div class="label">${__('Valid IDs')}</div>
                </div>
                <div class="validation-card error">
                    <div class="value">${validation.invalid_count}</div>
                    <div class="label">${__('Invalid IDs')}</div>
                </div>
                <div class="validation-card">
                    <div class="value">${validation.total_count}</div>
                    <div class="label">${__('Total IDs')}</div>
                </div>
                <div class="validation-card">
                    <div class="value">${validation.estimated_batches}</div>
                    <div class="label">${__('Batches')}</div>
                </div>
            </div>
        `;

        if (validation.invalid_ids && validation.invalid_ids.length > 0) {
            html += `
                <div class="alert alert-warning" style="margin-top: 15px;">
                    <strong>${__('Invalid IDs (not found on producer):')}</strong>
                    <ul style="margin-top: 10px; max-height: 150px; overflow-y: auto;">
                        ${validation.invalid_ids.slice(0, 20).map(id => `<li>${id}</li>`).join('')}
                        ${validation.invalid_ids.length > 20 ? `<li><em>... and ${validation.invalid_ids.length - 20} more</em></li>` : ''}
                    </ul>
                </div>
            `;
        }

        if (validation.sample_docs && validation.sample_docs.length > 0) {
            html += `
                <div style="margin-top: 15px;">
                    <h6>${__('Sample Documents:')}</h6>
                    <table class="table table-bordered">
                        <thead>
                            <tr>
                                <th>${__('ID')}</th>
                                <th>${__('Created')}</th>
                                <th>${__('Modified')}</th>
                                <th>${__('Status')}</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${validation.sample_docs.map(doc => `
                                <tr>
                                    <td>${doc.name}</td>
                                    <td>${doc.creation || '-'}</td>
                                    <td>${doc.modified || '-'}</td>
                                    <td>${doc.docstatus == 0 ? 'Draft' : doc.docstatus == 1 ? 'Submitted' : 'Cancelled'}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            `;
        }

        $results.html(html);
    }

    start_id_migration() {
        const producer = $('#event-producer').val();
        const doctype = $('#id-doctype').val();
        const document_ids = this.json_document_ids;
        const batch_size = parseInt($('#id-batch-size').val()) || 50;

        if (!producer || !doctype || !document_ids || document_ids.length === 0) {
            frappe.msgprint(__('Please validate the IDs first'));
            return;
        }

        frappe.confirm(
            __('Are you sure you want to migrate {0} documents of type {1}? This will process them in batches of {2}.', 
                [document_ids.length, doctype, batch_size]),
            () => {
                // Show progress section
                $('#id-migration-progress').removeClass('hidden');
                const $stats = $('.id-migration-stats');
                
                $stats.html(`
                    <div class="alert alert-info">
                        <i class="fa fa-spinner fa-spin"></i> Starting ID-based migration...
                    </div>
                `);

                // Call backend to start migration
                frappe.call({
                    method: 'event_streaming.event_streaming.page.migration_dashboard.migration_dashboard.start_id_based_migration',
                    args: {
                        producer: producer,
                        doctype: doctype,
                        document_ids: document_ids,
                        batch_size: batch_size
                    },
                    callback: (r) => {
                        if (r.message && r.message.status === 'success') {
                            this.setup_id_migration_tracking(r.message.job_id);
                            frappe.show_alert({
                                message: __('ID-based migration started successfully'),
                                indicator: 'green'
                            });
                        } else {
                            $stats.html(`
                                <div class="alert alert-danger">
                                    <i class="fa fa-times"></i> ${r.message.message || __('Failed to start migration')}
                                </div>
                            `);
                        }
                    },
                    error: (err) => {
                        $stats.html(`
                            <div class="alert alert-danger">
                                <i class="fa fa-times"></i> ${err.message || __('Failed to start migration')}
                            </div>
                        `);
                    }
                });
            }
        );
    }

    setup_id_migration_tracking(job_id) {
        const $stats = $('.id-migration-stats');
        
        this.id_migration_interval = setInterval(() => {
            frappe.call({
                method: 'event_streaming.event_streaming.page.migration_dashboard.migration_dashboard.get_migration_job_progress',
                args: {
                    job_name: job_id
                },
                callback: (r) => {
                    if (r.message) {
                        const progress = r.message;
                        this.update_id_migration_ui(progress);

                        // Stop tracking if job is complete or failed
                        if (progress.status === 'Completed' || progress.status === 'Failed') {
                            clearInterval(this.id_migration_interval);
                        }
                    }
                }
            });
        }, 3000); // Update every 3 seconds
    }

    update_id_migration_ui(progress) {
        const $stats = $('.id-migration-stats');
        const start_time = progress.start_time ? frappe.datetime.str_to_user(progress.start_time) : '';
        const end_time = progress.end_time ? frappe.datetime.str_to_user(progress.end_time) : '';
        
        const processed = progress.processed_docs || 0;
        const total = progress.total_docs || 0;
        const percent = total ? Math.round((processed / total) * 100) : 0;
        
        let status_color = 'info';
        if (progress.status === 'Completed') status_color = 'success';
        if (progress.status === 'Failed') status_color = 'danger';
        
        let html = `
            <div class="alert alert-${status_color}">
                <h6><strong>${__('Status')}:</strong> ${progress.status || ''}</h6>
                <p><strong>${__('Progress')}:</strong> ${processed} / ${total} documents (${percent}%)</p>
                <div class="progress" style="height: 25px; margin-top: 10px;">
                    <div class="progress-bar progress-bar-striped ${progress.status === 'In Progress' ? 'active' : ''}" 
                         role="progressbar" 
                         style="width: ${percent}%;"
                         aria-valuenow="${percent}" aria-valuemin="0" aria-valuemax="100">
                        ${percent}%
                    </div>
                </div>
            </div>
            
            <div class="row" style="margin-top: 15px;">
                <div class="col-md-6">
                    <p><strong>${__('Start Time')}:</strong> ${start_time}</p>
                </div>
                <div class="col-md-6">
                    ${end_time ? `<p><strong>${__('End Time')}:</strong> ${end_time}</p>` : ''}
                </div>
            </div>
        `;

        if (progress.processed_by_doctype) {
            const doctype_data = Object.values(progress.processed_by_doctype)[0] || {};
            if (doctype_data.failed && doctype_data.failed > 0) {
                html += `
                    <div class="alert alert-warning" style="margin-top: 15px;">
                        <strong>${__('Failed Documents')}:</strong> ${doctype_data.failed}
                    </div>
                `;
            }
        }

        if (progress.error) {
            html += `
                <div class="alert alert-danger" style="margin-top: 15px;">
                    <h6>${__('Error')}</h6>
                    <pre style="max-height: 200px; overflow-y: auto;">${progress.error}</pre>
                </div>
            `;
        }

        $stats.html(html);
    }
}