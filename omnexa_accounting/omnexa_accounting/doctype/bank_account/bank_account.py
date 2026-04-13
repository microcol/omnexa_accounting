# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class BankAccount(Document):
	def validate(self):
		gl_co = frappe.db.get_value("GL Account", self.gl_account, "company")
		if gl_co != self.company:
			frappe.throw(_("GL Account must belong to the same company."), title=_("Company"))
		if frappe.db.get_value("GL Account", self.gl_account, "is_group"):
			frappe.throw(_("GL Account must be a leaf account (not a group)."), title=_("GL Account"))
		if self.currency:
			comp_curr = frappe.db.get_value("Company", self.company, "default_currency")
			if self.currency != comp_curr:
				frappe.throw(
					_("Bank Account currency must match the company default currency (MVP)."),
					title=_("Currency"),
				)
