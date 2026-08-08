"""
שלב 2: הורדת דגימה קטנה + המרה ל-CSV.

מטרת הסקריפט: להוריד כמה קבצים אמיתיים מ-4 הרשתות שאישרנו שעובדות
(שופרסל, רמי לוי, יוחננוף, טיב טעם), ולהמיר אותם לקבצי CSV מסודרים -
כדי שנוכל *לראות בפועל* את העמודות והמבנה, לפני שבונים את כל שאר הצינור.

מריצים את זה בדיוק כמו את test_chain_access.py - ב-GitHub Actions,
לא במחשב האישי (חוץ אם תרצה, זה גם יעבוד מקומית עם pip install זהה).
"""

from il_supermarket_scarper import ScarpingTask, ScraperFactory
from il_supermarket_parsers import ConvertingTask
import os

# 4 הרשתות שאישרנו שעובדות
WORKING_CHAINS = [
    ScraperFactory.SHUFERSAL.name,
    ScraperFactory.RAMI_LEVY.name,
    ScraperFactory.YOHANANOF.name,
    ScraperFactory.TIV_TAAM.name,
]

RAW_DUMPS_PATH = "./dumps"
PARSED_CSV_PATH = "./parsed_csv"

print("=" * 60)
print("שלב א: מוריד דגימה (קובץ סניפים + קובץ מחירים מלא) מ-4 הרשתות")
print("=" * 60)

# חשוב: מפרידים בין סוגי הקבצים לשתי הורדות נפרדות, כל אחת עם limit משלה.
# בהורדה אחת עם limit משותף (כמו שעשינו קודם), ה-limit "נגמר" על קבצי הסניפים
# לפני שמגיעים בכלל לקובץ המחירים - ואז חלק מהרשתות לא מקבלות מחירים בכלל.
store_scraper = ScarpingTask(
    enabled_scrapers=WORKING_CHAINS,
    files_types=["STORE_FILE"],
    multiprocessing=1,
    output_configuration={"output_mode": "disk", "storage_path": RAW_DUMPS_PATH},
)
store_scraper.start(limit=1)
print("ממתין לסיום הורדת קובצי הסניפים...")
store_scraper.join()
print("קובצי הסניפים ירדו בהצלחה.\n")

price_scraper = ScarpingTask(
    enabled_scrapers=WORKING_CHAINS,
    files_types=["PRICE_FULL_FILE"],
    multiprocessing=1,
    output_configuration={"output_mode": "disk", "storage_path": RAW_DUMPS_PATH},
)
# limit=6 -> דגימה של עד 6 סניפים לכל רשת (איזון בין כיסוי לזמן ריצה),
# במקום סניף אחד בלבד. כך ההשוואה בין רשתות מבוססת על כמה סניפים ולא רק אחד.
price_scraper.start(limit=6)
print("ממתין לסיום הורדת קובצי המחירים המלאים...")
price_scraper.join()
print("ההורדה הסתיימה.\n")

print("=" * 60)
print("שלב ב: ממיר את הקבצים הגולמיים ל-CSV מסודר")
print("=" * 60)

converter = ConvertingTask(
    enabled_parsers=WORKING_CHAINS,
    files_types=["STORE_FILE", "PRICE_FULL_FILE"],
    source_configuration={"folder": RAW_DUMPS_PATH},
    output_configuration=[{"output_mode": "csv", "output_folder": PARSED_CSV_PATH}],
    status_configuration={"database_type": "json", "base_path": "./parse_status_logs"},
    multiprocessing=1,
)
converter.start()
print("ממתין לסיום ההמרה...")
converter.join()
print("ההמרה הסתיימה.\n")

print("=" * 60)
print("תוצאות - קבצי ה-CSV שנוצרו, ותצוגה מקדימה של השורות הראשונות")
print("=" * 60)

for dirpath, dirnames, filenames in os.walk(PARSED_CSV_PATH):
    for fname in filenames:
        full_path = os.path.join(dirpath, fname)
        print(f"\n--- {full_path} ---")
        with open(full_path, encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i >= 4:  # רק כותרת + 3 שורות ראשונות, כדי לא להציף
                    print("    ... (עוד שורות)")
                    break
                print("   ", line.strip())

print("\nהעתק/י את כל הפלט הזה ושלח/י אליי.")
