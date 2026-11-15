# -*- coding: utf-8 -*-
import os, sys, types, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for k, v in {"TELEGRAM_BOT_TOKEN": "x", "CHAT_ID": "1", "TOPIC_SELL": "1", "TOPIC_RENT": "2"}.items():
    os.environ.setdefault(k, v)
try:
    import telegram, dotenv  # noqa
except ImportError:
    t = types.ModuleType("telegram"); t.Bot = object; sys.modules["telegram"] = t
    d = types.ModuleType("dotenv"); d.load_dotenv = lambda *a, **k: None; sys.modules["dotenv"] = d
from location_resolver import LocationResolver, fold_key
import main

def nb(i, n): return {"id": str(i), "name": n}
TREE = [{"id": "3", "name": "مشهد", "regions": [
    {"id": "9", "name": "۹", "neighborhoods": [nb(1, "هفت تیر(آب و برق)"), nb(2, "هفت تیر(حافظ)"), nb(3, "هفت تیر(نه دره)"), nb(4, "زیباشهر")]},
    {"id": "11", "name": "۱۱", "neighborhoods": [nb(5, "وکیل آباد"), nb(6, "زیباشهر")]},   # same name under 2 regions
]}]
def M(raw, pid, city="مشهد", region="", t="neighborhood"):
    return {"rawKey": fold_key(raw), "rawText": raw, "cityKey": fold_key(city), "regionKey": fold_key(region), "placeType": t, "placeId": str(pid), "neighborhoodId": str(pid)}

def R(mappings=()):
    r = LocationResolver(); r.load(list(mappings), TREE); return r

