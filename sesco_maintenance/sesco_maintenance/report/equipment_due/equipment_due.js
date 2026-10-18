frappe.query_reports["Equipment Due"] = {
	filters: [
		{
			fieldname: "due_type",
			label: __("Due Type"),
			fieldtype: "Select",
			options: ["Service", "Hydrostatic Test"],
			default: "Service",
			reqd: 1,
		},
		{ fieldname: "days", label: __("Due Within (Days)"), fieldtype: "Int", default: 60, reqd: 1 },
		{ fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "Customer" },
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "state" && data) {
			value = `<span class="indicator-pill ${data.days_left < 0 ? "red" : "orange"}">${value}</span>`;
		}
		return value;
	},
};
