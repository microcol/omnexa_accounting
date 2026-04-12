# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class TaxRule(Document):
	def validate(self):
		if getdate(self.valid_from) > getdate(self.valid_to):
			frappe.throw(_("Valid From must be on or before Valid To."), title=_("Validation"))
		self._validate_overlap()

	def _validate_overlap(self):
		filters = {"company": self.company, "tax_type": self.tax_type}
		if self.name:
			filters["name"] = ["!=", self.name]
		others = frappe.get_all("Tax Rule", filters=filters, fields=["name", "valid_from", "valid_to"])
		a0, b0 = getdate(self.valid_from), getdate(self.valid_to)
		for row in others:
			a1, b1 = getdate(row.valid_from), getdate(row.valid_to)
			if a0 <= b1 and a1 <= b0:
				frappe.throw(
					_("Tax Rule date range overlaps with {0}").format(row.name), title=_("Overlap")
				)
