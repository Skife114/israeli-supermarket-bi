"""
שלב 3: טרנספורמציה - הופך את קבצי ה-CSV הגולמיים (תוצר החבילה) לסכימה
שהדשבורד שלנו כבר יודע לקרוא (chains.json, stores.json, products.json, prices.json).

החלטות שהתקבלו:
- מותגי המשנה של שופרסל (שלי, יש, גוד מרקט, דיל, אקספרס, יוניברס) מאוחדים ל"שופרסל" אחת
- סניפים לא-פיזיים (ליקוט, פיק-אפ, אונליין) מסוננים החוצה
- לוקחים רק את הקובץ העדכני ביותר לכל רשת (לא כפילויות מכמה תאריכים)

הערה חשובה: השלב הזה עדיין לא כולל גיאוקודינג (המרת כתובת לקואורדינטות) -
זה שלב נפרד שיתווסף בהמשך, כי קבצי המקור לא כוללים lat/lng בכלל.
"""

import pandas as pd
import json
import re

import os
INPUT_DIR = "parsed_csv" if os.path.isdir("parsed_csv") else "real_data_test"

CHAIN_ID_TO_NAME = {
    "7290027600007": {"id": "shufersal", "name_he": "שופרסל", "color": "#E4002B"},
    "7290058140886": {"id": "rami_levy", "name_he": "רמי לוי", "color": "#F5A623"},
    "7290803800003": {"id": "yohananof", "name_he": "יוחננוף", "color": "#557153"},
    "7290873255550": {"id": "tiv_taam", "name_he": "טיב טעם", "color": "#6A1B9A"},
}

# דפוסים שמזהים סניף לא-פיזי (ליקוט, פיק-אפ, אונליין) - לפי מה שראינו בדאטה האמיתי
NON_PHYSICAL_PATTERNS = re.compile(r"ליקוט|פיק ?אפ|אינטרנט|ONLINE", re.IGNORECASE)

# סיווג קטגוריות מוצר לפי מילות מפתח בשם - הרשתות לא מפרסמות שדה "קטגוריה" בקובץ,
# אז בונים סיווג בעצמנו. זה לא מושלם (הרבה מוצרים לא-מזון כמו כלי בית, קוסמטיקה
# וכו' יישארו "אחר" בכוונה - לא הוספנו קטגוריות בית/חשמל), אבל מכסה חלק משמעותי
# מהמוצרים ומספיק כדי שסינון קטגוריה בדשבורד יהיה שימושי.
CATEGORY_PATTERNS = [
    ("פארם, תינוקות וטואלטיקה", r"טיטול|מגבונים לחים|משחת שיניים|דאודורנט|פד(ים)? היגייני|תרכובת תינוקות|מוצץ|בקבוק תינוק"),
    ("ניקיון וטיפוח", r"נייר טואלט|נייר סופג|סבון|אבקת כביסה|מרכך כביסה|שמפו|אקונומיקה|מגבון(?!ים לחים)|נוזל כלים|קרם גוף"),
    ("חלב ומוצריו", r"חלב|גבינה|קוטג|יוגורט|שמנת|חמאה|לבנה \d|גבינת"),
    ("ביצים", r"^ביצים|ביצי[םה] "),
    ("לחם ומאפים", r"לחם|לחמני|פיתה|באגט|חלה|בייגל|מאפה"),
    ("קפה ותה", r"קפה|נמס |תה |קפוצ|אספרסו|נס קפה"),
    ("משקאות", r"קולה|ספרייט|פאנטה|מיץ|מים מינרלים|משקה|סודה|נביעות|מי עדן|איזוטוני"),
    ("חטיפים וממתקים", r"שוקולד|וופל|ביסלי|במבה|חטיף|עוגי[ותה]|קרמבו|סוכריה|מסטיק|צ'יפס|תפוצ'יפס|דוריטוס"),
    ("בשר ועוף", r"עוף|בשר|קבב|שניצל|נקניק|טחון|הודו טחון|כבש|המבורגר|קורנביף"),
    ("דגים", r"סלמון|טונה|אמנון|פילה דג|דג פנג|סרדינים"),
    ("שימורים וקטניות", r"שימורים|תירס מתוק|חומוס|עדשים|שעועית|זיתים|חמוצים|רסק עגבניות|מלפפון חמוץ"),
    ("פסטה, אורז ודגנים", r"פסטה|אורז|קוסקוס|פתיתים|בורגול|קינואה|קורנפלקס|גרנולה|ספגטי|נודלס|איטריות"),
    ("פירות וירקות", r"עגבני|מלפפון|בננ[ותה]|בצל|תפוחי אדמה|פלפל (אדום|ירוק|צהוב)|גזר|תפוז|לימון|אבוקדו|אבטיח"),
    ("מזון יבש ותבלינים", r"סוכר|מלח בישול|קמח|שמן (זית|קנולה|חמניות)|תבלין|כמון|פפריקה|אבקת אפיה|וניל"),
]
_COMPILED_CATEGORIES = [(name, re.compile(pat)) for name, pat in CATEGORY_PATTERNS]

