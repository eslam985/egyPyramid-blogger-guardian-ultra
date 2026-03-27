import os
import re
import time
import json
import random
from datetime import datetime

# 1. استدعاء الخدمات المركزية
from services.supabase_db import SupabaseService
from services.blogger_api import BloggerService

# 2. استدعاء الأدوات المحلية (تأكد من وجود النقطة قبل اسم الملف)
from .utils import (
    ar_to_en,
    clean_for_match,
    convert_vk_to_embed,
    generate_clean_slug,
    generate_ai_seo_description,
    generate_seo_tags,
    format_duration_iso,
)


# 3. استدعاء القوالب
from .templates_store import HTML_TEMPLATE_SERIES, HTML_TEMPLATE_MOVIE

# 3. تعريف المتغيرات العالمية (Global Variables) لتوافق الكود القديم
# هذا يحل أخطاء "supabase is not defined"
supabase = SupabaseService.client
BLOG_ID = os.getenv("BLOG_ID")


# 4. دالة الجسر (Bridge Function)
# هذا يحل أخطاء "get_blogger_service is not defined"
def get_blogger_service():
    blogger_inst = BloggerService(blog_id=BLOG_ID)
    return blogger_inst.get_service()


# 5. كائن البلوجر للاستخدام العام
blogger = BloggerService(blog_id=BLOG_ID)


def prepare_content(row, is_series_by_title):
    # --- أضف هذا التعريف الافتراضي في الأعلى ---
    f_voe = f_vid = f_ok = f_vk = ""
    # ------------------------------------------

    episodes_list = []
    content_type = "MOVIE"
    # ... بقية الكود كما هو
    # محاولة جمع الحلقات
    for i in range(1, 51):
        voe_val = str(row.get(f"ep{i}_voe", "")).strip()
        vid_val = str(row.get(f"ep{i}_vidtube", "")).strip()
        ok_val = str(row.get(f"ep{i}_ok", "")).strip()

        if "vidtube.one/" in vid_val and "embed-" not in vid_val:
            vid_val = vid_val.replace("vidtube.one/", "vidtube.one/embed-")

        down_val = str(row.get(f"ep{i}_down", "")).strip()

        # تحويل روابط VK لكل حلقة
        vk_raw_ep = str(row.get(f"ep{i}_vk", "")).strip()
        vk_val_ep = (
            convert_vk_to_embed(vk_raw_ep) if vk_raw_ep and vk_raw_ep != "nan" else ""
        )

        if voe_val and voe_val != "nan":
            episodes_list.append(
                {
                    "no": str(i),
                    "voe": voe_val,
                    "vidtube": vid_val if (vid_val and vid_val != "nan") else "",
                    "ok": ok_val if (ok_val and ok_val != "nan") else "",
                    "vk": vk_val_ep if (vk_val_ep and vk_val_ep != "nan") else "",
                    "down": (
                        down_val
                        if (down_val and down_val != "nan")
                        else str(row.get("download_url", ""))
                    ),
                }
            )

    if episodes_list:
        content_type = "SERIES"
        # تأمين جلب القيم الأولى للاستخدام الخارجي (لو لزم الأمر)
        f_voe = episodes_list[0].get("voe", "")
        f_vid = episodes_list[0].get("vidtube", "")
        f_ok = episodes_list[0].get("ok", "")
        f_vk = episodes_list[0].get("vk", "")

        # التعديل هنا لضمان توافق الهيكل مع نظام الحقن الجديد
        ep_buttons_html = (
            '\n<div class="episodes-container ep-More" id="episodes-container">\n'
        )
        for ep in episodes_list:
            is_active = "active" if ep["no"] == "1" else ""

            # التعديل: تجميع ديناميكي لكل السيرفرات المتاحة في كائن الحلقة
            current_links = []
            excluded = ["down", "no", "telegram_direct", "archive"]

            for s_key, s_url in ep.items():
                if (
                    s_key not in excluded
                    and s_url
                    and str(s_url).lower() not in ["nan", ""]
                ):
                    current_links.append({"name": s_key, "url": s_url})

            links_json = json.dumps(current_links).replace('"', "&quot;")

            # بناء الزر الديناميكي
            ep_buttons_html += f'    <div class="ep-btn {is_active}" onclick="playEpDynamic(this, \'{ep["no"]}\', \'{ep["down"]}\', \'{links_json}\')">{ep["no"]}</div>\n'
    else:
        # إذا كانت قائمة الحلقات فارغة ولكننا نعلم أنه مسلسل من العنوان
        if is_series_by_title:
            content_type = "SERIES"

            # تجميع ديناميكي من الـ row مباشرة
            current_links = []
            excluded_from_view = [
                "telegram_direct",
                "archive",
                "download",
                "title",
                "poster",
                "story",
                "labels",
                "Rating",
                "Movie Runtime",
                "Year",
            ]

            for key, value in row.items():
                if key.endswith("_url"):
                    s_name = key.replace("_url", "")
                    if s_name not in excluded_from_view:
                        u = str(value).strip()
                        if u and u.lower() not in ["nan", ""]:
                            # تصحيحات سريعة للروابط المشهورة
                            if s_name == "vidtube" and "embed-" not in u:
                                u = u.replace("vidtube.one/", "vidtube.one/embed-")
                            if s_name == "vk":
                                u = convert_vk_to_embed(u)
                            current_links.append({"name": s_name, "url": u})

            links_json = json.dumps(current_links).replace('"', "&quot;")
            down_url = row.get("download_url", "")

            # بناء أزرار افتراضية بنظام Dynamic
            ep_buttons_html = (
                f'\n<div class="episodes-container ep-More" id="episodes-container">\n'
            )
            ep_buttons_html += f"    <div class=\"ep-btn active\" onclick=\"playEpDynamic(this, '1', '{down_url}', '{links_json}')\">1</div>\n"
            ep_buttons_html += "\n</div>\n"

            episodes_list = [{"no": "1"}]  # للمحافظة على تدفق السكريبت
        else:
            # حالة الفيلم الحقيقية
            content_type = "MOVIE"
            f_voe = str(row.get("voe_url", "")).strip()
            f_ok = str(row.get("ok_url", "")).strip()
            vk_raw_movie = str(row.get("vk_url", "")).strip()
            f_vk = (
                convert_vk_to_embed(vk_raw_movie)
                if vk_raw_movie and vk_raw_movie != "nan"
                else ""
            )
            vid_val = str(row.get("vidtube_url", "")).strip()
            if "vidtube.one/" in vid_val and "embed-" not in vid_val:
                vid_val = vid_val.replace("vidtube.one/", "vidtube.one/embed-")
            f_vid = vid_val
            ep_buttons_html = ""

    return content_type, episodes_list, ep_buttons_html, f_voe, f_vid, f_ok, f_vk


