"""Equipment movement: validation, status changes, the activity log and reverting on cancel.

Every change to a Customer Equipment record goes through `apply_movement`, which also writes an
Equipment Activity row holding a snapshot of the previous values. Cancelling a document calls
`revert_movements`, which restores those snapshots.
"""

import json

import frappe
from frappe import _
from frappe.utils import add_months, add_years, getdate

TRACKED_FIELDS = (
	"status",
	"route",
	"current_location",
	"current_supplier",
	"last_receipt",
	"last_service_date",
	"next_service_date",
	"last_hydrotest_date",
	"next_hydrotest_date",
)

# child table -> parent doctype; an equipment row in any draft of these is "reserved"
EQUIPMENT_TABLES = {
	"Equipment Receipt Item": "Equipment Receipt",
	"Maintenance Report Item": "Equipment Maintenance Report",
	"External Service Dispatch Item": "External Service Dispatch",
	"Equipment Delivery Item": "Equipment Delivery",
}


def get_settings():
	return frappe.get_cached_doc("Equipment Maintenance Settings")


def get_equipment_info(equipment):
	return frappe.db.get_value(
		"Customer Equipment",
		equipment,
		["name", "customer", "equipment_type", "status", "route", "last_receipt"],
		as_dict=True,
	)


def service_updates(equipment_type, date):
	months = frappe.get_cached_value("Equipment Type", equipment_type, "maintenance_interval_months") or 12
	return {"last_service_date": date, "next_service_date": add_months(getdate(date), months)}


def hydrotest_updates(equipment_type, date):
	years = frappe.get_cached_value("Equipment Type", equipment_type, "hydrotest_interval_years")
	if not (years and date):
		return {}
	return {"last_hydrotest_date": date, "next_hydrotest_date": add_years(getdate(date), years)}


def get_reserving_draft(equipment, doc=None):
	"""Return (doctype, name) of another draft that already holds this equipment, or None."""
	for child, parent in EQUIPMENT_TABLES.items():
		for name in frappe.get_all(
			child, filters={"equipment": equipment, "docstatus": 0, "parenttype": parent}, pluck="parent"
		):
			if doc and parent == doc.doctype and name == doc.name:
				continue
			return parent, name
	return None


def check_not_reserved(equipment, doc, idx=None):
	hit = get_reserving_draft(equipment, doc)
	if hit:
		frappe.throw(
			_("Row {0}: Equipment {1} is already in draft {2} {3}, which is waiting for approval.").format(
				idx or "-", equipment, _(hit[0]), hit[1]
			)
		)


def validate_rows(doc, allowed_status, customer=None, route=None, table="items"):
	"""Common row checks: exists, not duplicated, right customer / status / route, not in another draft."""
	seen = set()
	for row in doc.get(table):
		if not row.equipment:
			continue
		if row.equipment in seen:
			frappe.throw(_("Row {0}: Equipment {1} is added more than once.").format(row.idx, row.equipment))
		seen.add(row.equipment)

		info = get_equipment_info(row.equipment)
		if not info:
			frappe.throw(_("Row {0}: Equipment {1} does not exist.").format(row.idx, row.equipment))
		if customer and info.customer != customer:
			frappe.throw(
				_("Row {0}: Equipment {1} belongs to customer {2}.").format(row.idx, row.equipment, info.customer)
			)
		if info.status not in allowed_status:
			frappe.throw(
				_("Row {0}: Equipment {1} is {2}. Allowed status: {3}.").format(
					row.idx, row.equipment, _(info.status), ", ".join(_(s) for s in allowed_status)
				)
			)
		if route and info.route != route:
			frappe.throw(
				_("Row {0}: Equipment {1} route is {2}, this document is for {3} equipment.").format(
					row.idx, row.equipment, _(info.route or ""), _(route)
				)
			)
		check_not_reserved(row.equipment, doc, row.idx)


def apply_movement(doc, equipment, activity_type, updates, to_location, date=None, notes=None):
	"""Update the equipment and log the activity with a snapshot of the previous values."""
	eq = frappe.get_doc("Customer Equipment", equipment)
	snapshot = {f: (str(eq.get(f)) if eq.get(f) is not None else None) for f in TRACKED_FIELDS}
	from_location = eq.current_location

	eq.update(updates)
	eq.current_location = to_location
	eq.flags.ignore_permissions = True
	eq.save()

	frappe.get_doc(
		{
			"doctype": "Equipment Activity",
			"equipment": eq.name,
			"customer": eq.customer,
			"activity_type": activity_type,
			"activity_date": date or doc.get("posting_date"),
			"from_location": from_location,
			"to_location": to_location,
			"reference_doctype": doc.doctype,
			"reference_name": doc.name,
			"user": frappe.session.user,
			"notes": notes,
			"snapshot": json.dumps(snapshot),
		}
	).insert(ignore_permissions=True)


def revert_movements(doc):
	"""Undo all movements of `doc`. Blocks if any equipment moved again afterwards."""
	activities = frappe.get_all(
		"Equipment Activity",
		filters={"reference_doctype": doc.doctype, "reference_name": doc.name},
		fields=["name", "equipment", "snapshot", "creation"],
		order_by="creation desc",
	)
	for act in activities:
		later = frappe.db.get_value(
			"Equipment Activity",
			{"equipment": act.equipment, "creation": (">", act.creation), "reference_name": ("!=", doc.name)},
			["reference_doctype", "reference_name"],
			as_dict=True,
		)
		if later:
			frappe.throw(
				_("Equipment {0} moved again in {1} {2}. Cancel that document first.").format(
					act.equipment, _(later.reference_doctype), later.reference_name
				)
			)

	for act in activities:
		eq = frappe.get_doc("Customer Equipment", act.equipment)
		eq.update(json.loads(act.snapshot or "{}"))
		eq.flags.ignore_permissions = True
		eq.save()
		frappe.delete_doc("Equipment Activity", act.name, ignore_permissions=True, force=True)


def set_receipt_reference(doc):
	"""Remember which receipt each row's equipment came in with (used by the profitability report)."""
	for row in doc.items:
		if row.equipment:
			row.equipment_receipt = frappe.db.get_value("Customer Equipment", row.equipment, "last_receipt")
