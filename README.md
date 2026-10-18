# SESCO Maintenance (`sesco_maintenance`)

Custom app لـ ERPNext v15 لصيانة المعدات اللي ملك العملاء، وأولها الطفايات. بيتابع كل معدة: هي فين، بتاعة مين، ومرّت بإيه. وده كله من غير ما معدات العملاء تدخل مخزون الشركة.

Custom app for ERPNext v15 to service customer-owned equipment (fire extinguishers first). Customer equipment never enters company stock.

> **حالة الكود:** ده أساس كامل مكتوب، بس **لسه ما اتسطبش ولا اتجرّب على bench**. الفحص اللي اتعمل كان ثابت بس: الـ Python بيتعمل له compile، والـ JS والـ JSON سليمين، وكل الإشارات بين الملفات (الحقول، والـ methods، والتقارير، والـ hooks) اتراجعت. المطلوب من المبرمج في القسم الأخير.

المرجع الوظيفي والديمو التفاعلي: https://claude.ai/artifact/JaEQEX11WVHaskbwM682X8 (زرار «ملاحظات المبرمج»).

---

## التسطيب

```bash
cd ~/frappe-bench
# انسخ الفولدر لـ apps/sesco_maintenance أو اعمله get-app من الـ git repo بتاعكم
bench --site <site> install-app sesco_maintenance
bench --site <site> migrate
bench build --app sesco_maintenance
```

بعد التسطيب:

1. **Equipment Maintenance Settings**: الشركة، و«مخزن الصيانة»، وحساب مصروف الأكسسوارات (المحاسب يختاره).
2. **Items**: صنف خدمة **غير مخزني** لكل نوع معدة، للعميل (زي «صيانة طفاية بودرة 6 كجم»)، وصنف خدمة للمورد للأنواع الخارجية.
3. **Item Price**: سعر عام في Standard Selling، وسعر خاص لكل عميل في Price List بتاعته، مع `Customer.default_price_list`.
4. **Equipment Type**: الأنواع (المسار، ودورة الصيانة، ودورة اختبار الضغط: CO2 = 5).
5. **Roles**: إدّي المستخدمين الأدوار:
   - `Maintenance Storekeeper` لأمين المخزن.
   - `Maintenance Supervisor` للمشرف.
   - `Maintenance Approver` للمحاسب.
6. **Print Settings**: مقاس الملصق 50×30 مم لما الطابعة توصل، وفعّل الـ Scheduler عشان تنبيه اختبار الضغط يشتغل.

---

## الهيكل

| الملف | الدور |
|---|---|
| `movement.py` | كل تغيير في حالة المعدة. `apply_movement` بيحدّث المعدة ويكتب `Equipment Activity` ومعاه snapshot، و`revert_movements` بيرجّعها عند الإلغاء. `validate_rows` فيه الفحوصات المشتركة، وفيه حجز المعدة لو موجودة في مسودة تانية. |
| `billing.py` | الفوترة من تقارير الصيانة عن طريق Quotation / Sales Order، ومنع الفوترة مرتين (`billed_in`)، وسعر العميل. |
| `api.py` | أزرار «جلب»، والسكان، وتفاصيل الأكسسوار، والخط الزمني للمعدة، والـ Number Cards من نوع Custom. |
| `install.py` | الأدوار والـ Custom Fields على Quotation/Sales Order/Sales Invoice Item و Purchase Invoice و Stock Entry. بيشتغل في `after_install` و`after_migrate`. |
| `utils.py` | `get_qr_svg` لملصقات الـ QR (Jinja). |
| `public/js/sesco_common.js` | دوال الواجهة المشتركة، وزرار «Get Items From › Maintenance Reports». |

### DocTypes

