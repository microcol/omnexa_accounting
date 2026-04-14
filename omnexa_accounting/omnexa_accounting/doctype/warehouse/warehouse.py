import frappe
from frappe import _
from frappe.model.document import Document


class Warehouse(Document):
	def validate(self):
		if self.parent_warehouse:
			parent_company = frappe.db.get_value("Warehouse", self.parent_warehouse, "company")
			if parent_company and parent_company != self.company:
				frappe.throw(_("Parent Warehouse belongs to a different company."), title=_("Company"))
