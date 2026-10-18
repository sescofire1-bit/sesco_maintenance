frappe.query_reports["Customer Equipment Register"] = {
	filters: [{ fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "Customer", reqd: 1 }],
};
