const SUPABASE_URL = "https://syprdvmgktmlrbdqwjif.supabase.co";
const SUPABASE_KEY = "sb_publishable_W09k2FI0QhaRv5UQKmoabA_Z_rmAkQ3";
const supabaseClient = supabase.createClient(SUPABASE_URL, SUPABASE_KEY);

// 1. التأكد من تعريف الدوال في النطاق العالمي (Global Scope)
window.openModal = function (modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'block'; // دي اللي هتظهره فوراً
        modal.classList.add('show');  // ودي عشان الأنميشن لو موجود
        console.log("المودال المفروض ظهر قدامك دلوقتي!");
    }
};

window.closeModal = function () {
    const modal = document.getElementById('mediaModal');
    if (modal) {
        modal.style.display = 'none';
        // اختياري: لو أضفت خلفية تعتيم
        const overlay = document.querySelector('.modal-overlay');
        if (overlay) overlay.style.display = 'none';
    }
};

// 2. دالة فتح إضافة عمل جديد
window.openAddModal = function () {
    console.log("فتح نافذة إضافة عمل جديد...");
    const form = document.getElementById('mediaForm');
    if (form) form.reset();
    document.getElementById('media_id').value = '';
    document.getElementById('modalTitle').innerText = 'إضافة عمل جديد';
    document.getElementById('episodesSection').style.display = 'none';
    window.openModal('mediaModal');
};
window.deleteMedia = async function (mediaId) {
    if (!confirm("⚠️ هل أنت متأكد من حذف هذا العمل نهائياً من ساب باز؟")) return;
    try {
        const response = await fetch(`/api/media/delete/${mediaId}`, { method: 'POST' });
        const result = await response.json();
        if (result.status === "deleted") {
            location.reload();
        }
    } catch (e) { alert("فشل الحذف"); }
};

document.getElementById('mediaForm').onsubmit = async function (e) {
    e.preventDefault();
    const mediaId = document.getElementById('media_id').value;
    const formData = new FormData(this);

    // استخراج القيم الإضافية للتعامل معها
    const sourceUrl = document.getElementById('source_url').value;
    const title = document.getElementById('title').value;

    const url = mediaId ? `/api/media/update/${mediaId}` : `/api/media/add`;

    try {
        const response = await fetch(url, { method: 'POST', body: formData });
        const result = await response.json();

        if (result.status === "success") {
            // الحقيقة الصارمة: إذا كان هناك رابط مصدر، نرسله فوراً لجدول المهام (الوحش)
            if (sourceUrl && !mediaId) { // فقط عند إضافة عمل جديد
                await supabaseClient
                    .from('download_tasks')
                    .insert([{
                        source_url: sourceUrl,
                        task_name: title,
                        status: 'idle',
                        status_message: 'Waiting for Beast...'
                    }]);
                console.log("🚀 تم إرسال المهمة للوحش بنجاح!");
            }

            alert("✅ تم حفظ البيانات بنجاح");
            location.reload();
        } else {
            alert("خطأ أثناء الحفظ: " + (result.error || "حاول مرة أخرى"));
        }
    } catch (e) {
        alert("فشل الاتصال بالسيرفر");
    }
};
// 3. دالة تعديل العمل (التي تجلب البيانات)
window.editMedia = async function (mediaId) {
    try {
        const response = await fetch(`/api/media/details/${mediaId}`);
        const data = await response.json();

        // ملء كافة الحقول (القديمة والجديدة)
        document.getElementById('media_id').value = data.id;
        document.getElementById('title').value = data.title;
        document.getElementById('tmdb_id').value = data.tmdb_id || '';
        document.getElementById('year').value = data.year || '';
        document.getElementById('rating').value = data.rating || '';
        document.getElementById('labels').value = data.labels || '';
        document.getElementById('runtime').value = data.runtime || '';
        document.getElementById('poster_url').value = data.poster_url || '';
        document.getElementById('story').value = data.story || '';
        document.getElementById('category').value = data.category;
        // أضف هذا السطر داخل window.editMedia
        document.getElementById('duration_iso').value = data.duration_iso || '';
        const epSection = document.getElementById('episodesSection');
        if (data.category === 'tv') {
            epSection.style.display = 'block';
            const epList = document.getElementById('episodesList');
            // الحقيقة الصارمة: دمجنا الـ identifier مع أزرار التحكم في مكان واحد
            epList.innerHTML = data.episodes.map(ep => `
    <div class="ep-admin-item" style="display:flex; justify-content:space-between; align-items:center; padding:10px; border-bottom:1px solid var(--color-border);">
        <span>حلقة ${ep.episode_number} <small style="color:gray;">[${ep.identifier || 'بدون ID'}]</small></span>
        <div style="display:flex; gap:5px;">
            <button type="button" onclick="manageLinks(${ep.id})" class="btn-mini" style="background:var(--color-primary); color:white; padding:4px 8px; border-radius:4px;">
                <i class="fa fa-link"></i> السيرفرات
            </button>
            <button type="button" onclick="syncToBlogger(${ep.id})" class="btn-mini" 
                    style="background:${ep.is_synced ? '#10b981' : '#f59e0b'}; color:white; padding:4px 8px; border-radius:4px;">
                <i class="fa fa-share-square"></i> ${ep.is_synced ? 'منشور' : 'نشر'}
            </button>
            <button type="button" onclick="deleteEpisode(${ep.id})" class="btn-mini" style="background:#ef4444; color:white; padding:4px 8px; border-radius:4px;">
                <i class="fa fa-trash"></i> حذف
            </button>
        </div>
    </div>
`).join('');
        } else {
            epSection.style.display = 'none';
        }

        document.getElementById('modalTitle').innerText = 'تعديل: ' + data.title;
        window.openModal('mediaModal');
    } catch (error) { alert("خطأ في جلب البيانات: " + error.message); }
};

