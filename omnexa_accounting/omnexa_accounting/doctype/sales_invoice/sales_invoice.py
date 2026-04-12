# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import hashlib

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate

from omnexa_accounting.utils.posting import assert_posting_date_open


class SalesInvoice(Document):
	def validate(self):
		self._set_amounts()
		self._validate_tax_rules()

	def on_submit(self):
		assert_posting_date_open(self.company, self.posting_date)
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

	def _validate_tax_rules(self):
		if self.default_tax_rule:
			if frappe.db.get_value("Tax Rule", self.default_tax_rule, "company") != self.company:
				frappe.throw(_("Default Tax Rule must belong to the same company."), title=_("Tax"))
		for row in self.items or []:
			if row.income_account and frappe.db.get_value("GL Account", row.income_account, "company") != self.company:
				frappe.throw(_("Row {0}: GL Account company mismatch.").format(row.idx), title=_("GL"))

	def _enqueue_eta_submission(self):
		if not frappe.db.get_value("Company", self.company, "eta_einvoice_enabled"):
			return
		payload = f"{self.doctype}|{self.name}|{self.posting_date}|{self.grand_total}".encode()
		h = hashlib.sha256(payload).hexdigest()
		doc = frappe.new_doc("E-Document Submission")
		doc.company = self.company
		doc.reference_doctype = self.doctype
		doc.reference_name = self.name
		doc.payload_hash = h
		doc.authority_status = "Queued"
		doc.insert(ignore_permissions=True)
		doc.submit()
