frappe.query_reports["Equipment Location"] = {
	filters: [
		{ fieldname: "equipment", label: __("Equipment Code"), fieldtype: "Data" },
		{ fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "Customer" },
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: ["", "At Customer", "In Workshop", "At Supplier", "Ready", "Damaged"],
		},
		{ fieldname: "equipment_type", label: __("Equipment Type"), fieldtype: "Link", options: "Equipment Type" },
	],
};
