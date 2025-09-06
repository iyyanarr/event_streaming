# Copyright (c) 2025, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
import json
from frappe.model.document import Document

class EventMigrationJob(Document):
    def validate(self):
        if self.from_date and self.to_date:
            if self.from_date > self.to_date:
                frappe.throw("From Date cannot be after To Date")

    def before_insert(self):
        if not self.selected_doctypes:
            frappe.throw("At least one Document Type must be selected")

        if not frappe.db.exists("Event Producer", self.producer):
            frappe.throw("Invalid Event Producer")