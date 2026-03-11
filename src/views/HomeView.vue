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
          <button @click="currentStatus = 'all'" class="px-4 py-2 rounded-lg text-sm font-medium transition-colors"
            :class="currentStatus === 'all' ? 'bg-primary text-white' : 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'">
            الكل
          </button>
          <button @click="currentStatus = 'published'"
            class="px-4 py-2 rounded-lg text-sm font-medium transition-colors"
            :class="currentStatus === 'published' ? 'bg-green-600 text-white' : 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'">
            ✅ منشور
          </button>
          <button @click="currentStatus = 'draft'" class="px-4 py-2 rounded-lg text-sm font-medium transition-colors"
            :class="currentStatus === 'draft' ? 'bg-amber-600 text-white' : 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'">
            ⏳ غير منشور
          </button>

          <!-- تحديد النوع -->
          <select v-model="currentCategory"
            class="px-4 py-2 rounded-lg text-sm font-medium bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 border-none focus:ring-2 focus:ring-primary outline-none">
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
          <MediaCard v-for="item in mediaList" :key="item.id" :media="item" @delete="handleDelete(item.id)"
            @toggle-blogger="handleToggleBlogger(item)" />
        </template>

        <!-- حالة عدم وجود نتائج -->
        <div v-else class="col-span-full text-center py-12">
          <p class="text-gray-500 dark:text-gray-400 text-lg">لا توجد نتائج تطابق الفلاتر المحددة.</p>
        </div>
      </div>

      <!-- Pagination -->
      <div class="pagination flex items-center justify-center gap-2 mt-8" v-if="totalPages > 1">
        <button @click="loadMediaList(currentPage - 1)" :disabled="currentPage <= 1"
          class="px-4 py-2 rounded-lg bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-200 dark:hover:bg-gray-700 transition">
          السابق
        </button>

        <span class="px-4 py-2 text-gray-700 dark:text-gray-300">
          صفحة {{ currentPage }} من {{ totalPages }}
        </span>

        <button @click="loadMediaList(currentPage + 1)" :disabled="currentPage >= totalPages"
          class="px-4 py-2 rounded-lg bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-200 dark:hover:bg-gray-700 transition">
          التالي
        </button>
      </div>
    </main>
  </div>
</template>

<script setup>
import Swal from 'sweetalert2';
import { ref, computed, onMounted, watch } from 'vue';
import api from '../services/api';
import MediaCard from '../components/MediaCard.vue';
import DownloadMonitor from '../components/DownloadMonitor.vue';
import MediaSkeleton from '../components/MediaSkeleton.vue';
import { onUnmounted } from 'vue';
import { supabaseClient } from '../services/supabase';

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


// 2. جوه الـ onMounted، زود الـ channel بعد استدعاء loadMediaList
onMounted(() => {
  // 1. التحميل الأولي للبيانات
  loadMediaList(1);

  // 2. تفعيل المزامنة اللحظية مرة واحدة فقط
  const channel = supabaseClient
    .channel('public:medias_list')
    .on('postgres_changes', { event: '*', schema: 'public', table: 'medias' }, (payload) => {
      console.log('تحديث لحظي: جاري تحديث القائمة...');
      loadMediaList(currentPage.value);
    })
    .subscribe();
});

onUnmounted(() => {
  supabaseClient.channel('public:medias_list').unsubscribe();
});

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



const handleDelete = async (id) => {
  // التنبيه المودرن
  const result = await Swal.fire({
    title: 'هل أنت متأكد؟',
    text: "سيتم حذف هذا العمل وجميع حلقاته وروابطه نهائياً!",
    icon: 'warning',
    showCancelButton: true,
    confirmButtonColor: '#ef4444', // لون أحمر متناسق مع Tailwind (red-500)
    cancelButtonColor: '#6b7280',  // لون رمادي (gray-500)
    confirmButtonText: 'نعم، احذف الكل',
    cancelButtonText: 'تراجع',
    background: '#1f2937', // لون Dark متناسق مع الداشبورد بتاعتك
    color: '#ffffff',
    iconColor: '#f87171'
  });

  if (result.isConfirmed) {
    try {
      // إرسال الطلب الفعلي للسيرفر
      const response = await api.post(`/media/delete/${id}`);

      if (response.data.status === "deleted") {
        // حذف من الشاشة
        mediaList.value = mediaList.value.filter(item => item.id !== id);
        totalCount.value -= 1;

        // رسالة نجاح سريعة (Toast)
        Swal.fire({
          icon: 'success',
          title: 'تم الحذف بنجاح',
          showConfirmButton: false,
          timer: 1500,
          background: '#1f2937',
          color: '#ffffff'
        });
      }
    } catch (error) {
      Swal.fire({
        icon: 'error',
        title: 'فشل الحذف',
        text: 'حدث خطأ أثناء الاتصال بالسيرفر، حاول مرة أخرى.',
        background: '#1f2937',
        color: '#ffffff'
      });
    }
  }
};

</script>