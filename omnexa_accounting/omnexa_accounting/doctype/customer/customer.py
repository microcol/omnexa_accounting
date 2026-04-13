# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class Customer(Document):
	def validate(self):
		if flt(self.credit_limit) < 0:
			frappe.throw(_("Credit limit cannot be negative."), title=_("Credit"))
		existing = frappe.db.get_value(
			"Customer",
			{"company": self.company, "customer_name": self.customer_name},
			"name",
		)
		if existing and (not self.name or existing != self.name):
			frappe.throw(
				_("Customer Name must be unique per company."),
				title=_("Duplicate"),
			)
