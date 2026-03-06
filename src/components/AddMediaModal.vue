<template>
    <div class="modal-overlay" @click.self="$emit('close')">
        <div class="modal-content">
            <h2>إضافة عمل جديد</h2>
            <div class="form-grid">
                <div class="form-group">
                    <label>عنوان العمل</label>
                    <input v-model="newMedia.title" class="form-control">
                </div>
                <div class="form-group">
                    <label>TMDB ID</label>
                    <input v-model="newMedia.tmdb_id" class="form-control">
                </div>
                <div class="form-group">
                    <label>سنة الإنتاج</label>
                    <input v-model="newMedia.year" class="form-control">
                </div>
                <div class="form-group">
                    <label>المدة (duration_iso)</label>
                    <input v-model="newMedia.duration_iso" class="form-control" placeholder="PT1H30M">
                </div>
                <div class="form-group">
                    <label>التصنيفات (labels)</label>
                    <input v-model="newMedia.labels" class="form-control" placeholder="أكشن, دراما">
                </div>
                <div class="form-group">
                    <label>حالة البلوجر</label>
                    <select v-model="newMedia.blogger_status" class="form-control">
                        <option value="draft">مسودة</option>
                        <option value="published">منشور</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>النوع (category)</label>
                    <select v-model="newMedia.category" class="form-control">
                        <option value="movie">فيلم</option>
                        <option value="tv">مسلسل</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>التقييم (rating)</label>
                    <input v-model="newMedia.rating" class="form-control" placeholder="8.5">
                </div>
                <div class="form-group">
                    <label>وقت العرض (runtime)</label>
                    <input v-model="newMedia.runtime" class="form-control" placeholder="120 دقيقة">
                </div>
            </div>

            <div class="form-group">
                <label>رابط البوستر</label>
                <input v-model="newMedia.poster_url" class="form-control">
            </div>

            <div class="form-group">
                <label>قصة العمل</label>
                <textarea v-model="newMedia.story" class="form-control textarea"></textarea>
            </div>

            <div class="modal-actions">
                <button @click="$emit('close')" class="btn-cancel">إلغاء</button>
                <button @click="saveNewMedia" class="btn-primary" :disabled="isSaving">
                    {{ isSaving ? 'جاري الحفظ...' : 'حفظ العمل' }}
                </button>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref } from 'vue';
import api from '../services/api';

const emit = defineEmits(['close', 'saved']);
const isSaving = ref(false);

const newMedia = ref({
    title: '',
    tmdb_id: '',
    year: '',
    category: 'movie', // تم تحديثها من type لـ category لتطابق الـ Backend
    poster_url: '',
    story: '',
    duration_iso: '',
    labels: '',
    blogger_status: 'draft',
    rating: '', // حقل جديد
    runtime: '' // حقل جديد
});

const saveNewMedia = async () => {
    isSaving.value = true;
    try {
        await api.post('/media/create', newMedia.value);
        alert("✅ تم إضافة العمل بنجاح");
        emit('saved');
        emit('close');
    } catch (e) {
        alert("❌ فشل في إضافة العمل");
    } finally {
        isSaving.value = false;
    }
};
</script>

<style scoped>
/* التنسيق الحالي ممتاز، تأكد فقط من الـ grid */
.modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.6);
    display: flex;
    justify-content: center;
    align-items: center;
    z-index: 2000;
}

.modal-content {
    background: white;
    padding: 25px;
    border-radius: 12px;
    width: 90%;
    max-width: 700px;
    max-height: 90vh;
    overflow-y: auto;
}

.form-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
    margin-bottom: 15px;
}

.form-group {
    margin-bottom: 10px;
}

.form-control {
    width: 100%;
    padding: 8px;
    border: 1px solid #ddd;
    border-radius: 6px;
}

.textarea {
    height: 80px;
    width: 100%;
}

.modal-actions {
    display: flex;
    gap: 10px;
    justify-content: flex-end;
    margin-top: 15px;
}
</style>