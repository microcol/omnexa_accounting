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

	def _deactivate_purchase_approval_rules(self):
		for name in frappe.get_all(
			"Purchase Approval Rule",
			filters={"company": self.company, "is_active": 1},
			pluck="name",
		):
			frappe.db.set_value("Purchase Approval Rule", name, "is_active", 0, update_modified=False)

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

	def test_payment_entry_rejects_duplicate_reference_rows(self):
		cust = frappe.new_doc("Customer")
		cust.company = self.company
		cust.customer_name = "Dup Ref Cust"
		cust.insert(ignore_permissions=True)
		leaf = self._gl("5501", "Revenue Dup Ref", 0)
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
		pe.paid_amount = 200
		pe.append(
			"references",
			{
				"reference_doctype": "Sales Invoice",
				"reference_name": si.name,
				"allocated_amount": 100,
			},
		)
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

	def test_payment_entry_rejects_non_positive_allocation(self):
		cust = frappe.new_doc("Customer")
		cust.company = self.company
		cust.customer_name = "Zero Alloc Cust"
		cust.insert(ignore_permissions=True)
		leaf = self._gl("5502", "Revenue Zero Alloc", 0)
		si = frappe.new_doc("Sales Invoice")
		si.company = self.company
		si.customer = cust.name
		si.posting_date = today()
		si.append("items", {"item_code": "line", "qty": 1, "rate": 100, "income_account": leaf})
		si.insert(ignore_permissions=True)
		si.submit()
		pe = frappe.new_doc("Payment Entry")
		pe.company = self.company
		pe.party_type = "Customer"
		pe.party = cust.name
		pe.posting_date = today()
		pe.paid_amount = 100
		pe.append(
			"references",
			{
				"reference_doctype": "Sales Invoice",
				"reference_name": si.name,
				"allocated_amount": 0,
			},
		)
		with self.assertRaises(frappe.ValidationError):
			pe.insert(ignore_permissions=True)

	def test_payment_entry_rejects_over_allocation_against_existing_payments(self):
		cust = frappe.new_doc("Customer")
		cust.company = self.company
		cust.customer_name = "Outstanding Cap Cust"
		cust.insert(ignore_permissions=True)
		leaf = self._gl("5503", "Revenue Outstanding Cap", 0)
		si = frappe.new_doc("Sales Invoice")
		si.company = self.company
		si.customer = cust.name
		si.posting_date = today()
		si.append("items", {"item_code": "line", "qty": 1, "rate": 100, "income_account": leaf})
		si.insert(ignore_permissions=True)
		si.submit()
		pe1 = frappe.new_doc("Payment Entry")
		pe1.company = self.company
		pe1.party_type = "Customer"
		pe1.party = cust.name
		pe1.posting_date = today()
		pe1.paid_amount = 60
		pe1.append(
			"references",
			{
				"reference_doctype": "Sales Invoice",
				"reference_name": si.name,
				"allocated_amount": 60,
			},
		)
		pe1.insert(ignore_permissions=True)
		pe1.submit()
		pe2 = frappe.new_doc("Payment Entry")
		pe2.company = self.company
		pe2.party_type = "Customer"
		pe2.party = cust.name
		pe2.posting_date = today()
		pe2.paid_amount = 50
		pe2.append(
			"references",
			{
				"reference_doctype": "Sales Invoice",
				"reference_name": si.name,
				"allocated_amount": 50,
			},
		)
		with self.assertRaises(frappe.ValidationError):
			pe2.insert(ignore_permissions=True)

	def test_payment_entry_remittance_requires_reference_and_date(self):
		cust = frappe.new_doc("Customer")
		cust.company = self.company
		cust.customer_name = "Remit Cust"
		cust.insert(ignore_permissions=True)
		pe = frappe.new_doc("Payment Entry")
		pe.company = self.company
		pe.party_type = "Customer"
		pe.party = cust.name
		pe.posting_date = today()
		pe.paid_amount = 10
		pe.remittance_date = today()
		with self.assertRaises(frappe.ValidationError):
			pe.insert(ignore_permissions=True)

	def test_payment_entry_remittance_date_cannot_exceed_posting_date(self):
		cust = frappe.new_doc("Customer")
		cust.company = self.company
		cust.customer_name = "Remit Date Cust"
		cust.insert(ignore_permissions=True)
		pe = frappe.new_doc("Payment Entry")
		pe.company = self.company
		pe.party_type = "Customer"
		pe.party = cust.name
		pe.posting_date = today()
		pe.paid_amount = 10
		pe.remittance_reference = "TXN-1"
		pe.remittance_date = add_days(getdate(today()), 1)
		with self.assertRaises(frappe.ValidationError):
			pe.insert(ignore_permissions=True)

	def test_bank_remittance_mode_requires_bank_account(self):
		mop = frappe.new_doc("Mode of Payment")
		mop.company = self.company
		mop.mode_name = "Wire Transfer"
		mop.type = "Wire"
		mop.insert(ignore_permissions=True)
		cust = frappe.new_doc("Customer")
		cust.company = self.company
		cust.customer_name = "Remit Wire Cust"
		cust.insert(ignore_permissions=True)
		pe = frappe.new_doc("Payment Entry")
		pe.company = self.company
		pe.party_type = "Customer"
		pe.party = cust.name
		pe.posting_date = today()
		pe.paid_amount = 10
		pe.mode_of_payment = mop.name
		pe.remittance_reference = "WIRE-1"
		pe.remittance_date = today()
		with self.assertRaises(frappe.ValidationError):
			pe.insert(ignore_permissions=True)

	def test_payment_entry_accepts_valid_remittance_metadata(self):
		mop = frappe.new_doc("Mode of Payment")
		mop.company = self.company
		mop.mode_name = "Cheque Local"
		mop.type = "Cheque"
		mop.insert(ignore_permissions=True)
		bank_gl = self._gl("5509", "Remit Bank GL", 0)
		ba = frappe.new_doc("Bank Account")
		ba.company = self.company
		ba.account_title = "Remit Bank"
		ba.gl_account = bank_gl
		ba.insert(ignore_permissions=True)
		cust = frappe.new_doc("Customer")
		cust.company = self.company
		cust.customer_name = "Remit Valid Cust"
		cust.insert(ignore_permissions=True)
		pe = frappe.new_doc("Payment Entry")
		pe.company = self.company
		pe.party_type = "Customer"
		pe.party = cust.name
		pe.posting_date = today()
		pe.paid_amount = 10
		pe.mode_of_payment = mop.name
		pe.bank_account = ba.name
		pe.remittance_reference = "CHQ-1"
		pe.remittance_date = today()
		pe.remittance_bank_reference = "NBE-REF-77"
		pe.insert(ignore_permissions=True)
		self.assertEqual(pe.remittance_reference, "CHQ-1")

	def test_sales_invoice_outstanding_updates_from_payment_lifecycle(self):
		cust = frappe.new_doc("Customer")
		cust.company = self.company
		cust.customer_name = "Outstanding SI"
		cust.insert(ignore_permissions=True)
		leaf = self._gl("5504", "Revenue Outstanding SI", 0)
		si = frappe.new_doc("Sales Invoice")
		si.company = self.company
		si.customer = cust.name
		si.posting_date = today()
		si.append("items", {"item_code": "line", "qty": 1, "rate": 100, "income_account": leaf})
		si.insert(ignore_permissions=True)
		si.submit()
		si.reload()
		self.assertEqual(si.outstanding_amount, 100.0)
		pe = frappe.new_doc("Payment Entry")
		pe.company = self.company
		pe.party_type = "Customer"
		pe.party = cust.name
		pe.posting_date = today()
		pe.paid_amount = 40
		pe.append(
			"references",
			{
				"reference_doctype": "Sales Invoice",
				"reference_name": si.name,
				"allocated_amount": 40,
			},
		)
		pe.insert(ignore_permissions=True)
		pe.submit()
		si.reload()
		self.assertEqual(si.outstanding_amount, 60.0)
		pe.cancel()
		si.reload()
		self.assertEqual(si.outstanding_amount, 100.0)

	def test_purchase_invoice_outstanding_updates_from_payment_lifecycle(self):
		supp = frappe.new_doc("Supplier")
		supp.company = self.company
		supp.supplier_name = "Outstanding PI"
		supp.insert(ignore_permissions=True)
		exp = self._gl("5505", "Expense Outstanding PI", 0)
		pi = frappe.new_doc("Purchase Invoice")
		pi.company = self.company
		pi.supplier = supp.name
		pi.posting_date = today()
		pi.append("items", {"item_code": "line", "qty": 1, "rate": 100, "expense_account": exp})
		pi.insert(ignore_permissions=True)
		pi.submit()
		pi.reload()
		self.assertEqual(pi.outstanding_amount, 100.0)
		pe = frappe.new_doc("Payment Entry")
		pe.company = self.company
		pe.party_type = "Supplier"
		pe.party = supp.name
		pe.posting_date = today()
		pe.paid_amount = 30
		pe.append(
			"references",
			{
				"reference_doctype": "Purchase Invoice",
				"reference_name": pi.name,
				"allocated_amount": 30,
			},
		)
		pe.insert(ignore_permissions=True)
		pe.submit()
		pi.reload()
		self.assertEqual(pi.outstanding_amount, 70.0)
		pe.cancel()
		pi.reload()
		self.assertEqual(pi.outstanding_amount, 100.0)

	def test_sales_invoice_payment_schedule_sets_due_date(self):
		cust = frappe.new_doc("Customer")
		cust.company = self.company
		cust.customer_name = "PS Cust"
		cust.insert(ignore_permissions=True)
		leaf = self._gl("5506", "Revenue PS", 0)
		si = frappe.new_doc("Sales Invoice")
		si.company = self.company
		si.customer = cust.name
		si.posting_date = today()
		si.append("items", {"item_code": "line", "qty": 1, "rate": 100, "income_account": leaf})
		si.append("payment_schedule", {"due_date": add_days(getdate(today()), 10), "payment_amount": 40})
		si.append("payment_schedule", {"due_date": add_days(getdate(today()), 20), "payment_amount": 60})
		si.insert(ignore_permissions=True)
		self.assertEqual(getdate(si.due_date), add_days(getdate(today()), 20))

	def test_sales_invoice_payment_schedule_total_must_match_grand_total(self):
		cust = frappe.new_doc("Customer")
		cust.company = self.company
		cust.customer_name = "PS Bad Cust"
		cust.insert(ignore_permissions=True)
		leaf = self._gl("5507", "Revenue PS Bad", 0)
		si = frappe.new_doc("Sales Invoice")
		si.company = self.company
		si.customer = cust.name
		si.posting_date = today()
		si.append("items", {"item_code": "line", "qty": 1, "rate": 100, "income_account": leaf})
		si.append("payment_schedule", {"due_date": add_days(getdate(today()), 5), "payment_amount": 30})
		with self.assertRaises(frappe.ValidationError):
			si.insert(ignore_permissions=True)

	def test_purchase_invoice_payment_schedule_due_date_validation(self):
		supp = frappe.new_doc("Supplier")
		supp.company = self.company
		supp.supplier_name = "PS Supp"
		supp.insert(ignore_permissions=True)
		exp = self._gl("5508", "Expense PS", 0)
		pi = frappe.new_doc("Purchase Invoice")
		pi.company = self.company
		pi.supplier = supp.name
		pi.posting_date = today()
		pi.append("items", {"item_code": "line", "qty": 1, "rate": 100, "expense_account": exp})
		pi.append("payment_schedule", {"due_date": add_days(getdate(today()), -1), "payment_amount": 100})
		with self.assertRaises(frappe.ValidationError):
			pi.insert(ignore_permissions=True)

	def test_purchase_invoice_submit_blocked_without_required_approver_role(self):
		self._deactivate_purchase_approval_rules()
		role_name = "Purchase Approver Test"
		if not frappe.db.exists("Role", role_name):
			r = frappe.new_doc("Role")
			r.role_name = role_name
			r.desk_access = 1
			r.is_custom = 1
			r.insert(ignore_permissions=True)
		rule = frappe.new_doc("Purchase Approval Rule")
		rule.rule_name = "Rule Block"
		rule.company = self.company
		rule.approver_role = role_name
		rule.min_amount = 50
		rule.max_amount = 500
		rule.require_three_way_match = 0
		rule.is_active = 1
		rule.insert(ignore_permissions=True)
		supp = frappe.new_doc("Supplier")
		supp.company = self.company
		supp.supplier_name = "Approval Block Supp"
		supp.insert(ignore_permissions=True)
		exp = self._gl("5510", "Exp Approval Block", 0)
		pi = frappe.new_doc("Purchase Invoice")
		pi.company = self.company
		pi.supplier = supp.name
		pi.posting_date = today()
		pi.append("items", {"item_code": "x", "qty": 1, "rate": 100, "expense_account": exp})
		pi.insert(ignore_permissions=True)
		user_email = "approverless@example.com"
		if not frappe.db.exists("User", user_email):
			u = frappe.new_doc("User")
			u.email = user_email
			u.first_name = "Approverless"
			u.enabled = 1
			u.new_password = "test123"
			u.insert(ignore_permissions=True)
		frappe.set_user(user_email)
		pi.flags.ignore_permissions = True
		with self.assertRaises(frappe.ValidationError):
			pi.submit()
		frappe.set_user("Administrator")

	def test_purchase_invoice_submit_allowed_with_approver_role(self):
		self._deactivate_purchase_approval_rules()
		role_name = "Purchase Approver Allowed"
		if not frappe.db.exists("Role", role_name):
			r = frappe.new_doc("Role")
			r.role_name = role_name
			r.desk_access = 1
			r.is_custom = 1
			r.insert(ignore_permissions=True)
		admin = frappe.get_doc("User", "Administrator")
		if not any((d.role == role_name) for d in admin.roles):
			admin.append("roles", {"role": role_name})
			admin.save(ignore_permissions=True)
		rule = frappe.new_doc("Purchase Approval Rule")
		rule.rule_name = "Rule Allow"
		rule.company = self.company
		rule.approver_role = role_name
		rule.min_amount = 50
		rule.max_amount = 500
		rule.require_three_way_match = 0
		rule.is_active = 1
		rule.insert(ignore_permissions=True)
		supp = frappe.new_doc("Supplier")
		supp.company = self.company
		supp.supplier_name = "Approval Allow Supp"
		supp.insert(ignore_permissions=True)
		exp = self._gl("5511", "Exp Approval Allow", 0)
		pi = frappe.new_doc("Purchase Invoice")
		pi.company = self.company
		pi.supplier = supp.name
		pi.posting_date = today()
		pi.append("items", {"item_code": "x", "qty": 1, "rate": 100, "expense_account": exp})
		pi.insert(ignore_permissions=True)
		pi.submit()
		self.assertEqual(pi.docstatus, 1)

	def test_purchase_invoice_three_way_match_required_by_rule(self):
		self._deactivate_purchase_approval_rules()
		role_name = "Purchase Approver 3WM"
		if not frappe.db.exists("Role", role_name):
			r = frappe.new_doc("Role")
			r.role_name = role_name
			r.desk_access = 1
			r.is_custom = 1
			r.insert(ignore_permissions=True)
		admin = frappe.get_doc("User", "Administrator")
		if not any((d.role == role_name) for d in admin.roles):
			admin.append("roles", {"role": role_name})
			admin.save(ignore_permissions=True)
		rule = frappe.new_doc("Purchase Approval Rule")
		rule.rule_name = "Rule 3WM"
		rule.company = self.company
		rule.approver_role = role_name
		rule.min_amount = 1
		rule.max_amount = 1000
		rule.require_three_way_match = 1
		rule.is_active = 1
		rule.insert(ignore_permissions=True)
		supp = frappe.new_doc("Supplier")
		supp.company = self.company
		supp.supplier_name = "Approval 3WM Supp"
		supp.insert(ignore_permissions=True)
		exp = self._gl("5512", "Exp Approval 3WM", 0)
		pi = frappe.new_doc("Purchase Invoice")
		pi.company = self.company
		pi.supplier = supp.name
		pi.posting_date = today()
		pi.append("items", {"item_code": "x", "qty": 1, "rate": 100, "expense_account": exp})
		pi.insert(ignore_permissions=True)
		matched_rule = pi._get_matching_approval_rule()
		self.assertIsNotNone(matched_rule)
		self.assertEqual(int(matched_rule.require_three_way_match), 1)
		self.assertFalse(pi.po_reference)
		self.assertFalse(pi.goods_receipt_reference)
		with self.assertRaises(frappe.ValidationError):
			pi.submit()
		pi.reload()
		po = frappe.new_doc("Purchase Order")
		po.company = self.company
		po.supplier = supp.name
		po.posting_date = today()
		po.append("items", {"item_code": "x", "qty": 1, "rate": 100})
		po.insert(ignore_permissions=True)
		po.submit()
		grn = frappe.new_doc("Purchase Receipt")
		grn.company = self.company
		grn.supplier = supp.name
		grn.posting_date = today()
		grn.purchase_order = po.name
		grn.append("items", {"item_code": "x", "qty": 1, "rate": 100})
		grn.insert(ignore_permissions=True)
		grn.submit()
		pi.po_reference = po.name
		pi.goods_receipt_reference = grn.name
		pi.submit()
		self.assertEqual(pi.docstatus, 1)

	def test_purchase_invoice_three_way_match_blocks_qty_exceeding_receipt(self):
		self._deactivate_purchase_approval_rules()
		role_name = "Purchase Approver 3WM Qty"
		if not frappe.db.exists("Role", role_name):
			r = frappe.new_doc("Role")
			r.role_name = role_name
			r.desk_access = 1
			r.is_custom = 1
			r.insert(ignore_permissions=True)
		admin = frappe.get_doc("User", "Administrator")
		if not any((d.role == role_name) for d in admin.roles):
			admin.append("roles", {"role": role_name})
			admin.save(ignore_permissions=True)
		rule = frappe.new_doc("Purchase Approval Rule")
		rule.rule_name = "Rule 3WM Qty"
		rule.company = self.company
		rule.approver_role = role_name
		rule.min_amount = 1
		rule.max_amount = 1000
		rule.require_three_way_match = 1
		rule.is_active = 1
		rule.insert(ignore_permissions=True)
		supp = frappe.new_doc("Supplier")
		supp.company = self.company
		supp.supplier_name = "Approval 3WM Qty Supp"
		supp.insert(ignore_permissions=True)
		exp = self._gl("5513", "Exp Approval 3WM Qty", 0)
		po = frappe.new_doc("Purchase Order")
		po.company = self.company
		po.supplier = supp.name
		po.posting_date = today()
		po.append("items", {"item_code": "x", "qty": 2, "rate": 100})
		po.insert(ignore_permissions=True)
		po.submit()
		grn = frappe.new_doc("Purchase Receipt")
		grn.company = self.company
		grn.supplier = supp.name
		grn.posting_date = today()
		grn.purchase_order = po.name
		grn.append("items", {"item_code": "x", "qty": 1, "rate": 100})
		grn.insert(ignore_permissions=True)
		grn.submit()
		pi = frappe.new_doc("Purchase Invoice")
		pi.company = self.company
		pi.supplier = supp.name
		pi.posting_date = today()
		pi.po_reference = po.name
		pi.goods_receipt_reference = grn.name
		pi.append("items", {"item_code": "x", "qty": 2, "rate": 100, "expense_account": exp})
		pi.insert(ignore_permissions=True)
		with self.assertRaises(frappe.ValidationError):
			pi.submit()

	def test_landed_cost_voucher_distributes_charges_to_purchase_invoice_items(self):
		supp = frappe.new_doc("Supplier")
		supp.company = self.company
		supp.supplier_name = "LCV Supp"
		supp.insert(ignore_permissions=True)
		exp = self._gl("5514", "Exp LCV", 0)
		pi = frappe.new_doc("Purchase Invoice")
		pi.company = self.company
		pi.supplier = supp.name
		pi.posting_date = today()
		pi.append("items", {"item_code": "A", "qty": 1, "rate": 100, "expense_account": exp})
		pi.append("items", {"item_code": "B", "qty": 1, "rate": 300, "expense_account": exp})
		pi.insert(ignore_permissions=True)
		pi.submit()
		lcv = frappe.new_doc("Landed Cost Voucher")
		lcv.company = self.company
		lcv.purchase_invoice = pi.name
		lcv.posting_date = today()
		lcv.append("charges", {"description": "Freight", "amount": 80})
		lcv.insert(ignore_permissions=True)
		lcv.submit()
		pi.reload()
		item_map = {row.item_code: row for row in pi.items}
		self.assertEqual(item_map["A"].landed_cost_amount, 20.0)
		self.assertEqual(item_map["B"].landed_cost_amount, 60.0)
		self.assertEqual(item_map["A"].landed_rate, 120.0)
		self.assertEqual(item_map["B"].landed_rate, 360.0)

	def test_landed_cost_voucher_rejects_second_submitted_voucher_for_same_invoice(self):
		supp = frappe.new_doc("Supplier")
		supp.company = self.company
		supp.supplier_name = "LCV Single Supp"
		supp.insert(ignore_permissions=True)
		exp = self._gl("5515", "Exp LCV Single", 0)
		pi = frappe.new_doc("Purchase Invoice")
		pi.company = self.company
		pi.supplier = supp.name
		pi.posting_date = today()
		pi.append("items", {"item_code": "A", "qty": 1, "rate": 100, "expense_account": exp})
		pi.insert(ignore_permissions=True)
		pi.submit()
		lcv1 = frappe.new_doc("Landed Cost Voucher")
		lcv1.company = self.company
		lcv1.purchase_invoice = pi.name
		lcv1.posting_date = today()
		lcv1.append("charges", {"description": "Freight", "amount": 10})
		lcv1.insert(ignore_permissions=True)
		lcv1.submit()
		lcv2 = frappe.new_doc("Landed Cost Voucher")
		lcv2.company = self.company
		lcv2.purchase_invoice = pi.name
		lcv2.posting_date = today()
		lcv2.append("charges", {"description": "Insurance", "amount": 5})
		with self.assertRaises(frappe.ValidationError):
			lcv2.insert(ignore_permissions=True)

	def test_stock_reconciliation_sets_next_date_and_variance(self):
		self._ensure_uom()
		it = frappe.new_doc("Item")
		it.item_code = "STK-1"
		it.item_name = "Stock One"
		it.company = self.company
		it.stock_uom = "Nos"
		it.current_stock_qty = 10
		it.insert(ignore_permissions=True)
		sr = frappe.new_doc("Stock Reconciliation")
		sr.company = self.company
		sr.reconciliation_date = today()
		sr.cadence = "Weekly"
		sr.append("items", {"item": it.name, "counted_qty": 8})
		sr.insert(ignore_permissions=True)
		self.assertEqual(sr.items[0].system_qty, 10.0)
		self.assertEqual(sr.items[0].variance_qty, -2.0)
		self.assertEqual(getdate(sr.next_reconciliation_date), add_days(getdate(today()), 7))

	def test_stock_reconciliation_submit_updates_item_stock_qty(self):
		self._ensure_uom()
		it = frappe.new_doc("Item")
		it.item_code = "STK-2"
		it.item_name = "Stock Two"
		it.company = self.company
		it.stock_uom = "Nos"
		it.current_stock_qty = 3
		it.insert(ignore_permissions=True)
		sr = frappe.new_doc("Stock Reconciliation")
		sr.company = self.company
		sr.reconciliation_date = today()
		sr.cadence = "Monthly"
		sr.append("items", {"item": it.name, "counted_qty": 12})
		sr.insert(ignore_permissions=True)
		sr.submit()
		it.reload()
		self.assertEqual(it.current_stock_qty, 12.0)
		self.assertEqual(getdate(it.last_stock_reconciliation_date), getdate(today()))

	def test_employee_code_unique_per_company(self):
		e1 = frappe.new_doc("Employee")
		e1.employee_code = "EMP-001"
		e1.employee_name = "Emp One"
		e1.company = self.company
		e1.insert(ignore_permissions=True)
		e2 = frappe.new_doc("Employee")
		e2.employee_code = "EMP-001"
		e2.employee_name = "Emp Two"
		e2.company = self.company
		with self.assertRaises(frappe.ValidationError):
			e2.insert(ignore_permissions=True)

	def test_employee_manager_must_be_same_company(self):
		other = self._create_company("OMNX-EMP")
		mgr = frappe.new_doc("Employee")
		mgr.employee_code = "EMP-MGR"
		mgr.employee_name = "Mgr"
		mgr.company = other
		mgr.insert(ignore_permissions=True)
		e = frappe.new_doc("Employee")
		e.employee_code = "EMP-SUB"
		e.employee_name = "Sub"
		e.company = self.company
		e.manager = mgr.name
		with self.assertRaises(frappe.ValidationError):
			e.insert(ignore_permissions=True)

	def test_employee_leave_policy_company_match(self):
		other = self._create_company("OMNX-LP")
		lp = frappe.new_doc("Leave Policy")
		lp.policy_name = "Other Policy"
		lp.company = other
		lp.annual_leave_days = 21
		lp.insert(ignore_permissions=True)
		e = frappe.new_doc("Employee")
		e.employee_code = "EMP-LP"
		e.employee_name = "Emp LP"
		e.company = self.company
		e.leave_policy = lp.name
		with self.assertRaises(frappe.ValidationError):
			e.insert(ignore_permissions=True)

	def test_employee_license_expiry_before_issue_rejected(self):
		e = frappe.new_doc("Employee")
		e.employee_code = "EMP-LIC-1"
		e.employee_name = "Emp Lic"
		e.company = self.company
		e.primary_license_type = "Engineering"
		e.license_number = "ENG-123"
		e.license_issue_date = today()
		e.license_expiry_date = add_days(getdate(today()), -1)
		with self.assertRaises(frappe.ValidationError):
			e.insert(ignore_permissions=True)

	def test_employee_license_tracking_requires_type_and_number(self):
		e = frappe.new_doc("Employee")
		e.employee_code = "EMP-LIC-2"
		e.employee_name = "Emp Lic 2"
		e.company = self.company
		e.license_issue_date = today()
		e.license_expiry_date = add_days(getdate(today()), 120)
		with self.assertRaises(frappe.ValidationError):
			e.insert(ignore_permissions=True)

	def test_employee_license_status_auto_sets_expiring_soon(self):
		e = frappe.new_doc("Employee")
		e.employee_code = "EMP-LIC-3"
		e.employee_name = "Emp Lic 3"
		e.company = self.company
		e.primary_license_type = "Engineering"
		e.license_number = "ENG-456"
		e.license_issue_date = add_days(getdate(today()), -30)
		e.license_expiry_date = add_days(getdate(today()), 30)
		e.insert(ignore_permissions=True)
		self.assertEqual(e.license_status, "Expiring Soon")

	def test_billable_timesheet_creates_sales_invoice_bridge(self):
		leaf = self._gl("5516", "Rev Time", 0)
		cust = frappe.new_doc("Customer")
		cust.company = self.company
		cust.customer_name = "Time Cust"
		cust.insert(ignore_permissions=True)
		project = frappe.new_doc("Project Template")
		project.template_name = "Implementation"
		project.company = self.company
		project.customer = cust.name
		project.default_income_account = leaf
		project.default_billing_rate = 200
		project.append("tasks", {"task_title": "Design", "estimated_hours": 8, "is_billable": 1})
		project.insert(ignore_permissions=True)
		ts = frappe.new_doc("Timesheet Entry")
		ts.company = self.company
		ts.project_template = project.name
		ts.posting_date = today()
		ts.hours = 3
		ts.is_billable = 1
		ts.billing_rate = 0
		ts.insert(ignore_permissions=True)
		ts.submit()
		ts.reload()
		self.assertEqual(ts.billable_amount, 600.0)
		self.assertTrue(ts.sales_invoice)
		si = frappe.get_doc("Sales Invoice", ts.sales_invoice)
		self.assertEqual(si.docstatus, 0)
		self.assertEqual(si.grand_total, 600.0)

	def test_non_billable_timesheet_sets_zero_billable_amount(self):
		leaf = self._gl("5517", "Rev Time NB", 0)
		cust = frappe.new_doc("Customer")
		cust.company = self.company
		cust.customer_name = "Time NB Cust"
		cust.insert(ignore_permissions=True)
		project = frappe.new_doc("Project Template")
		project.template_name = "Support"
		project.company = self.company
		project.customer = cust.name
		project.default_income_account = leaf
		project.default_billing_rate = 100
		project.insert(ignore_permissions=True)
		ts = frappe.new_doc("Timesheet Entry")
		ts.company = self.company
		ts.project_template = project.name
		ts.posting_date = today()
		ts.hours = 2
		ts.is_billable = 0
		ts.billing_rate = 100
		ts.insert(ignore_permissions=True)
		ts.submit()
		ts.reload()
		self.assertEqual(ts.billable_amount, 0.0)
		self.assertFalse(ts.sales_invoice)

	def test_opportunity_open_stage_requires_follow_up_date(self):
		opp = frappe.new_doc("Pipeline Opportunity")
		opp.company = self.company
		opp.opportunity_name = "Pipeline Opp"
		opp.stage = "Prospecting"
		opp.amount = 1000
		opp.probability = 20
		with self.assertRaises(frappe.ValidationError):
			opp.insert(ignore_permissions=True)

	def test_opportunity_closed_stage_requires_closing_date(self):
		opp = frappe.new_doc("Pipeline Opportunity")
		opp.company = self.company
		opp.opportunity_name = "Won Opp"
		opp.stage = "Won"
		opp.amount = 5000
		opp.probability = 100
		with self.assertRaises(frappe.ValidationError):
			opp.insert(ignore_permissions=True)

	def test_opportunity_stage_regression_blocked(self):
		opp = frappe.new_doc("Pipeline Opportunity")
		opp.company = self.company
		opp.opportunity_name = "Stage Opp"
		opp.stage = "Qualified"
		opp.amount = 1200
		opp.probability = 40
		opp.next_follow_up_date = add_days(getdate(today()), 5)
		opp.insert(ignore_permissions=True)
		opp.stage = "Proposal"
		opp.next_follow_up_date = add_days(getdate(today()), 7)
		opp.save(ignore_permissions=True)
		opp.stage = "Qualified"
		with self.assertRaises(frappe.ValidationError):
			opp.save(ignore_permissions=True)

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

	def test_credit_limit_override_requires_reason(self):
		cust = frappe.new_doc("Customer")
		cust.company = self.company
		cust.customer_name = "Override Missing Reason"
		cust.credit_limit = 50
		cust.insert(ignore_permissions=True)
		leaf = self._gl("5301", "Revenue OVR", 0)
		si = frappe.new_doc("Sales Invoice")
		si.company = self.company
		si.customer = cust.name
		si.posting_date = today()
		si.credit_limit_override_approved = 1
		si.append("items", {"item_code": "line", "qty": 1, "rate": 100, "income_account": leaf})
		si.insert(ignore_permissions=True)
		with self.assertRaises(frappe.ValidationError):
			si.submit()

	def test_credit_limit_override_allows_submit_with_reason(self):
		cust = frappe.new_doc("Customer")
		cust.company = self.company
		cust.customer_name = "Override Approved"
		cust.credit_limit = 50
		cust.insert(ignore_permissions=True)
		leaf = self._gl("5302", "Revenue OVR2", 0)
		si = frappe.new_doc("Sales Invoice")
		si.company = self.company
		si.customer = cust.name
		si.posting_date = today()
		si.credit_limit_override_approved = 1
		si.credit_limit_override_reason = "Approved for strategic account launch."
		si.append("items", {"item_code": "line", "qty": 1, "rate": 100, "income_account": leaf})
		si.insert(ignore_permissions=True)
		si.submit()
		self.assertEqual(si.docstatus, 1)

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

	def test_purchase_invoice_amend_after_cancel(self):
		frappe.set_user("Administrator")
		supp = frappe.new_doc("Supplier")
		supp.company = self.company
		supp.supplier_name = "Amend PI"
		supp.insert(ignore_permissions=True)
		exp = self._gl("7370", "Exp Amend PI", 0)
		pi = frappe.new_doc("Purchase Invoice")
		pi.company = self.company
		pi.supplier = supp.name
		pi.posting_date = today()
		pi.append("items", {"item_code": "x", "qty": 1, "rate": 8, "expense_account": exp})
		pi.insert(ignore_permissions=True)
		pi.submit()
		pi.cancel()
		amended = frappe.copy_doc(frappe.get_doc("Purchase Invoice", pi.name))
		amended.amended_from = pi.name
		amended.docstatus = 0
		amended.insert(ignore_permissions=True)
		amended.items[0].rate = 12
		amended.save(ignore_permissions=True)
		amended.submit()
		self.assertEqual(amended.docstatus, 1)
		self.assertEqual(amended.amended_from, pi.name)
		self.assertEqual(amended.grand_total, 12.0)

	def test_journal_entry_amend_after_cancel(self):
		frappe.set_user("Administrator")
		a1 = self._gl("7371", "JE Am Dr", 0)
		a2 = self._gl("7372", "JE Am Cr", 0)
		je = frappe.new_doc("Journal Entry")
		je.company = self.company
		je.posting_date = today()
		je.append("accounts", {"account": a1, "debit": 20, "credit": 0})
		je.append("accounts", {"account": a2, "debit": 0, "credit": 20})
		je.insert(ignore_permissions=True)
		je.submit()
		je.cancel()
		amended = frappe.copy_doc(frappe.get_doc("Journal Entry", je.name))
		amended.amended_from = je.name
		amended.docstatus = 0
		amended.insert(ignore_permissions=True)
		amended.accounts[0].debit = 25
		amended.accounts[1].credit = 25
		amended.save(ignore_permissions=True)
		amended.submit()
		self.assertEqual(amended.docstatus, 1)
		self.assertEqual(amended.amended_from, je.name)

	def test_payment_entry_amend_after_cancel(self):
		frappe.set_user("Administrator")
		cust = frappe.new_doc("Customer")
		cust.company = self.company
		cust.customer_name = "Amend PE"
		cust.insert(ignore_permissions=True)
		pe = frappe.new_doc("Payment Entry")
		pe.company = self.company
		pe.party_type = "Customer"
		pe.party = cust.name
		pe.posting_date = today()
		pe.paid_amount = 3
		pe.insert(ignore_permissions=True)
		pe.submit()
		pe.cancel()
		amended = frappe.copy_doc(frappe.get_doc("Payment Entry", pe.name))
		amended.amended_from = pe.name
		amended.docstatus = 0
		amended.insert(ignore_permissions=True)
		amended.paid_amount = 9
		amended.save(ignore_permissions=True)
		amended.submit()
		self.assertEqual(amended.docstatus, 1)
		self.assertEqual(amended.amended_from, pe.name)
		self.assertEqual(amended.paid_amount, 9.0)

	def test_payment_entry_amend_with_reference_switches_to_amended_invoice(self):
		frappe.set_user("Administrator")
		cust = frappe.new_doc("Customer")
		cust.company = self.company
		cust.customer_name = "PE Amend Ref"
		cust.insert(ignore_permissions=True)
		leaf = self._gl("7373", "Rev PE Amend Ref", 0)
		si = frappe.new_doc("Sales Invoice")
		si.company = self.company
		si.customer = cust.name
		si.posting_date = today()
		si.append("items", {"item_code": "x", "qty": 1, "rate": 15, "income_account": leaf})
		si.insert(ignore_permissions=True)
		si.submit()
		pe = frappe.new_doc("Payment Entry")
		pe.company = self.company
		pe.party_type = "Customer"
		pe.party = cust.name
		pe.posting_date = today()
		pe.paid_amount = 15
		pe.append(
			"references",
			{
				"reference_doctype": "Sales Invoice",
				"reference_name": si.name,
				"allocated_amount": 15,
			},
		)
		pe.insert(ignore_permissions=True)
		pe.submit()
		pe.cancel()
		si.cancel()
		si_amended = frappe.copy_doc(frappe.get_doc("Sales Invoice", si.name))
		si_amended.amended_from = si.name
		si_amended.docstatus = 0
		si_amended.insert(ignore_permissions=True)
		si_amended.submit()
		pe_amended = frappe.copy_doc(frappe.get_doc("Payment Entry", pe.name))
		pe_amended.amended_from = pe.name
		pe_amended.docstatus = 0
		with self.assertRaises(frappe.CancelledLinkError):
			pe_amended.insert(ignore_permissions=True)
		pe_amended = frappe.copy_doc(frappe.get_doc("Payment Entry", pe.name))
		pe_amended.amended_from = pe.name
		pe_amended.docstatus = 0
		pe_amended.references[0].reference_name = si_amended.name
		pe_amended.insert(ignore_permissions=True)
		pe_amended.submit()
		self.assertEqual(pe_amended.docstatus, 1)
		self.assertEqual(pe_amended.references[0].reference_name, si_amended.name)

	def test_sales_invoice_amendment_chain_allows_multiple_generations(self):
		frappe.set_user("Administrator")
		cust = frappe.new_doc("Customer")
		cust.company = self.company
		cust.customer_name = "Amend Chain"
		cust.insert(ignore_permissions=True)
		leaf = self._gl("7374", "Rev Amend Chain", 0)
		original = frappe.new_doc("Sales Invoice")
		original.company = self.company
		original.customer = cust.name
		original.posting_date = today()
		original.append("items", {"item_code": "x", "qty": 1, "rate": 5, "income_account": leaf})
		original.insert(ignore_permissions=True)
		original.submit()
		original.cancel()
		amend_1 = frappe.copy_doc(frappe.get_doc("Sales Invoice", original.name))
		amend_1.amended_from = original.name
		amend_1.docstatus = 0
		amend_1.insert(ignore_permissions=True)
		amend_1.items[0].rate = 7
		amend_1.save(ignore_permissions=True)
		amend_1.submit()
		amend_1.cancel()
		amend_2 = frappe.copy_doc(frappe.get_doc("Sales Invoice", amend_1.name))
		amend_2.amended_from = amend_1.name
		amend_2.docstatus = 0
		amend_2.insert(ignore_permissions=True)
		amend_2.items[0].rate = 9
		amend_2.save(ignore_permissions=True)
		amend_2.submit()
		self.assertEqual(amend_2.docstatus, 1)
		self.assertEqual(amend_2.amended_from, amend_1.name)
		self.assertEqual(amend_2.grand_total, 9.0)

	def test_payment_entry_amendment_chain_with_reference_updates_each_generation(self):
		frappe.set_user("Administrator")
		cust = frappe.new_doc("Customer")
		cust.company = self.company
		cust.customer_name = "PE Chain Ref"
		cust.insert(ignore_permissions=True)
		leaf = self._gl("7375", "Rev PE Chain", 0)
		si = frappe.new_doc("Sales Invoice")
		si.company = self.company
		si.customer = cust.name
		si.posting_date = today()
		si.append("items", {"item_code": "x", "qty": 1, "rate": 20, "income_account": leaf})
		si.insert(ignore_permissions=True)
		si.submit()
		pe = frappe.new_doc("Payment Entry")
		pe.company = self.company
		pe.party_type = "Customer"
		pe.party = cust.name
		pe.posting_date = today()
		pe.paid_amount = 20
		pe.append(
			"references",
			{
				"reference_doctype": "Sales Invoice",
				"reference_name": si.name,
				"allocated_amount": 20,
			},
		)
		pe.insert(ignore_permissions=True)
		pe.submit()
		pe.cancel()
		si.cancel()
		si_amend_1 = frappe.copy_doc(frappe.get_doc("Sales Invoice", si.name))
		si_amend_1.amended_from = si.name
		si_amend_1.docstatus = 0
		si_amend_1.insert(ignore_permissions=True)
		si_amend_1.submit()
		pe_amend_1 = frappe.copy_doc(frappe.get_doc("Payment Entry", pe.name))
		pe_amend_1.amended_from = pe.name
		pe_amend_1.docstatus = 0
		pe_amend_1.references[0].reference_name = si_amend_1.name
		pe_amend_1.insert(ignore_permissions=True)
		pe_amend_1.submit()
		pe_amend_1.cancel()
		si_amend_1.cancel()
		si_amend_2 = frappe.copy_doc(frappe.get_doc("Sales Invoice", si_amend_1.name))
		si_amend_2.amended_from = si_amend_1.name
		si_amend_2.docstatus = 0
		si_amend_2.insert(ignore_permissions=True)
		si_amend_2.submit()
		pe_amend_2 = frappe.copy_doc(frappe.get_doc("Payment Entry", pe_amend_1.name))
		pe_amend_2.amended_from = pe_amend_1.name
		pe_amend_2.docstatus = 0
		pe_amend_2.references[0].reference_name = si_amend_2.name
		pe_amend_2.insert(ignore_permissions=True)
		pe_amend_2.submit()
		self.assertEqual(pe_amend_2.docstatus, 1)
		self.assertEqual(pe_amend_2.amended_from, pe_amend_1.name)
		self.assertEqual(pe_amend_2.references[0].reference_name, si_amend_2.name)
