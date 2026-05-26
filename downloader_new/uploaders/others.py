# /media/es/DDrive/projects/apps-python/egyPyramid-guardian-ultra/downloader_new/uploaders/others.py
import urllib
import httpx
import asyncio
from downloader_new.shared.logger import get_beast_logger

log = get_beast_logger("GuardianUltra")


async def upload_to_doodstream(api_key, identifier, file_name):
    """الرفع لـ DoodStream مع تجربة نطاقات متعددة وفحص صبور"""
    log.info(f"📡 DoodStream: إرسال أمر سحب من الأرشيف...")

    # قائمة النطاقات البديلة للـ API
    api_domains = [
        "doodapi.co",
        "d_api.com",
        "doodapi.com",
        "dood.to",
        "dood.stream",
        "playmogo.com",
        "doodstream.com",
    ]
    clean_file_name = urllib.parse.quote(file_name)
    # المصدر هو الرابط المباشر أو بناء رابط الأرشيف
    remote_url = (
        identifier
        if str(identifier).startswith("http")
        else f"https://archive.org/download/{identifier}/{clean_file_name}"
    )

    headers = {"User-Agent": "Mozilla/5.0"}

    async with httpx.AsyncClient(
        timeout=30.0, headers=headers, follow_redirects=True
    ) as client:
        # محاولة إرسال الأمر باستخدام النطاقات المتاحة
        data = None
        for domain in api_domains:
            try:
                # نقوم بعمل encode للاسم لضمان وصوله للسيرفر بالحروف العربية
                safe_title = urllib.parse.quote(file_name)
                add_url = f"https://{domain}/api/upload/url?key={api_key}&url={remote_url}&new_title={safe_title}"
                response = await client.get(add_url)
                data = response.json()
                # بدلاً من الشرط الحالي، خليه أشمل:
                if data.get("msg") == "OK" or data.get("success") is True:
                    log.info(f"✅ DoodStream: تم قبول الأمر عبر {domain}")
                    break
            except Exception:
                await asyncio.sleep(2)  # انتظار بسيط قبل تجربة نطاق آخر
                continue

        if not data or (data.get("msg") != "OK" and not data.get("success")):
            return None

        # التعديل وفقاً للتوثيق: المفتاح هو filecode والنتيجة قاموس
        f_code = data.get("result", {}).get("filecode")
        log.info(f"🔍 DoodStream Task ID: {f_code}")

        # محاولات الفحص (نزيد الوقت قليلاً لضمان عدم الحظر)
        for i in range(1, 21):
            await asyncio.sleep(20)  # 15 ثانية وقت مثالي للملفات الصغيرة
            log.info(f"🔄 DoodStream Polling Attempt {i}/20...")

            for domain in api_domains:
                try:
                    # الطريقة الأضمن: اسأل عن "معلومات الملف" مباشرة بالـ f_code
                    info_url = f"https://{domain}/api/file/info?key={api_key}&file_code={f_code}"
                    res = await client.get(info_url)
                    info_data = res.json()

                    # إذا رد السيرفر بمعلومات الملف وكان الـ status 200 (أي الملف موجود)
                    if info_data.get("status") == 200:
                        result = info_data.get("result", [{}])[0]
                        # بمجرد وجود الـ file_code والحجم (حتى لو لسه 0 أو بيزيد) نعتبره نجاح
                        if result.get("file_code") == f_code:
                            raw_size = result.get("size", 0)
                            size_mb = float(raw_size) / (1024 * 1024)
                            log.info(
                                f"✅ DoodStream Success: الملف موجود وبدأ المعالجة ({size_mb:.2f} MB)"
                            )
                            return f"https://playmogo.com/e/{f_code}"

                    # إذا فشل Info، جرب الـ Status التقليدي
                    try:
                        # استخدام Check بدلاً من Info لسرعة الرد
                        check_url = f"https://{domain}/api/file/check?key={api_key}&file_code={f_code}"
                        res = await client.get(check_url)
                        check_data = res.json()

                        if check_data.get("status") == 200:
                            results = check_data.get("result", [])
                            if results:  # أي نتيجة ترجع للملف ده يعني السيرفر شافه
                                log.info(f"✅ DoodStream Success (File Found in Check)!")
                                return f"https://playmogo.com/e/{f_code}"
                    except:
                        continue

                except Exception as e:
                    # لا تطبع كل الأخطاء لعدم ملء اللوجات، فقط لو كان الخطأ غريباً
                    continue

            # فحص أخير بالاسم في كل محاولة "زوجية" لتقليل الضغط
            if i % 2 == 0:
                try:
                    list_url = (
                        f"https://doodapi.co/api/file/list?key={api_key}&per_page=5"
                    )
                    l_res = await client.get(list_url)
                    files = l_res.json().get("result", {}).get("files", [])
                    # داخل دالة دود ستريم (جزء البحث بالاسم)
                    # البحث بالاسم العربي كما هو مسجل في السيرفر
                    search_term = file_name.split(".")[0].strip()
                    for f in files:
                        server_title = f.get("title", "")
                        if search_term in server_title:
                            log.info(
                                f"✅ DoodStream Found by Precise Arabic Name Match: {server_title}"
                            )
                            return f"https://playmogo.com/e/{f.get('file_code')}"
                except:
                    pass
        return None


