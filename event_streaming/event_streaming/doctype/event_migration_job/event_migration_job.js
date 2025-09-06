// Copyright (c) 2025, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Event Migration Job', {
    refresh: function(frm) {
        // Disable all fields once job starts
        if (frm.doc.status !== 'Queued') {
            frm.disable_form();
        }

        // Set status indicator
        frm.set_indicator_formatter('status', function(doc) {
            let indicator = 'orange';
            if (doc.status === 'Completed') {
                indicator = 'green';
            } else if (doc.status === 'Failed') {
                indicator = 'red';
            } else if (doc.status === 'In Progress') {
                indicator = 'blue';
            }
            return indicator;
        });

        // Add view dashboard button
        frm.add_custom_button(__('View Dashboard'), () => {
            frappe.set_route('migration-dashboard');
        });

        // Add a refresh progress button for active jobs
        if (frm.doc.status === 'In Progress') {
            frm.add_custom_button(__('Refresh Progress'), function() {
                frm.reload_doc();
            });
        }

        // Show progress indicator
        if (frm.doc.status) {
            let color = {
                'Queued': 'orange',
                'In Progress': 'blue',
                'Completed': 'green',
                'Failed': 'red'
            }[frm.doc.status];
            
            frm.page.set_indicator(__(frm.doc.status), color);
        }

        // Show progress bar 
        if (frm.doc.total_docs > 0) {
            let progress = (frm.doc.processed_docs / frm.doc.total_docs) * 100;
            frm.dashboard.add_progress('Migration Progress', progress);
        }

        // Show progress details
        if (frm.doc.processed_doctypes) {
            try {
                let processed = JSON.parse(frm.doc.processed_doctypes);
                let total = Object.values(processed).reduce((a, b) => a + b, 0);
                
                let html = `<div class="progress-stats">
                    <p><strong>${__('Total Documents Processed')}:</strong> ${total}</p>
                    <div class="doctype-progress">`;
                
                for (let [dt, count] of Object.entries(processed)) {
                    html += `<p>${dt}: ${count} ${__('documents')}</p>`;
                }
                
                html += '</div></div>';
                
                $(frm.fields_dict.progress_html.wrapper)
                    .html(html)
                    .find('.progress-stats')
                    .css({
                        'padding': '10px',
                        'background': 'var(--fg-color)',
                        'border-radius': '4px',
                        'margin-top': '10px'
                    });
            } catch (e) {
                console.error('Failed to parse progress', e);
            }
        }
    },

    date_filter_type: function(frm) {
        // Clear dates when filter type changes
        frm.set_value('from_date', '');
        frm.set_value('to_date', '');
    }
});