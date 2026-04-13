# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class CostCenter(Document):
	def validate(self):
		existing = frappe.db.get_value(
			"Cost Center",
			{"company": self.company, "cost_center_name": self.cost_center_name},
			"name",
		)
		if existing and (not self.name or existing != self.name):
			frappe.throw(
				_("Cost Center Name must be unique per company."),
				title=_("Duplicate"),
			)
