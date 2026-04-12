# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from omnexa_accounting.utils.posting import assert_posting_date_open


class PaymentEntry(Document):
	def validate(self):
		self._validate_allocations()

	def on_submit(self):
		assert_posting_date_open(self.company, self.posting_date)

	def _validate_allocations(self):
		total = sum(flt(r.allocated_amount) for r in self.references or [])
		if self.references and flt(total) > flt(self.paid_amount):
			frappe.throw(
				_("Total allocated amount cannot exceed Paid Amount."), title=_("Allocation")
			)
