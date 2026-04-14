# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate

from omnexa_accounting.utils.branch import validate_branch_company
from omnexa_accounting.utils.posting import assert_posting_date_open


class PaymentEntry(Document):
	def validate(self):
		validate_branch_company(self)
		self._validate_party()
		self._validate_bank_account()
		self._validate_mode_of_payment()
		self._validate_remittance_metadata()
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
		self._update_reference_outstanding_amounts()

	def on_cancel(self):
		self._update_reference_outstanding_amounts()

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

	def _validate_remittance_metadata(self):
		if not (
			self.remittance_reference
			or self.remittance_date
			or self.remittance_bank_reference
		):
			return
		if not self.remittance_reference:
			frappe.throw(_("Remittance Reference is required when remittance metadata is set."), title=_("Remittance"))
		if not self.remittance_date:
			frappe.throw(_("Remittance Date is required when remittance metadata is set."), title=_("Remittance"))
		if getdate(self.remittance_date) > getdate(self.posting_date):
			frappe.throw(_("Remittance Date cannot be after Posting Date."), title=_("Remittance"))
		if not self.mode_of_payment:
			frappe.throw(_("Mode of Payment is required when remittance metadata is set."), title=_("Remittance"))
		mop_type = frappe.db.get_value("Mode of Payment", self.mode_of_payment, "type")
		if mop_type in {"Bank", "Wire", "Cheque"} and not self.bank_account:
			frappe.throw(
				_("Bank Account is required for bank remittance modes."),
				title=_("Remittance"),
			)

	def _validate_references(self):
		seen = set()
		for row in self.references or []:
			if not row.reference_doctype or not row.reference_name:
				continue
			key = (row.reference_doctype, row.reference_name)
			if key in seen:
				frappe.throw(
					_("Duplicate reference row for {0} {1}.").format(row.reference_doctype, row.reference_name),
					title=_("Reference"),
				)
			seen.add(key)
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
		for row in self.references or []:
			if flt(row.allocated_amount) <= 0:
				frappe.throw(
					_("Allocated Amount must be greater than zero in row {0}.").format(row.idx),
					title=_("Allocation"),
				)
			ref_total = flt(
				frappe.db.get_value(row.reference_doctype, row.reference_name, "grand_total") or 0
			)
			already_allocated = self._get_submitted_allocated_amount(
				row.reference_doctype, row.reference_name, exclude_current=True
			)
			remaining = ref_total - already_allocated
			if flt(row.allocated_amount) > flt(remaining):
				frappe.throw(
					_(
						"Allocated Amount in row {0} exceeds outstanding reference amount."
					).format(row.idx),
					title=_("Allocation"),
				)
		total = sum(flt(r.allocated_amount) for r in self.references or [])
		if self.references and flt(total) > flt(self.paid_amount):
			frappe.throw(
				_("Total allocated amount cannot exceed Paid Amount."), title=_("Allocation")
			)

	def _get_submitted_allocated_amount(self, reference_doctype, reference_name, exclude_current=False):
		conditions = [
			"per.reference_doctype = %(reference_doctype)s",
			"per.reference_name = %(reference_name)s",
			"pe.docstatus = 1",
			"per.parenttype = 'Payment Entry'",
		]
		params = {
			"reference_doctype": reference_doctype,
			"reference_name": reference_name,
		}
		if exclude_current and self.name:
			conditions.append("pe.name != %(parent_name)s")
			params["parent_name"] = self.name
		result = frappe.db.sql(
			f"""
			SELECT COALESCE(SUM(per.allocated_amount), 0)
			FROM `tabPayment Entry Reference` per
			INNER JOIN `tabPayment Entry` pe ON pe.name = per.parent
			WHERE {' AND '.join(conditions)}
			""",
			params,
		)
		return flt(result[0][0] if result else 0)

	def _update_reference_outstanding_amounts(self):
		refs = {(r.reference_doctype, r.reference_name) for r in (self.references or []) if r.reference_doctype and r.reference_name}
		for reference_doctype, reference_name in refs:
			grand_total = flt(
				frappe.db.get_value(reference_doctype, reference_name, "grand_total") or 0
			)
			allocated = self._get_submitted_allocated_amount(reference_doctype, reference_name)
			outstanding = max(flt(grand_total - allocated), 0)
			frappe.db.set_value(
				reference_doctype,
				reference_name,
				"outstanding_amount",
				outstanding,
				update_modified=False,
			)