async def upload_to_streamtape(login, key, identifier, file_name):
    """الرفع لـ Streamtape مع قنص الرابط بالاسم"""
    log.info(f"📡 Streamtape: إرسال أمر سحب من الأرشيف...")
    try:
        clean_file_name = urllib.parse.quote(file_name)
        # إذا كان المعرف يبدأ بـ http (مثل رابط السبيس الجديد)، نستخدمه مباشرة كمصدر
        remote_url = (
            identifier
            if str(identifier).startswith("http")
            else f"https://archive.org/download/{identifier}/{clean_file_name}"
        )

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            # نقوم بعمل quote للاسم لضمان وصول الحروف العربية للسيرفر بشكل سليم
            safe_name = urllib.parse.quote(file_name)
            add_url = f"https://api.streamtape.com/remotedl/add?login={login}&key={key}&url={remote_url}&name={safe_name}"
            # محاولة قنص الرابط مع إعادة المحاولة في حال تذبذب البوت
            data = {}  # تعريف أولي فارغ
            for attempt in range(3):
                try:
                    res = await client.get(add_url)
                    data = res.json()
                    if data.get("status") == 200:
                        break
                except Exception as e:
                    log.warning(f"⚠️ خطأ في الاتصال: {e}")

                log.warning(f"⚠️ محاولة فاشلة ({attempt+1}/3)...")
                await asyncio.sleep(5)

            # التأكد من قبول السيرفر للأمر
            # التأكد من قبول السيرفر للأمر
            if data.get("status") == 200:
                result_data = data.get("result", {})
                remote_id = str(
                    result_data.get("id")
                )  # تحويل لنص لضمان المطابقة في القاموس لاحقاً

                # محاولة قنص فورية (في حال كان الملف مرفوعاً مسبقاً)
                if result_data.get("url") and "/v/" in result_data.get("url"):
                    file_code = result_data.get("url").split("/v/")[1].split("/")[0]
                    log.info(f"✅ Streamtape Direct Match: {file_code}")
                    return f"https://streamtape.com/e/{file_code}"

                for i in range(1, 51):  # زيادة المحاولات لـ 50 (صبر الوحش)
                    await asyncio.sleep(15)  # مسافة أمان 15 ثانية
                    log.info(
                        f"🔄 Streamtape Polling Attempt {i}/50 for ID: {remote_id}..."
                    )

                    try:
                        status_url = f"https://api.streamtape.com/remotedl/status?login={login}&key={key}&id={remote_id}"
                        s_res = await client.get(status_url)
                        s_data = s_res.json()

                        # استخراج معلومات المهمة بذكاء (دعم الرقم والنص كمفتاح)
                        tasks = s_data.get("result", {})
                        task_info = (
                            tasks.get(remote_id) or tasks.get(int(remote_id)) or {}
                        )

                        # منطق القنص الشامل للمعرف
                        file_code = task_info.get("extid") or task_info.get("fileid")
                        if (
                            not file_code
                            and task_info.get("url")
                            and "/v/" in task_info.get("url")
                        ):
                            file_code = (
                                task_info.get("url").split("/v/")[1].split("/")[0]
                            )

                        if file_code:
                            log.info(f"✅ Streamtape Captured ID: {file_code}")
                            # إعادة التسمية لضمان الدقة
                            try:
                                rename_url = f"https://api.streamtape.com/file/rename?login={login}&key={key}&file={file_code}&name={urllib.parse.quote(file_name)}"
                                await client.get(rename_url)
                            except:
                                pass
                            return f"https://streamtape.com/e/{file_code}"

                        # إذا انتهى الرفع ولم يظهر الكود، نقوم بفحص المجلد كخيار أخير في كل دورة
                        if i % 5 == 0:  # فحص المجلد كل 5 محاولات لتوفير الـ API Calls
                            list_url = f"https://api.streamtape.com/file/listfolder?login={login}&key={key}"
                            l_res = await client.get(list_url)
                            files = l_res.json().get("result", {}).get("files", [])
                            for f in files:
                                if file_name.split(".")[0] in f.get("name", ""):
                                    log.info(
                                        f"✅ Streamtape Emergency Match: {f.get('linkid')}"
                                    )
                                    return f"https://streamtape.com/e/{f.get('linkid')}"

                    except Exception as poll_err:
                        log.warning(f"⚠️ Streamtape Poll Warning: {poll_err}")
    except Exception as e:
        log.error(f"❌ Streamtape Global Error: {e}")
    return None


