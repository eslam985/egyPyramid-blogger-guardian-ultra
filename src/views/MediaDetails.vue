<template>
    <button class="back-btn" @click="$router.push('/')">
        <i class="fa fa-arrow-right"></i> العودة للرئيسية
    </button>
    <div class="media-details-container my-card" v-if="mediaData.title">
        <div class="details-header my-card">
            <div class="poster-side">
                <img :src="mediaData.poster_url" :alt="mediaData.title">
            </div>
            <div class="info-side">
                <div class="edit-form-container">
                    <div class="form-grid">
                        <div class="form-group">
                            <label>عنوان العمل</label>
                            <input v-model="mediaData.title" class="form-control">
                        </div>
                        <div class="form-group">
                            <label>TMDB ID</label>
                            <input v-model="mediaData.tmdb_id" class="form-control">
                        </div>
                        <div class="form-group">
                            <label>سنة الإنتاج (year)</label>
                            <input v-model="mediaData.year" class="form-control">
                        </div>
                        <div class="form-group">
                            <label>المدة (duration_iso)</label>
                            <input v-model="mediaData.duration_iso" class="form-control" placeholder="ISO 8601">
                        </div>
                        <div class="form-group">
                            <label>التصنيفات (labels)</label>
                            <input v-model="mediaData.labels" class="form-control" placeholder="مثال: أكشن, دراما">
                        </div>
                        <div class="form-group">
                            <label>حالة البلوجر (blogger_status)</label>
                            <select v-model="mediaData.blogger_status" class="form-control">
                                <option value="draft">مسودة</option>
                                <option value="published">منشور</option>
                            </select>
                        </div>

                        <div class="form-group">
                            <label>النوع (category)</label>
                            <select v-model="mediaData.category" class="form-control">
                                <option value="movie">فيلم</option>
                                <option value="tv">مسلسل</option>
                            </select>
                        </div>

                        <div class="form-group">
                            <label>التقييم (rating)</label>
                            <input v-model="mediaData.rating" class="form-control" placeholder="مثال: 8.5">
                        </div>

                        <div class="form-group">
                            <label>وقت العرض (runtime)</label>
                            <input v-model="mediaData.runtime" class="form-control" placeholder="مثال: 120 دقيقة">
                        </div>


                    </div>

                    <div class="form-group">
                        <label>رابط البوستر</label>
                        <input v-model="mediaData.poster_url" class="form-control">
                    </div>

                    <div class="form-group">
                        <label>قصة العمل</label>
                        <textarea v-model="mediaData.story" class="form-control textarea my-card text-dark "></textarea>
                    </div>

                    <button @click="saveMediaDetails" class="btn-primary" :disabled="isSaving">
                        {{ isSaving ? 'جاري الحفظ...' : 'حفظ التعديلات' }}
                    </button>
                </div>
            </div>
        </div>

        <div class="episodes-section">
            <div class="ep-header">
                <h2>إدارة الحلقات</h2>
                <button @click="addNewEpisodeRow" class="btn-add">إضافة حلقة جديدة</button>
            </div>

            <div class="episodes-grid" v-if="mediaData.episodes && mediaData.episodes.length > 0">
                <div v-for="ep in mediaData.episodes" :key="ep.id" class="ep-card my-card">
                    <span>حلقة {{ ep.episode_number }}</span>
                    <div class="actions">
                        <button @click="manageLinks(ep.id)" class="btn-links">السيرفرات</button>
                        <button @click="syncToBlogger(ep)" :class="['btn-sync', ep?.is_synced ? 'synced' : 'pending']">
                            {{ ep?.is_synced ? 'منشور' : 'نشر الآن' }}
                        </button>
                        <button @click="deleteEpisode(ep.id)" class="btn-delete-ep">حذف</button>
                    </div>
                </div>
            </div>
            <div v-else class="empty-state">
                <p>لا توجد حلقات مضافة بعد. اضغط على "إضافة حلقة جديدة".</p>
            </div>
        </div>

        <div v-if="showLinksModal" class="modal-overlay-sub" @click.self="showLinksModal = false">
            <div class="modal-content-sub my-card">
                <h3>إدارة سيرفرات الحلقة: {{ selectedEpisodeId }}</h3>
                <div v-for="link in links" :key="link.id" class="link-row">
                    <input class="server-name" v-model="link.server_name" @blur="updateLink(link)"
                        placeholder="اسم السيرفر">
                    <input class="server-url" v-model="link.url" @blur="updateLink(link)" placeholder="الرابط">
                    <button @click="deleteLink(link.id)">×</button>
                </div>
                <div class="footer--content-sub">
                    <button class="btn-add" @click="addNewLink(selectedEpisodeId)">إضافة سيرفر جديد</button>
                    <button class="close-btn" @click="showLinksModal = false">إغلاق</button>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useRoute } from 'vue-router';
import api from '../services/api';

const route = useRoute();
const mediaData = ref({});
const links = ref([]);
const showLinksModal = ref(false);
const selectedEpisodeId = ref(null);
const props = defineProps(['search', 'id']);

const loadMedia = async () => {
    try {
        const response = await api.get(`/media/details/${route.params.id}`);
        mediaData.value = response.data;
    } catch (e) { console.error(e); }
};

// --- منطق السيرفرات ---
const manageLinks = async (epId) => {
    selectedEpisodeId.value = epId;
    showLinksModal.value = true;
    const res = await api.get(`/episodes/${epId}/links`);
    links.value = res.data.links || res.data;
};

const updateLink = async (link) => {
    const params = new URLSearchParams();
    params.append('server_name', link.server_name);
    params.append('url', link.url);
    await api.post(`/links/${link.id}/update`, params);
};

