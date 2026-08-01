"""
סקריפט בדיקת נגישות (connectivity test) ל-6 רשתות המזון שבחרנו.

מטרת הסקריפט: לענות על שאלה אחת בלבד - "האם אני יכול למשוך קובץ אמיתי
מכל אחת מ-6 הרשתות מהמחשב שלי?" זה לא בונה עדיין את הדשבורד האמיתי,
זו רק בדיקת היתכנות לפני שמשקיעים זמן בבניית כל הצינור.

איך להריץ:
1. ודא שמותקן Python 3.9 ומעלה במחשב שלך (לא בסביבה של קלוד - היא חסומה
   לאתרי הרשתות בכוונה, מטעמי אבטחה, אז חייבים להריץ את זה אצלך).
2. פתח טרמינל (CMD / PowerShell / Terminal) בתיקייה שבה שמרת את הקובץ הזה.
3. הרץ: pip install il-supermarket-scraper
4. הרץ: python test_chain_access.py
5. חכה כדקה-שתיים (הסקריפט מוריד קובץ בדיקה אחד קטן מכל רשת).
6. תעתיק אליי את הפלט המלא שהוא מדפיס - משם נדע בדיוק איך להמשיך.
"""

from il_supermarket_scarper import ScarpingTask, ScraperFactory
import os

# 6 הרשתות שבחרנו לפרויקט. שימו לב ל-VICTORY_NEW_SOURCE ולא VICTORY -
# זה השם הנוכחי בחבילה (המקור הישן של ויקטורי כבר לא קיים בגרסה העדכנית).
OUR_CHAINS = {
    "שופרסל": ScraperFactory.SHUFERSAL.name,
    "רמי לוי": ScraperFactory.RAMI_LEVY.name,
    "ויקטורי": ScraperFactory.VICTORY_NEW_SOURCE.name,
    "יוחננוף": ScraperFactory.YOHANANOF.name,
    "טיב טעם": ScraperFactory.TIV_TAAM.name,
    "חצי חינם": ScraperFactory.HAZI_HINAM.name,
}

STORAGE_PATH = "./test_dumps"

print("=" * 60)
print("בודק נגישות ל-6 הרשתות - מוריד קובץ בדיקה אחד מכל רשת")
print("=" * 60)

scraper = ScarpingTask(
    enabled_scrapers=list(OUR_CHAINS.values()),
    files_types=["STORE_FILE", "PRICE_FILE"],  # רק קובץ חנויות + קובץ מחירים, לבדיקה מהירה
    multiprocessing=1,  # רשת אחת בכל פעם, כדי שהפלט יהיה קריא וברור
    output_configuration={"output_mode": "disk", "storage_path": STORAGE_PATH},
)

# limit=1 => מוריד קובץ אחד בלבד לכל רשת/סוג קובץ (מספיק כדי לבדוק גישה)
scraper.start(limit=1)

# חשוב: start() מפעיל את ההורדה ב-thread ברקע וחוזר מיד -
# בלי join() נבדוק את התוצאות לפני שההורדה בכלל התחילה בפועל!
print("ממתין לסיום ההורדה בפועל...")
scraper.join()

print("\n" + "=" * 60)
print("תוצאות - כמה קבצים ירדו בפועל לכל רשת:")
print("=" * 60)

for name_he, factory_name in OUR_CHAINS.items():
    chain_folder = os.path.join(STORAGE_PATH, factory_name)
    if os.path.isdir(chain_folder):
        files = [f for f in os.listdir(chain_folder) if os.path.isfile(os.path.join(chain_folder, f))]
        status = "✅ הצליח" if len(files) > 0 else "❌ נכשל (התיקייה ריקה)"
        print(f"{name_he} ({factory_name}): {status} - {len(files)} קבצים")
    else:
        print(f"{name_he} ({factory_name}): ❌ נכשל (לא נוצרה תיקייה בכלל)")

print("\nהעתק/י את כל הפלט הזה ושלח/י אליי - משם נדע בדיוק איך להמשיך.")