def categorize_product(name):
    if not isinstance(name, str) or not name:
        return "אחר"
    for cat_name, pattern in _COMPILED_CATEGORIES:
        if pattern.search(name):
            return cat_name
    return "אחר"

def is_bad_address(addr, city):
    """כתובת לא שמישה: ריקה, unknown, או placeholder כמו '' או {}"""
    if pd.isna(addr) or str(addr).strip() in ("", "unknown", "''", "{}", "0"):
        return True
    return False


def clean_str(val):
    """ממיר תא ריק/NaN של pandas למחרוזת ריקה - כדי שלא ידלוף כ-NaN
    לא-תקין (לא JSON תקני, ישבור JSON.parse בצד הדשבורד) לקבצי הפלט."""
    if pd.isna(val):
        return ""
    return str(val)


def load_and_ffill(path, ffill_cols):
    df = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])
    df[ffill_cols] = df[ffill_cols].ffill()
    return df


# ============================================================
# חלק א: עיבוד קובצי הסניפים
# ============================================================
def process_store_file(path):
    df = load_and_ffill(path, ["found_folder", "file_name", "chainid", "chainname",
                                "lastupdatedate", "lastupdatetime", "subchainid", "subchainname"])

    if df.empty:
        # קובץ קיים אבל ריק (0 שורות) - לא נופלים על idxmax של סדרה ריקה.
        # מדלגים על הרשת הזו לריצה הזו במקום להפיל את כל הסקריפט בגללה.
        return None, [], None

    # לוקחים רק את הקובץ העדכני ביותר (הכי הרבה lastupdatedate+lastupdatetime)
    df["_ts"] = df["lastupdatedate"].fillna("") + df["lastupdatetime"].fillna("")
    latest_file = df.loc[df["_ts"].idxmax(), "file_name"]
    df = df[df["file_name"] == latest_file].copy()

    chain_info = CHAIN_ID_TO_NAME.get(df["chainid"].iloc[0])
    if chain_info is None:
        raise ValueError(f"רשת לא מוכרת: {df['chainid'].iloc[0]}")

    stores = []
    skipped_non_physical = 0
    skipped_bad_address = 0
    for _, row in df.iterrows():
        name = row.get("storename", "")
        if pd.notna(name) and NON_PHYSICAL_PATTERNS.search(str(name)):
            skipped_non_physical += 1
            continue
        if is_bad_address(row.get("address"), row.get("city")):
            skipped_bad_address += 1
            continue
        stores.append({
            "store_id": f'{chain_info["id"]}_{row["storeid"]}',
            "chain_id": chain_info["id"],
            "chain_name_he": chain_info["name_he"],
            "store_name": clean_str(name),
            "address": row.get("address", ""),
            "city_code": clean_str(row.get("city")),
            "zipcode": clean_str(row.get("zipcode")),
            # lat/lng ייתווספו בשלב הגיאוקודינג הנפרד
        })

    return chain_info, stores, {
        "total_rows": len(df), "kept": len(stores),
        "skipped_non_physical": skipped_non_physical, "skipped_bad_address": skipped_bad_address,
        "latest_file_used": latest_file,
    }


print("=" * 60)
print("עיבוד קובצי סניפים")
print("=" * 60)

