frappe.ui.form.on("External Service Dispatch", {
	setup(frm) {
		frm.ignore_doctypes_on_cancel_all = ["Equipment Activity"];
	},

	refresh(frm) {
		const items = frm.doc.items || [];
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Get External Equipment"), () => sesco_maintenance.get_equipment(frm, "dispatch"));
		}
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__("Print Gate Pass"), () => sesco_maintenance.print(frm, "Equipment Gate Pass"));
			if (items.some((r) => r.return_status === "At Supplier")) {
				frm.add_custom_button(__("Register Return"), () => register_return(frm)).addClass("btn-primary");
			}
			if (items.some((r) => r.return_status === "Returned OK" && !r.purchase_invoice) && frappe.model.can_create("Purchase Invoice")) {
				frm.add_custom_button(__("Purchase Invoice"), () => make_purchase_invoice(frm), __("Create"));
			}
			const billable = items.some((r) => r.return_status === "Returned OK" && !r.billed_in);
			sesco_maintenance.add_billing_buttons(frm, billable);
		}
	},
});

function register_return(frm) {
	const data = (frm.doc.items || [])
		.filter((r) => r.return_status === "At Supplier")
		.map((r) => ({ row: r.name, equipment: r.equipment, equipment_type: r.equipment_type, return_status: "", hydrotest_done: 0 }));

	const dialog = new frappe.ui.Dialog({
		title: __("Register Return from Supplier"),
		size: "large",
		fields: [
			{ fieldname: "return_date", fieldtype: "Date", label: __("Return Date"), reqd: 1, default: frappe.datetime.get_today() },
			{
				fieldname: "items",
				fieldtype: "Table",
				label: __("Equipment"),
				cannot_add_rows: true,
				cannot_delete_rows: true,
				in_place_edit: true,
				data,
				fields: [
					{ fieldname: "row", fieldtype: "Data", hidden: 1 },
					{ fieldname: "equipment", fieldtype: "Data", label: __("Equipment"), read_only: 1, in_list_view: 1, columns: 3 },
					{ fieldname: "equipment_type", fieldtype: "Data", label: __("Equipment Type"), read_only: 1, in_list_view: 1, columns: 3 },
					{
						fieldname: "return_status",
						fieldtype: "Select",
						label: __("Return Status"),
						options: ["", "Returned OK", "Returned Damaged"],
						in_list_view: 1,
						columns: 2,
					},
					{ fieldname: "hydrotest_done", fieldtype: "Check", label: __("Hydrostatic Test Done"), in_list_view: 1, columns: 2 },
				],
			},
			{
				fieldtype: "HTML",
				options: `<p class="text-muted small">${__("Leave the status empty for equipment still at the supplier. You can register the rest later.")}</p>`,
			},
		],
		primary_action_label: __("Register Return"),
		primary_action(values) {
			const rows = (values.items || []).filter((r) => r.return_status);
			if (!rows.length) {
				frappe.msgprint(__("Choose Returned OK or Returned Damaged for at least one row."));
				return;
			}
			frm.call("register_return", { rows, return_date: values.return_date }).then(() => {
				dialog.hide();
				frm.reload_doc();
			});
		},
	});
	dialog.show();
}

function make_purchase_invoice(frm) {
	frappe
		.call({
			method: "sesco_maintenance.sesco_maintenance.doctype.external_service_dispatch.external_service_dispatch.make_purchase_invoice",
			args: { source_name: frm.doc.name },
			freeze: true,
		})
		.then((r) => {
			if (!r.message) return;
			const doc = frappe.model.sync(r.message)[0];
			frappe.set_route("Form", doc.doctype, doc.name);
		});
}
