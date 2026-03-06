<template>
    <div class="modal-overlay" v-if="mediaId" @click.self="$emit('close')">
        <div class="modal-content">
            <header>
                <h3>تعديل: {{ mediaData.title }}</h3>
                <button @click="$emit('close')">إغلاق</button>
            </header>

            <form @submit.prevent="saveMedia">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                    <div class="form-group">
                        <label>عنوان العمل</label>
                        <input v-model="mediaData.title" required>
                    </div>
                    <div class="form-group">
                        <label>TMDB ID</label>
                        <input v-model="mediaData.tmdb_id">
                    </div>
                    <div class="form-group">
                        <label>النوع</label>
                        <select v-model="mediaData.category">
                            <option value="tv">مسلسل</option>
                            <option value="movie">فيلم</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>سنة الإنتاج</label>
                        <input v-model="mediaData.year">
                    </div>
                    <div class="form-group">
                        <label>التقييم</label>
                        <input v-model="mediaData.rating">
                    </div>
                    <div class="form-group">
                        <label>مدة العرض</label>
                        <input v-model="mediaData.runtime">
                    </div>
                </div>

                <div class="form-group">
                    <label>رابط البوستر</label>
                    <input v-model="mediaData.poster_url">
                </div>
                <div class="form-group">
                    <label>قصة العمل</label>
                    <textarea v-model="mediaData.story"></textarea>
                </div>
                <div id="episodesSection" style="display: block;">
                    <div class="episodes-header">
                        <h3><i class="fa fa-list-ol"></i> إدارة الحلقات</h3>
                        <button type="button" @click="addNewEpisodeRow" class="btn-add-episode">
                            <i class="fa fa-plus-circle"></i> إضافة حلقة
                        </button>
                    </div>

                    <div class="episodes-admin-list">
                        <div v-for="ep in mediaData.episodes" :key="ep.id" class="ep-admin-item"
                            style="display:flex; justify-content:space-between; align-items:center; padding:10px; border-bottom:1px solid #ccc;">

                            <span>حلقة {{ ep.episode_number }}
                                <small style="color:gray;">[{{ ep.identifier }}]</small>
                            </span>

                            <div style="display:flex; gap:5px;">
                                <button type="button" @click="manageLinks(ep.id)" class="btn-mini"
                                    style="background:var(--color-primary); color:white; padding:4px 8px; border-radius:4px; border:none; cursor:pointer;">
                                    <i class="fa fa-link"></i> السيرفرات
                                </button>
                                <button type="button" @click="syncToBlogger(ep.id)" class="btn-mini"
                                    style="background:#10b981; color:white; padding:4px 8px; border-radius:4px; border:none; cursor:pointer;">
                                    <i class="fa fa-share-square"></i> منشور
                                </button>
                                <button type="button" @click="deleteEpisode(ep.id)" class="btn-mini"
                                    style="background:#ef4444; color:white; padding:4px 8px; border-radius:4px; border:none; cursor:pointer;">
                                    <i class="fa fa-trash"></i> حذف
                                </button>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="modal-footer">
                    <button type="submit" class="btn-primary">حفظ البيانات</button>
                </div>
            </form>
        </div>
        <div v-if="showLinksModal" class="modal-overlay-sub">

            <div class="modal-content-sub">
                <div class="modal-header" style="display:flex; justify-content:space-between; align-items:center;">
                    <h3>إدارة سيرفرات الحلقة: {{ selectedEpisodeId }}</h3>
                    <button @click="showLinksModal = false"
                        style="background:none; border:none; cursor:pointer; font-size:20px;">×</button>
                </div>

                <div id="linksList" class="episodes-admin-list" style="margin-bottom:15px; min-height:100px;">
                    <div v-for="link in links" :key="link.id" class="link-row"
                        style="display:flex; gap:5px; margin-bottom:5px;">
                        <input type="text" v-model="link.server_name" @blur="updateLink(link)" placeholder="اسم السيرفر"
                            style="width:30%">
                        <input type="text" v-model="link.url" @blur="updateLink(link)" placeholder="الرابط"
                            style="flex:1">
                        <button type="button" @click="deleteLink(link.id)"
                            style="color:red; background:none; border:none; cursor:pointer;">
                            <i class="fa fa-trash"></i>
                        </button>
                    </div>
                </div>

                <button type="button" @click="addNewLink(selectedEpisodeId)" class="btn-add-episode"
                    style="width:100%; justify-content:center;">
                    <i class="fa fa-plus-circle"></i> إضافة سيرفر جديد
                </button>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue';
import api from '../services/api';

const props = defineProps(['mediaId']);
const emit = defineEmits(['close']);
const mediaData = ref({});
const links = ref([]); // <--- أضف هذا السطر هنا
const showLinksModal = ref(false); // للتحكم في ظهور نافذة السيرفرات
const selectedEpisodeId = ref(null); // لتخزين رقم الحلقة المختارة
// في EditModal.vue
const loadMedia = async () => {
    if (!props.mediaId) return; // حماية
    try {
        const response = await api.get(`/media/details/${props.mediaId}`);
        // تأكد من هيكل البيانات، غالباً تحتاج response.data.data
        mediaData.value = response.data.data || response.data;
    } catch (e) {
        console.error("خطأ:", e);
    }
};

