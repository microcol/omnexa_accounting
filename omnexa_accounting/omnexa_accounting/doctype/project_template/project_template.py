# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class ProjectTemplate(Document):
	def validate(self):
		if self.default_billing_rate and flt(self.default_billing_rate) < 0:
			frappe.throw(_("Default Billing Rate cannot be negative."), title=_("Project Template"))
		if self.customer:
			customer_company = frappe.db.get_value("Customer", self.customer, "company")
			if customer_company != self.company:
				frappe.throw(_("Customer belongs to a different company."), title=_("Project Template"))
		if self.default_income_account:
			account_company = frappe.db.get_value("GL Account", self.default_income_account, "company")
			if account_company != self.company:
				frappe.throw(_("Default Income Account belongs to a different company."), title=_("Project Template"))
