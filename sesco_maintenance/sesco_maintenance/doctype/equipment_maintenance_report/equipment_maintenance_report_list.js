frappe.listview_settings["Equipment Maintenance Report"] = {
	get_indicator(doc) {
		if (doc.docstatus === 0) return [__("Waiting for Approval"), "orange", "docstatus,=,0"];
		if (doc.docstatus === 1) return [__("Approved"), "green", "docstatus,=,1"];
	},
};
