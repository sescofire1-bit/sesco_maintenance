from collections import Counter

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, getdate, today

from sesco_maintenance.movement import (
	apply_movement,
	hydrotest_updates,
	revert_movements,
	service_updates,
	set_receipt_reference,
	validate_rows,
)

RETURN_ROLES = ("Maintenance Storekeeper", "Maintenance Approver", "System Manager")


class ExternalServiceDispatch(Document):
	def validate(self):
		validate_rows(self, allowed_status=("In Workshop",), route="External")
		set_receipt_reference(self)
		if self.transport_mode != "Company Driver":
			self.driver = None
		self.status = "Draft"

	def on_submit(self):
		supplier_name = frappe.db.get_value("Supplier", self.supplier, "supplier_name") or self.supplier
		driver = frappe.db.get_value("Employee", self.driver, "employee_name") if self.driver else None
		notes = _(self.transport_mode) + (f" — {driver}" if driver else "")
		for row in self.items:
			apply_movement(
				self,
				row.equipment,
				"Sent to Supplier",
				{"status": "At Supplier", "current_supplier": self.supplier},
				supplier_name,
				notes=notes,
			)
		self.db_set("status", "At Supplier")

	def on_cancel(self):
		self.ignore_linked_doctypes = ("Equipment Activity", "Purchase Invoice")
		if any(row.return_status != "At Supplier" for row in self.items):
			frappe.throw(_("Some equipment is already returned from the supplier, so this dispatch can't be cancelled."))
		revert_movements(self)
		self.db_set("status", "Cancelled")

	@frappe.whitelist()
	def register_return(self, rows, return_date=None):
		"""rows: [{"row": <child name>, "return_status": "Returned OK" | "Returned Damaged", "hydrotest_done": 0/1}]"""
		if not set(RETURN_ROLES) & set(frappe.get_roles()):
			frappe.throw(_("You are not allowed to register returns."), frappe.PermissionError)
		if self.docstatus != 1:
			frappe.throw(_("Submit the dispatch before registering returns."))

		return_date = getdate(return_date or today())
		if return_date < getdate(self.posting_date):
			frappe.throw(_("Return date can't be before the dispatch date."))

		by_name = {row.name: row for row in self.items}
		done = 0
		for entry in frappe.parse_json(rows) or []:
			row = by_name.get(entry.get("row"))
			status = entry.get("return_status")
			if not row or row.return_status != "At Supplier" or status not in ("Returned OK", "Returned Damaged"):
				continue

			hydro = cint(entry.get("hydrotest_done"))
			if status == "Returned OK":
				updates = {"status": "Ready", **service_updates(row.equipment_type, return_date)}
				location = _("Workshop (Ready)")
			else:
				updates = {"status": "Damaged"}
				location = _("Workshop (Damaged)")
			updates["current_supplier"] = None
			if hydro:
				updates.update(hydrotest_updates(row.equipment_type, return_date))

			notes = _("Hydrostatic test done") if hydro else (_("Rejected by supplier") if status == "Returned Damaged" else None)
			apply_movement(self, row.equipment, "Returned from Supplier", updates, location, date=return_date, notes=notes)
			row.db_set({"return_status": status, "return_date": return_date, "hydrotest_done": hydro})
			done += 1

		if not done:
			frappe.throw(_("Choose Returned OK or Returned Damaged for at least one row."))
		self.update_return_status()
		return done

	def update_return_status(self):
		pending = sum(1 for row in self.items if row.return_status == "At Supplier")
		if pending == len(self.items):
			status = "At Supplier"
		elif pending:
			status = "Partially Returned"
		else:
			status = "Returned"
		self.db_set("status", status)


@frappe.whitelist()
def make_purchase_invoice(source_name):
	"""Draft Purchase Invoice with the supplier's service items for equipment returned OK and not invoiced yet."""
	dispatch = frappe.get_doc("External Service Dispatch", source_name)
	dispatch.check_permission("read")
	frappe.has_permission("Purchase Invoice", "create", throw=True)

	rows = [r for r in dispatch.items if r.return_status == "Returned OK" and not r.purchase_invoice]
	if not rows:
		frappe.throw(_("No equipment returned OK is waiting for a supplier invoice."))

	pi = frappe.new_doc("Purchase Invoice")
	pi.supplier = dispatch.supplier
	pi.external_service_dispatch = dispatch.name
	for equipment_type, qty in Counter(r.equipment_type for r in rows).items():
		item_code, rate = frappe.get_cached_value(
			"Equipment Type", equipment_type, ["supplier_service_item", "supplier_rate"]
		)
		if not item_code:
			frappe.throw(_("Set the Supplier Service Item on equipment type {0}.").format(equipment_type))
		pi.append("items", {"item_code": item_code, "qty": qty, "rate": rate})

	pi.set_missing_values()
	pi.calculate_taxes_and_totals()
	return pi


def link_purchase_invoice(doc, method=None):
	"""Purchase Invoice on_submit: mark the dispatch rows it pays for."""
	if not doc.get("external_service_dispatch"):
		return
	for row in frappe.get_all(
		"External Service Dispatch Item",
		filters={"parent": doc.external_service_dispatch, "return_status": "Returned OK", "purchase_invoice": ("is", "not set")},
		pluck="name",
	):
		frappe.db.set_value("External Service Dispatch Item", row, "purchase_invoice", doc.name)


def unlink_purchase_invoice(doc, method=None):
	if not doc.get("external_service_dispatch"):
		return
	for row in frappe.get_all("External Service Dispatch Item", filters={"purchase_invoice": doc.name}, pluck="name"):
		frappe.db.set_value("External Service Dispatch Item", row, "purchase_invoice", None)
