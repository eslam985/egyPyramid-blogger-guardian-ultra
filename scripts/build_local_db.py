import csv
import gzip
import sqlite3
import os

def build_radar():
    db_dir = 'downloader_new/metadata'
    db_path = os.path.join(db_dir, 'imdb_lookup.db')
    os.makedirs(db_dir, exist_ok=True)

    # الإعدادات
    min_year = 2000
    basics_file = 'title.basics.tsv.gz'
    ratings_file = 'title.ratings.tsv.gz'

    print(f"⏳ بدأت معالجة البيانات (سنة {min_year}+)...")

    try:
        # 1. تحميل التقييمات في الذاكرة أولاً (لأنها أصغر)
        ratings_dict = {}
        with gzip.open(ratings_file, 'rt', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='\t')
            for row in reader:
                ratings_dict[row['tconst']] = row['averageRating']

        # 2. إنشاء قاعدة البيانات
        conn = sqlite3.connect(db_path)
        conn.execute("DROP TABLE IF EXISTS imdb_lookup")
        conn.execute("""
            CREATE TABLE imdb_lookup (
                tconst TEXT,
                primaryTitle TEXT,
                startYear INTEGER,
                averageRating REAL,
                genres TEXT
            )
        """)

        # 3. قراءة البيانات الأساسية وتصفيتها وحفظها
        with gzip.open(basics_file, 'rt', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='\t', quoting=csv.QUOTE_NONE)
            batch = []
            for row in reader:
                # تصفية: أفلام ومسلسلات فقط + سنة صالحة + أكبر من 2000
                if row['titleType'] in ['movie', 'tvSeries'] and row['startYear'].isdigit():
                    year = int(row['startYear'])
                    if year >= min_year:
                        t_id = row['tconst']
                        rating = ratings_dict.get(t_id, 0)
                        batch.append((t_id, row['primaryTitle'], year, float(rating), row['genres']))
                
                # إدخال البيانات على دفعات (Batch) لتسريع العملية
                if len(batch) >= 10000:
                    conn.executemany("INSERT INTO imdb_lookup VALUES (?,?,?,?,?)", batch)
                    batch = []

            if batch:
                conn.executemany("INSERT INTO imdb_lookup VALUES (?,?,?,?,?)", batch)

        # 4. إنشاء الكشاف (Index) للسرعة الخارقة
        conn.execute("CREATE INDEX idx_title_year ON imdb_lookup (primaryTitle, startYear)")
        conn.commit()
        conn.close()

        print(f"✅ تم بناء الرادار بنجاح! قاعدة البيانات جاهزة في: {db_path}")

    except Exception as e:
        print(f"❌ خطأ فني: {e}")
        exit(1)

if __name__ == "__main__":
    build_radar()