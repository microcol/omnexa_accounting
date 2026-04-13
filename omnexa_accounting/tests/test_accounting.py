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

	def _gl(self, number, name, is_group=0, parent=None, company=None):
		d = frappe.new_doc("GL Account")
		d.company = company or self.company
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
		frz_co = self._create_company("OMNX-FRZ")
		fy = frappe.new_doc("Fiscal Year")
		fy.title = "FY Test"
		fy.company = frz_co
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
		leaf = self._gl("3000", "Suspense", 0, company=frz_co)
		je = frappe.new_doc("Journal Entry")
		je.company = frz_co
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
		cust = frappe.new_doc("Customer")
		cust.company = self.company
		cust.customer_name = "C1"
		cust.insert(ignore_permissions=True)
		leaf = self._gl("5500", "Revenue Pay", 0)
		si = frappe.new_doc("Sales Invoice")
		si.company = self.company
		si.customer = cust.name
		si.posting_date = today()
		si.append("items", {"item_code": "line", "qty": 1, "rate": 200, "income_account": leaf})
		si.insert(ignore_permissions=True)
		si.submit()
		pe = frappe.new_doc("Payment Entry")
		pe.company = self.company
		pe.party_type = "Customer"
		pe.party = cust.name
		pe.posting_date = today()
		pe.paid_amount = 50
		pe.append(
			"references",
			{
				"reference_doctype": "Sales Invoice",
				"reference_name": si.name,
				"allocated_amount": 100,
			},
		)
		with self.assertRaises(frappe.ValidationError):
			pe.insert(ignore_permissions=True)

	def test_customer_name_unique_per_company(self):
		c1 = frappe.new_doc("Customer")
		c1.company = self.company
		c1.customer_name = "SameName"
		c1.insert(ignore_permissions=True)
		c2 = frappe.new_doc("Customer")
		c2.company = self.company
		c2.customer_name = "SameName"
		with self.assertRaises(frappe.ValidationError):
			c2.insert(ignore_permissions=True)

	def test_sales_invoice_customer_must_match_company(self):
		other = self._create_company("OMNX-OTH")
		c = frappe.new_doc("Customer")
		c.company = other
		c.customer_name = "OtherCoCust"
		c.insert(ignore_permissions=True)
		leaf = self._gl("5100", "Revenue X", 0)
		si = frappe.new_doc("Sales Invoice")
		si.company = self.company
		si.customer = c.name
		si.posting_date = today()
		si.append("items", {"item_code": "line", "qty": 1, "rate": 1, "income_account": leaf})
		with self.assertRaises(frappe.ValidationError):
			si.insert(ignore_permissions=True)

	def _ensure_usd(self):
		if not frappe.db.exists("Currency", "USD"):
			frappe.get_doc(
				{"doctype": "Currency", "currency_name": "USD", "symbol": "$", "enabled": 1}
			).insert(ignore_permissions=True)

	def _ensure_uom(self, name="Nos"):
		if not frappe.db.exists("UOM", name):
			frappe.get_doc({"doctype": "UOM", "uom_name": name}).insert(ignore_permissions=True)
		return name

	def test_sales_invoice_multi_currency_from_exchange_rate(self):
		self._ensure_usd()
		frappe.get_doc(
			{
				"doctype": "Currency Exchange Rate",
				"company": self.company,
				"exchange_date": today(),
				"from_currency": "USD",
				"to_currency": "EGP",
				"exchange_rate": 50.0,
			}
		).insert(ignore_permissions=True)
		cust = frappe.new_doc("Customer")
		cust.company = self.company
		cust.customer_name = "FX Cust"
		cust.insert(ignore_permissions=True)
		leaf = self._gl("5200", "Revenue FX", 0)
		si = frappe.new_doc("Sales Invoice")
		si.company = self.company
		si.customer = cust.name
		si.posting_date = today()
		si.currency = "USD"
		si.conversion_rate = 1.0
		si.append("items", {"item_code": "line", "qty": 2, "rate": 10, "income_account": leaf})
		si.insert(ignore_permissions=True)
		self.assertEqual(si.conversion_rate, 50.0)
		self.assertEqual(si.grand_total, 20)
		self.assertEqual(si.base_grand_total, 1000.0)

	def test_sales_invoice_foreign_currency_without_rate_raises(self):
		self._ensure_usd()
		cust = frappe.new_doc("Customer")
		cust.company = self.company
		cust.customer_name = "No FX"
		cust.insert(ignore_permissions=True)
		leaf = self._gl("5210", "Revenue NF", 0)
		si = frappe.new_doc("Sales Invoice")
		si.company = self.company
		si.customer = cust.name
		si.posting_date = today()
		si.currency = "USD"
		si.conversion_rate = 1.0
		si.append("items", {"item_code": "line", "qty": 1, "rate": 1, "income_account": leaf})
		with self.assertRaises(frappe.ValidationError):
			si.insert(ignore_permissions=True)

	def test_credit_limit_blocks_submit(self):
		cust = frappe.new_doc("Customer")
		cust.company = self.company
		cust.customer_name = "Limited Co"
		cust.credit_limit = 50
		cust.insert(ignore_permissions=True)
		leaf = self._gl("5300", "Revenue L", 0)
		si = frappe.new_doc("Sales Invoice")
		si.company = self.company
		si.customer = cust.name
		si.posting_date = today()
		si.append("items", {"item_code": "line", "qty": 1, "rate": 100, "income_account": leaf})
		si.insert(ignore_permissions=True)
		with self.assertRaises(frappe.ValidationError):
			si.submit()

	def test_cost_center_company_mismatch_on_invoice_line(self):
		other = self._create_company("OMNX-CC")
		cc = frappe.new_doc("Cost Center")
		cc.company = other
		cc.cost_center_name = "Other CC"
		cc.insert(ignore_permissions=True)
		cust = frappe.new_doc("Customer")
		cust.company = self.company
		cust.customer_name = "CC test"
		cust.insert(ignore_permissions=True)
		leaf = self._gl("5400", "Revenue CC", 0)
		si = frappe.new_doc("Sales Invoice")
		si.company = self.company
		si.customer = cust.name
		si.posting_date = today()
		si.append(
			"items",
			{
				"item_code": "line",
				"qty": 1,
				"rate": 1,
				"income_account": leaf,
				"cost_center": cc.name,
			},
		)
		with self.assertRaises(frappe.ValidationError):
			si.insert(ignore_permissions=True)

	def test_bank_account_rejects_group_gl(self):
		grp = self._gl("6000", "Bank Parent", 1)
		ba = frappe.new_doc("Bank Account")
		ba.company = self.company
		ba.account_title = "Main"
		ba.gl_account = grp
		with self.assertRaises(frappe.ValidationError):
			ba.insert(ignore_permissions=True)

	def test_payment_entry_reference_customer_mismatch(self):
		c1 = frappe.new_doc("Customer")
		c1.company = self.company
		c1.customer_name = "Payer A"
		c1.insert(ignore_permissions=True)
		c2 = frappe.new_doc("Customer")
		c2.company = self.company
		c2.customer_name = "Invoice B"
		c2.insert(ignore_permissions=True)
		leaf = self._gl("5600", "Rev PE", 0)
		si = frappe.new_doc("Sales Invoice")
		si.company = self.company
		si.customer = c2.name
		si.posting_date = today()
		si.append("items", {"item_code": "x", "qty": 1, "rate": 10, "income_account": leaf})
		si.insert(ignore_permissions=True)
		si.submit()
		pe = frappe.new_doc("Payment Entry")
		pe.company = self.company
		pe.party_type = "Customer"
		pe.party = c1.name
		pe.posting_date = today()
		pe.paid_amount = 10
		pe.append(
			"references",
			{"reference_doctype": "Sales Invoice", "reference_name": si.name, "allocated_amount": 10},
		)
		with self.assertRaises(frappe.ValidationError):
			pe.insert(ignore_permissions=True)

	def test_sales_credit_note_validates_return_against(self):
		cust = frappe.new_doc("Customer")
		cust.company = self.company
		cust.customer_name = "CN Cust"
		cust.insert(ignore_permissions=True)
		leaf = self._gl("5700", "Rev CN", 0)
		orig = frappe.new_doc("Sales Invoice")
		orig.company = self.company
		orig.customer = cust.name
		orig.posting_date = today()
		orig.append("items", {"item_code": "a", "qty": 1, "rate": 50, "income_account": leaf})
		orig.insert(ignore_permissions=True)
		orig.submit()
		cn = frappe.new_doc("Sales Invoice")
		cn.company = self.company
		cn.customer = cust.name
		cn.posting_date = today()
		cn.is_return = 1
		cn.return_against = orig.name
		cn.append("items", {"item_code": "a", "qty": 1, "rate": 10, "income_account": leaf})
		cn.insert(ignore_permissions=True)
		cn.submit()

	def test_sales_credit_note_skips_credit_limit(self):
		cust = frappe.new_doc("Customer")
		cust.company = self.company
		cust.customer_name = "CN Limited"
		cust.credit_limit = 30
		cust.insert(ignore_permissions=True)
		leaf = self._gl("5800", "Rev CNL", 0)
		orig = frappe.new_doc("Sales Invoice")
		orig.company = self.company
		orig.customer = cust.name
		orig.posting_date = today()
		orig.append("items", {"item_code": "a", "qty": 1, "rate": 5, "income_account": leaf})
		orig.insert(ignore_permissions=True)
		orig.submit()
		cn = frappe.new_doc("Sales Invoice")
		cn.company = self.company
		cn.customer = cust.name
		cn.posting_date = today()
		cn.is_return = 1
		cn.return_against = orig.name
		cn.append("items", {"item_code": "a", "qty": 1, "rate": 100, "income_account": leaf})
		cn.insert(ignore_permissions=True)
		cn.submit()

	def test_item_code_unique_per_company(self):
		self._ensure_uom()
		i1 = frappe.new_doc("Item")
		i1.item_code = "SKU-DUP"
		i1.item_name = "One"
		i1.company = self.company
		i1.stock_uom = "Nos"
		i1.insert(ignore_permissions=True)
		i2 = frappe.new_doc("Item")
		i2.item_code = "SKU-DUP"
		i2.item_name = "Two"
		i2.company = self.company
		i2.stock_uom = "Nos"
		with self.assertRaises(frappe.ValidationError):
			i2.insert(ignore_permissions=True)

	def test_supplier_name_unique_per_company(self):
		s1 = frappe.new_doc("Supplier")
		s1.company = self.company
		s1.supplier_name = "DupSupp"
		s1.insert(ignore_permissions=True)
		s2 = frappe.new_doc("Supplier")
		s2.company = self.company
		s2.supplier_name = "DupSupp"
		with self.assertRaises(frappe.ValidationError):
			s2.insert(ignore_permissions=True)

	def test_sales_invoice_line_item_company_mismatch(self):
		self._ensure_uom()
		other = self._create_company("OMNX-ITM")
		it = frappe.new_doc("Item")
		it.item_code = "OTH-SKU"
		it.item_name = "OtherCo Item"
		it.company = other
		it.stock_uom = "Nos"
		it.insert(ignore_permissions=True)
		cust = frappe.new_doc("Customer")
		cust.company = self.company
		cust.customer_name = "ItemCoTest"
		cust.insert(ignore_permissions=True)
		leaf = self._gl("5920", "Rev ITM", 0)
		si = frappe.new_doc("Sales Invoice")
		si.company = self.company
		si.customer = cust.name
		si.posting_date = today()
		si.append(
			"items",
			{
				"item": it.name,
				"item_code": it.item_code,
				"qty": 1,
				"rate": 1,
				"income_account": leaf,
			},
		)
		with self.assertRaises(frappe.ValidationError):
			si.insert(ignore_permissions=True)

	def test_sales_invoice_syncs_item_code_from_item_link(self):
		self._ensure_uom()
		it = frappe.new_doc("Item")
		it.item_code = "SKU-AUTO"
		it.item_name = "Auto"
		it.company = self.company
		it.stock_uom = "Nos"
		it.insert(ignore_permissions=True)
		cust = frappe.new_doc("Customer")
		cust.company = self.company
		cust.customer_name = "SyncCust"
		cust.insert(ignore_permissions=True)
		leaf = self._gl("5930", "Rev SYN", 0)
		si = frappe.new_doc("Sales Invoice")
		si.company = self.company
		si.customer = cust.name
		si.posting_date = today()
		si.append(
			"items",
			{"item": it.name, "item_code": "", "qty": 1, "rate": 2, "income_account": leaf},
		)
		si.insert(ignore_permissions=True)
		self.assertEqual(si.items[0].item_code, "SKU-AUTO")

	def test_item_not_sales_item_blocked_on_sales_invoice(self):
		self._ensure_uom()
		it = frappe.new_doc("Item")
		it.item_code = "RAW-1"
		it.item_name = "Raw"
		it.company = self.company
		it.stock_uom = "Nos"
		it.is_sales_item = 0
		it.insert(ignore_permissions=True)
		cust = frappe.new_doc("Customer")
		cust.company = self.company
		cust.customer_name = "NoSale"
		cust.insert(ignore_permissions=True)
		leaf = self._gl("5940", "Rev NS", 0)
		si = frappe.new_doc("Sales Invoice")
		si.company = self.company
		si.customer = cust.name
		si.posting_date = today()
		si.append(
			"items",
			{"item": it.name, "item_code": "RAW-1", "qty": 1, "rate": 1, "income_account": leaf},
		)
		with self.assertRaises(frappe.ValidationError):
			si.insert(ignore_permissions=True)

	def test_purchase_debit_note_return_against(self):
		supp = frappe.new_doc("Supplier")
		supp.company = self.company
		supp.supplier_name = "PI Supp DN"
		supp.insert(ignore_permissions=True)
		exp = self._gl("5950", "Exp DN", 0)
		orig = frappe.new_doc("Purchase Invoice")
		orig.company = self.company
		orig.supplier = supp.name
		orig.posting_date = today()
		orig.append("items", {"item_code": "x", "qty": 1, "rate": 40, "expense_account": exp})
		orig.insert(ignore_permissions=True)
		orig.submit()
		dn = frappe.new_doc("Purchase Invoice")
		dn.company = self.company
		dn.supplier = supp.name
		dn.posting_date = today()
		dn.is_return = 1
		dn.return_against = orig.name
		dn.append("items", {"item_code": "x", "qty": 1, "rate": 5, "expense_account": exp})
		dn.insert(ignore_permissions=True)
		dn.submit()

	def test_opening_journal_bypasses_frozen_period(self):
		frz_co = self._create_company("OMNX-OPN")
		fy = frappe.new_doc("Fiscal Year")
		fy.title = "FY OPN"
		fy.company = frz_co
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
		a1 = self._gl("7100", "Opening Dr", 0, company=frz_co)
		a2 = self._gl("7101", "Opening Cr", 0, company=frz_co)
		je = frappe.new_doc("Journal Entry")
		je.company = frz_co
		je.posting_date = today()
		je.is_opening = 1
		je.append("accounts", {"account": a1, "debit": 100, "credit": 0})
		je.append("accounts", {"account": a2, "debit": 0, "credit": 100})
		je.insert(ignore_permissions=True)
		je.submit()
		je2 = frappe.new_doc("Journal Entry")
		je2.company = frz_co
		je2.posting_date = today()
		je2.is_opening = 0
		je2.append("accounts", {"account": a1, "debit": 10, "credit": 0})
		je2.append("accounts", {"account": a2, "debit": 0, "credit": 10})
		je2.insert(ignore_permissions=True)
		with self.assertRaises(frappe.ValidationError):
			je2.submit()

	def test_sales_invoice_due_date_before_posting_raises(self):
		cust = frappe.new_doc("Customer")
		cust.company = self.company
		cust.customer_name = "DueTest"
		cust.insert(ignore_permissions=True)
		leaf = self._gl("7200", "Rev Due", 0)
		si = frappe.new_doc("Sales Invoice")
		si.company = self.company
		si.customer = cust.name
		si.posting_date = today()
		si.due_date = add_days(getdate(today()), -3)
		si.append("items", {"item_code": "x", "qty": 1, "rate": 1, "income_account": leaf})
		with self.assertRaises(frappe.ValidationError):
			si.insert(ignore_permissions=True)

	def test_mode_of_payment_duplicate_per_company(self):
		m1 = frappe.new_doc("Mode of Payment")
		m1.company = self.company
		m1.mode_name = "Bank Transfer"
		m1.type = "Bank"
		m1.insert(ignore_permissions=True)
		m2 = frappe.new_doc("Mode of Payment")
		m2.company = self.company
		m2.mode_name = "Bank Transfer"
		m2.type = "Wire"
		with self.assertRaises(frappe.ValidationError):
			m2.insert(ignore_permissions=True)

	def test_payment_entry_mode_of_payment_company_mismatch(self):
		other = self._create_company("OMNX-MOP")
		mop = frappe.new_doc("Mode of Payment")
		mop.company = other
		mop.mode_name = "Cash"
		mop.type = "Cash"
		mop.insert(ignore_permissions=True)
		cust = frappe.new_doc("Customer")
		cust.company = self.company
		cust.customer_name = "MOP Cust"
		cust.insert(ignore_permissions=True)
		pe = frappe.new_doc("Payment Entry")
		pe.company = self.company
		pe.party_type = "Customer"
		pe.party = cust.name
		pe.posting_date = today()
		pe.paid_amount = 1
		pe.mode_of_payment = mop.name
		with self.assertRaises(frappe.ValidationError):
			pe.insert(ignore_permissions=True)

	def test_customer_credit_days_negative_rejected(self):
		cust = frappe.new_doc("Customer")
		cust.company = self.company
		cust.customer_name = "BadDays"
		cust.credit_days = -1
		with self.assertRaises(frappe.ValidationError):
			cust.insert(ignore_permissions=True)

	def test_sales_invoice_due_date_from_party_credit_days(self):
		cust = frappe.new_doc("Customer")
		cust.company = self.company
		cust.customer_name = "Net14 Cust"
		cust.credit_days = 14
		cust.insert(ignore_permissions=True)
		leaf = self._gl("7300", "Rev Net", 0)
		si = frappe.new_doc("Sales Invoice")
		si.company = self.company
		si.customer = cust.name
		si.posting_date = today()
		si.append("items", {"item_code": "x", "qty": 1, "rate": 1, "income_account": leaf})
		si.insert(ignore_permissions=True)
		self.assertEqual(getdate(si.due_date), add_days(getdate(si.posting_date), 14))

	def test_sales_invoice_due_date_from_payment_terms_net_phrase(self):
		cust = frappe.new_doc("Customer")
		cust.company = self.company
		cust.customer_name = "TermsOnly"
		cust.payment_terms = "Net 7"
		cust.insert(ignore_permissions=True)
		leaf = self._gl("7310", "Rev T", 0)
		si = frappe.new_doc("Sales Invoice")
		si.company = self.company
		si.customer = cust.name
		si.posting_date = today()
		si.append("items", {"item_code": "x", "qty": 1, "rate": 1, "income_account": leaf})
		si.insert(ignore_permissions=True)
		self.assertEqual(getdate(si.due_date), add_days(getdate(si.posting_date), 7))

	def test_credit_days_takes_priority_over_net_phrase(self):
		cust = frappe.new_doc("Customer")
		cust.company = self.company
		cust.customer_name = "Pri Cust"
		cust.credit_days = 3
		cust.payment_terms = "Net 99"
		cust.insert(ignore_permissions=True)
		leaf = self._gl("7311", "Rev Pri", 0)
		si = frappe.new_doc("Sales Invoice")
		si.company = self.company
		si.customer = cust.name
		si.posting_date = today()
		si.append("items", {"item_code": "x", "qty": 1, "rate": 1, "income_account": leaf})
		si.insert(ignore_permissions=True)
		self.assertEqual(getdate(si.due_date), add_days(getdate(si.posting_date), 3))

	def test_purchase_invoice_due_date_from_supplier_credit_days(self):
		supp = frappe.new_doc("Supplier")
		supp.company = self.company
		supp.supplier_name = "SupNet"
		supp.credit_days = 10
		supp.insert(ignore_permissions=True)
		exp = self._gl("7320", "Exp Sup", 0)
		pi = frappe.new_doc("Purchase Invoice")
		pi.company = self.company
		pi.supplier = supp.name
		pi.posting_date = today()
		pi.append("items", {"item_code": "x", "qty": 1, "rate": 1, "expense_account": exp})
		pi.insert(ignore_permissions=True)
		self.assertEqual(getdate(pi.due_date), add_days(getdate(pi.posting_date), 10))

	def test_sales_invoice_submit_and_cancel(self):
		frappe.set_user("Administrator")
		cust = frappe.new_doc("Customer")
		cust.company = self.company
		cust.customer_name = "Cancel SI"
		cust.insert(ignore_permissions=True)
		leaf = self._gl("7330", "Rev Can", 0)
		si = frappe.new_doc("Sales Invoice")
		si.company = self.company
		si.customer = cust.name
		si.posting_date = today()
		si.append("items", {"item_code": "x", "qty": 1, "rate": 1, "income_account": leaf})
		si.insert(ignore_permissions=True)
		si.submit()
		self.assertEqual(si.docstatus, 1)
		si.cancel()
		self.assertEqual(si.docstatus, 2)

	def test_purchase_invoice_submit_and_cancel(self):
		frappe.set_user("Administrator")
		supp = frappe.new_doc("Supplier")
		supp.company = self.company
		supp.supplier_name = "Cancel PI"
		supp.insert(ignore_permissions=True)
		exp = self._gl("7340", "Exp Can", 0)
		pi = frappe.new_doc("Purchase Invoice")
		pi.company = self.company
		pi.supplier = supp.name
		pi.posting_date = today()
		pi.append("items", {"item_code": "x", "qty": 1, "rate": 1, "expense_account": exp})
		pi.insert(ignore_permissions=True)
		pi.submit()
		self.assertEqual(pi.docstatus, 1)
		pi.cancel()
		self.assertEqual(pi.docstatus, 2)

	def test_payment_entry_submit_and_cancel_no_reference(self):
		frappe.set_user("Administrator")
		cust = frappe.new_doc("Customer")
		cust.company = self.company
		cust.customer_name = "PE Cancel"
		cust.insert(ignore_permissions=True)
		pe = frappe.new_doc("Payment Entry")
		pe.company = self.company
		pe.party_type = "Customer"
		pe.party = cust.name
		pe.posting_date = today()
		pe.paid_amount = 1
		pe.insert(ignore_permissions=True)
		pe.submit()
		self.assertEqual(pe.docstatus, 1)
		pe.cancel()
		self.assertEqual(pe.docstatus, 2)

	def test_journal_entry_submit_and_cancel(self):
		frappe.set_user("Administrator")
		leaf = self._gl("7350", "JE Can A", 0)
		leaf2 = self._gl("7351", "JE Can B", 0)
		je = frappe.new_doc("Journal Entry")
		je.company = self.company
		je.posting_date = today()
		je.append("accounts", {"account": leaf, "debit": 5, "credit": 0})
		je.append("accounts", {"account": leaf2, "debit": 0, "credit": 5})
		je.insert(ignore_permissions=True)
		je.submit()
		self.assertEqual(je.docstatus, 1)
		je.cancel()
		self.assertEqual(je.docstatus, 2)

	def test_sales_invoice_amend_rejected_when_original_not_cancelled(self):
		frappe.set_user("Administrator")
		cust = frappe.new_doc("Customer")
		cust.company = self.company
		cust.customer_name = "Amend Block"
		cust.insert(ignore_permissions=True)
		leaf = self._gl("7360", "Rev Amend B", 0)
		si = frappe.new_doc("Sales Invoice")
		si.company = self.company
		si.customer = cust.name
		si.posting_date = today()
		si.append("items", {"item_code": "x", "qty": 1, "rate": 3, "income_account": leaf})
		si.insert(ignore_permissions=True)
		si.submit()
		amended = frappe.copy_doc(frappe.get_doc("Sales Invoice", si.name))
		amended.amended_from = si.name
		amended.docstatus = 0
		with self.assertRaises(frappe.ValidationError):
			amended.insert(ignore_permissions=True)
		si.cancel()

	def test_sales_invoice_amend_after_cancel(self):
		frappe.set_user("Administrator")
		cust = frappe.new_doc("Customer")
		cust.company = self.company
		cust.customer_name = "Amend OK"
		cust.insert(ignore_permissions=True)
		leaf = self._gl("7361", "Rev Amend A", 0)
		si = frappe.new_doc("Sales Invoice")
		si.company = self.company
		si.customer = cust.name
		si.posting_date = today()
		si.append("items", {"item_code": "x", "qty": 1, "rate": 4, "income_account": leaf})
		si.insert(ignore_permissions=True)
		si.submit()
		si.cancel()
		amended = frappe.copy_doc(frappe.get_doc("Sales Invoice", si.name))
		amended.amended_from = si.name
		amended.docstatus = 0
		amended.insert(ignore_permissions=True)
		amended.items[0].rate = 6
		amended.save(ignore_permissions=True)
		amended.submit()
		self.assertEqual(amended.docstatus, 1)
		self.assertEqual(amended.amended_from, si.name)
		self.assertEqual(amended.grand_total, 6.0)

	def test_payment_entry_cancel_with_sales_invoice_reference(self):
		frappe.set_user("Administrator")
		cust = frappe.new_doc("Customer")
		cust.company = self.company
		cust.customer_name = "PE Ref Cancel"
		cust.insert(ignore_permissions=True)
		leaf = self._gl("7362", "Rev PE Ref", 0)
		si = frappe.new_doc("Sales Invoice")
		si.company = self.company
		si.customer = cust.name
		si.posting_date = today()
		si.append("items", {"item_code": "x", "qty": 1, "rate": 11, "income_account": leaf})
		si.insert(ignore_permissions=True)
		si.submit()
		pe = frappe.new_doc("Payment Entry")
		pe.company = self.company
		pe.party_type = "Customer"
		pe.party = cust.name
		pe.posting_date = today()
		pe.paid_amount = si.grand_total
		pe.append(
			"references",
			{
				"reference_doctype": "Sales Invoice",
				"reference_name": si.name,
				"allocated_amount": si.grand_total,
			},
		)
		pe.insert(ignore_permissions=True)
		pe.submit()
		self.assertEqual(pe.docstatus, 1)
		pe.cancel()
		self.assertEqual(pe.docstatus, 2)
		si.reload()
		si.cancel()
		self.assertEqual(si.docstatus, 2)
