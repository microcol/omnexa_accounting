# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe import _
from frappe.utils.nestedset import NestedSet


class GLAccount(NestedSet):
	def validate(self):
		filters = {"company": self.company, "account_number": self.account_number}
		if self.name:
			filters["name"] = ["!=", self.name]
		if frappe.get_all("GL Account", filters=filters, limit=1):
			frappe.throw(
				_("Account Number {0} already exists for company {1}").format(
					self.account_number, self.company
				),
				title=_("Duplicate"),
			)
