# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class Supplier(Document):
	def validate(self):
		existing = frappe.db.get_value(
			"Supplier",
			{"company": self.company, "supplier_name": self.supplier_name},
			"name",
		)
		if existing and (not self.name or existing != self.name):
			frappe.throw(
				_("Supplier Name must be unique per company."),
				title=_("Duplicate"),
			)