all_chains = {}
all_stores = []
for fname in ["store_file_shufersal.csv", "store_file_rami_levy.csv",
              "store_file_yohananof.csv", "store_file_tiv_taam.csv"]:
    try:
        chain_info, stores, stats = process_store_file(f"{INPUT_DIR}/{fname}")
    except FileNotFoundError:
        print(f"\n{fname}: ⚠️  קובץ הסניפים לא נמצא - מדלגים על הרשת הזו לריצה הזו")
        continue
    if chain_info is None:
        print(f"\n{fname}: ⚠️  קובץ הסניפים ריק (0 שורות) - מדלגים על הרשת הזו לריצה הזו")
        continue
    all_chains[chain_info["id"]] = chain_info
    all_stores.extend(stores)
    print(f"\n{chain_info['name_he']} ({fname}):")
    print(f"  קובץ שנבחר (העדכני ביותר): {stats['latest_file_used']}")
    print(f"  סה\"כ שורות: {stats['total_rows']}")
    print(f"  סוננו כלא-פיזיים: {stats['skipped_non_physical']}")
    print(f"  סוננו בגלל כתובת חסרה: {stats['skipped_bad_address']}")
    print(f"  נשארו (סניפים תקינים): {stats['kept']}")

print(f"\nסה\"כ סניפים תקינים בכל הרשתות: {len(all_stores)}")

with open("chains_transformed.json", "w", encoding="utf-8") as f:
    json.dump(list(all_chains.values()), f, ensure_ascii=False, indent=2)

import requests

# קובץ יישובים - data.gov.il. ה-resource_id הראשון שהשתמשנו בו (b7cf8f14...)
# הפסיק לעבוד (404) אחרי כמה שבועות - פורטלי ממשלה מחליפים את המזהים האלה
# מדי פעם. לכן במקום מזהה קבוע אחד, מנסים רשימת מועמדים ברצף עד שאחד עובד.
# הבדיקה שנעשתה (2026-09-18): 8f714b6f ו-d4901968 ו-b7cf8f14 עבדו, 5938933b
# החזיר 404 - סדר הרשימה עודכן כך שהמועמד שאומת כעובד ונמצא הכי עשיר בשדות
# (city_code/city_name_he) מנוסה ראשון.
CBS_RESOURCE_ID_CANDIDATES = [
    "8f714b6f-c35c-4b40-a0e7-547b675eee0e",  # אושר עובד בפועל - שדות: city_code, city_name_he
    "d4901968-dad3-4845-a9b0-a57d027f11ab",
    "b7cf8f14-64a2-4b33-8d4b-edb286fdbd37",  # הישן - נשאר כניסיון נוסף ליתר ביטחון
]

# קובץ סטטי בתוך הריפו עם מיפוי קוד יישוב -> שם יישוב, כגיבוי אחרון למקרה
# שה-API החי נכשל לגמרי (data.gov.il הוכיח את עצמו כלא אמין - IDs מתחלפים,
# ולפעמים מחזיר 404 לכל המועמדים באותו יום ריצה). קודי יישובים בישראל כמעט
# ולא משתנים, אז קובץ סטטי הוא גיבוי סביר. הקובץ מתעדכן אוטומטית בכל פעם
# שה-API החי כן מצליח.
CITY_CODE_FALLBACK_PATH = os.path.join("data", "city_code_fallback.json")