// 4. دالة بلوجر (التي كانت تعطي الخطأ)
// أضفنا event هنا لضمان استلام الحدث بشكل صحيح
window.toggleBlogger = async function (postId, event) {
    if (!postId || postId === 'None' || postId === '') return alert("⚠️ لا يوجد ID لهذا المقال!");

    const btn = event.currentTarget;
    const originalIcon = btn.innerHTML;
    btn.innerHTML = '<i class="fa fa-spinner fa-spin"></i>';

    try {
        // التغيير الجوهري هنا: نستخدم مسار toggle وليس revert
        const response = await fetch(`/api/blogger/toggle/${postId}`, { method: 'POST' });
        const result = await response.json();

        if (result.status === "success") {
            const isLive = result.new_status === 'live';
            alert(`✅ الحالة الجديدة: ${isLive ? 'منشور (Live)' : 'مسودة (Draft)'}`);

            // تحديث الشكل بصرياً فوراً
            btn.classList.toggle('is-live', isLive);
            btn.classList.toggle('is-draft', !isLive);
        } else {
            alert("❌ خطأ: " + result.error);
        }
    } catch (e) {
        alert("❌ فشل الاتصال بالسيرفر");
    } finally {
        btn.innerHTML = originalIcon;
    }
};

window.addNewEpisodeRow = async function () {
    const mediaId = document.getElementById('media_id').value;
    const epNum = prompt("أدخل رقم الحلقة الجديدة:");

    if (!epNum) return;

    try {
        // 1. فحص هل الحلقة موجودة مسبقاً في القائمة المعروضة (لتوفير طلب سيرفر)
        const epList = document.getElementById('episodesList');
        if (epList.innerText.includes(`حلقة ${epNum} `)) {
            return alert(`⚠️ الحلقة رقم ${epNum} موجودة فعلاً في هذا المسلسل!`);
        }

        // 2. إرسال طلب الإضافة
        const response = await fetch(`/api/media/${mediaId}/add-episode`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: `episode_number=${epNum}`
        });

        const result = await response.json();

        if (result.status === "success") {
            alert("✅ تمت إضافة الحلقة بنجاح");
            window.editMedia(mediaId); // تحديث القائمة فوراً
        } else {
            // لو السيرفر رفض (مثلاً الحلقة موجودة في ساب باز فعلاً)
            alert("❌ خطأ: " + (result.error || "فشل إضافة الحلقة"));
        }
    } catch (e) {
        alert("فشل إضافة الحلقة، ربما رقم الحلقة مكرر في ساب باز.");
    }
};


// تأكد أن هذا السطر في أعلى الملف تماماً خارج كل الدوال
let currentEpisodeId = null;

window.manageLinks = async function (episodeId) {
    if (!episodeId) return alert("خطأ: لم يتم العثور على ID الحلقة");

    currentEpisodeId = episodeId; // تأكد أنك عرفت let currentEpisodeId في أعلى الملف
    const modal = document.getElementById('linksModal');

    modal.classList.add('show');
    modal.style.display = 'block'; // تأكيد العرض
    try {
        const response = await fetch(`/api/episodes/${episodeId}/links`);
        const links = await response.json();

        // التأكد أن البيانات مصفوفة لتجنب خطأ .map
        if (!Array.isArray(links)) throw new Error("بيانات غير صالحة");

        const linksList = document.getElementById('linksList');
        linksList.innerHTML = links.map(link => `
            <div class="link-row">
                <input type="text" value="${link.server_name || ''}" placeholder="اسم السيرفر" 
                       onchange="updateLink(${link.id}, 'server_name', this.value)" style="width:30%">
                <input type="text" value="${link.url || ''}" placeholder="الرابط" 
                       onchange="updateLink(${link.id}, 'url', this.value)" style="flex:1">
                <button type="button" onclick="deleteLink(${link.id})" style="color:red; background:none; border:none; cursor:pointer;">
                    <i class="fa fa-trash"></i>
                </button>
            </div>
        `).join('');
    } catch (e) {
        console.error("خطأ:", e);
        document.getElementById('linksList').innerHTML = "لا توجد سيرفرات مضافة حالياً.";
    }
};


