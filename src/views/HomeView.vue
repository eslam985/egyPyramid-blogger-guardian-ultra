<template>
 <div id="app">

  <main class="w-full max-w-7xl mx-auto p-8">

   <DownloadMonitor />

   <header class="dashboard-header">
    <h2>إدارة المحتوى ({{ Array.isArray(mediaList) ? mediaList.length : 0 }})</h2>

    <div class="filters-bar">
     <button class="btn-filter" :class="{ active: currentStatus === 'all' }"
      @click="currentStatus = 'all'">الكل</button>
     <button class="btn-filter" :class="{ active: currentStatus === 'published' }"
      @click="currentStatus = 'published'">✅ منشور</button>
     <button class="btn-filter" :class="{ active: currentStatus === 'draft' }" @click="currentStatus = 'draft'">⏳
      غير منشور</button>

     <select class="select-filter" v-model="currentCategory">
      <option value="all">كل الأنواع</option>
      <option value="tv">مسلسلات</option>
      <option value="movie">أفلام</option>
     </select>
    </div>
   </header>

   <div class="media-grid">
    <template v-if="loading">
     <MediaSkeleton v-for="i in 12" :key="'skeleton-' + i" />
    </template>

    <template v-else>
     <MediaCard v-for="media in filteredMedia" :key="media.id" :media="media" @delete="handleDelete" />
    </template>
   </div>
   <div class="pagination" v-if="totalPages > 1">

    <button v-if="currentPage > 1" class="btn-page" @click="loadMediaList(currentPage - 1)">
     السابق
    </button>

    <span class="page-info">صفحة {{ currentPage }} من {{ totalPages }}</span>

    <button v-if="currentPage < totalPages" class="btn-page" @click="loadMediaList(currentPage + 1)">
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
const props = defineProps(['search']);

const mediaList = ref([]);
const loading = ref(true);
const currentStatus = ref('all');
const currentCategory = ref('all');
const currentPage = ref(1);
const totalPages = ref(1);
// عدل الـ computed لضمان عدم حدوث الخطأ أبداً
const filteredMedia = computed(() => {
 return Array.isArray(mediaList.value) ? mediaList.value : [];
});
// دالة جلب البيانات الأساسية
const loadMediaList = async (page = 1) => {
 loading.value = true;
 try {
  // نستخدم props.search مباشرة من الـ Parent لضمان دقة القيمة
  const url = `/media/list?page=${page}&cat=${currentCategory.value}&status=${currentStatus.value}&search=${props.search || ''}`;
  const response = await api.get(url);

  mediaList.value = response.data.data || [];
  totalPages.value = Math.max(1, Math.ceil(response.data.total_count / 12));
  currentPage.value = page;
 } catch (e) {
  console.error("خطأ في جلب البيانات:", e);
 } finally {
  loading.value = false;
 }
};

// مراقبة التغيرات: أي تغيير في الفلاتر أو البحث يعيدنا للصفحة الأولى ويجلب البيانات
watch([() => props.search, currentStatus, currentCategory], () => {
 loadMediaList(1);
});

const handleDelete = (id) => {
 console.log("Delete triggered for:", id);
};

onMounted(async () => {
 await loadMediaList(1);
});
</script>