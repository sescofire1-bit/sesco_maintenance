frappe.listview_settings["External Service Dispatch"] = {
	add_fields: ["status"],
	get_indicator(doc) {
		if (doc.docstatus === 0) return [__("Waiting for Approval"), "orange", "docstatus,=,0"];
		const colors = { "At Supplier": "blue", "Partially Returned": "orange", Returned: "green", Cancelled: "red" };
		return [__(doc.status), colors[doc.status] || "gray", "status,=," + doc.status];
	},
};