def load_city_code_lookup():
    """
    מוריד את טבלת קודי היישובים הרשמית (משרד הפנים/למ"ס) דרך data.gov.il,
    וממפה קוד יישוב -> שם יישוב. מנסה כמה resource_id מועמדים ברצף (כי הם
    מתחלפים מדי פעם) - הראשון שמצליח נבחר. אם ה-API החי מצליח, מרעננים גם
    את קובץ הגיבוי הסטטי (data/city_code_fallback.json) עם הנתונים העדכניים.
    אם כל המועמדים נכשלים, נופלים חזרה לקובץ הסטטי (לא מיפוי ריק).
    """
    for resource_id in CBS_RESOURCE_ID_CANDIDATES:
        try:
            resp = requests.get(
                "https://data.gov.il/api/3/action/datastore_search",
                params={"resource_id": resource_id, "limit": 3000},
                timeout=30,
            )
            resp.raise_for_status()
            records = resp.json()["result"]["records"]
            print(f"  הורדו {len(records)} רשומות יישובים מ-data.gov.il (resource_id: {resource_id})")
            if records:
                print(f"  לדוגמה, שדות הרשומה הראשונה: {list(records[0].keys())}")
            lookup = {}
            for r in records:
                code = str(r.get("סמל_ישוב") or r.get("SEMEL_YISHUV") or r.get("סמל יישוב") or r.get("city_code") or "").strip()
                name = str(r.get("שם_ישוב") or r.get("SHEM_YISHUV") or r.get("שם יישוב") or r.get("city_name_he") or "").strip()
                if code:
                    lookup[code] = name
            if lookup:
                try:
                    os.makedirs(os.path.dirname(CITY_CODE_FALLBACK_PATH), exist_ok=True)
                    with open(CITY_CODE_FALLBACK_PATH, "w", encoding="utf-8") as f:
                        json.dump(lookup, f, ensure_ascii=False, indent=2)
                    print(f"  רוענן קובץ הגיבוי הסטטי: {CITY_CODE_FALLBACK_PATH} ({len(lookup)} רשומות)")
                except Exception as e:
                    print(f"  ⚠️  לא הצלחנו לרענן את קובץ הגיבוי הסטטי ({e}) - ממשיכים בכל זאת")
                return lookup
            print(f"  ⚠️  resource_id {resource_id} החזיר תשובה ריקה - מנסה את הבא")
        except Exception as e:
            print(f"  ⚠️  resource_id {resource_id} נכשל ({e}) - מנסה את הבא")

    print("  ⚠️  כל ה-resource_id המועמדים נכשלו - נופלים לקובץ הגיבוי הסטטי")
    try:
        with open(CITY_CODE_FALLBACK_PATH, "r", encoding="utf-8") as f:
            fallback_lookup = json.load(f)
        print(f"  נטען קובץ גיבוי סטטי: {CITY_CODE_FALLBACK_PATH} ({len(fallback_lookup)} רשומות)")
        return fallback_lookup
    except Exception as e:
        print(f"  ⚠️  גם טעינת קובץ הגיבוי הסטטי נכשלה ({e}) - ממשיכים עם קוד גולמי בלבד")
        return {}


print("\n" + "=" * 60)
print("הורדת מיפוי קודי יישובים -> שמות ערים")
print("=" * 60)
city_lookup = load_city_code_lookup()
for s in all_stores:
    s["city_name"] = city_lookup.get(s["city_code"], "")
missing = sum(1 for s in all_stores if not s["city_name"])
print(f"סניפים עם שם עיר שנמצא: {len(all_stores) - missing} מתוך {len(all_stores)}")

print("\nדוגמה לשלוש רשומות סניף ראשונות (כולל שם עיר):")
for s in all_stores[:3]:
    print(" ", s)

with open("stores_transformed.json", "w", encoding="utf-8") as f:
    json.dump(all_stores, f, ensure_ascii=False, indent=2)
# ============================================================
print("\n" + "=" * 60)
print("עיבוד קובצי מחירים - כל 4 הרשתות")
print("=" * 60)

PRICE_FILES = {
    "shufersal": "price_full_file_shufersal.csv",
    "rami_levy": "price_full_file_rami_levy.csv",
    "yohananof": "price_full_file_yohananof.csv",
    "tiv_taam": "price_full_file_tiv_taam.csv",
}

all_products = []
all_prices = []

for friendly_id, fname in PRICE_FILES.items():
    fpath = f"{INPUT_DIR}/{fname}"
    try:
        price_df = load_and_ffill(fpath, ["found_folder", "file_name", "chainid", "subchainid", "storeid", "bikoretno"])
    except FileNotFoundError:
        print(f"\n{friendly_id}: ⚠️  קובץ {fname} לא נמצא - מדלגים (ייתכן ולא היה בדגימה)")
        continue

    print(f"\n{friendly_id} ({fname}):")
    print(f"  סה\"כ שורות מחיר: {len(price_df)}")
    print(f"  מוצרים ייחודיים: {price_df['itemcode'].nunique()}")

    products = (
        price_df.groupby("itemcode").first()[["itemname", "manufacturename"]]
        .reset_index().rename(columns={"itemcode": "barcode", "itemname": "name", "manufacturename": "manufacturer"})
    )
    all_products.append(products)

    prices = price_df[["chainid", "storeid", "itemcode", "itemprice"]].copy()
    prices.columns = ["chain_id_raw", "store_num", "barcode", "price"]
    prices["chain_id"] = friendly_id
    prices["store_id"] = prices["chain_id"] + "_" + prices["store_num"]
    all_prices.append(prices[["chain_id", "store_id", "barcode", "price"]])

