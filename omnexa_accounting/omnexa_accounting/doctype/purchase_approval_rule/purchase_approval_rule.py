# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class PurchaseApprovalRule(Document):
	def validate(self):
		if flt(self.min_amount) < 0:
			frappe.throw(_("Min Amount cannot be negative."), title=_("Approval Rule"))
		if flt(self.max_amount) <= 0:
			frappe.throw(_("Max Amount must be greater than zero."), title=_("Approval Rule"))
		if flt(self.max_amount) < flt(self.min_amount):
			frappe.throw(_("Max Amount cannot be less than Min Amount."), title=_("Approval Rule"))
