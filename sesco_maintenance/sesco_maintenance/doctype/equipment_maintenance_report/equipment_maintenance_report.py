from collections import defaultdict

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from sesco_maintenance.billing import is_active_billing
from sesco_maintenance.movement import (
	apply_movement,
	get_settings,
	hydrotest_updates,
	revert_movements,
	service_updates,
	set_receipt_reference,
	validate_rows,
)


class EquipmentMaintenanceReport(Document):
	def validate(self):
		validate_rows(self, allowed_status=("In Workshop",), route="Internal")
		set_receipt_reference(self)
		self.set_accessory_details()
		self.validate_stock()

	def set_accessory_details(self):
		warehouse = get_settings().maintenance_warehouse
		total = 0
		for acc in self.accessories:
			if not acc.uom:
				acc.uom = frappe.get_cached_value("Item", acc.item_code, "stock_uom")
			bin_data = (
				frappe.db.get_value(
					"Bin",
					{"item_code": acc.item_code, "warehouse": warehouse},
					["actual_qty", "valuation_rate"],
					as_dict=True,
				)
				or {}
			)
			acc.available_qty = flt(bin_data.get("actual_qty"))
			acc.valuation_rate = flt(bin_data.get("valuation_rate")) or flt(
				frappe.get_cached_value("Item", acc.item_code, "valuation_rate")
			)
			acc.amount = flt(acc.qty) * flt(acc.valuation_rate)
			total += acc.amount
		self.total_accessories_cost = total

	def validate_stock(self):
		warehouse = get_settings().maintenance_warehouse
		required = defaultdict(float)
		available = {}
		for acc in self.accessories:
			if flt(acc.qty) <= 0:
				frappe.throw(_("Row {0}: Quantity of {1} must be more than zero.").format(acc.idx, acc.item_code))
			if not frappe.get_cached_value("Item", acc.item_code, "is_stock_item"):
				frappe.throw(_("Row {0}: {1} is not a stock item.").format(acc.idx, acc.item_code))
			required[acc.item_code] += flt(acc.qty)
			available[acc.item_code] = (flt(acc.available_qty), acc.uom)

		for item_code, qty in required.items():
			avail, uom = available[item_code]
			if qty > avail:
				message = _(
					"Not enough stock of {0} in {1}: available {2} {3}, required {4}. The report stays as a draft until the stock or the quantity is corrected."
				).format(item_code, warehouse, avail, _(uom or ""), qty)
				if getattr(self, "_action", None) == "submit":
					frappe.throw(message, title=_("Not Enough Stock"))
				frappe.msgprint(message, indicator="orange", alert=True)

	def on_submit(self):
		for row in self.items:
			if row.result == "OK":
				updates = {"status": "Ready", **service_updates(row.equipment_type, self.posting_date)}
				location = _("Workshop (Ready)")
			else:
				updates = {"status": "Damaged"}
				location = _("Workshop (Damaged)")
			if row.hydrotest_done:
				updates.update(hydrotest_updates(row.equipment_type, self.posting_date))

			technician = frappe.db.get_value("Employee", row.technician, "employee_name") or row.technician
			notes = _("Technician: {0}").format(technician) + (f" — {row.notes}" if row.notes else "")
			apply_movement(self, row.equipment, "Maintained", updates, location, notes=notes)

		self.make_stock_entry()

	def make_stock_entry(self):
		if not self.accessories:
			return
		settings = get_settings()
		se = frappe.new_doc("Stock Entry")
		se.stock_entry_type = "Material Issue"
		se.purpose = "Material Issue"
		se.company = settings.company
		se.posting_date = self.posting_date
		se.set_posting_time = 1
		se.equipment_maintenance_report = self.name
		se.remarks = _("Accessories used in maintenance report {0}").format(self.name)
		for acc in self.accessories:
			row = {
				"item_code": acc.item_code,
				"qty": acc.qty,
				"s_warehouse": settings.maintenance_warehouse,
				"uom": acc.uom,
				"stock_uom": acc.uom,
				"conversion_factor": 1,
				"transfer_qty": acc.qty,
			}
			if settings.accessories_expense_account:
				row["expense_account"] = settings.accessories_expense_account
			se.append("items", row)

		se.flags.ignore_permissions = True
		se.insert()
		se.submit()
		self.db_set("stock_entry", se.name)

	def on_cancel(self):
		self.ignore_linked_doctypes = ("Stock Entry", "Equipment Activity")
		for row in self.items:
			if row.billed_in and is_active_billing(row.billed_in_doctype, row.billed_in):
				frappe.throw(
					_("Row {0}: Equipment {1} is billed in {2}. Cancel that first.").format(
						row.idx, row.equipment, row.billed_in
					)
				)

		if self.stock_entry:
			se = frappe.get_doc("Stock Entry", self.stock_entry)
			if se.docstatus == 1:
				se.flags.ignore_permissions = True
				se.cancel()

		revert_movements(self)