async def upload_to_lulustream(key, identifier, file_name):
    log.info(f"📡 LuluStream: بدء الرفع للملف: {file_name}")
    try:
        # التعديل هنا: إضافة www لتجنب خطأ الـ 301
        base_api = "https://www.lulustream.com/api"
        clean_file_name = urllib.parse.quote(file_name)
        # إذا كان المعرف يبدأ بـ http (مثل رابط السبيس الجديد)، نستخدمه مباشرة كمصدر
        remote_url = (
            identifier
            if str(identifier).startswith("http")
            else f"https://archive.org/download/{identifier}/{clean_file_name}"
        )

        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            add_url = f"{base_api}/upload/url?key={key}&url={urllib.parse.quote(remote_url, safe='')}"

            data = {}
            for attempt in range(3):
                try:
                    res = await client.get(add_url)
                    if res.status_code == 200:
                        data = res.json()
                        if data.get("status") == 200:
                            break
                    log.warning(
                        f"⚠️ LuluStream: محاولة فاشلة ({attempt+1}/3).. الرمز: {res.status_code}"
                    )
                except Exception as e:
                    log.warning(f"⚠️ LuluStream: خطأ اتصال: {e}")

                await asyncio.sleep(5)

            if data.get("status") != 200:
                log.error(f"❌ LuluStream: فشل الطلب نهائياً بعد المحاولات: {data}")
                return None

            file_code = data["result"].get("filecode")
            log.info(f"✅ تم قبول الرفع! الكود: {file_code}")

            async def hunter_fixer(target_code, target_title):
                log.info(f"🕵️ [Hunter] بدأ مراقبة الكود: {target_code}")
                for attempt in range(1, 21):
                    try:
                        async with httpx.AsyncClient(timeout=30.0) as hunter_client:
                            # الاستعلام المباشر باستخدام النطاق المحدث
                            info_url = f"{base_api}/file/info?key={key}&file_code={target_code}"
                            info_res = await hunter_client.get(info_url)

                            if info_res.status_code == 200:
                                info_data = info_res.json()
                                if info_data.get("status") == 200 and info_data.get(
                                    "result"
                                ):
                                    file_info = info_data["result"][0]
                                    if file_info.get("canplay") == 1:
                                        log.info(
                                            f"🎯 [Hunter] الملف جاهز! جاري فرض الاسم النظيف..."
                                        )
                                        edit_params = {
                                            "key": key,
                                            "file_code": target_code,
                                            "file_title": target_title,
                                        }
                                        edit_res = await hunter_client.get(
                                            f"{base_api}/file/edit", params=edit_params
                                        )
                                        if "true" in edit_res.text:
                                            log.info(
                                                f"✨ [Hunter] نجاح: تم تثبيت الاسم: {target_title}"
                                            )
                                            return
                                    else:
                                        log.info(
                                            f"⏳ [Hunter] المحاولة {attempt}: الملف جاري معالجته..."
                                        )
                    except Exception as e:
                        log.warning(f"⚠️ [Hunter] خطأ: {e}")
                    await asyncio.sleep(45)
                log.error(f"🛑 [Hunter] انتهت المحاولات.")

            asyncio.create_task(hunter_fixer(file_code, file_name))
            return f"https://lulustream.com/e/{file_code}"
    except Exception as e:
        log.error(f"❌ Fatal Error: {e}")
    return None


async def upload_to_mixdrop(file_path, email, key):
    log.info(f"💧 جاري الرفع إلى MixDrop...")
    try:
        async with httpx.AsyncClient(timeout=600.0, follow_redirects=True) as client:
            # البيانات المطلوبة حسب التوثيق
            data = {"email": email, "key": key}
            # إرسال الملف فعلياً
            with open(file_path, "rb") as f:
                files = {"file": f}
                response = await client.post(
                    "https://ul.mixdrop.ag/api", data=data, files=files
                )

                res_json = response.json()
                if res_json.get("success"):
                    # الرابط المطلوب للمشاهدة هو embedurl
                    embed_url = res_json["result"]["embedurl"]
                    # تأكد أن الرابط يبدأ بـ https
                    if not embed_url.startswith("https:"):
                        embed_url = "https:" + embed_url
                    log.info(f"✅ تم الرفع لـ MixDrop: {embed_url}")
                    return embed_url
                else:
                    log.error(f"❌ فشل MixDrop: {res_json}")
                    return None
    except Exception as e:
        log.error(f"⚠️ خطأ تقني في MixDrop: {e}")
        return None
