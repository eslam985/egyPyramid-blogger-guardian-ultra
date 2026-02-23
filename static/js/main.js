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

// 3. دالة تعديل العمل (التي تجلب البيانات)
window.editMedia = async function (mediaId) {
    console.log("جاري جلب بيانات العمل ID:", mediaId);
    try {
        const response = await fetch(`/api/media/details/${mediaId}`);
        const data = await response.json();

        if (data.error) throw new Error(data.error);

        // ملء البيانات في الفورم
        document.getElementById('media_id').value = data.id;
        document.getElementById('title').value = data.title;
        document.getElementById('story').value = data.story;
        document.getElementById('poster_url').value = data.poster_url;
        document.getElementById('category').value = data.category;
        document.getElementById('year').value = data.year;

        // إظهار الحلقات لو مسلسل
        const epSection = document.getElementById('episodesSection');
        if (data.category === 'tv') {
            epSection.style.display = 'block';
            const epList = document.getElementById('episodesList');
            epList.innerHTML = data.episodes.map(ep => `
                    <div class="ep-admin-item" style="display:flex; justify-content:space-between; align-items:center; padding:10px; border-bottom:1px solid var(--color-border);">
                        <span>الحلقة ${ep.episode_number}</span>
                        <div style="display:flex; gap:5px;">
                            <button type="button" onclick="manageLinks(${ep.id})" class="btn-mini" style="background:var(--color-primary); color:white; padding:4px 8px; border-radius:4px;">
                                <i class="fa fa-link"></i> السيرفرات
                            </button>
                            <button type="button" onclick="forceSync(${ep.id})" class="btn-mini" style="background:var(--color-text-muted); color:white; padding:4px 8px; border-radius:4px;">
                                <i class="fa fa-sync"></i> تصفير
                            </button>
                        </div>
                    </div>
                `).join('');
        } else {
            epSection.style.display = 'none';
        }

        document.getElementById('modalTitle').innerText = 'تعديل: ' + data.title;
        window.openModal('mediaModal');
    } catch (error) {
        alert("خطأ في جلب البيانات: " + error.message);
    }
};

// 4. دالة بلوجر (التي كانت تعطي الخطأ)
window.toggleBlogger = async function (postId) {
    console.log("تغيير حالة مقال بلوجر ID:", postId);
    if (!postId || postId === 'None') return alert("لا يوجد ID مقال!");

    try {
        const response = await fetch(`/api/blogger/revert/${postId}`, { method: 'POST' });
        const result = await response.json();
        alert(result.error ? "خطأ: " + result.error : "✅ تم تحويل المقال لمسودة");
    } catch (e) {
        alert("فشل الاتصال بالسيرفر");
    }
};

window.addNewEpisodeRow = async function () {
    const mediaId = document.getElementById('media_id').value;
    const epNum = prompt("أدخل رقم الحلقة الجديدة:");

    if (!epNum) return;

    // الحقيقة الصارمة: سنرسل طلب سريع للسيرفر لإنشاء حلقة فارغة لهذا المسلسل
    try {
        const response = await fetch(`/api/media/${mediaId}/add-episode`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: `episode_number=${epNum}`
        });
        const result = await response.json();

        if (result.status === "success") {
            // إعادة تحميل بيانات المودال لتظهر الحلقة الجديدة
            window.editMedia(mediaId);
        } else {
            alert("خطأ: " + result.error);
        }
    } catch (e) {
        alert("فشل إضافة الحلقة");
    }
};


// تأكد أن هذا السطر في أعلى الملف تماماً خارج كل الدوال
let currentEpisodeId = null;

window.manageLinks = async function (episodeId) {
    currentEpisodeId = episodeId; // حفظ الـ ID لاستخدامه عند إضافة سيرفر
    const modal = document.getElementById('linksModal');

    modal.style.display = 'block';
    modal.classList.add('show');

    try {
        const response = await fetch(`/api/episodes/${episodeId}/links`);
        const links = await response.json();

        const linksList = document.getElementById('linksList');
        // الحقيقة الصارمة: تأكد من وجود مفتاح للحذف وتعديل البيانات
        linksList.innerHTML = links.map(link => `
            <div class="ep-admin-item" style="gap:10px; margin-bottom:8px;">
                <input type="text" value="${link.server_name}" placeholder="اسم السيرفر" 
                       onchange="updateLink(${link.id}, 'server_name', this.value)" style="width:30%">
                <input type="text" value="${link.link_url}" placeholder="رابط السيرفر" 
                       onchange="updateLink(${link.id}, 'link_url', this.value)" style="flex:1">
                <button type="button" onclick="deleteLink(${link.id})" style="color:var(--color-btn-delete); border:none; background:none; cursor:pointer;">
                    <i class="fa fa-trash"></i>
                </button>
            </div>
        `).join('');
    } catch (e) {
        console.error("فشل جلب السيرفرات:", e);
    }
};

window.addNewLink = async function () {
    // إرسال طلب للسيرفر لإنشاء لينك فارغ مربوط بـ currentEpisodeId
    await fetch(`/api/episodes/${currentEpisodeId}/add-link`, { method: 'POST' });
    manageLinks(currentEpisodeId); // تحديث القائمة
};

window.updateLink = async function (linkId, field, value) {
    await fetch(`/api/links/${linkId}/update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `${field}=${encodeURIComponent(value)}`
    });
};

window.deleteLink = async function (linkId) {
    if (!confirm("هل تريد حذف هذا السيرفر؟")) return;
    await fetch(`/api/links/${linkId}/delete`, { method: 'POST' });
    manageLinks(currentEpisodeId); // إعادة تحميل القائمة
};

window.forceSync = async function (epId) {
    if (!confirm("هل أنت متأكد من تصفير مزامنة هذه الحلقة؟")) return;
    try {
        const response = await fetch(`/api/episodes/${epId}/reset-sync`, { method: 'POST' });
        const result = await response.json();
        if (result.status === "success") {
            alert("تم تصفير المزامنة بنجاح");
        } else {
            alert("خطأ: " + result.error);
        }
    } catch (e) {
        alert("فشل الاتصال بالسيرفر");
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