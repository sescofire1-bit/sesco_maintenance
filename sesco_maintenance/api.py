"""Whitelisted helpers for forms, the workspace number cards and the equipment timeline."""

import frappe
from frappe import _
from frappe.utils import add_days, flt, today

from sesco_maintenance.billing import get_billable_sources
from sesco_maintenance.movement import EQUIPMENT_TABLES, get_reserving_draft, get_settings

PURPOSES = {
	# purpose: (allowed status, route)
	"maintenance": (("In Workshop",), "Internal"),
	"dispatch": (("In Workshop",), "External"),
	"delivery": (("Ready", "Damaged"), None),
}


def _hydrotest_flag(next_date):
	if not next_date:
		return None
	days = (frappe.utils.getdate(next_date) - frappe.utils.getdate(today())).days
	if days < 0:
		return "overdue"
	if days <= (get_settings().hydrotest_reminder_days or 60):
		return "due"
	return None


@frappe.whitelist()
def get_available_equipment(purpose, customer=None, doctype=None, docname=None, exclude=None):
	"""Equipment a 'Get ...' button may add: right status/route, not in another draft."""
	if purpose not in PURPOSES:
		frappe.throw(_("Unknown purpose {0}").format(purpose))
	frappe.has_permission("Customer Equipment", "read", throw=True)
	statuses, route = PURPOSES[purpose]
	filters = {"status": ("in", statuses)}
	if route:
		filters["route"] = route
	if customer:
		filters["customer"] = customer
	exclude = set(frappe.parse_json(exclude) or [])
	current = frappe._dict(doctype=doctype, name=docname) if doctype else None

	out = []
	for eq in frappe.get_all(
		"Customer Equipment",
		filters=filters,
		fields=["name", "customer", "equipment_type", "status", "next_hydrotest_date"],
		order_by="name asc",
	):
		if eq.name in exclude or get_reserving_draft(eq.name, current):
			continue
		eq.hydrotest = _hydrotest_flag(eq.next_hydrotest_date)
		out.append(eq)
	return out


@frappe.whitelist()
def get_equipment_for_receipt(code, customer, doctype=None, docname=None):
	"""Scan on Equipment Receipt: returns the equipment or a message saying why it can't be added."""
	code = (code or "").strip().upper()
	eq = frappe.db.get_value(
		"Customer Equipment", code, ["name", "customer", "equipment_type", "route", "status", "next_hydrotest_date", "last_hydrotest_date"], as_dict=True
	)
	if not eq:
		return {"error": _("Code {0} doesn't exist. For new equipment use Add by Quantity.").format(code)}
	if eq.customer != customer:
		return {"error": _("Equipment {0} belongs to customer {1}.").format(code, eq.customer)}
	if eq.status != "At Customer":
		return {"error": _("Equipment {0} is already with us ({1}), so it can't be received again.").format(code, _(eq.status))}
	hit = get_reserving_draft(code, frappe._dict(doctype=doctype, name=docname) if doctype else None)
	if hit:
		return {"error": _("Equipment {0} is in draft {1} {2}, which is waiting for approval.").format(code, _(hit[0]), hit[1])}
	eq.hydrotest = _hydrotest_flag(eq.next_hydrotest_date)
	return {"equipment": eq}


@frappe.whitelist()
def get_accessory_details(item_code):
	warehouse = get_settings().maintenance_warehouse
	data = frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, ["actual_qty", "valuation_rate"], as_dict=True) or {}
	return {
		"available_qty": flt(data.get("actual_qty")),
		"valuation_rate": flt(data.get("valuation_rate")) or flt(frappe.db.get_value("Item", item_code, "valuation_rate")),
		"warehouse": warehouse,
	}


@frappe.whitelist()
def get_equipment_activity(equipment):
	frappe.get_doc("Customer Equipment", equipment).check_permission("read")
	return frappe.get_all(
		"Equipment Activity",
		filters={"equipment": equipment},
		fields=["activity_date", "activity_type", "from_location", "to_location", "reference_doctype", "reference_name", "user", "notes"],
		order_by="creation desc",
	)


# ---------------------------------------------------------------- number cards (type: Custom)
# The number card widget calls these with a `filters` argument, which they ignore.


def _card(value, route=None, route_options=None):
	return {"value": value, "fieldtype": "Int", "route": route, "route_options": route_options}


@frappe.whitelist()
def pending_approvals(filters=None):
	parents = set(EQUIPMENT_TABLES.values())
	return _card(sum(frappe.db.count(dt, {"docstatus": 0}) for dt in parents))


@frappe.whitelist()
def billable_equipment(filters=None):
	customers = set(
		frappe.get_all("Maintenance Report Item", filters={"docstatus": 1, "result": "OK"}, pluck="customer")
	) | set(
		frappe.get_all("External Service Dispatch Item", filters={"docstatus": 1, "return_status": "Returned OK"}, pluck="customer")
	)
	count = sum(len(s["equipment"]) for c in customers if c for s in get_billable_sources(c))
	return _card(count)


@frappe.whitelist()
def service_due_30_days(filters=None):
	count = frappe.db.count(
		"Customer Equipment", {"status": "At Customer", "next_service_date": ("<=", add_days(today(), 30))}
	)
	return _card(count, ["query-report", "Equipment Due"], {"due_type": "Service", "days": 30})


@frappe.whitelist()
def hydrotest_due(filters=None):
	days = get_settings().hydrotest_reminder_days or 60
	count = frappe.db.count("Customer Equipment", {"next_hydrotest_date": ("<=", add_days(today(), days))})
	return _card(count, ["query-report", "Equipment Due"], {"due_type": "Hydrostatic Test", "days": days})
