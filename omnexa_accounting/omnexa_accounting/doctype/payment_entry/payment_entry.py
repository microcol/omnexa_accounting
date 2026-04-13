# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from omnexa_accounting.utils.posting import assert_posting_date_open


class PaymentEntry(Document):
	def validate(self):
		self._validate_party()
		self._validate_bank_account()
		self._validate_mode_of_payment()
		self._validate_references()
		self._validate_allocations()

	def _validate_party(self):
		if not self.party_type or not self.party:
			return
		if self.party_type == "Customer":
			if not frappe.db.exists("Customer", self.party):
				frappe.throw(_("Customer {0} does not exist.").format(self.party), title=_("Party"))
			if frappe.db.get_value("Customer", self.party, "company") != self.company:
				frappe.throw(_("Customer belongs to a different company."), title=_("Party"))
		elif self.party_type == "Supplier":
			if not frappe.db.exists("Supplier", self.party):
				frappe.throw(_("Supplier {0} does not exist.").format(self.party), title=_("Party"))
			if frappe.db.get_value("Supplier", self.party, "company") != self.company:
				frappe.throw(_("Supplier belongs to a different company."), title=_("Party"))

	def on_submit(self):
		assert_posting_date_open(self.company, self.posting_date)

	def _validate_bank_account(self):
		if not self.bank_account:
			return
		ba_co = frappe.db.get_value("Bank Account", self.bank_account, "company")
		if ba_co != self.company:
			frappe.throw(_("Bank Account belongs to a different company."), title=_("Company"))

	def _validate_mode_of_payment(self):
		if not self.mode_of_payment:
			return
		mop_co = frappe.db.get_value("Mode of Payment", self.mode_of_payment, "company")
		if mop_co != self.company:
			frappe.throw(_("Mode of Payment belongs to a different company."), title=_("Company"))

	def _validate_references(self):
		for row in self.references or []:
			if not row.reference_doctype or not row.reference_name:
				continue
			if row.reference_doctype == "Sales Invoice":
				if self.party_type != "Customer":
					frappe.throw(
						_("Sales Invoice reference requires Party Type Customer."),
						title=_("Reference"),
					)
				if not frappe.db.exists("Sales Invoice", row.reference_name):
					frappe.throw(_("Sales Invoice {0} not found.").format(row.reference_name), title=_("Reference"))
				ref = frappe.get_doc("Sales Invoice", row.reference_name)
				if ref.docstatus != 1:
					frappe.throw(_("Referenced Sales Invoice must be submitted."), title=_("Reference"))
				if ref.company != self.company:
					frappe.throw(_("Referenced invoice company mismatch."), title=_("Reference"))
				if ref.customer != self.party:
					frappe.throw(_("Referenced Sales Invoice customer does not match Party."), title=_("Reference"))
			elif row.reference_doctype == "Purchase Invoice":
				if self.party_type != "Supplier":
					frappe.throw(
						_("Purchase Invoice reference requires Party Type Supplier."),
						title=_("Reference"),
					)
				if not frappe.db.exists("Purchase Invoice", row.reference_name):
					frappe.throw(
						_("Purchase Invoice {0} not found.").format(row.reference_name), title=_("Reference")
					)
				ref = frappe.get_doc("Purchase Invoice", row.reference_name)
				if ref.docstatus != 1:
					frappe.throw(_("Referenced Purchase Invoice must be submitted."), title=_("Reference"))
				if ref.company != self.company:
					frappe.throw(_("Referenced invoice company mismatch."), title=_("Reference"))
				if ref.supplier != self.party:
					frappe.throw(_("Referenced Purchase Invoice supplier does not match Party."), title=_("Reference"))
			else:
				frappe.throw(
					_("Reference DocType must be Sales Invoice or Purchase Invoice."),
					title=_("Reference"),
				)

	def _validate_allocations(self):
		total = sum(flt(r.allocated_amount) for r in self.references or [])
		if self.references and flt(total) > flt(self.paid_amount):
			frappe.throw(
				_("Total allocated amount cannot exceed Paid Amount."), title=_("Allocation")
			)
