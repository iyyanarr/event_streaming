# Copyright (c) 2024, Shree Polymer and contributors
# License: MIT. See LICENSE

import frappe
from erpnext.manufacturing.doctype.work_order.work_order import WorkOrder

class CustomWorkOrder(WorkOrder):
	def create_job_card(self):
		"""
		Override to prevent automatic Job Card creation during sync.
		The 'from_live_sync' flag is set by the event_streaming app.
		"""
		if self.flags.from_live_sync:
			# Skip Job Card creation as they should be synced from the remote site.
			return
		
		# Procede with standard Job Card creation for local Work Orders.
		super().create_job_card()