class T(unittest.TestCase):
    def test_mapping_city_raw(self):
        r = R([M("شهرک غرب", 5)]).resolve("شهرک غرب", "")
        self.assertFalse(r.needs_review); self.assertEqual((r.region, r.neighborhood, r.source), ("۱۱", "وکیل آباد", "mapping"))
    def test_mapping_full_context_beats_city_only(self):
        r = R([M("جاده قدیم", 5), M("جاده قدیم", 1, region="۹")]).resolve("جاده قدیم", "واقع در منطقه ۹ نزدیک آب و برق")
        self.assertEqual(r.neighborhood, "هفت تیر(آب و برق)")
    def test_mapping_raw_alone(self):
        r = R([M("خیابان x", 5, city="")]).resolve("خیابان X", "")
        self.assertEqual(r.neighborhood, "وکیل آباد")
    def test_folding(self):
        r = R([M("وكيل آباد‌ نو", 5)]).resolve("وکیل‌آباد نو", "")  # ك/ي, ZWNJ
        self.assertEqual(r.source, "mapping")
    def test_duplicate_generic_without_evidence_needs_review(self):
        r = R().resolve("هفت تیر", "آپارتمان تمیز")
        self.assertTrue(r.needs_review); self.assertEqual((r.city, r.region, r.neighborhood), ("مشهد", "", "هفت تیر"))
    def test_duplicate_resolved_by_description(self):
        r = R().resolve("هفت تیر", "نزدیک نه دره")
        self.assertEqual((r.neighborhood, r.source), ("هفت تیر(نه دره)", "tree"))
    def test_duplicate_two_qualifiers_ambiguous(self):
        self.assertTrue(R().resolve("هفت تیر", "بین حافظ و آب و برق").needs_review)
    def test_same_name_two_regions_uses_region_text(self):
        r = R().resolve("زیباشهر", "منطقه ۱۱")
        self.assertEqual((r.region, r.neighborhood), ("۱۱", "زیباشهر"))
        self.assertTrue(R().resolve("زیباشهر", "").needs_review)
    def test_learned_generic_mapping_cannot_guess(self):
        # admin once linked bare «هفت تیر» → حافظ ; without evidence in this ad it must NOT be reused
        self.assertTrue(R([M("هفت تیر", 2)]).resolve("هفت تیر", "").needs_review)
        self.assertEqual(R([M("هفت تیر", 2)]).resolve("هفت تیر", "حافظ").neighborhood, "هفت تیر(حافظ)")
    def test_unknown_needs_review_keeps_raw(self):
        r = R().resolve("محله ناشناخته", "")
        self.assertEqual((r.needs_review, r.region, r.neighborhood), (True, "", "محله ناشناخته"))
    def test_static_fallback_when_tree_empty(self):
        r = LocationResolver(); r.load([], [])
        a = r.resolve("احمدآباد", ""); self.assertEqual((a.region, a.neighborhood, a.source), ("۱", "احمدآباد", "static"))
        b = r.resolve("کوهسنگی", ""); self.assertEqual((b.region, b.neighborhood, b.source), ("۱", "کوه سنگی", "static"))
        c = r.resolve("سجادشهر", ""); self.assertEqual((c.neighborhood, c.region), ("سجاد شهر", "۱"))
        self.assertTrue(r.resolve("هفت تیر", "").needs_review)             # این ریپو منطقه ۱ و ۱۰ است؛ هفت‌تیر مال ۹/۱۱ است
        self.assertTrue(r.resolve("هفت تیر", "آب و برق").needs_review)
        gone = r.resolve("فردوسی", "")
        self.assertTrue(gone.needs_review)
        self.assertNotEqual(gone.region, "۱")
        self.assertNotIn("فردوسی", __import__("config").PANEL_NEIGHBORHOODS)

    def test_region10_divar_labels_map_to_panel(self):
        r = LocationResolver(); r.load([], [])
        cases = {
            "الهیه": ("۱۰", "الهیه"),
            "یوسفیه (شهرک غرب)": ("۱۰", "یوسفیه"),
            "یوسفیه(شهرک غرب)": ("۱۰", "یوسفیه"),
            "استاد یوسفی (شهرک غرب)": ("۱۰", "استادیوسفی (شهرک غرب)"),
            "استادیوسفی": ("۱۰", "استادیوسفی (شهرک غرب)"),
            "شهرک رازی (شهرک غرب)": ("۱۰", "شهرک رازی(شهرک غرب)"),
            "حجاب (شهرک غرب)": ("۱۰", "حجاب"),
            "امامیه (شهرک غرب)": ("۱۰", "امامیه"),
            "حسابی جنوبی (شهرک غرب)": ("۱۰", "حسابی جنوبی"),
            "شهرک لشکر (شهرک غرب)": ("۱۰", "شهرک لشکر"),
            "لشکر": ("۱۰", "شهرک لشکر"),
            "لشگر": ("۱۰", "شهرک لشکر"),
            "فرهنگیان (شهرک غرب)": ("۱۰", "فرهنگیان"),
            "شاهد (شهرک غرب)": ("۱۰", "شاهد"),
            "جاهدشهر": ("۱۰", "جاهد شهر"),
            "ولی عصر": ("۱۰", "ولیعصر"),
            "ولی‌عصر": ("۱۰", "ولیعصر"),
            "ادیب نیشابوری (شهرک غرب)": ("۱۰", "ادیب (شهرک غرب)"),
            "ادیب (شهرک غرب)": ("۱۰", "ادیب (شهرک غرب)"),
            "امیریه": ("۱۰", "امیریه"),
            "مشکینی (شهرک غرب)": ("۱۰", "مشکینی"),
            "میعاد": ("۱۰", "میعاد"),
            "نرگس": ("۱۰", "نرگس"),
        }
        for raw, exp in cases.items():
            got = r.resolve(raw, "")
            self.assertFalse(got.needs_review, raw)
            self.assertEqual((got.region, got.neighborhood), exp, raw)
        # منطقه ۱ دست‌نخورده بماند
        self.assertEqual(r.resolve("احمدآباد", "").region, "۱")
        self.assertEqual(r.resolve("سناباد", "").neighborhood, "سناباد")

    def test_region10_live_tree_uses_panel_node(self):
        tree = [{"id": "3", "name": "مشهد", "regions": [
            {"id": "1", "name": "۱", "neighborhoods": [nb(10, "احمدآباد")]},
            {"id": "10", "name": "۱۰", "neighborhoods": [
                nb(70, "یوسفیه"), nb(71, "استادیوسفی (شهرک غرب)"), nb(72, "ادیب (شهرک غرب)"),
            ]},
        ]}]
        r = LocationResolver(); r.load([], tree)
        a = r.resolve("یوسفیه (شهرک غرب)", "")
        self.assertEqual((a.region, a.neighborhood, a.source), ("۱۰", "یوسفیه", "tree"))
        b = r.resolve("استاد یوسفی (شهرک غرب)", "")
        self.assertEqual((b.neighborhood, b.region, b.source), ("استادیوسفی (شهرک غرب)", "۱۰", "tree"))
        c = r.resolve("ادیب نیشابوری (شهرک غرب)", "")
        self.assertEqual((c.neighborhood, c.region), ("ادیب (شهرک غرب)", "۱۰"))
        self.assertEqual(r.resolve("احمدآباد", "").region, "۱")

    def test_list_filter_region10_and_not_ferdowsi(self):
        def row(token, district, title="آپارتمان"):
            return {"widget_type": "POST_ROW", "data": {
                "title": title,
                "action": {"payload": {"token": token, "web_info": {"district_persian": district, "title": title}}},
            }}
        data = {"list_widgets": [
            row("a", "یوسفیه (شهرک غرب)"),
            row("b", "استاد یوسفی (شهرک غرب)"),
            row("c", "ادیب نیشابوری (شهرک غرب)"),
            row("d", "شهرک رازی (شهرک غرب)"),
            row("e", "حجاب (شهرک غرب)"),
            row("f", "شهرک لشکر (شهرک غرب)"),
            row("g", "فردوسی"),
            row("h", "سجادیه"),
            row("i", "احمدآباد"),
        ]}
        out = {c["district"] for c in main.extract_candidates(data, "apartment-sell", "فروش")}
        self.assertEqual(out, {
            "یوسفیه (شهرک غرب)", "استاد یوسفی (شهرک غرب)", "ادیب نیشابوری (شهرک غرب)",
            "شهرک رازی (شهرک غرب)", "حجاب (شهرک غرب)", "شهرک لشکر (شهرک غرب)", "احمدآباد",
        })

    def test_balance_does_not_starve_region10(self):
        main.MAPPER.load([], [])
        cands = []
        for i in range(6):
            cands.append({"token": f"r1{i}", "district": "احمدآباد", "title": "ت", "category": "apartment-sell", "catLabel": "ف"})
        for i in range(2):
            cands.append({"token": f"r10{i}", "district": "الهیه", "title": "ت", "category": "apartment-sell", "catLabel": "ف"})
        cands.append({"token": "fx", "district": "فردوسی", "title": "ت", "category": "apartment-sell", "catLabel": "ف"})
        picked = main.pick_balanced(cands, 4)
        regions = [main.canon_region(main.MAPPER.resolve(c["district"], "").region) for c in picked]
        self.assertEqual(regions.count("۱۰"), 2)
        self.assertEqual(regions.count("۱"), 2)
        self.assertNotIn("فردوسی", {c["district"] for c in picked})

    def test_units_floor_and_amenity_ticks(self):
        main.MAPPER.load([], [])
        details = {"webengage": {"business_type": "personal"}, "sections": [{"widgets": [
            {"data": {"@type": "x.DescriptionRowData", "text": "واحد تمیز. بدون انباری. ۳ واحد در هر طبقه"}},
            {"widget_type": "GROUP_FEATURE_ROW", "data": {
                "@type": "widgets.GroupFeatureRowData",
                "items": [
                    {"title": "آسانسور", "available": True},
                    {"title": "پارکینگ", "available": False},
                    {"title": "بالکن", "available": True},
                    {"title": "انباری", "available": False},
                ],
            }},
            {"data": {"@type": "x.UnexpandableRowData", "title": "تعداد واحد در طبقه", "value": "۲"}},
            {"data": {"@type": "x.UnexpandableRowData", "title": "طبقه", "value": "۳ از ۵"}},
            {"data": {"@type": "x.UnexpandableRowData", "title": "قیمت کل", "value": "۲٬۰۰۰٬۰۰۰٬۰۰۰"}},
        ]}]}
        cand = {"token": "tok", "district": "حجاب (شهرک غرب)", "title": "فروش فول", "category": "apartment-sell", "catLabel": "فروش"}
        payload = main.is_owner_and_format(details, cand)["panel_payload"]
        self.assertEqual(payload["status"], "pending")
        self.assertEqual(payload["category"], "new")
        self.assertEqual((payload["region"], payload["neighborhood"]), ("۱۰", "حجاب"))
        # ردیف ساخت‌یافته بر توضیح «۳ واحد» اولویت دارد؛ طبقه با «واحد در طبقه» قاطی نمی‌شود
        self.assertEqual(payload["unitsPerFloor"], 2)
        self.assertEqual(payload["floor"], 3)
        self.assertEqual(payload["amenities"], {"elevator": True, "terrace": True})
        self.assertNotIn("parking", payload["amenities"])
        self.assertNotIn("storage", payload["amenities"])

        # فقط متن: نفی‌ها تیک نمی‌خورند، تک‌واحدی = ۱
        details2 = {"webengage": {"business_type": "personal"}, "sections": [{"widgets": [
            {"data": {"@type": "x.DescriptionRowData", "text": "آسانسور ندارد. پارکینگ دارد. انباری دارد. تک واحدی"}},
            {"data": {"@type": "x.UnexpandableRowData", "title": "قیمت کل", "value": "۱"}},
        ]}]}
        cand2 = dict(cand, title="فروش تراس", district="الهیه")
        payload2 = main.is_owner_and_format(details2, cand2)["panel_payload"]
        self.assertEqual(payload2["unitsPerFloor"], 1)
        self.assertEqual(payload2["region"], "۱۰")
        self.assertEqual(payload2["amenities"], {"parking": True, "terrace": True, "storage": True})
        self.assertNotIn("elevator", payload2["amenities"])
        self.assertEqual(payload2["status"], "pending")
    def test_dormant_mapping_ignored(self):
        self.assertTrue(R([M("جای حذف شده", 999)]).resolve("جای حذف شده", "").needs_review)
    def test_payload_end_to_end(self):
        main.MAPPER.load([], TREE)
        def post(district, desc):
            details = {"webengage": {"business_type": "personal"}, "sections": [{"widgets": [
                {"data": {"@type": "x.DescriptionRowData", "text": desc}},
                {"data": {"@type": "x.UnexpandableRowData", "title": "قیمت کل", "value": "۲٬۰۰۰٬۰۰۰٬۰۰۰"}}]}]}
            cand = {"token": "tok", "district": district, "title": "فروش", "category": "apartment-sell", "catLabel": "فروش"}
            return main.is_owner_and_format(details, cand)["panel_payload"]
        ok = post("وکیل آباد", "خوب"); self.assertEqual((ok["region"], ok["neighborhood"]), ("۱۱", "وکیل آباد")); self.assertNotIn("needs_review", ok)
        bad = post("هفت تیر", "خوب"); self.assertEqual((bad["city"], bad["region"], bad["neighborhood"], bad["needs_review"]), ("مشهد", "", "هفت تیر", True))
        self.assertEqual(post("هفت تیر", "کنار حافظ")["neighborhood"], "هفت تیر(حافظ)")

if __name__ == "__main__":
    unittest.main(verbosity=2)