def update_series_post(
    service, post_id, row, lang_val="لغة أصلية", ep_no=None, ep_id=None
):
    # واحذف أسطر الـ re.search الخاصة بالـ ep_match
    # واستخدم ep_no الممرر مباشرة
    try:
        # 1. جلب بيانات المقال من بلوجر
        try:
            post = service.posts().get(blogId=BLOG_ID, postId=post_id).execute()
        except Exception as e:
            if "404" in str(e):
                print(f"🛑 المقال {post_id} غير موجود. سيتم تجاهل التحديث.")
                return False
            raise e

        content = post.get("content", "")

        # 3. منع التكرار داخل HTML بلوجر
        # هنسمح بالتحديث حتى لو موجودة عشان نحدث السيرفرات (Force Update)
        if f", '{ep_no}'," in content and "playEpDynamic" in content:
            # لو موجودة وبالنظام الجديد فعلاً، خلاص مش لازم نحدث
            print(f"🟡 الحلقة {ep_no} موجودة بالنظام الجديد فعلاً.")
            # return True # ممكن تقفل الريتيرن دي لو عايز تجبره يلبس الكود الجديد
            return True

        # 4. معالجة الروابط وتحديث Supabase (بدلاً من الأرشيف القديم)
        # نرسل content_type كـ SERIES هنا لأن الدالة لتحديث المسلسلات
        # sync_res = sync_to_supabase(row, "SERIES", post_id)
        # if not sync_res:
        # print("⚠️ فشل مزامنة البيانات مع ساب باز، لكن سنستمر في تحديث بلوجر.")

        # 5. بناء كود الزر الجديد (الحقن الرقمي)
        # جلب الروابط المحولة جاهزة (VK تم تحويله داخل sync_to_supabase)
        voe_url = str(row.get("voe_url", "")).strip()
        vid_url = (
            str(row.get("vidtube_url", ""))
            .strip()
            .replace("vidtube.one/", "vidtube.one/embed-")
        )
        ok_url = str(row.get("ok_url", "")).strip()
        if ok_url.startswith("//"):
            ok_url = "https:" + ok_url
        vk_url = convert_vk_to_embed(
            str(row.get("vk_url", ""))
        )  # تحويل يدوي سريع للـ HTML
        down_url = str(row.get("download_url", "")).strip()

        # التعديل: تجميع ديناميكي لكل السيرفرات المتاحة في الصف
        # 1. تجميع الروابط المتاحة لهذه الحلقة من الـ row الممرر (تعديل ديناميكي)
        episode_links = []
        target_servers = [
            "voe",
            "vidtube",
            "ok",
            "vk",
            "doodstream",
            "streamtape",
            "lulustream",
            "mixdrop",
        ]
        for s_name in target_servers:
            u = row.get(f"{s_name}_url") or row.get(s_name)
            if u and str(u).lower() not in ["nan", "", "none", "pending"]:
                u = str(u).strip()
                if s_name == "vidtube" and "embed-" not in u:
                    u = u.replace("vidtube.one/", "vidtube.one/embed-")
                if s_name == "vk":
                    u = convert_vk_to_embed(u)
                episode_links.append({"name": s_name, "url": u})

        links_json = json.dumps(episode_links).replace('"', "&quot;")

        # 2. بناء الزر الديناميكي الجديد
        new_btn = f"<div class=\"ep-btn\" onclick=\"playEpDynamic(this, '{ep_no}', '{down_url}', '{links_json}')\">{ep_no}</div>"

        # 6. عملية الحقن داخل كلاس ep-More
        target_marker = 'ep-More"'
        if target_marker in content:
            parts = content.split(target_marker, 1)
            sub_parts = parts[1].split(">", 1)
            updated_content = (
                parts[0]
                + target_marker
                + sub_parts[0]
                + ">"
                + f"\n    {new_btn}"
                + sub_parts[1]
            )
        else:
            # حالة الطوارئ لو الكلاس غير موجود
            updated_content = (
                content + f'\n<div class="episodes-container ep-More">{new_btn}</div>'
            )

        # 7. تنفيذ التحديث في بلوجر
        post["content"] = updated_content
        updated_post_obj = (
            service.posts().patch(blogId=BLOG_ID, postId=post_id, body=post).execute()
        )
        # --- التعديل هنا: تحديث الحالة في ساب باز ---
        supabase.table("episodes").update(
            {"blogger_status": "published", "is_synced": True}
        ).eq(
            "id", ep_id
        ).execute()  # تأكد أن ep_id ممرر للدالة
        # ------------------------------------------
        print(f"✅ تم حقن الحلقة {ep_no} بنجاح في بلوجر وساب باز.")
        return True

    except Exception as e:
        if "404" in str(e):
            print(f"🛑 المقال {post_id} غير موجود في بلوجر!")
            # الحل الذكي: امسح الـ ID من Supabase ليضطر السكريبت لإنشاء مقال جديد صحيح
            supabase.table("medias").update({"blogger_post_id": None}).eq(
                "blogger_post_id", post_id
            ).execute()
            return False
        raise e


