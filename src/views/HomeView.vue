<template>
  <div id="app">
    <main class="w-full max-w-7xl mx-auto p-4 md:p-8">
      <!-- مكون مراقبة التحميل (إذا كان موجوداً) -->
      <DownloadMonitor />

      <!-- رأس الصفحة مع الفلاتر -->
      <header class="dashboard-header flex flex-col md:flex-row items-start md:items-center justify-between gap-4 mb-6">
        <h2 class="text-2xl font-bold text-gray-800 dark:text-white">
          إدارة المحتوى ({{ totalCount }})
        </h2>

        <div class="filters-bar flex flex-wrap items-center gap-2">
          <!-- أزرار حالة النشر -->
          <button
            @click="currentStatus = 'all'"
            class="px-4 py-2 rounded-lg text-sm font-medium transition-colors"
            :class="currentStatus === 'all' ? 'bg-primary text-white' : 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'"
          >
            الكل
          </button>
          <button
            @click="currentStatus = 'published'"
            class="px-4 py-2 rounded-lg text-sm font-medium transition-colors"
            :class="currentStatus === 'published' ? 'bg-green-600 text-white' : 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'"
          >
            ✅ منشور
          </button>
          <button
            @click="currentStatus = 'draft'"
            class="px-4 py-2 rounded-lg text-sm font-medium transition-colors"
            :class="currentStatus === 'draft' ? 'bg-amber-600 text-white' : 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'"
          >
            ⏳ غير منشور
          </button>

          <!-- تحديد النوع -->
          <select
            v-model="currentCategory"
            class="px-4 py-2 rounded-lg text-sm font-medium bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 border-none focus:ring-2 focus:ring-primary outline-none"
          >
            <option value="all">كل الأنواع</option>
            <option value="tv">مسلسلات</option>
            <option value="movie">أفلام</option>
          </select>
        </div>
      </header>

      <!-- شبكة البطاقات -->
      <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
        <template v-if="loading">
          <MediaSkeleton v-for="i in 12" :key="'skeleton-' + i" />
        </template>

        <template v-else-if="mediaList.length > 0">
          <MediaCard
            v-for="media in mediaList"
            :key="media.id"
            :media="media"
            @delete="handleDelete"
            @toggle-blogger="handleToggleBlogger"
          />
        </template>

        <!-- حالة عدم وجود نتائج -->
        <div v-else class="col-span-full text-center py-12">
          <p class="text-gray-500 dark:text-gray-400 text-lg">لا توجد نتائج تطابق الفلاتر المحددة.</p>
        </div>
      </div>

      <!-- Pagination -->
      <div class="pagination flex items-center justify-center gap-2 mt-8" v-if="totalPages > 1">
        <button
          @click="loadMediaList(currentPage - 1)"
          :disabled="currentPage <= 1"
          class="px-4 py-2 rounded-lg bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-200 dark:hover:bg-gray-700 transition"
        >
          السابق
        </button>

        <span class="px-4 py-2 text-gray-700 dark:text-gray-300">
          صفحة {{ currentPage }} من {{ totalPages }}
        </span>

        <button
          @click="loadMediaList(currentPage + 1)"
          :disabled="currentPage >= totalPages"
          class="px-4 py-2 rounded-lg bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-200 dark:hover:bg-gray-700 transition"
        >
          التالي
        </button>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import api from '../services/api';
import MediaCard from '../components/MediaCard.vue';
import DownloadMonitor from '../components/DownloadMonitor.vue';
import MediaSkeleton from '../components/MediaSkeleton.vue';

const props = defineProps({
  search: {
    type: String,
    default: ''
  }
});

const mediaList = ref([]);
const loading = ref(false);
const currentStatus = ref('all');
const currentCategory = ref('all');
const currentPage = ref(1);
const totalPages = ref(1);
const totalCount = ref(0); // العدد الإجمالي للعناصر (للعرض في العنوان)

// دالة جلب البيانات
const loadMediaList = async (page = 1) => {
  loading.value = true;
  try {
    const url = `/media/list?page=${page}&cat=${currentCategory.value}&status=${currentStatus.value}&search=${props.search}`;
    const response = await api.get(url);
    mediaList.value = response.data.data || [];
    totalCount.value = response.data.total_count || 0;
    totalPages.value = Math.ceil(totalCount.value / 12);
    currentPage.value = page;
  } catch (error) {
    console.error('خطأ في جلب البيانات:', error);
    // يمكن إضافة إشعار للمستخدم هنا
  } finally {
    loading.value = false;
  }
};

// مراقبة تغير الفلاتر أو البحث
watch(
  [() => props.search, currentStatus, currentCategory],
  () => {
    loadMediaList(1); // العودة للصفحة الأولى
  }
);

const handleDelete = (id) => {
  // بعد الحذف يمكن إعادة تحميل القائمة أو إزالة العنصر محلياً
  mediaList.value = mediaList.value.filter(item => item.id !== id);
  totalCount.value -= 1;
  // تحديث عدد الصفحات إذا لزم الأمر
};

const handleToggleBlogger = ({ postId, mediaId }) => {
  // يمكن تحديث حالة blogger محلياً بعد النجاح
  // أو إعادة تحميل القائمة
};

onMounted(() => {
  loadMediaList(1);
});
</script>

<!-- لم يعد هناك حاجة لأي CSS إضافي، كل شيء عبر Tailwind -->