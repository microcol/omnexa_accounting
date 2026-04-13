# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class PipelineLead(Document):
	def validate(self):
		if self.customer and frappe.db.get_value("Customer", self.customer, "company") != self.company:
			frappe.throw(_("Customer belongs to a different company."), title=_("Lead"))