window.updateLink = async function (linkId, field, value) {
    try {
        const response = await fetch(`/api/links/${linkId}/update`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: `${field}=${encodeURIComponent(value)}`
        });
        const result = await response.json();
        if (result.status === "success") {
            console.log(`✅ تم تحديث ${field} للرابط رقم ${linkId}`);
        } else {
            console.error("فشل التحديث:", result.error);
        }
    } catch (e) {
        console.error("فشل الاتصال بالسيرفر:", e);
    }
};

window.addNewLink = async function () {
    // إرسال طلب للسيرفر لإنشاء لينك فارغ مربوط بـ currentEpisodeId
    await fetch(`/api/episodes/${currentEpisodeId}/add-link`, { method: 'POST' });
    manageLinks(currentEpisodeId); // تحديث القائمة
};





// دالة المزامنة مع بلوجر (التي كانت ناقصة وتسبب الخطأ)
window.syncToBlogger = async function (epId) {
    // إشعار مستخدم بسيط قبل البدء
    console.log("جاري بدء عملية المزامنة للحلقة:", epId);

    try {
        // الحقيقة الصارمة: سنرسل الطلب لمسار المزامنة في الباك اند
        // ملاحظة: تأكد من وجود هذا المسار في app.py لاحقاً
        const response = await fetch(`/api/episodes/${epId}/sync`, {
            method: 'POST'
        });

        const result = await response.json();

        if (result.status === "success") {
            alert("✅ تم نشر الحلقة وتحديث مقال بلوجر بنجاح!");
            // إعادة جلب البيانات لتحديث لون الزر من برتقالي لأخضر
            const mediaId = document.getElementById('media_id').value;
            window.editMedia(mediaId);
        } else {
            alert("❌ خطأ في المزامنة: " + (result.error || "فشل غير معروف"));
        }
    } catch (e) {
        console.error("Connection Error:", e);
        alert("فشل الاتصال بالسيرفر، تأكد أن تطبيق FastAPI يعمل.");
    }
};

window.triggerPublisher = function () {
    const btn = document.getElementById('publishBtn');
    if (!btn) return;

    const originalText = btn.innerHTML;
    btn.innerHTML = "⏳ جاري البدء...";
    btn.disabled = true;

    fetch('/publisher/run', { method: 'POST' })
        .then(response => {
            if (response.status === 401) throw new Error("غير مصرح لك");
            return response.json();
        })
        .then(data => alert("✅ " + data.message))
        .catch(error => alert("❌ خطأ: " + error.message))
        .finally(() => {
            btn.innerHTML = originalText;
            btn.disabled = false;
        });
};



// البحث عن هذا الجزء وتعديله
document.getElementById('downloadForm').addEventListener('submit', async function (e) {
    e.preventDefault();



    // 1. استخراج البيانات من الفورم
    const taskUrl = document.getElementById('taskUrl').value;
    const taskName = document.getElementById('taskName').value;
    const submitBtn = this.querySelector('button');

    try {
        // تعطيل الزرار لمنع التكرار
        submitBtn.disabled = true;
        submitBtn.innerText = '🚀 جاري إرسال الأمر للوحش...';

        // 2. حقن البيانات مباشرة في سوبابيز (الجدول الجديد)
        const { data, error } = await supabaseClient
            .from('download_tasks')
            .insert([
                {
                    source_url: taskUrl,
                    task_name: taskName,
                    status: 'idle',
                    status_message: 'Waiting for Beast...'
                }
            ]);

        if (error) throw error;

        // 3. النجاح: إخفاء المودال وإظهار حاوية التقدم
        document.getElementById('downloadTaskModal').style.display = 'none';
        this.reset();

        const container = document.getElementById('progress-container');
        if (container) container.style.display = 'block';

        console.log('✅ تم إرسال المهمة بنجاح لجداول المهام');

    } catch (error) {
        console.error('❌ فشل الإرسال:', error);
        alert('حدث خطأ أثناء الاتصال بسوبابيز: ' + error.message);
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerText = 'ابدأ السحب والمعالجة';
    }
});


