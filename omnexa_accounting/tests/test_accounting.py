# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate, today


class TestOmnexaAccounting(FrappeTestCase):
	def setUp(self):
		super().setUp()
		self._ensure_geo()
		self.company = self._create_company("OMNX-TEST")

	def _ensure_geo(self):
		if not frappe.db.exists("Currency", "EGP"):
			frappe.get_doc(
				{"doctype": "Currency", "currency_name": "EGP", "symbol": "E£", "enabled": 1}
			).insert(ignore_permissions=True)
		if not frappe.db.exists("Country", "Egypt"):
			frappe.get_doc(
				{"doctype": "Country", "country_name": "Egypt", "code": "EG"}
			).insert(ignore_permissions=True)

	def _create_company(self, abbr: str):
		if frappe.db.exists("Company", {"abbr": abbr}):
			return frappe.db.get_value("Company", {"abbr": abbr}, "name")
		doc = frappe.get_doc(
			{
				"doctype": "Company",
				"company_name": f"Test Co {abbr}",
				"abbr": abbr,
				"default_currency": "EGP",
				"country": "Egypt",
				"status": "Active",
			}
		)
		doc.insert(ignore_permissions=True)
		return doc.name

	def _gl(self, number, name, is_group=0, parent=None):
		d = frappe.new_doc("GL Account")
		d.company = self.company
		d.account_number = number
		d.account_name = name
		d.is_group = is_group
		d.parent_account = parent
		d.insert(ignore_permissions=True)
		return d.name

	def test_gl_duplicate_account_number(self):
		self._gl("1000", "Cash", 0)
		d2 = frappe.new_doc("GL Account")
		d2.company = self.company
		d2.account_number = "1000"
		d2.account_name = "Dup"
		d2.is_group = 0
		with self.assertRaises(frappe.ValidationError):
			d2.insert(ignore_permissions=True)

	def test_journal_unbalanced_rejected(self):
		leaf = self._gl("2000", "Bank", 0)
		je = frappe.new_doc("Journal Entry")
		je.company = self.company
		je.posting_date = today()
		je.append("accounts", {"account": leaf, "debit": 100, "credit": 0})
		je.append("accounts", {"account": leaf, "debit": 0, "credit": 50})
		je.insert(ignore_permissions=True)
		with self.assertRaises(frappe.ValidationError):
			je.submit()

	def test_frozen_period_blocks_journal(self):
		fy = frappe.new_doc("Fiscal Year")
		fy.title = "FY Test"
		fy.company = self.company
		fy.year_start_date = getdate(today())
		fy.year_end_date = add_days(getdate(today()), 365)
		fy.append(
			"periods",
			{
				"period_name": "P1",
				"period_start_date": fy.year_start_date,
				"period_end_date": fy.year_end_date,
				"frozen": 1,
			},
		)
		fy.insert(ignore_permissions=True)
		leaf = self._gl("3000", "Suspense", 0)
		je = frappe.new_doc("Journal Entry")
		je.company = self.company
		je.posting_date = today()
		je.append("accounts", {"account": leaf, "debit": 10, "credit": 0})
		je.append("accounts", {"account": leaf, "debit": 0, "credit": 10})
		je.insert(ignore_permissions=True)
		with self.assertRaises(frappe.ValidationError):
			je.submit()

	def test_tax_rule_overlap(self):
		head = self._gl("4000", "VAT", 0)
		d1 = frappe.new_doc("Tax Rule")
		d1.title = "TR1"
		d1.company = self.company
		d1.valid_from = "2026-01-01"
		d1.valid_to = "2026-12-31"
		d1.tax_type = "standard"
		d1.rate = 14
		d1.account_head = head
		d1.insert(ignore_permissions=True)
		d2 = frappe.new_doc("Tax Rule")
		d2.title = "TR2"
		d2.company = self.company
		d2.valid_from = "2026-06-01"
		d2.valid_to = "2026-06-30"
		d2.tax_type = "standard"
		d2.rate = 14
		d2.account_head = head
		with self.assertRaises(frappe.ValidationError):
			d2.insert(ignore_permissions=True)

	def test_payment_allocation_limit(self):
		pe = frappe.new_doc("Payment Entry")
		pe.company = self.company
		pe.party_type = "Customer"
		pe.party = "C1"
		pe.posting_date = today()
		pe.paid_amount = 50
		pe.append(
			"references",
			{
				"reference_doctype": "User",
				"reference_name": "Administrator",
				"allocated_amount": 100,
			},
		)
		with self.assertRaises(frappe.ValidationError):
			pe.insert(ignore_permissions=True)