if all_products:
    products_combined = pd.concat(all_products, ignore_index=True).drop_duplicates(subset="barcode", keep="first")
    prices_combined = pd.concat(all_prices, ignore_index=True)

    products_combined["category"] = products_combined["name"].apply(categorize_product)
    n_categorized = (products_combined["category"] != "אחר").sum()
    if len(products_combined) > 0:
        print(f"\nסיווג קטגוריות: {n_categorized} מתוך {len(products_combined)} מוצרים סווגו "
              f"({n_categorized/len(products_combined)*100:.0f}%) - השאר תחת 'אחר'")
    else:
        print("\n⚠️  אין מוצרים לסיווג (קבצי המחירים שנמצאו היו ריקים)")

    print(f"\nסה\"כ מוצרים ייחודיים בכל הרשתות: {len(products_combined)}")
    print(f"סה\"כ רשומות מחיר בכל הרשתות: {len(prices_combined)}")
    print("\nדוגמה לקטלוג מוצרים משולב:")
    print(products_combined.head(5).to_string(index=False))
    print("\nדוגמה לטבלת מחירים משולבת:")
    print(prices_combined.head(5).to_string(index=False))

    products_combined.to_json("products_transformed.json", orient="records", force_ascii=False, indent=2)
    prices_combined.to_json("prices_transformed.json", orient="records", force_ascii=False, indent=2)

    # --- קובץ סיכום מצומצם: ממוצע מחיר לכל רשת+ברקוד (במקום כל רשומת מחיר גולמית) ---
    # הדשבורד לא צריך את כל 280K+ הרשומות הגולמיות כדי להציג טבלת השוואה -
    # מספיק לו ממוצע לכל רשת+מוצר. זה מקטין את הקובץ שהדפדפן צריך לטעון ביותר מפי 5.
    prices_numeric = prices_combined.copy()
    prices_numeric["price"] = pd.to_numeric(prices_numeric["price"], errors="coerce")
    n_before = len(prices_numeric)
    prices_numeric = prices_numeric.dropna(subset=["price"])
    n_dropped = n_before - len(prices_numeric)
    if n_dropped:
        print(f"  (הוסרו {n_dropped} רשומות עם מחיר חסר/לא-תקין מתוך {n_before} - "
              f"{n_dropped/n_before*100:.0f}%, תואם למה שראינו בקבצי המקור)")

    current_avg = (
        prices_numeric.groupby(["chain_id", "barcode"])["price"]
        .agg(avg_price="mean", n_stores="count")
        .reset_index()
    )
    current_avg["avg_price"] = current_avg["avg_price"].round(2)

    if len(current_avg) > 0:
        print(f"\nקובץ סיכום מצומצם (current_avg): {len(current_avg)} רשומות "
              f"(במקום {len(prices_combined)} הגולמיות - צמצום של פי {len(prices_combined)/len(current_avg):.1f})")
    else:
        print(f"\nקובץ סיכום מצומצם (current_avg): 0 רשומות (אין מחירים תקינים לסיכום)")

    current_avg.to_json("current_avg_transformed.json", orient="records", force_ascii=False)
else:
    print("\n⚠️  לא נמצא אף קובץ מחירים לעיבוד")


# ============================================================
# חלק ג: גיאוקודינג - המרת כתובת לקואורדינטות (lat/lng)
# ============================================================
import time

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# חובה לפי מדיניות השימוש של Nominatim: User-Agent שמזהה את האפליקציה
HEADERS = {"User-Agent": "israeli-supermarket-bi-portfolio-project/1.0"}


def geocode_store(address, city_name):
    """
    ממיר כתובת + שם עיר לקואורדינטות (lat, lng) דרך Nominatim (OpenStreetMap) - שירות חינמי.
    חשוב: מדיניות השימוש ההוגן של Nominatim מגבילה לבקשה אחת בשנייה בלבד -
    לכן יש המתנה (sleep) של יותר משנייה בין כל בקשה לבקשה.

    אם הכתובת המדויקת (רחוב+מספר+עיר) לא נמצאת, מנסים fallback לרמת העיר בלבד -
    פחות מדויק (ממקם את הסניף במרכז העיר, לא בכתובת המדויקת), אבל עדיף על כלום.
    """
    if not city_name:
        return None, None, "no_city"

    def try_query(q):
        try:
            resp = requests.get(
                NOMINATIM_URL,
                params={"q": q, "format": "json", "limit": 1, "countrycodes": "il"},
                headers=HEADERS, timeout=15,
            )
            resp.raise_for_status()
            results = resp.json()
            if results:
                return float(results[0]["lat"]), float(results[0]["lon"])
        except Exception:
            pass
        return None, None

    lat, lng = try_query(f"{address}, {city_name}, ישראל")
    if lat is not None:
        return lat, lng, "exact"

    time.sleep(1.1)  # עוד בקשה = עוד המתנה, לפי אותה מדיניות שימוש הוגן
    lat, lng = try_query(f"{city_name}, ישראל")
    if lat is not None:
        return lat, lng, "city_fallback"

    return None, None, "failed"


