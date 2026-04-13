# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, getdate


class Employee(Document):
	def validate(self):
		existing = frappe.db.get_value(
			"Employee",
			{"company": self.company, "employee_code": self.employee_code},
			"name",
		)
		if existing and (not self.name or existing != self.name):
			frappe.throw(_("Employee Code must be unique per company."), title=_("Employee"))
		if self.manager:
			if self.manager == self.name:
				frappe.throw(_("Employee cannot be their own manager."), title=_("Employee"))
			manager_company = frappe.db.get_value("Employee", self.manager, "company")
			if manager_company != self.company:
				frappe.throw(_("Manager belongs to a different company."), title=_("Employee"))
		if self.leave_policy:
			policy_company = frappe.db.get_value("Leave Policy", self.leave_policy, "company")
			if policy_company != self.company:
				frappe.throw(_("Leave Policy belongs to a different company."), title=_("Employee"))
		self._validate_license_tracking()

	def _validate_license_tracking(self):
		if self.license_issue_date and self.license_expiry_date:
			if getdate(self.license_expiry_date) < getdate(self.license_issue_date):
				frappe.throw(_("License Expiry Date cannot be before License Issue Date."), title=_("Employee"))

		if self.primary_license_type or self.license_number or self.license_issue_date or self.license_expiry_date:
			if not self.primary_license_type or not self.license_number:
				frappe.throw(
					_("Primary License Type and License Number are required when license tracking is used."),
					title=_("Employee"),
				)

		if not self.license_expiry_date:
			if self.primary_license_type or self.license_number:
				self.license_status = "Valid"
			else:
				self.license_status = "Not Required"
			return

		today = getdate()
		expiry = getdate(self.license_expiry_date)
		if expiry < today:
			self.license_status = "Expired"
		elif expiry <= add_days(today, 60):
			self.license_status = "Expiring Soon"
		else:
			self.license_status = "Valid"