async function updateDownloadProgress() {
    const container = document.getElementById('progress-container');
    if (!container) return;

    try {
        // الحقيقة الصارمة: نسحب البيانات من سوبابيز مباشرة وليس من API
        const { data: activeTasks, error } = await supabaseClient
            .from('download_tasks')
            .select('*')
            .order('created_at', { ascending: false });

        if (error) throw error;

        if (!activeTasks || activeTasks.length === 0) {
            container.style.display = 'none';
            return;
        }

        container.style.display = 'block';

        // 2. بناء العنوان مع العدد الحقيقي للمهام النشطة
        let htmlContent = `<h5 style="color: #28a745; margin-bottom: 12px; font-size: 0.95rem; border-bottom: 1px solid #333; padding-bottom: 8px;">⏳ معالجة نشطة (${activeTasks.length})</h5>`;

        activeTasks.forEach(task => {
            const percent = task.progress_percent || 0;
            // تغيير لون الشريط بناءً على المرحلة
            // استبدل تحديد barClass بهذا المنطق المتطور:
            let barClass = "bg-success";
            let textClass = "text-white";

            if (task.status_message.includes("تليجرام")) barClass = "bg-info";
            if (task.status_message.includes("VK")) barClass = "bg-primary";
            if (task.status_message.includes("انتظار")) barClass = "bg-secondary progress-bar-striped";
            // إذا وجد خطأ، اقلب الألوان للأحمر فوراً
            if (task.status_message.includes("❌") || task.status_message.includes("خطأ") || task.download_speed === 'Error') {
                barClass = "bg-danger";
                textClass = "text-danger fw-black";
            }

            if (task.download_speed === 'Done') barClass = "bg-warning";

            htmlContent += `
                    <div class="progress-item mb-2" style="border-bottom: 1px solid #222; padding-bottom: 8px;">
                        <div class="d-flex justify-content-between mb-1" style="font-size: 11px;">
							<small class="${textClass} fw-bold">${task.status_message}</small>
                            <small class="text-warning">${task.download_speed || '--'}</small>
                        </div>
                        <div class="progress" style="height: 6px; background: #111; border-radius: 10px;">
                            <div class="progress-bar progress-bar-striped ${task.download_speed !== 'Done' ? 'progress-bar-animated' : ''} ${barClass}" 
                                 role="progressbar" 
                                 style="width: ${percent}%; transition: width 0.6s ease;">
                            </div>
                        </div>
                        <div class="d-flex justify-content-between mt-1" style="font-size: 9px; opacity: 0.7;">
                            <span class="text-light">${percent}%</span>
                            <span class="text-muted">ID: ${task.id ? (task.id.toString().substring(0, 8)) : '---'}</span>
                        </div>
                    </div>
                `;
        });
        if (!container) return;
        container.innerHTML = htmlContent;
    } catch (err) {
        console.error("خطأ في جلب التحديثات:", err);
    }
}
// تشغيل الدالة كل 2 ثانية
setInterval(updateDownloadProgress, 3000);
window.deleteLink = async function (linkId) {
    if (!confirm("هل تريد حذف هذا السيرفر؟")) return;
    await fetch(`/api/links/${linkId}/delete`, { method: 'POST' });
    manageLinks(currentEpisodeId); // إعادة تحميل القائمة
};


window.closeLinksModal = function () {
    const modal = document.getElementById('linksModal');
    modal.style.display = 'none';
    modal.classList.remove('show');
};


window.deleteEpisode = async function (epId) {
    if (!confirm("⚠️ هل أنت متأكد من حذف هذه الحلقة نهائياً بكل سيرفراتها؟")) return;
    try {
        const response = await fetch(`/api/episodes/${epId}/delete`, { method: 'POST' });
        const result = await response.json();
        if (result.status === "success") {
            alert("✅ تم حذف الحلقة بنجاح");
            const mediaId = document.getElementById('media_id').value;
            window.editMedia(mediaId); // تحديث القائمة لإخفاء الحلقة المحذوفة
        } else {
            alert("❌ خطأ: " + result.error);
        }
    } catch (e) {
        alert("❌ فشل الاتصال بالسيرفر");
    }
};


// منطق تبديل الوضع الداكن/الفاتح
const themeToggle = document.getElementById('theme-toggle');
const body = document.body;

// التعديل الصحيح
themeToggle.addEventListener('click', () => {
    const isDark = document.documentElement.classList.toggle('dark-mode');
    localStorage.setItem('theme', isDark ? 'dark' : 'light');
});

// ولضمان التنفيذ عند تحميل الصفحة:
if (localStorage.getItem('theme') === 'dark') {
    document.documentElement.classList.add('dark-mode');
}