frappe.listview_settings["Customer Equipment"] = {
	add_fields: ["status"],
	get_indicator(doc) {
		const colors = { "At Customer": "gray", "In Workshop": "orange", "At Supplier": "blue", Ready: "green", Damaged: "red" };
		return [__(doc.status), colors[doc.status] || "gray", "status,=," + doc.status];
	},
};
