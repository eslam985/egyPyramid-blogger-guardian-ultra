<template>
  <div id="app">
    <Navbar @open-add-modal="showModal = true" @update-search="searchQuery = $event" />

    <main class="container">
      <DownloadMonitor />

      <header class="dashboard-header">
        <h2>إدارة المحتوى ({{ filteredMedia.length }})</h2>

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

      <div v-if="loading">جاري التحميل...</div>

      <div class="media-grid" v-else>
        <MediaCard v-for="media in filteredMedia" :key="media.id" :media="media" @edit="handleEdit"
          @delete="handleDelete" />
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

    <EditModal v-if="selectedMediaId" :mediaId="selectedMediaId" @close="closeModal" />

    <button @click="toggleTheme" class="theme-toggle-btn">
      <i class="fa" :class="isDarkMode ? 'fa-sun' : 'fa-moon'"></i>
    </button>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import api from './services/api';
import Navbar from './components/Navbar.vue';
import MediaCard from './components/MediaCard.vue';
import EditModal from './components/EditModal.vue';
import DownloadMonitor from './components/DownloadMonitor.vue';
import { watch } from 'vue';

const mediaList = ref([]);
const loading = ref(true);
const showModal = ref(false);
const selectedMediaId = ref(null);
const isDarkMode = ref(false);


// الفلاتر
// الفلاتر
const currentStatus = ref('all');   // الحالة (published, draft)
const currentCategory = ref('all'); // النوع (tv, movie)
const searchQuery = ref('');


const currentPage = ref(1);
const totalPages = ref(1);


watch([currentCategory, currentStatus, searchQuery], () => {
  loadMediaList(1);
});
const loadMediaList = async (page = 1) => {
  loading.value = true;
  try {
    // أضفنا &search=${searchQuery.value} إلى الرابط
    const url = `/media/list?page=${page}&cat=${currentCategory.value}&status=${currentStatus.value}&search=${searchQuery.value}`;
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
// [دمج منطق الفلترة في Computed واحدة فقط]
// [داخل App.vue]
const filteredMedia = computed(() => {
  // لا حاجة لفلترة الـ title هنا لأن السيرفر أرجع النتائج المفلترة بالفعل
  return mediaList.value;
});

const toggleTheme = () => {
  isDarkMode.value = !isDarkMode.value;
  document.documentElement.classList.toggle('dark-mode');
  localStorage.setItem('theme', isDarkMode.value ? 'dark' : 'light');
};

const handleEdit = (id) => { selectedMediaId.value = id; showModal.value = true; };
const closeModal = () => { showModal.value = false; selectedMediaId.value = null; };
const handleDelete = (id) => { console.log("Delete triggered for:", id); };

// دالة OnMounted موحدة
// في script setup
onMounted(async () => {
  // 1. تهيئة الثيم (كما هي)
  if (localStorage.getItem('theme') === 'dark') {
    isDarkMode.value = true;
    document.documentElement.classList.add('dark-mode');
  }

  // 2. جلب البيانات باستخدام الدالة الموحدة
  await loadMediaList(1);
  loading.value = false;
});
</script>