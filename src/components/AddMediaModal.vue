<template>
  <div
    class="fixed inset-0 bg-black/60 backdrop-blur-sm flex justify-center items-center z-[999] p-4 text-gray-900 dark:text-gray-100"
    @click.self="$emit('close')"
  >
    <div
      class="my-card bg-white dark:bg-secondary-dark w-full max-w-3xl max-h-[90vh] overflow-y-auto rounded-2xl shadow-card p-6 md:p-8"
    >
      <!-- العنوان -->
      <div class="flex items-center justify-between mb-6">
        <h2 class="text-2xl font-bold text-gray-800 dark:text-white">إضافة عمل جديد</h2>
        <button
          @click="$emit('close')"
          class="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition"
        >
          <i class="fa fa-times text-xl"></i>
        </button>
      </div>

      <!-- شبكة الحقول (عمودان على الشاشات المتوسطة فأكبر) -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        <div
          v-for="field in shortFields"
          :key="field"
          class="flex flex-col"
        >
          <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            {{ getLabel(field) }}
          </label>

          <!-- حقول اختيار (select) -->
          <select
            v-if="field === 'blogger_status'"
            v-model="newMedia[field]"
            class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-secondary-dark text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-primary transition"
          >
            <option value="draft">مسودة</option>
            <option value="published">منشور</option>
          </select>

          <select
            v-else-if="field === 'category'"
            v-model="newMedia[field]"
            class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-secondary-dark text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-primary transition"
          >
            <option value="movie">فيلم</option>
            <option value="tv">مسلسل</option>
          </select>

          <!-- حقول نصية عادية -->
          <input
            v-else
            v-model="newMedia[field]"
            type="text"
            :placeholder="getPlaceholder(field)"
            class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-secondary-dark text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary transition"
          />
        </div>
      </div>

      <!-- حقل رابط البوستر (يمتد على عمودين) -->
      <div class="mb-4">
        <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">رابط البوستر</label>
        <input
          v-model="newMedia.poster_url"
          type="text"
          placeholder="https://example.com/poster.jpg"
          class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-secondary-dark text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary transition"
        />
      </div>

      <!-- حقل القصة (يمتد على عمودين) -->
      <div class="mb-6">
        <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">قصة العمل</label>
        <textarea
          v-model="newMedia.story"
          rows="4"
          class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-secondary-dark text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary transition resize-none"
        ></textarea>
      </div>

      <!-- أزرار الإجراءات -->
      <div class="flex flex-col-reverse sm:flex-row gap-3 justify-end mt-6">
        <button
          @click="$emit('close')"
          class="px-6 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition font-medium"
        >
          إلغاء
        </button>
        <button
          @click="saveNewMedia"
          :disabled="isSaving"
          class="px-6 py-2 bg-primary hover:bg-primary-dark text-white rounded-lg transition font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
        >
          <i v-if="isSaving" class="fa fa-spinner fa-spin"></i>
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

// قائمة الحقول القصيرة (التي ستظهر في الشبكة)
const shortFields = [
  'title', 'tmdb_id', 'year', 'duration_iso', 'labels',
  'blogger_status', 'category', 'rating', 'runtime',
  'media_type', 'slug'
];

const newMedia = ref({
  title: '',
  tmdb_id: '',
  year: '',
  category: 'movie',
  poster_url: '',
  story: '',
  duration_iso: '',
  labels: '',
  blogger_status: 'draft',
  rating: '',
  runtime: '',
  media_type: '',
  slug: ''
});

// دوال مساعدة للعناوين والـ placeholders
const getLabel = (field) => {
  const labels = {
    title: 'عنوان العمل',
    tmdb_id: 'TMDB ID',
    year: 'سنة الإنتاج',
    duration_iso: 'المدة (ISO)',
    labels: 'التصنيفات',
    blogger_status: 'حالة البلوجر',
    category: 'النوع',
    rating: 'التقييم',
    runtime: 'وقت العرض',
    media_type: 'نوع الميديا',
    slug: 'الرابط اللطيف (slug)'
  };
  return labels[field] || field;
};

const getPlaceholder = (field) => {
  const placeholders = {
    duration_iso: 'PT1H30M',
    labels: 'أكشن, دراما',
    rating: '8.5',
    runtime: '120 دقيقة'
  };
  return placeholders[field] || '';
};

const saveNewMedia = async () => {
  isSaving.value = true;
  try {
    await api.post('/media/add', newMedia.value);
    alert('✅ تم إضافة العمل بنجاح');
    emit('saved');
    emit('close');
  } catch (e) {
    alert('❌ فشل في إضافة العمل');
    console.error(e);
  } finally {
    isSaving.value = false;
  }
};
</script>