const addNewLink = async (epId) => {
    await api.post(`/episodes/${epId}/add-link`);
    manageLinks(epId); // تحديث القائمة
};

const deleteLink = async (linkId) => {
    if (!confirm("هل أنت متأكد من حذف هذا السيرفر؟")) return; // حماية من الحذف الخطأ
    await api.post(`/links/${linkId}/delete`);
    links.value = links.value.filter(l => l.id !== linkId);
};

// --- منطق الحلقات ---
const addNewEpisodeRow = async () => {
    const epNum = prompt("رقم الحلقة:");
    if (!epNum) return;
    await api.post(`/media/${route.params.id}/add-episode`, new URLSearchParams({ episode_number: epNum }));
    loadMedia();
};

const deleteEpisode = async (epId) => {
    if (!confirm("حذف الحلقة؟")) return;
    await api.post(`/episodes/${epId}/delete`);
    loadMedia();
};

const syncToBlogger = async (ep) => {
    try {
        const res = await api.post(`/episodes/${ep.id}/sync`);
        if (res.data.status === 'success') {
            ep.is_synced = true;
            alert("✅ " + res.data.message);
        } else {
            alert("⚠️ " + (res.data.error || "حدث خطأ غير معروف"));
        }
    } catch (e) {
        console.error(e);
        alert("❌ فشل الاتصال بالسيرفر - تأكد من المسار");
    }
};

onMounted(loadMedia);

const isSaving = ref(false); // أضف هذا المتغير

const saveMediaDetails = async () => {
    isSaving.value = true;
    try {
        // تحويل البيانات إلى تنسيق Form Data ليتوافق مع app.py
        const params = new URLSearchParams();
        for (const key in mediaData.value) {
            // تجاهل الحلقات عند الإرسال لأن السيرفر لا يتوقع مصفوفة حلقات في مسار التحديث
            if (key !== 'episodes') {
                params.append(key, mediaData.value[key]);
            }
        }

        await api.post(`/media/update/${route.params.id}`, params);
        alert("✅ تم تحديث بيانات العمل بنجاح");
    } catch (e) {
        console.error(e);
        alert("❌ فشل في حفظ البيانات");
    } finally {
        isSaving.value = false;
    }
};


</script>
<style scoped>
.media-details-container {
    display: flex;
    flex-direction: column;
    gap: 20px;
    max-width: 900px;
    margin: 20px auto 0;
    padding: 20px;
    border-radius: 16px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
}

.details-header {
    display: flex;
    flex-direction: row-reverse;
    justify-content: space-evenly;
    margin-bottom: 30px;

}

.poster-side img {
    max-width: 300px;
    aspect-ratio: 1 / 1;
    border-radius: 12px;
    box-shadow: 0 8px 16px rgba(0, 0, 0, 0.2);
}

.episodes-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 15px;
    margin-top: 20px;
}

.form-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    /* عمودين */
    gap: 15px;
    margin-bottom: 15px;
}

.form-group {
    margin-bottom: 10px;
}

.form-group label {
    font-size: 13px;
    font-weight: 600;
    color: #555;
    margin-bottom: 4px;
    display: block;
}

.form-control {
    width: 100%;
    padding: 8px 12px;
    border-radius: 8px;
    border: 1px solid #e0e0e0;
    font-size: 16px;

}

/* زر العودة */
.back-btn {
    background: none;
    font-size: 20px;
    border: none;
    cursor: pointer;
    padding: 16px;
    color: var(--color-primary);
    font-weight: bold;
}

/* تنسيق حلقة واحدة */
.ep-card {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    border-radius: 8px;
    border: 1px solid #e0e0e0;
    margin-bottom: 10px;
}

.actions {
    display: flex;
    gap: 10px;
    align-items: center;
    padding: 8px;

}

.textarea {
    width: 100%;
    height: 80px;
    padding: 12px;

    border: 1px solid #444;
    border-radius: 8px;
    font-family: sans-serif;
    outline: none;
    min-height: 200px;
    max-width: 500px;
}

.btn-delete-ep {
    background: none;
    border: none;
    cursor: pointer;
    color: #ff4d4f;
    font-size: 16px;

}

.btn-links {
    font-weight: 700;
    background: none;
    border: none;
    cursor: pointer;
    color: var(--color-primary);
    font-size: 16px;
}

.btn-action {
    background: none;
    border: none;
    cursor: pointer;
    color: #666;
    font-size: 16px;
}

.btn-action:hover {
    color: #333;
}

.btn-sync.synced {
    color: #28a745;
    font-weight: bold;
    cursor: pointer;
}

/* تنسيق المودال */
.modal-overlay-sub {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    justify-content: center;
    align-items: center;
    z-index: 1000;
}

.modal-content-sub {

    padding: 25px;
    border-radius: 12px;
    width: 90%;
    max-width: 600px;
    max-height: 90vh;
    overflow-y: auto;
}

.link-row {
    display: flex;
    gap: 10px;
    margin-bottom: 10px;
}

.link-row input {
    padding: 8px;
    border: 1px solid #ddd;
    border-radius: 4px;
}

.modal-content-sub .server-name {
    max-width: 150px;

}

.server-url {
    flex-grow: 1;
}

.link-row button {
    background: #ff4d4f;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 0 10px;
    cursor: pointer;
}

.footer--content-sub {
    display: flex;
    justify-content: space-between;
    margin-top: 20px;
    padding: 8px 0;
}

.add-server-btn {
    background: #007bff;
    color: white;
    width: 100%;
    padding: 10px;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    margin-top: 15px;
}

button:disabled {
    opacity: 0.6;
    cursor: not-allowed;
    filter: grayscale(1);
    /* يجعل الزر يبدو باهتاً عند التحميل */
}
</style>