// تحديث الرابط (بدلاً من onchange استخدمنا blur لتقليل طلبات السيرفر)
const updateLink = async (link) => {
    const params = new URLSearchParams();
    params.append('server_name', link.server_name);
    params.append('url', link.url);

    try {
        await api.post(`/links/${link.id}/update`, params);
        console.log("تم الحفظ");
    } catch (e) {
        alert("فشل الحفظ");
    }
};

const deleteLink = async (linkId) => {
    if (!confirm("حذف السيرفر نهائياً؟")) return;

    try {
        // 1. إرسال أمر الحذف للسيرفر
        await api.post(`/links/${linkId}/delete`);

        // 2. التحديث الفوري للواجهة (الحقيقة الصارمة: نحذف العنصر من المصفوفة)
        links.value = links.value.filter(link => link.id !== linkId);

        console.log("تم الحذف بنجاح من الواجهة وقاعدة البيانات");
    } catch (e) {
        alert("فشل الحذف، راجع الاتصال");
        // اختياري: يمكنك إعادة تحميل البيانات إذا فشل الحذف
        loadMedia();
    }
};

const addNewLink = async (epId) => {
    try {
        // 1. إضافة السيرفر الجديد في السيرفر
        await api.post(`/episodes/${epId}/add-link`);

        // 2. تحديث قائمة الروابط مباشرة بدلاً من إعادة تحميل العمل بالكامل
        // هذا أسرع وأضمن لتجنب تضارب الـ IDs
        const response = await api.get(`/episodes/${epId}/links`);
        links.value = response.data || []; // بما أن سيرفرك يرجع Array مباشرة

        console.log("تم تحديث السيرفرات بنجاح");
    } catch (e) {
        alert("فشل إضافة الرابط");
    }
};

const deleteEpisode = async (epId) => {
    if (!confirm("هل أنت متأكد؟")) return;
    await api.post(`/episodes/${epId}/delete`);
    loadMedia();
};

onMounted(loadMedia);
watch(() => props.mediaId, loadMedia);
const syncToBlogger = async (epId) => {
    console.log("جاري بدء عملية المزامنة للحلقة:", epId);
    try {
        const response = await api.post(`/episodes/${epId}/sync`);
        const result = response.data;

        if (result.status === "success") {
            alert("✅ تم نشر الحلقة وتحديث مقال بلوجر بنجاح!");
            loadMedia(); // إعادة جلب البيانات لتحديث الحالة
        } else {
            alert("❌ خطأ في المزامنة: " + (result.error || "فشل غير معروف"));
        }
    } catch (e) {
        console.error("Connection Error:", e);
        alert("فشل الاتصال بالسيرفر، تأكد أن تطبيق FastAPI يعمل.");
    }
};
const addNewEpisodeRow = async () => {
    const epNum = prompt("أدخل رقم الحلقة الجديدة:");
    if (!epNum) return;

    try {
        await api.post(`/media/${props.mediaId}/add-episode`, new URLSearchParams({
            episode_number: epNum,
            identifier: `m${props.mediaId}_ep${epNum}`
        }));
        alert("✅ تمت إضافة الحلقة");
        loadMedia();
    } catch (e) {
        alert("فشل إضافة الحلقة، ربما الرقم مكرر.");
    }
};
// [داخل EditModal.vue - script setup]

const manageLinks = async (episodeId) => {
    selectedEpisodeId.value = episodeId;
    showLinksModal.value = true;

    try {
        const response = await api.get(`/episodes/${episodeId}/links`);

        // أضف هذا السطر لمراقبة البيانات في الكونسول
        console.log("البيانات القادمة من السيرفر:", response.data);

        // إذا كانت البيانات داخل كائن، قد تحتاج response.data.links أو response.data فقط
        links.value = response.data.links || response.data || [];

    } catch (e) {
        console.error("فشل جلب السيرفرات", e);
        links.value = [];
    }
};
const saveMedia = async () => {
    try {
        // تحويل البيانات إلى تنسيق Form Data
        const params = new URLSearchParams();
        params.append('title', mediaData.value.title || '');
        params.append('story', mediaData.value.story || '');
        params.append('category', mediaData.value.category || '');
        params.append('poster_url', mediaData.value.poster_url || '');
        params.append('tmdb_id', mediaData.value.tmdb_id || '');
        params.append('year', mediaData.value.year || '');
        params.append('rating', mediaData.value.rating || '');
        params.append('runtime', mediaData.value.runtime || '');

        await api.post(`/media/update/${props.mediaId}`, params);

        alert("✅ تم الحفظ بنجاح");
        emit('close');
    } catch (e) {
        console.error("خطأ:", e.response?.data);
        alert("فشل الحفظ: راجع الكونسول");
    }
};
</script>

<style scoped>
/* التنسيق هنا يضمن أن كل حلقة تعرض سيرفراتها بوضوح */
.ep-row {
    border: 1px solid #eee;
    padding: 10px;
    margin-bottom: 10px;
}

.link-item {
    display: flex;
    gap: 5px;
    margin-top: 5px;
}

.btn-danger {
    background: #ff4d4f;
    color: white;
    border: none;
    padding: 5px;
}

.modal-overlay-sub {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.7);
    display: flex;
    justify-content: center;
    align-items: center;
    z-index: 9999;
    /* لضمان ظهوره فوق كل شيء */
}

.modal-content-sub {
    background: var(--color-surface);
    padding: 20px;
    border-radius: 8px;
    width: 90%;
    max-width: 500px;
    max-height: 80vh;
    overflow-y: auto;
}
</style>