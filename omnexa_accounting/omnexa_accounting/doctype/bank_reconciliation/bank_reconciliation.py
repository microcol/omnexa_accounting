# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from omnexa_accounting.utils.branch import validate_branch_company


class BankReconciliation(Document):
	def validate(self):
		validate_branch_company(self)
		self._validate_bank_account_company()
		self._recompute_balances()
		self._validate_status_consistency()

	def _validate_bank_account_company(self):
		if not self.bank_account:
			return
		bank_company = frappe.db.get_value("Bank Account", self.bank_account, "company")
		if not bank_company:
			frappe.throw(_("Bank Account does not exist."), title=_("Bank Account"))
		if bank_company != self.company:
			frappe.throw(_("Bank Account belongs to a different company."), title=_("Company"))

	def _recompute_balances(self):
		opening = flt(self.opening_balance)
		debits = flt(self.statement_debits)
		credits = flt(self.statement_credits)
		book_closing = flt(self.closing_balance_book)
		statement_closing = opening + debits - credits
		self.closing_balance_statement = statement_closing
		self.difference_amount = flt(book_closing - statement_closing)

	def _validate_status_consistency(self):
		has_difference = abs(flt(self.difference_amount)) > 0.0001
		if has_difference and self.status == "Reconciled":
			frappe.throw(
				_("Status cannot be Reconciled while difference amount is not zero."),
				title=_("Reconciliation"),
			)
		if not has_difference and self.status == "Open":
			frappe.throw(
				_("Status cannot remain Open when difference amount is zero."),
				title=_("Reconciliation"),
			)
