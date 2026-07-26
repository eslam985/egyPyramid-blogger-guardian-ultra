# /media/es/DDrive/projects/apps-python/egyPyramid-guardian-ultra/downloader_new/metadata/local_lookup.py
import sqlite3
import os

# المسار الصحيح لقاعدة البيانات داخل الحاوية
DB_PATH = os.path.join(os.path.dirname(__file__), 'imdb_lookup.db')

def search_local_imdb(clean_name, year):
    if not os.path.exists(DB_PATH) or not clean_name:
        return None
        
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        target_year = int(year)
        name_parts = clean_name.split()
        # تجهيز الكلمات المفتاحية للبحث المرن
        first_three_words = " ".join(name_parts[:3]) if len(name_parts) >= 3 else clean_name
        first_two_words = " ".join(name_parts[:2]) if len(name_parts) >= 2 else clean_name

        # --- الطبقة 1: التطابق التام (الدقة المطلقة) ---
        query1 = "SELECT tconst FROM imdb_lookup WHERE primaryTitle = ? AND startYear = ?"
        cursor.execute(query1, (clean_name, target_year))
        res = cursor.fetchall()
        
        if len(res) > 1:
            # تم اكتشاف أكثر من فيلم متطابق في الاسم والسنة، نُسقط البحث لمنع جلب بيانات خاطئة
            return finalize(conn, None)
        elif len(res) == 1:
            return finalize(conn, res[0][0])

        # --- الطبقة 2: مرونة السنة (+/- 1) مع الاسم كامل ---
        query2 = "SELECT tconst FROM imdb_lookup WHERE primaryTitle = ? AND (startYear BETWEEN ? AND ?) LIMIT 1"
        cursor.execute(query2, (clean_name, target_year - 1, target_year + 1))
        res = cursor.fetchone()
        if res: return finalize(conn, res[0])

        # --- الطبقة 3: البحث المرن (LIKE) بنفس السنة ---
        query3 = "SELECT tconst FROM imdb_lookup WHERE primaryTitle LIKE ? AND startYear = ? LIMIT 1"
        cursor.execute(query3, (f"{clean_name}%", target_year))
        res = cursor.fetchone()
        if res: return finalize(conn, res[0])

        # --- الطبقة 4: نظام "أول 3 كلمات" + نطاق 3 سنوات (القوة المرنة) ---
        query4 = "SELECT tconst FROM imdb_lookup WHERE primaryTitle LIKE ? AND (startYear BETWEEN ? AND ?) ORDER BY averageRating DESC LIMIT 1"
        cursor.execute(query4, (f"{first_three_words}%", target_year - 1, target_year + 1))
        res = cursor.fetchone()
        if res: return finalize(conn, res[0])

        # --- الطبقة 5: الملاذ الأخير (أول كلمتين) ---
        cursor.execute(query4, (f"{first_two_words}%", target_year - 1, target_year + 1))
        res = cursor.fetchone()
        if res: return finalize(conn, res[0])

        conn.close()
        return None
    except Exception as e:
        # تسجيل الخطأ بهدوء لعدم تعطيل السكريبت
        return None

def finalize(conn, result):
    conn.close()
    return result