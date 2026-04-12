# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from omnexa_accounting.utils.posting import assert_posting_date_open


class JournalEntry(Document):
	def validate(self):
		if self.docstatus == 0:
			self._validate_accounts()

	def on_submit(self):
		self._validate_balanced()
		self._validate_accounts()
		assert_posting_date_open(self.company, self.posting_date)

	def _validate_balanced(self):
		total_debit = sum(flt(r.debit) for r in self.accounts or [])
		total_credit = sum(flt(r.credit) for r in self.accounts or [])
		if flt(total_debit - total_credit, 2) != 0:
			frappe.throw(_("Total Debit must equal Total Credit."), title=_("Unbalanced"))

	def _validate_accounts(self):
		for row in self.accounts or []:
			if not row.account:
				continue
			if frappe.db.get_value("GL Account", row.account, "is_group"):
				frappe.throw(
					_("Row {0}: GL Account must be a leaf account.").format(row.idx),
					title=_("Invalid Account"),
				)
			acc_company = frappe.db.get_value("GL Account", row.account, "company")
			if acc_company != self.company:
				frappe.throw(
					_("Row {0}: Account belongs to a different company.").format(row.idx),
					title=_("Company"),
				)
