import frappe
from frappe import _


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if not filters.get("customer"):
		return get_columns(), []

	equipment = frappe.get_all(
		"Customer Equipment",
		filters={"customer": filters.customer},
		fields=["name", "equipment_type", "status", "last_service_date", "next_service_date", "next_hydrotest_date"],
		order_by="name asc",
	)
	visits = dict(
		frappe.db.sql(
			"""select equipment, count(*) from `tabEquipment Activity`
			where customer = %s and activity_type = 'Received' group by equipment""",
			filters.customer,
		)
	)
	data = [
		{
			"equipment": e.name,
			"equipment_type": e.equipment_type,
			"status": _(e.status),
			"last_service_date": e.last_service_date,
			"next_service_date": e.next_service_date,
			"next_hydrotest_date": e.next_hydrotest_date,
			"times_received": visits.get(e.name, 0),
		}
		for e in equipment
	]
	return get_columns(), data


def get_columns():
	return [
		{"label": _("Equipment"), "fieldname": "equipment", "fieldtype": "Link", "options": "Customer Equipment", "width": 130},
		{"label": _("Equipment Type"), "fieldname": "equipment_type", "fieldtype": "Link", "options": "Equipment Type", "width": 180},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 120},
		{"label": _("Last Service Date"), "fieldname": "last_service_date", "fieldtype": "Date", "width": 120},
		{"label": _("Next Service Date"), "fieldname": "next_service_date", "fieldtype": "Date", "width": 120},
		{"label": _("Next Hydrostatic Test"), "fieldname": "next_hydrotest_date", "fieldtype": "Date", "width": 140},
		{"label": _("Times Received"), "fieldname": "times_received", "fieldtype": "Int", "width": 110},
	]
