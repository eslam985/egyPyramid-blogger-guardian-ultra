// static/js/main.js

// 1. وظيفة البحث المتقدم (بدون عمل Refresh لو أردت تطويرها)
function searchMedia() {
    console.log("Searching...");
}

// 2. وظيفة فتح نافذة التعديل وجلب بيانات العمل
// 2. وظيفة فتح نافذة التعديل وجلب بيانات العمل
// استبدل دالة editMedia القديمة بهذا الكود المطور
async function editMedia(mediaId) {
    console.log("جاري جلب تفاصيل العمل ID:", mediaId);

    try {
        const response = await fetch(`/api/media/details/${mediaId}`);
        const data = await response.json();

        if (data.error) throw new Error(data.error);

        // 1. ملء بيانات الميديا الأساسية
        document.getElementById('media_id').value = data.id;
        document.getElementById('title').value = data.title;
        document.getElementById('story').value = data.story;
        document.getElementById('poster_url').value = data.poster_url;
        document.getElementById('category').value = data.category;
        document.getElementById('year').value = data.year;

        // 2. إدارة قسم الحلقات
        const epSection = document.getElementById('episodesSection');
        const epList = document.getElementById('episodesList');

        if (data.category === 'tv' && data.episodes.length > 0) {
            epSection.style.display = 'block';
            epList.innerHTML = data.episodes.map(ep => `
                <div class="ep-admin-item">
                    <span>الحلقة ${ep.episode_number}</span>
                    <div class="ep-btns">
                        <span class="status-badge ${ep.is_synced ? 'synced' : 'pending'}">
                            ${ep.is_synced ? 'منشورة' : 'انتظار'}
                        </span>
                        <button type="button" onclick="forceSync(${ep.id})" class="btn-mini-sync">
                            <i class="fa fa-refresh"></i> إعادة نشر
                        </button>
                    </div>
                </div>
            `).join('');
        } else {
            epSection.style.display = 'none';
        }

        document.getElementById('modalTitle').innerText = 'تعديل العمل والحلقات';
        document.getElementById('mediaModal').style.display = 'block';

    } catch (error) {
        alert("❌ فشل جلب البيانات: " + error.message);
    }
}


// 1. وظيفة الحذف الاحترافية
async function deleteMedia(mediaId) {
    if (!confirm("⚠️ هل أنت متأكد من حذف هذا العمل وجميع حلقاته نهائياً؟")) return;

    try {
        const response = await fetch(`/api/media/delete/${mediaId}`, {
            method: 'POST',
        });
        const result = await response.json();

        if (result.status === 'deleted') {
            // حذف الكارت من الواجهة فوراً بحركة ناعمة
            const card = document.getElementById(`media-${mediaId}`);
            card.style.opacity = '0';
            card.style.transform = 'scale(0.9)';
            setTimeout(() => card.remove(), 300);
        } else {
            alert("❌ حدث خطأ أثناء الحذف");
        }
    } catch (error) {
        console.error("Error:", error);
        alert("❌ تعذر الاتصال بالسيرفر");
    }
}

// 2. وظيفة التبديل في بلوجر (Live/Draft)
async function toggleBlogger(postId) {
    if (!postId || postId === 'None') {
        alert("🚫 لا يوجد ID مقال مرتبط بهذا العمل");
        return;
    }

    // تغيير شكل الزر مؤقتاً للإشارة إلى التحميل
    console.log("جاري تغيير حالة المقال في بلوجر...");

    try {
        const response = await fetch(`/api/blogger/revert/${postId}`, {
            method: 'POST',
        });
        const result = await response.json();

        if (!result.error) {
            alert("✅ تمت العملية بنجاح (تم تحويل المقال لمسودة)");
        } else {
            alert("❌ خطأ من بلوجر: " + result.error);
        }
    } catch (error) {
        alert("❌ فشل الاتصال بمحرك بلوجر");
    }
}

// 3. وظيفة فتح نافذة الإضافة (سيتم ربطها بالفورم لاحقاً)
// استبدل كل دوال فتح وإغلاق المودال بهذا الجزء الموحد
window.openModal = function (modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'block';
    }
};

window.closeModal = function () {
    const modal = document.getElementById('mediaModal');
    if (modal) {
        modal.style.display = 'none';
        document.getElementById('mediaForm').reset(); // تنظيف الفورم عند الإغلاق
    }
};

window.openAddModal = function () {
    document.getElementById('mediaForm').reset();
    document.getElementById('media_id').value = '';
    document.getElementById('modalTitle').innerText = 'إضافة عمل جديد';
    document.getElementById('episodesSection').style.display = 'none'; // إخفاء قسم الحلقات عند الإضافة
    window.openModal('mediaModal');
};


// إرسال البيانات (Submit Logic)
document.getElementById('mediaForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const formData = new FormData(e.target);
    const mediaId = formData.get('media_id');

    // تحديد الرابط بناءً على هل هو تعديل أم إضافة
    const url = mediaId ? `/api/media/update/${mediaId}` : '/api/media/add';

    try {
        const response = await fetch(url, {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (result.status === 'success') {
            alert("✅ تم حفظ البيانات بنجاح!");
            location.reload(); // تحديث الصفحة لرؤية التغييرات
        } else {
            alert("❌ فشل الحفظ: " + (result.error || "خطأ مجهول"));
        }
    } catch (error) {
        alert("❌ تعذر الاتصال بالسيرفر");
    }
});

async function forceSync(episodeId) {
    const res = await fetch(`/api/episodes/${episodeId}/reset-sync`, { method: 'POST' });
    if (res.ok) {
        alert('تم تصفير حالة المزامنة. سيقوم سكريبت النشر بتحديث بلوجر في الدورة القادمة.');
    }
}