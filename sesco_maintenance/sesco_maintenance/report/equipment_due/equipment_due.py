import frappe
from frappe import _
from frappe.utils import add_days, cint, date_diff, getdate, today


def execute(filters=None):
	filters = frappe._dict(filters or {})
	days = cint(filters.get("days")) or 60
	hydrotest = filters.get("due_type") == "Hydrostatic Test"
	date_field = "next_hydrotest_date" if hydrotest else "next_service_date"

	conditions = {date_field: ("<=", add_days(today(), days))}
	if not hydrotest:
		conditions["status"] = "At Customer"  # service is due only once the equipment is back at the customer
	if filters.get("customer"):
		conditions["customer"] = filters.customer

	rows = frappe.get_all(
		"Customer Equipment",
		filters=conditions,
		fields=["name", "customer", "equipment_type", "status", date_field],
		order_by=f"{date_field} asc",
	)
	data = []
	for r in rows:
		due = getdate(r.get(date_field))
		left = date_diff(due, today())
		data.append(
			{
				"customer": r.customer,
				"equipment": r.name,
				"equipment_type": r.equipment_type,
				"status": _(r.status),
				"due_date": due,
				"days_left": left,
				"state": _("Overdue") if left < 0 else _("Due"),
			}
		)
	return get_columns(), data


def get_columns():
	return [
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 200},
		{"label": _("Equipment"), "fieldname": "equipment", "fieldtype": "Link", "options": "Customer Equipment", "width": 130},
		{"label": _("Equipment Type"), "fieldname": "equipment_type", "fieldtype": "Link", "options": "Equipment Type", "width": 170},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 110},
		{"label": _("Due Date"), "fieldname": "due_date", "fieldtype": "Date", "width": 110},
		{"label": _("Days Left"), "fieldname": "days_left", "fieldtype": "Int", "width": 90},
		{"label": _("State"), "fieldname": "state", "fieldtype": "Data", "width": 90},
	]
