# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import hashlib

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, cint, flt, getdate

from omnexa_core.omnexa_core.constants import DOC_STATUS_QUEUED
from omnexa_accounting.utils.currency import apply_multi_currency_to_invoice
from omnexa_accounting.utils.party import get_effective_credit_days
from omnexa_accounting.utils.posting import assert_posting_date_open


class SalesInvoice(Document):
	def validate(self):
		self._apply_due_date_from_party()
		self._validate_customer_company()
		self._validate_due_date()
		self._validate_return()
		self._sync_and_validate_line_items()
		self._set_amounts()
		apply_multi_currency_to_invoice(self)
		self._validate_payment_schedule()
		self._validate_tax_rules()
		self._validate_item_cost_centers()
		self._set_outstanding_amount()

	def _apply_due_date_from_party(self):
		if self.due_date or self.is_return or not self.customer:
			return
		days = get_effective_credit_days("Customer", self.customer)
		if days > 0:
			self.due_date = add_days(getdate(self.posting_date), days)

	def _validate_customer_company(self):
		if not self.customer:
			return
		c_company = frappe.db.get_value("Customer", self.customer, "company")
		if c_company != self.company:
			frappe.throw(_("Customer belongs to a different company."), title=_("Company"))

	def _validate_due_date(self):
		if not self.due_date:
			return
		if getdate(self.due_date) < getdate(self.posting_date):
			frappe.throw(_("Due Date cannot be before Posting Date."), title=_("Due Date"))

	def _validate_return(self):
		if not self.is_return:
			self.return_against = None
			return
		if not self.return_against:
			frappe.throw(_("Return Against is required for a credit note."), title=_("Return"))
		orig = frappe.get_doc("Sales Invoice", self.return_against)
		if orig.docstatus != 1:
			frappe.throw(_("Return Against must be a submitted Sales Invoice."), title=_("Return"))
		if orig.company != self.company:
			frappe.throw(_("Original invoice must belong to the same company."), title=_("Return"))
		if orig.customer != self.customer:
			frappe.throw(
				_("Credit note customer must match the original invoice customer."),
				title=_("Return"),
			)
		if orig.get("is_return"):
			frappe.throw(_("Cannot return against another credit note (MVP)."), title=_("Return"))

	def _sync_and_validate_line_items(self):
		for row in self.items or []:
			if not row.item and (not row.item_code or not str(row.item_code).strip()):
				frappe.throw(
					_("Row {0}: Set Item or Item Code.").format(row.idx),
					title=_("Items"),
				)
			if not row.item:
				continue
			it = frappe.get_cached_doc("Item", row.item)
			if it.company != self.company:
				frappe.throw(
					_("Row {0}: Item belongs to a different company.").format(row.idx),
					title=_("Item"),
				)
			if it.disabled:
				frappe.throw(_("Row {0}: Item is disabled.").format(row.idx), title=_("Item"))
			if not it.is_sales_item:
				frappe.throw(
					_("Row {0}: Item cannot be sold (Is Sales Item is off).").format(row.idx),
					title=_("Item"),
				)
			if not row.item_code:
				row.item_code = it.item_code
			elif row.item_code != it.item_code:
				frappe.throw(
					_("Row {0}: Item Code must match the selected Item.").format(row.idx),
					title=_("Item"),
				)

	def on_submit(self):
		assert_posting_date_open(self.company, self.posting_date)
		self._check_credit_limit()
		self._enqueue_eta_submission()

	def _set_amounts(self):
		net = 0
		tax = 0
		for row in self.items or []:
			line_net = flt(row.qty) * flt(row.rate)
			row.amount = line_net
			net += line_net
			rule_name = row.tax_rule or self.default_tax_rule
			if rule_name:
				rule = frappe.get_doc("Tax Rule", rule_name)
				if getdate(self.posting_date) < getdate(rule.valid_from) or getdate(
					self.posting_date
				) > getdate(rule.valid_to):
					frappe.throw(
						_("Row {0}: Tax Rule {1} is not valid on posting date.").format(row.idx, rule_name),
						title=_("Tax"),
					)
				if rule.tax_type == "standard" and flt(rule.rate):
					tax += line_net * flt(rule.rate) / 100.0
		self.net_total = net
		self.tax_total = tax
		self.grand_total = net + tax

	def _set_outstanding_amount(self):
		if not self.name:
			self.outstanding_amount = flt(self.grand_total)
			return
		allocated = frappe.db.sql(
			"""
			SELECT COALESCE(SUM(per.allocated_amount), 0)
			FROM `tabPayment Entry Reference` per
			INNER JOIN `tabPayment Entry` pe ON pe.name = per.parent
			WHERE per.reference_doctype = 'Sales Invoice'
				AND per.reference_name = %s
				AND pe.docstatus = 1
				AND per.parenttype = 'Payment Entry'
			""",
			(self.name,),
		)
		allocated_amount = flt(allocated[0][0] if allocated else 0)
		self.outstanding_amount = max(flt(self.grand_total) - allocated_amount, 0)

	def _validate_payment_schedule(self):
		if not self.payment_schedule:
			return
		total_schedule = 0
		max_due_date = None
		for row in self.payment_schedule:
			if getdate(row.due_date) < getdate(self.posting_date):
				frappe.throw(
					_("Payment Schedule row {0}: Due Date cannot be before Posting Date.").format(row.idx),
					title=_("Payment Schedule"),
				)
			if flt(row.payment_amount) <= 0:
				frappe.throw(
					_("Payment Schedule row {0}: Payment Amount must be greater than zero.").format(row.idx),
					title=_("Payment Schedule"),
				)
			total_schedule += flt(row.payment_amount)
			if max_due_date is None or getdate(row.due_date) > getdate(max_due_date):
				max_due_date = row.due_date
		if abs(flt(total_schedule) - flt(self.grand_total)) > 0.0001:
			frappe.throw(
				_("Payment Schedule total must equal Grand Total."),
				title=_("Payment Schedule"),
			)
		self.due_date = max_due_date

	def _validate_tax_rules(self):
		if self.default_tax_rule:
			if frappe.db.get_value("Tax Rule", self.default_tax_rule, "company") != self.company:
				frappe.throw(_("Default Tax Rule must belong to the same company."), title=_("Tax"))
		for row in self.items or []:
			if row.income_account and frappe.db.get_value("GL Account", row.income_account, "company") != self.company:
				frappe.throw(_("Row {0}: GL Account company mismatch.").format(row.idx), title=_("GL"))

	def _validate_item_cost_centers(self):
		for row in self.items or []:
			if not row.cost_center:
				continue
			cc_co = frappe.db.get_value("Cost Center", row.cost_center, "company")
			if cc_co != self.company:
				frappe.throw(
					_("Row {0}: Cost Center belongs to a different company.").format(row.idx),
					title=_("Cost Center"),
				)

	def _check_credit_limit(self):
		if self.is_return:
			return
		limit = flt(frappe.db.get_value("Customer", self.customer, "credit_limit"))
		if limit > 0 and flt(self.grand_total) > limit:
			if cint(getattr(self, "credit_limit_override_approved", 0)):
				if not (getattr(self, "credit_limit_override_reason", "") or "").strip():
					frappe.throw(
						_("Credit limit override reason is required."),
						title=_("Credit"),
					)
				if not self._can_approve_credit_limit_override():
					frappe.throw(
						_("Credit limit override can only be approved by Accounts Manager or System Manager."),
						title=_("Credit"),
					)
				return
			frappe.throw(
				_("Invoice grand total exceeds the customer's credit limit."),
				title=_("Credit"),
			)

	def _can_approve_credit_limit_override(self):
		roles = set(frappe.get_roles(frappe.session.user))
		return bool({"Accounts Manager", "System Manager"} & roles)

	def _enqueue_eta_submission(self):
		if self.is_return:
			return
		if not frappe.db.get_value("Company", self.company, "eta_einvoice_enabled"):
			return
		cust_label = frappe.db.get_value("Customer", self.customer, "customer_name") or self.customer
		payload = f"{self.doctype}|{self.name}|{self.posting_date}|{self.grand_total}|{cust_label}".encode()
		h = hashlib.sha256(payload).hexdigest()
		doc = frappe.new_doc("E-Document Submission")
		doc.company = self.company
		doc.reference_doctype = self.doctype
		doc.reference_name = self.name
		doc.payload_hash = h
		doc.authority_operation = "submit"
		doc.authority_status = DOC_STATUS_QUEUED
		doc.insert(ignore_permissions=True)
		doc.submit()