def start_publishing_from_supabase():
    print("🚀 جاري سحب المهام الجديدة من Supabase (is_synced = False)...")
    try:
        service = get_blogger_service()

        # 1. الاستعلام عن الحلقات التي لم تُنشر بعد مع بيانات الميديا
        query = (
            supabase.table("episodes")
            .select("*, medias(*)")
            .eq("is_synced", False)
            .in_(
                "blogger_sync", ["Approved", "Done", "Pending"]
            )  # يقرأ أي حالة طالما لم يُنشر
            .execute()
        )
        new_tasks = query.data

        if not new_tasks:
            print("☕ لا توجد حلقات جديدة للنشر حالياً. ساب باز نظيف!")
            return

        for task in new_tasks:
            ep_id = task["id"]
            ep_no = task["episode_number"]
            m_data = task["medias"]
            m_id = m_data["id"]
            title = m_data["title"]
            old_post_id = m_data.get("blogger_post_id")

            # تحديد نوع العمل بدقة من ساب باز
            is_series = m_data.get("category") == "tv" or "الحلقة" in title
            content_type = "SERIES" if is_series else "MOVIE"

            print(f"🎬 معالجة {content_type}: {title} - الحلقة {ep_no}")

            # 2. جلب الروابط وتجهيز الـ Row الوهمي
            l_query = (
                supabase.table("links").select("*").eq("episode_id", ep_id).execute()
            )
            links_map = {l["server_name"]: l["url"] for l in l_query.data}

            # 2. بناء الـ Row الأساسي
            row = {
                "title": title,
                "poster": m_data.get("poster_url", ""),
                "story": m_data.get("story", ""),
                "labels": m_data.get("labels", ""),
                "Rating": m_data.get("rating", "7.5"),
                "Movie Runtime": m_data.get("runtime", "غير محدد"),
                "Year": m_data.get("year", ""),
                "download_url": links_map.get("download", ""),
            }

            # 3. إضافة كل سيرفر موجود في ساب باز إلى الـ row تلقائياً
            for s_name, s_url in links_map.items():
                if s_name not in ["download", "telegram_direct", "archive"]:
                    row[f"{s_name}_url"] = s_url

            # 3. اختيار القالب وبناء المحتوى (Logic الاستدعاء)
            # استدعاء دالة prepare_content التي تملكها أصلاً لاختيار القالب المناسب
            _, _, ep_buttons, _, _, _, _ = prepare_content(row, is_series)

            # 4. منطق اتخاذ القرار (تحديث حلقة أم نشر جديد)
            if old_post_id and str(old_post_id).lower() != "nan":
                print(f"🔄 جاري حقن الحلقة {ep_no} في المقال {old_post_id}...")
                # اجعله هكذا (نمرر رقم الحلقة الصريح ep_no)
                success = update_series_post(
                    service, old_post_id, row, ep_no=ep_no, ep_id=ep_id
                )
            else:
                # --- لوجيك النشر الجديد كلياً (بناء القالب لأول مرة) ---
                print(f"🆕 إنشاء مقال جديد لـ {title}...")

                # توليد الـ SEO والوصف (نفس اللوجيك القديم عندك)
                auto_desc = generate_ai_seo_description(title, row.get("story", ""))
                
                # التعديل: استخدام الـ slug من قاعدة البيانات (المحتوي على الـ ID) لضمان توافق Next.js
                # وإذا لم يكن موجوداً، نقوم بتوليده كخطة احتياطية
                slug_name = m_data.get("slug")
                if not slug_name:
                    slug_name = generate_clean_slug(title)
                
                current_template = (
                    HTML_TEMPLATE_SERIES if is_series else HTML_TEMPLATE_MOVIE
                )

                # --- الكود الجديد يبدأ من هنا ---
                # 1. تجميع روابط السيرفرات ديناميكياً
                # 1. تجميع روابط السيرفرات ديناميكياً من المصدر الخام (links_map)
                current_links = []
                target_servers = [
                    "voe",
                    "vidtube",
                    "ok",
                    "vk",
                    "doodstream",
                    "streamtape",
                    "lulustream",
                    "mixdrop",
                ]

                for s_name in target_servers:
                    # نسحب الرابط مباشرة من ساب باز وليس من الـ row الوهمي
                    u = links_map.get(s_name)
                    if u and str(u).lower() not in ["nan", "", "none", "pending"]:
                        u = str(u).strip()
                        # تصحيحات الروابط (Embed)
                        if s_name == "vidtube" and "embed-" not in u:
                            u = u.replace("vidtube.one/", "vidtube.one/embed-")
                        if s_name == "vk":
                            u = convert_vk_to_embed(u)
                        current_links.append({"name": s_name, "url": u})

                links_json = json.dumps(current_links).replace('"', "&quot;")
                down_link = row.get("download_url", "#")

                # 2. بناء "كتلة الأزرار" بناءً على النوع
                if is_series:
                    # للمسلسل: نستخدم الحلقات التي تم تجهيزها في ep_buttons
                    final_buttons = ep_buttons
                else:
                    # للفيلم: ننشئ حاوية تحتوي على زر "مشاهدة الفيلم" الذي يولد السيرفرات
                    final_buttons = f"""
                    <div class="episodes-container ep-More">
                        <div class="ep-btn active" onclick="playEpDynamic(this, 'مشاهدة الفيلم', '{down_link}', '{links_json}')">▶ اضغط هنا لمشاهدة الفيلم</div>
                    </div>
                    """

                # --- التعديل الجوهري لإصلاح الشاشة السوداء ---

                # 1. استخراج أول رابط متاح للمشغل (Default Server)
                # اختيار أول سيرفر متاح كمشغل افتراضي مع التأكد من جاهزيته
                f_voe = links_map.get("voe")
                if f_voe and str(f_voe).lower() != "nan":
                    default_url = f_voe
                elif current_links:
                    default_url = current_links[0]["url"]
                else:
                    default_url = "https://about:blank"  # حماية لو مفيش روابط خالص

                print(f"🎬 [Player]: المشغل الافتراضي جاهز برابط: {default_url}")

                # 1. تجهيز المتغيرات الإضافية (MetaData)
                search_desc = f"مشاهدة فيلم {title} مترجم اون لاين بجودة عالية. تفاصيل فيلم {title} والقصة وسيرفرات المشاهدة."
                current_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+02:00")
                logo_url = "https://res.cloudinary.com/dbahqgo8j/image/upload/q_auto,f_auto,w_80,h_80,c_fill/blogger/logo.webp"  # ضع رابط لوجو موقعك هنا
                lang_work = row.get("LANGUAGE", " مدبلج / مترجم")

                # 2. عملية الحقن الشاملة (تأكد من شمول كل الأقواس)
                final_html = (
                    current_template.replace("{{TITLE}}", title)
                    .replace("{{POSTER_URL}}", row["poster"])
                    .replace("{{STORY}}", row["story"])
                    .replace("{{CUSTOM_LINK}}", slug_name)
                    .replace("{{EPISODES_BUTTONS}}", final_buttons)
                    .replace("{{DOWNLOAD_URL}}", down_link)
                    .replace("{{DISPLAY_DATE}}", row.get("Year", "2026"))
                    .replace("{{RATING}}", row.get("Rating", "7.5"))
                    .replace("{{RUNTIME}}", row.get("Movie Runtime", "غير محدد"))
                    .replace("{{LABELS}}", row.get("labels", "Movies"))
                    .replace("{{VOE_URL}}", default_url)
                    .replace("{{POST_ID}}", str(m_id))
                    # --- الإضافات الجديدة لإصلاح الميتا داتا ---
                    .replace("{{SEARCH_DESCRIPTION}}", search_desc)
                    .replace("{{CURRENT_DATE}}", current_time)
                    .replace("{{LOGO_URL}}", logo_url)
                    .replace("{{LANGUAGE}}", lang_work)
                    .replace(
                        "{{DURATION_ISO}}",
                        format_duration_iso(row.get("Movie Runtime", "120")),
                    )
                    .replace(
                        "{{TAGS_CONTENT}}",
                        generate_seo_tags(title, row.get("labels", "Movies")),
                    )
                )
                # --- الكود الجديد ينتهي هنا ---

                # إضافة الهيدر المخفي للـ Snippet
                extra_header = f'<div style="display:none;"><img src="{row["poster"]}" />{auto_desc}</div>'
                final_html = extra_header + final_html

                body = {
                    "kind": "blogger#post",
                    "blog": {"id": BLOG_ID},
                    "title": title,
                    "content": final_html,
                    # بدلاً من السطر القديم الذي يسبب الخطأ
                    "labels": [
                        l.strip()
                        for l in str(m_data.get("labels") or "Movies").split(",")
                        if l.strip()
                    ],
                    "description": auto_desc,
                    "customUrl": slug_name,
                }

                post_result = (
                    service.posts()
                    .insert(blogId=BLOG_ID, body=body, isDraft=True)
                    .execute()
                )
                # داخل الـ else (بعد إدخال المقال):
                new_id = post_result.get("id")
                # حدث فقط الـ ID الخاص بالميديا
                supabase.table("medias").update({"blogger_post_id": new_id}).eq(
                    "id", m_id
                ).execute()

                # الـ success = True كافية لتخبر السكريبت أن ينهي المهمة في الجزء الأخير
                success = True

            # 5. ختم المهمة (هذا الجزء يغطي الحالتين: النشر الجديد أو التحديث)
            if success:
                supabase.table("episodes").update(
                    {"is_synced": True, "blogger_status": "published"}
                ).eq("id", ep_id).execute()
                print(f"✅ تم إنهاء المهمة بنجاح.")

            # بدلاً من رقم ثابت
            time.sleep(random.randint(10, 20))
    except Exception as e:
        print(f"❌ فشل المحرك: {str(e)}")
        # بدلاً من الاكتفاء بالطباعة، ارفع الخطأ ليراه السيرفر
        raise e


