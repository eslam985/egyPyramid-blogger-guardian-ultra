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
                        <button type="button" onclick="forceSync(${ep.id})" class="btn-mini" style="background:#6b7280; color:white; padding:4px 8px; border-radius:4px;">
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
	} catch (error) { alert("خطأ في جلب البيانات: " + error.message); }
};

// 4. دالة بلوجر (التي كانت تعطي الخطأ)
window.toggleBlogger = async function (postId) {
	if (!postId || postId === 'None' || postId === '') return alert("⚠️ لا يوجد ID لهذا المقال (ربما لم يُنشر بعد)!");

	// تغيير شكل الأيقونة مؤقتاً للإشارة للجري
	const btn = event.currentTarget;
	const originalIcon = btn.innerHTML;
	btn.innerHTML = '<i class="fa fa-spinner fa-spin"></i>';

	try {
		// نرسل الطلب لمسار الـ toggle الجديد
		const response = await fetch(`/api/blogger/toggle/${postId}`, { method: 'POST' });
		const result = await response.json();

		if (result.status === "success") {
			alert(`✅ الحالة الجديدة: ${result.new_status === 'live' ? 'منشور (Live)' : 'مسودة (Draft)'}`);
			// يمكنك هنا تغيير لون الزر برمجياً إذا أردت
			btn.style.color = result.new_status === 'live' ? '#f57d00' : '#6b7280';
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

	// الحقيقة الصارمة: سنرسل طلب سريع للسيرفر لإنشاء حلقة فارغة لهذا المسلسل
	try {
		const response = await fetch(`/api/media/${mediaId}/add-episode`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
			body: `episode_number=${epNum}`
		});
		const result = await response.json();

		if (result.status === "success") {
			// تبديل الكلاسات برمجياً
			if (result.new_status === 'live') {
				btn.classList.remove('is-draft');
				btn.classList.add('is-live');
			} else {
				btn.classList.remove('is-live');
				btn.classList.add('is-draft');
			}
			console.log(`✅ تم تغيير الحالة إلى: ${result.new_status}`);
		}
	} catch (e) {
		alert("فشل إضافة الحلقة");
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

document.getElementById('mediaForm').onsubmit = async function (e) {
	e.preventDefault();
	const mediaId = document.getElementById('media_id').value;
	const formData = new FormData(this);

	// تحديد المسار: إضافة أم تعديل
	const url = mediaId ? `/api/media/update/${mediaId}` : `/api/media/add`;

	try {
		const response = await fetch(url, { method: 'POST', body: formData });
		const result = await response.json();
		if (result.status === "success") {
			location.reload(); // تحديث الصفحة لرؤية التغييرات
		} else {
			alert("خطأ أثناء الحفظ: " + (result.error || "حاول مرة أخرى"));
		}
	} catch (e) {
		alert("فشل الاتصال بالسيرفر");
	}
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