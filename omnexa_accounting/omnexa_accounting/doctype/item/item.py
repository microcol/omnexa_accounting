# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class Item(Document):
	def validate(self):
		existing = frappe.db.get_value(
			"Item",
			{"company": self.company, "item_code": self.item_code},
			"name",
		)
		if existing and (not self.name or existing != self.name):
			frappe.throw(_("Item Code must be unique per company."), title=_("Duplicate"))
