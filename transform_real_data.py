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

def is_bad_address(addr, city):
    """כתובת לא שמישה: ריקה, unknown, או placeholder כמו '' או {}"""
    if pd.isna(addr) or str(addr).strip() in ("", "unknown", "''", "{}", "0"):
        return True
    return False


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
            "store_name": name,
            "address": row.get("address", ""),
            "city_code": row.get("city", ""),
            "zipcode": row.get("zipcode", ""),
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
    chain_info, stores, stats = process_store_file(f"{INPUT_DIR}/{fname}")
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

CBS_RESOURCE_ID = "b7cf8f14-64a2-4b33-8d4b-edb286fdbd37"  # קובץ יישובים - data.gov.il

def load_city_code_lookup():
    """
    מוריד את טבלת קודי היישובים הרשמית (משרד הפנים/למ"ס) דרך data.gov.il,
    וממפה קוד יישוב -> שם יישוב. אם ה-API לא זמין/ה-resource_id השתנה,
    מחזיר מיפוי ריק (לא מפיל את כל הסקריפט - פשוט נשארים עם הקוד הגולמי).
    """
    try:
        resp = requests.get(
            "https://data.gov.il/api/3/action/datastore_search",
            params={"resource_id": CBS_RESOURCE_ID, "limit": 3000},
            timeout=30,
        )
        resp.raise_for_status()
        records = resp.json()["result"]["records"]
        print(f"  הורדו {len(records)} רשומות יישובים מ-data.gov.il")
        # שמות השדות בפועל ב-API עשויים להשתנות - מדפיסים את הראשון לבדיקה
        if records:
            print(f"  לדוגמה, שדות הרשומה הראשונה: {list(records[0].keys())}")
        lookup = {}
        for r in records:
            code = str(r.get("סמל_ישוב") or r.get("SEMEL_YISHUV") or r.get("סמל יישוב") or "").strip()
            name = str(r.get("שם_ישוב") or r.get("SHEM_YISHUV") or r.get("שם יישוב") or "").strip()
            if code:
                lookup[code] = name
        return lookup
    except Exception as e:
        print(f"  ⚠️  לא הצלחתי להוריד את קובץ היישובים ({e}) - ממשיכים עם קוד גולמי בלבד")
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

    print(f"\nסה\"כ מוצרים ייחודיים בכל הרשתות: {len(products_combined)}")
    print(f"סה\"כ רשומות מחיר בכל הרשתות: {len(prices_combined)}")
    print("\nדוגמה לקטלוג מוצרים משולב:")
    print(products_combined.head(5).to_string(index=False))
    print("\nדוגמה לטבלת מחירים משולבת:")
    print(prices_combined.head(5).to_string(index=False))

    products_combined.to_json("products_transformed.json", orient="records", force_ascii=False, indent=2)
    prices_combined.to_json("prices_transformed.json", orient="records", force_ascii=False, indent=2)
else:
    print("\n⚠️  לא נמצא אף קובץ מחירים לעיבוד")
