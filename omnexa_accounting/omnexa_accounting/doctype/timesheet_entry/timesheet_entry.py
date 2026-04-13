# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class TimesheetEntry(Document):
	def validate(self):
		self._validate_company_scope()
		self._validate_hours_and_rate()
		self._set_billable_amount()

	def on_submit(self):
		if self.is_billable and flt(self.billable_amount) > 0:
			self._create_sales_invoice_bridge()

	def _validate_company_scope(self):
		project = frappe.get_doc("Project Template", self.project_template)
		if project.company != self.company:
			frappe.throw(_("Project Template belongs to a different company."), title=_("Timesheet"))
		if self.employee and frappe.db.get_value("Employee", self.employee, "company") != self.company:
			frappe.throw(_("Employee belongs to a different company."), title=_("Timesheet"))

	def _validate_hours_and_rate(self):
		if flt(self.hours) <= 0:
			frappe.throw(_("Hours must be greater than zero."), title=_("Timesheet"))
		if flt(self.billing_rate) < 0:
			frappe.throw(_("Billing Rate cannot be negative."), title=_("Timesheet"))

	def _set_billable_amount(self):
		if not self.is_billable:
			self.billable_amount = 0
			return
		rate = flt(self.billing_rate)
		if rate <= 0:
			rate = flt(frappe.db.get_value("Project Template", self.project_template, "default_billing_rate") or 0)
			self.billing_rate = rate
		self.billable_amount = flt(self.hours) * rate

	def _create_sales_invoice_bridge(self):
		if self.sales_invoice:
			return
		project = frappe.get_doc("Project Template", self.project_template)
		if not project.customer:
			frappe.throw(_("Project Template requires Customer for billable timesheet bridging."), title=_("Timesheet"))
		if not project.default_income_account:
			frappe.throw(_("Project Template requires Default Income Account for billable timesheet bridging."), title=_("Timesheet"))
		si = frappe.new_doc("Sales Invoice")
		si.company = self.company
		si.customer = project.customer
		si.posting_date = self.posting_date
		si.append(
			"items",
			{
				"item_code": f"Timesheet {self.project_template}",
				"qty": 1,
				"rate": flt(self.billable_amount),
				"income_account": project.default_income_account,
			},
		)
		si.insert(ignore_permissions=True)
		self.db_set("sales_invoice", si.name)
