import pandas as pd
import sqlite3
import os

def build_radar():
    # المسارات بناءً على هيكلة مشروعك
    db_dir = 'downloader_new/metadata'
    db_path = os.path.join(db_dir, 'imdb_lookup.db')
    
    # التأكد من وجود المجلد
    os.makedirs(db_dir, exist_ok=True)

    print("⏳ بدأت معالجة ملفات IMDb... ده هياخد دقيقة")

    try:
        # 1. قراءة البيانات (الملفات دي الـ Dockerfile بيحملها قبل ما يشغل السكريبت ده)
        # نستخدم dtype لتقليل استهلاك الرامات أثناء المعالجة
        basics = pd.read_csv('title.basics.tsv.gz', sep='\t', low_memory=False, compression='gzip', 
                             usecols=['tconst', 'titleType', 'primaryTitle', 'startYear', 'genres'])
        
        ratings = pd.read_csv('title.ratings.tsv.gz', sep='\t', low_memory=False, compression='gzip',
                              usecols=['tconst', 'averageRating'])

        # 2. الدمج (Merge) بناءً على معرف IMDb الفريد
        df = pd.merge(basics, ratings, on='tconst')

        # 3. التصفية الجراحية (Cleaning)
        # نفلتر الأفلام والمسلسلات فقط
        df = df[df['titleType'].isin(['movie', 'tvSeries'])]
        
        # تحويل السنة لرقم وتصفية القيم غير الصالحة
        df = df[df['startYear'].str.isnumeric()]
        df['startYear'] = df['startYear'].astype(int)

        # ---------------------------------------------------------
        # التعديل المطلوب: لو عايز تغير السنة (مثلاً 2000 أو 1990) غير الرقم ده بس
        min_year = 2000 
        # ---------------------------------------------------------
        
        df = df[df['startYear'] >= min_year]

        # 4. حفظ النتيجة في قاعدة بيانات SQLite
        print(f"💾 جاري حفظ {len(df)} سجل في {db_path}...")
        conn = sqlite3.connect(db_path)
        
        # اختيار الأعمدة النهائية فقط لتقليل حجم الـ .db
        df[['tconst', 'primaryTitle', 'startYear', 'averageRating', 'genres']].to_sql(
            'imdb_lookup', conn, if_exists='replace', index=False
        )

        # 5. إنشاء Index (عشان البحث يكون لمح البصر)
        conn.execute("CREATE INDEX idx_title_year ON imdb_lookup (primaryTitle, startYear)")
        conn.close()

        print(f"✅ تم بناء الرادار المحلي بنجاح (سنة {min_year}+)")

    except Exception as e:
        print(f"❌ فشل بناء الرادار: {e}")
        exit(1)

if __name__ == "__main__":
    build_radar()