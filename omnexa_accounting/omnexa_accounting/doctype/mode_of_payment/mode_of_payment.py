# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class ModeofPayment(Document):
	def validate(self):
		existing = frappe.db.get_value(
			"Mode of Payment",
			{"company": self.company, "mode_name": self.mode_name},
			"name",
		)
		if existing and (not self.name or existing != self.name):
			frappe.throw(_("Mode Name must be unique per company."), title=_("Duplicate"))
