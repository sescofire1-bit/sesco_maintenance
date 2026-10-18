<p>{{ _("Hydrostatic test for equipment {0} ({1}) of customer {2} is due on {3}.").format(doc.name, doc.equipment_type, doc.customer_name or doc.customer, frappe.utils.formatdate(doc.next_hydrotest_date)) }}</p>
<p>{{ _("Status") }}: {{ _(doc.status) }}</p>
