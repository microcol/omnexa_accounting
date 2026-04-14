import frappe
from frappe.model.document import Document


class CRMActivity(Document):
	def validate(self):
		if self.reference_name and not self.reference_doctype:
			frappe.throw("Reference Type is required when Reference is set.")