| DocType | النوع | ملاحظات |
|---|---|---|
| Equipment Maintenance Settings | Single | الشركة، والمخزن، والحساب، وأيام تنبيه اختبار الضغط |
| Equipment Type | Master | المسار، والدورات، وأصناف الخدمة |
| Customer Equipment | Master `EQ-.######` | مش Item ولا Serial No. بيتعمل من إذن الاستلام بس، وكل حقوله read-only |
| Equipment Activity | Log | بيتكتب من الكود بس |
| Equipment Receipt | Submittable `EQR-` | سكان وإضافة بالعدد. بيعمل المعدات الجديدة عند الاعتماد |
| Equipment Maintenance Report | Submittable `EMR-` | Material Issue تلقائي من مخزن الصيانة عند الاعتماد |
| External Service Dispatch | Submittable `EXD-` | تسجيل رجوع جزئي (`register_return`)، وفاتورة مورد مسودة |
| Equipment Delivery | Submittable `EQD-` | استلام من الورشة أو مندوب، والإذن الموقّع مرفق |

### الاعتماد

أمين المخزن والمشرف بيحفظوا المسودة بس. `Maintenance Approver` (المحاسب) هو اللي بيعمل Submit و Cancel. المعدة مش بتتحرك غير مع الـ Submit. وأي معدة في مسودة بتبقى محجوزة، فمش بتظهر في «جلب» أي مستند تاني.

### الفوترة

- منفصلة عن التسليم.
- من Quotation أو Sales Order: `Get Items From › Maintenance Reports`، وتقدر تختار أكتر من تقرير. أو من زرار «Bill Customer» في التقرير نفسه.
- بيتعمل سطر لكل مصدر ونوع معدة = صنف الخدمة × العدد. السعر من Price List العميل، ولو مالوش سعر بياخد Standard Selling.
- الـ Submit بيعلّم سطور المصدر (`billed_in`). والـ Cancel، أو عرض السعر لو بقى Lost، بيرجّعها متاحة للفوترة.

### التقارير

- **Equipment Location** (أين المعدة؟)
- **Customer Equipment Register** (معدات عميل)
- **Equipment Due** (صيانات واختبارات ضغط مستحقة)
- **Receipt Profitability** (تكلفة وربح الإذن): تقديري، من غير Projects.

### الطباعة

- Equipment Labels: ملصقات QR بمقاس 50×30 مم.
- Equipment Gate Pass: بيان الخروج.
- Equipment Delivery Note: إذن التسليم.

### الترجمة

الواجهة مكتوبة بالإنجليزي في الكود، والترجمة العربي كلها في `translations/ar.csv`.

---

## المطلوب من المبرمج (TODO)

1. **التسطيب والتجربة على site تجريبي** للدورة كاملة:
   - استلام ← صيانة ← صرف ← رجوع جزئي ← تسليم ← عرض سعر ← أمر بيع ← فاتورة.
   - وجرّب الإلغاء في كل مرحلة.
2. **حاجات محتاجة تأكيد على v15 الفعلي:**
   - `doc.set_missing_values()` و`calculate_taxes_and_totals()` في `billing._append_lines` على Quotation و Sales Order الجديدين.
   - تحويل عرض السعر لأمر بيع بيحتفظ بالـ custom fields (`maintenance_source`, `equipment_codes`) لأن أسماءها واحدة.
   - الـ Stock Entry التلقائي (`uom`, `conversion_factor`, `expense_account`) مع إعدادات الشركة.
   - ملصق الـ QR بـ `pyqrcode` في wkhtmltopdf، وإعداد مقاس الصفحة.
   - شكل الـ Workspace والـ Number Cards من نوع Custom.
3. **Tests:** `FrappeTestCase` للدورة الأساسية، وللإلغاء، ولمنع الفوترة مرتين.
4. **Notification «Hydrostatic Test Due»:** متضبوطة على 60 يوم ثابت، وحقل `hydrotest_reminder_days` في الإعدادات بيأثر على الكروت والشارات بس. لو حبيتوا تربطوهم ببعض، اعملوا `after_save` على الإعدادات يحدّث الـ Notification.
5. **الأداء:** `get_reserving_draft` و `billable_equipment` بيعملوا استعلامات لكل معدة أو عميل. كويس لحجم البداية، وممكن يتجمعوا في استعلام واحد لو الحجم كبر.
