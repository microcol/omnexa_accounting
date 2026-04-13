# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class LandedCostVoucher(Document):
	def validate(self):
		self._validate_reference_invoice()
		self._validate_charges()
		self._validate_single_active_voucher()

	def on_submit(self):
		self._apply_distribution()

	def on_cancel(self):
		self._clear_distribution()

	def _validate_reference_invoice(self):
		pi = frappe.get_doc("Purchase Invoice", self.purchase_invoice)
		if pi.docstatus != 1:
			frappe.throw(_("Landed Cost Voucher requires a submitted Purchase Invoice."), title=_("Landed Cost"))
		if pi.company != self.company:
			frappe.throw(_("Purchase Invoice belongs to a different company."), title=_("Landed Cost"))
		if not pi.items:
			frappe.throw(_("Purchase Invoice has no items to distribute landed cost on."), title=_("Landed Cost"))

	def _validate_charges(self):
		if not self.charges:
			frappe.throw(_("Add at least one landed cost charge line."), title=_("Landed Cost"))
		total = 0
		for row in self.charges:
			if flt(row.amount) <= 0:
				frappe.throw(_("Charge row {0}: Amount must be greater than zero.").format(row.idx), title=_("Landed Cost"))
			total += flt(row.amount)
		self.total_charges = total

	def _validate_single_active_voucher(self):
		existing = frappe.get_all(
			"Landed Cost Voucher",
			filters={"purchase_invoice": self.purchase_invoice, "docstatus": 1, "name": ["!=", self.name or ""]},
			pluck="name",
			limit=1,
		)
		if existing:
			frappe.throw(
				_("Submitted Landed Cost Voucher already exists for this Purchase Invoice: {0}").format(existing[0]),
				title=_("Landed Cost"),
			)

	def _apply_distribution(self):
		pi = frappe.get_doc("Purchase Invoice", self.purchase_invoice)
		base_total = sum(flt(row.amount) for row in pi.items)
		if base_total <= 0:
			base_total = sum(flt(row.qty) for row in pi.items)
		if base_total <= 0:
			frappe.throw(_("Cannot distribute landed cost because invoice base total is zero."), title=_("Landed Cost"))

		remaining = flt(self.total_charges)
		for idx, row in enumerate(pi.items, start=1):
			if idx == len(pi.items):
				share = remaining
			else:
				basis = flt(row.amount) if sum(flt(r.amount) for r in pi.items) > 0 else flt(row.qty)
				share = flt(self.total_charges) * basis / base_total
				share = flt(share, 6)
			remaining -= share
			landed_rate = flt(row.rate) + (flt(share) / flt(row.qty) if flt(row.qty) else 0)
			frappe.db.set_value(
				"Purchase Invoice Item",
				row.name,
				{
					"landed_cost_amount": flt(share),
					"landed_rate": flt(landed_rate),
				},
				update_modified=False,
			)

	def _clear_distribution(self):
		pi = frappe.get_doc("Purchase Invoice", self.purchase_invoice)
		for row in pi.items:
			frappe.db.set_value(
				"Purchase Invoice Item",
				row.name,
				{
					"landed_cost_amount": 0,
					"landed_rate": flt(row.rate),
				},
				update_modified=False,
			)
