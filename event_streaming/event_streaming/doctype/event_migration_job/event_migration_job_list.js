frappe.listview_settings["Event Migration Job"] = {
    get_indicator: function(doc) {
        const status_colors = {
            'Queued': 'orange',
            'In Progress': 'blue',
            'Completed': 'green',
            'Failed': 'red'
        };
        return [__(doc.status), status_colors[doc.status], "status,=," + doc.status];
    },

    formatters: {
        status: function(value) {
            const colors = {
                'Queued': 'var(--orange-600)',
                'In Progress': 'var(--blue-600)',
                'Completed': 'var(--green-600)',
                'Failed': 'var(--red-600)'
            };
            return `<span style="color: ${colors[value]}">${value}</span>`;
        }
    },

    onload: function(listview) {
        listview.page.add_menu_item(__("Show Migration Dashboard"), function() {
            frappe.set_route("migration-dashboard");
        });
    }
};