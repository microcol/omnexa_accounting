# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class FiscalYear(Document):
	def validate(self):
		if self.year_start_date and self.year_end_date and getdate(self.year_start_date) > getdate(
			self.year_end_date
		):
			frappe.throw(_("Year start must be on or before year end."), title=_("Validation"))

		self._validate_no_overlap()
		self._validate_periods_within_year()
		self._validate_period_freeze_permissions()

	def _validate_no_overlap(self):
		filters = {"company": self.company}
		if self.name:
			filters["name"] = ["!=", self.name]
		others = frappe.get_all(
			"Fiscal Year",
			filters=filters,
			fields=["name", "year_start_date", "year_end_date"],
		)
		s0, e0 = getdate(self.year_start_date), getdate(self.year_end_date)
		for row in others:
			s1, e1 = getdate(row.year_start_date), getdate(row.year_end_date)
			if s0 <= e1 and s1 <= e0:
				frappe.throw(
					_("Fiscal Year overlaps with {0}").format(row.name), title=_("Overlap")
				)

	def _validate_periods_within_year(self):
		ys, ye = getdate(self.year_start_date), getdate(self.year_end_date)
		for row in self.periods or []:
			ps, pe = getdate(row.period_start_date), getdate(row.period_end_date)
			if ps < ys or pe > ye:
				frappe.throw(
					_("Period {0} must fall within fiscal year dates.").format(row.period_name or row.idx),
					title=_("Period"),
				)
			if ps > pe:
				frappe.throw(_("Period start must be on or before end."), title=_("Period"))

	def _validate_period_freeze_permissions(self):
		"""Only finance-privileged users can freeze periods."""
		current_user = frappe.session.user
		if current_user in ("Administrator", "Guest"):
			return

		roles = set(frappe.get_roles(current_user))
		if "System Manager" in roles or "Accounts Manager" in roles:
			return

		previous_frozen_by_row = {}
		if not self.is_new():
			for row in frappe.get_all(
				"Fiscal Year Period",
				filters={"parent": self.name, "parenttype": "Fiscal Year"},
				fields=["name", "frozen"],
			):
				previous_frozen_by_row[row.name] = int(row.frozen or 0)

		for row in self.periods or []:
			current_frozen = int(row.frozen or 0)
			if not current_frozen:
				continue
			# New frozen period or toggled from unfrozen -> frozen requires privileged role.
			previous_frozen = int(previous_frozen_by_row.get(row.name, 0))
			if not previous_frozen:
				frappe.throw(
					_("Only Accounts Manager or System Manager can freeze fiscal periods."),
					title=_("Permission"),
				)