def sync_to_supabase(row, content_type, post_id=None):
    """
    المحرك المركزي: يربط البيانات بـ Supabase بدلاً من شيت الأرشفة.
    """
    title = str(row.get("title", "")).strip()
    year = str(row.get("Year", "")).strip()
    if year in ["null", "None", "", "nan"]:
        year = None

    # 1. تجهيز بيانات الميديا (الأب)
    media_payload = {
        "title": title,
        "story": str(row.get("story", "")).strip(),
        "poster_url": str(row.get("poster", "")).strip(),
        "category": "tv" if content_type == "SERIES" else "movie",
        "year": year,
        "rating": str(row.get("Rating", "")).strip() if row.get("Rating") else None,
        "labels": str(row.get("labels", "")).strip(),
        "runtime": str(row.get("Movie Runtime", "")).strip(),
    }

    try:
        # تنفيذ الـ upsert بناءً على العنوان (Title)
        m_res = (
            supabase.table("medias")
            .upsert(media_payload, on_conflict="title")
            .execute()
        )
        if not m_res.data:
            return None

        m_id = m_res.data[0]["id"]

        # 2. تحديد رقم الحلقة (لو مسلسل)
        ep_no = 1
        if content_type == "SERIES":
            clean_t = title.replace("2026", "").replace("2025", "")
            ep_match = re.search(r"(?:الحلقة|حلقة)\s*([0-9٠-٩]+)", clean_t)
            ep_no = ar_to_en(ep_match.group(1).strip()) if ep_match else 1

        identifier = f"m{m_id}_ep{ep_no}"

        # 3. تحديث جدول الحلقات (Episodes) مع الـ Blogger Post ID
        ep_payload = {
            "media_id": m_id,
            "episode_number": ep_no,
            "identifier": identifier,
            "blogger_post_id": str(post_id) if post_id else None,
        }
        ep_res = (
            supabase.table("episodes")
            .upsert(ep_payload, on_conflict="identifier")
            .execute()
        )
        e_id = ep_res.data[0]["id"]

        # 4. تجهيز الروابط (Links)
        # نجمع الروابط المتاحة في الصف الحالي
        links = []
        map_basic = {
            "voe_url": "voe",
            "vidtube_url": "vidtube",
            "ok_url": "ok",
            "vk_url": "vk",
            "download_url": "download",
        }
        for k, s in map_basic.items():
            u = str(row.get(k, "")).strip()
            if u and u not in ["nan", "", "None", "Pending"]:
                if s == "vk":
                    u = convert_vk_to_embed(u)
                links.append({"episode_id": e_id, "server_name": s, "url": u})

        if links:
            # مسح الروابط القديمة لهذه الحلقة وإعادة حقنها (لضمان التحديث)
            supabase.table("links").delete().eq("episode_id", e_id).execute()
            supabase.table("links").insert(links).execute()

        return {"m_id": m_id, "e_id": e_id, "post_id": post_id}

    except Exception as e:
        print(f"❌ Supabase Sync Error for {title}: {e}")
        return None
