# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class UOM(Document):
	def validate(self):
		existing = frappe.db.get_value("UOM", {"uom_name": self.uom_name}, "name")
		if existing and (not self.name or existing != self.name):
			frappe.throw(_("UOM Name must be unique."), title=_("Duplicate"))
