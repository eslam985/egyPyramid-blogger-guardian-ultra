// 1. التأكد من تعريف الدوال في النطاق العالمي (Global Scope)
window.openModal = function(modalId) {
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
        modal.classList.remove('show');
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
                <div style="display:flex; justify-content:space-between; padding:5px; border-bottom:1px solid #444;">
                    <span>الحلقة ${ep.episode_number}</span>
                    <button type="button" onclick="forceSync(${ep.id})">تصفير المزامنة</button>
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