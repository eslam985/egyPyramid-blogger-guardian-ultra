// وظيفة فتح المودال العامة
window.openModal = function(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.style.display = 'block';
};

// وظيفة إغلاق المودال
window.closeModal = function() {
    document.getElementById('mediaModal').style.display = 'none';
};

// 1. زر إضافة عمل جديد (تنظيف وتصفير)
window.openAddModal = function() {
    const form = document.getElementById('mediaForm');
    if(form) form.reset();
    document.getElementById('media_id').value = '';
    document.getElementById('modalTitle').innerText = 'إضافة عمل جديد';
    document.getElementById('episodesSection').style.display = 'none';
    window.openModal('mediaModal');
};

// 2. زر تعديل العمل (جلب البيانات الحقيقية من السيرفر)
window.editMedia = async function(mediaId) {
    console.log("جاري جلب بيانات العمل ID:", mediaId);
    try {
        const response = await fetch(`/api/media/details/${mediaId}`);
        const data = await response.json();

        if (data.error) throw new Error(data.error);

        // ملء البيانات الأساسية
        document.getElementById('media_id').value = data.id;
        document.getElementById('title').value = data.title;
        document.getElementById('story').value = data.story;
        document.getElementById('poster_url').value = data.poster_url;
        document.getElementById('category').value = data.category;
        document.getElementById('year').value = data.year;

        // إدارة الحلقات (لو مسلسل)
        const epSection = document.getElementById('episodesSection');
        const epList = document.getElementById('episodesList');

        if (data.category === 'tv' && data.episodes && data.episodes.length > 0) {
            epSection.style.display = 'block';
            epList.innerHTML = data.episodes.map(ep => `
                <div class="ep-admin-item" style="display:flex; justify-content:space-between; align-items:center; padding:10px; border-bottom:1px solid #eee;">
                    <span>الحلقة ${ep.episode_number}</span>
                    <div>
                        <span class="badge">${ep.is_synced ? '✅ منشورة' : '⏳ انتظار'}</span>
                        <button type="button" onclick="forceSync(${ep.id})" class="btn-mini">تعديل/نشر</button>
                    </div>
                </div>
            `).join('');
        } else {
            epSection.style.display = 'none';
        }

        document.getElementById('modalTitle').innerText = 'تعديل: ' + data.title;
        window.openModal('mediaModal');

    } catch (error) {
        alert("❌ فشل جلب البيانات: " + error.message);
    }
};

// إغلاق المودال عند الضغط خارجه
window.onclick = function(event) {
    const modal = document.getElementById('mediaModal');
    if (event.target == modal) closeModal();
};