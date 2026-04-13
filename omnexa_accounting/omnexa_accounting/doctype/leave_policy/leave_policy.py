# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class LeavePolicy(Document):
	def validate(self):
		if flt(self.annual_leave_days) < 0:
			frappe.throw(_("Annual Leave Days cannot be negative."), title=_("Leave Policy"))