# קובץ מטמון (cache) בתוך הריפו: store_id -> {lat, lng, location_precision}
# מהריצה המוצלחת האחרונה. בדיוק כמו data/city_code_fallback.json - Nominatim
# הוא שירות חיצוני חינמי, ואם הוא נופל/חוסם/מגביל קצב עבור כל הסניפים באותו
# יום ריצה, עדיף לחזור לקואורדינטות הידועות האחרונות מאשר להשאיר את כל
# הסניפים בלי מיקום. מתעדכן (מתרענן) בכל פעם שגיאוקודינג חי מצליח לסניף.
GEOCODE_CACHE_PATH = os.path.join("data", "geocode_cache.json")


def load_geocode_cache():
    try:
        with open(GEOCODE_CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_geocode_cache(cache):
    try:
        os.makedirs(os.path.dirname(GEOCODE_CACHE_PATH), exist_ok=True)
        with open(GEOCODE_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"  ⚠️  לא הצלחנו לשמור את קובץ מטמון הגיאוקודינג ({e}) - ממשיכים בכל זאת")


print("\n" + "=" * 60)
print(f"גיאוקודינג - ממיר כתובת לקואורדינטות עבור {len(all_stores)} סניפים")
print("(זה איטי בכוונה - שירות חינמי עם מגבלת בקשה אחת בשנייה, אמור לקחת כ-10 דקות)")
print("=" * 60)

geocode_cache = load_geocode_cache()
print(f"נטען מטמון גיאוקודינג קיים: {len(geocode_cache)} סניפים (מריצות קודמות)")

geocoded_exact = 0
geocoded_city = 0
geocoded_from_cache = 0
for i, s in enumerate(all_stores):
    lat, lng, precision = geocode_store(s["address"], s["city_name"])
    if lat is not None:
        geocode_cache[s["store_id"]] = {"lat": lat, "lng": lng, "location_precision": precision}
    elif s["store_id"] in geocode_cache:
        cached = geocode_cache[s["store_id"]]
        lat, lng, precision = cached["lat"], cached["lng"], f'{cached["location_precision"]}_cached'
        geocoded_from_cache += 1
    s["lat"] = lat
    s["lng"] = lng
    s["location_precision"] = precision
    if precision == "exact":
        geocoded_exact += 1
    elif precision == "city_fallback":
        geocoded_city += 1
    if (i + 1) % 50 == 0:
        print(f"  התקדמות: {i+1}/{len(all_stores)} (מדויק: {geocoded_exact}, ברמת עיר: {geocoded_city}, "
              f"ממטמון: {geocoded_from_cache})")
    time.sleep(1.1)  # מדיניות השימוש ההוגן של Nominatim - בקשה אחת בשנייה, לא יותר

save_geocode_cache(geocode_cache)
print(f"  נשמר מטמון גיאוקודינג מעודכן: {len(geocode_cache)} סניפים")

geocoded_ok = geocoded_exact + geocoded_city + geocoded_from_cache
print(f"\nגיאוקודינג הסתיים: {geocoded_ok} מתוך {len(all_stores)} סניפים קיבלו קואורדינטות")
print(f"  מתוכם: {geocoded_exact} בדיוק כתובת מלאה, {geocoded_city} ברמת עיר בלבד (fallback), "
      f"{geocoded_from_cache} ממטמון (Nominatim נכשל אבל היה לנו מיקום ידוע מריצה קודמת)")

with open("stores_transformed.json", "w", encoding="utf-8") as f:
    json.dump(all_stores, f, ensure_ascii=False, indent=2)

print("\nדוגמה לשלוש רשומות סניף עם קואורדינטות:")
for s in all_stores[:3]:
    print(" ", s)
