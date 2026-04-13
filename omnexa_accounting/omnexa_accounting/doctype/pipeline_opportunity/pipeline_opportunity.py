# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt
from omnexa_core.omnexa_core.constants import (
	CLOSED_PIPELINE_STAGES,
	OPEN_PIPELINE_STAGES,
	PIPELINE_STAGE_ORDER,
)


class PipelineOpportunity(Document):
	def validate(self):
		if self.customer and frappe.db.get_value("Customer", self.customer, "company") != self.company:
			frappe.throw(_("Customer belongs to a different company."), title=_("Opportunity"))
		if self.pipeline_lead and frappe.db.get_value("Pipeline Lead", self.pipeline_lead, "company") != self.company:
			frappe.throw(_("Lead belongs to a different company."), title=_("Opportunity"))
		if flt(self.amount) < 0:
			frappe.throw(_("Amount cannot be negative."), title=_("Opportunity"))
		if flt(self.probability) < 0 or flt(self.probability) > 100:
			frappe.throw(_("Probability must be between 0 and 100."), title=_("Opportunity"))
		if self.stage in OPEN_PIPELINE_STAGES and not self.next_follow_up_date:
			frappe.throw(_("Next Follow Up Date is required for open pipeline stages."), title=_("Opportunity"))
		if self.stage in CLOSED_PIPELINE_STAGES and not self.closing_date:
			frappe.throw(_("Closing Date is required for Won/Lost stage."), title=_("Opportunity"))
		if not self.is_new():
			before = self.get_doc_before_save()
			if before and before.stage != self.stage:
				if before.stage in CLOSED_PIPELINE_STAGES:
					frappe.throw(_("Cannot move stage after opportunity is closed (Won/Lost)."), title=_("Opportunity"))
				if PIPELINE_STAGE_ORDER.get(self.stage, 0) < PIPELINE_STAGE_ORDER.get(before.stage, 0):
					frappe.throw(_("Stage regression is not allowed for pipeline hygiene."), title=_("Opportunity"))
