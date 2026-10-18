frappe.ui.form.on("Customer Equipment", {
	refresh(frm) {
		if (frm.is_new()) return;
		show_hydrotest_headline(frm);
		render_activity(frm);
	},
});

function show_hydrotest_headline(frm) {
	if (!frm.doc.next_hydrotest_date) return;
	const days = frappe.datetime.get_day_diff(frm.doc.next_hydrotest_date, frappe.datetime.get_today());
	if (days < 0) {
		frm.dashboard.set_headline(__("Hydrostatic test is overdue by {0} days.", [-days]), "red");
	} else if (days <= 60) {
		frm.dashboard.set_headline(__("Hydrostatic test is due in {0} days.", [days]), "orange");
	}
}

function render_activity(frm) {
	frappe.call("sesco_maintenance.api.get_equipment_activity", { equipment: frm.doc.name }).then((r) => {
		const rows = r.message || [];
		const esc = frappe.utils.escape_html;
		const html = rows.length
			? `<table class="table table-bordered table-condensed">
				<thead><tr>
					<th>${__("Date")}</th><th>${__("Activity")}</th><th>${__("From")}</th>
					<th>${__("To")}</th><th>${__("Document")}</th><th>${__("Notes")}</th>
				</tr></thead>
				<tbody>${rows
					.map(
						(a) => `<tr>
					<td>${frappe.datetime.str_to_user(a.activity_date)}</td>
					<td>${__(a.activity_type)}</td>
					<td>${esc(a.from_location || "")}</td>
					<td>${esc(a.to_location || "")}</td>
					<td><a href="/app/${frappe.router.slug(a.reference_doctype)}/${encodeURIComponent(a.reference_name)}">${esc(a.reference_name)}</a></td>
					<td>${esc(a.notes || "")}</td>
				</tr>`
					)
					.join("")}</tbody></table>`
			: `<p class="text-muted">${__("No activity yet.")}</p>`;
		frm.get_field("activity_html").$wrapper.html(html);
	});
}
