<template>
  <div class="database-view p-6 max-w-350 mx-auto py-8 min-h-screen">
    <div class="flex flex-col md:flex-row gap-6">
      <!-- Sidebar Tables Selection -->
      <aside class="w-full md:w-64 flex-shrink-0">
        <div class="my-card p-4 rounded-xl sticky top-24">
          <h2 class="text-xl font-bold mb-4 text-gray-800 dark:text-white flex items-center gap-2">
            <i class="fa fa-database text-primary"></i> الجداول
          </h2>
          <div class="flex flex-col gap-2">
            <button v-for="table in tables" :key="table" @click="selectTable(table)" :class="[
              'text-right px-4 py-2.5 rounded-lg transition font-medium',
              activeTable === table
                ? 'bg-primary text-white shadow-lg'
                : 'hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-300'
            ]">
              {{ translateTableName(table) }}
            </button>
          </div>
        </div>
      </aside>

      <!-- Main Content Area -->
      <main class="flex-1 overflow-hidden">
        <div v-if="activeTable" class="my-card rounded-xl overflow-hidden flex flex-col h-full">
          <!-- Table Header / Actions -->
          <div
            class="p-4 border-b border-gray-200 dark:border-gray-700 flex justify-between items-center bg-gray-50 dark:bg-gray-900/50">
            <h3 class="text-lg font-bold text-gray-800 dark:text-white uppercase">
              {{ translateTableName(activeTable) }}
            </h3>
            <div class="flex gap-2">
              <button @click="openAddModal"
                class="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg text-sm font-bold transition flex items-center gap-2">
                <i class="fa fa-plus"></i> إضافة سجل
              </button>
              <button @click="loadTableData"
                class="bg-primary hover:bg-primary-dark text-white px-4 py-2 rounded-lg text-sm font-bold transition flex items-center gap-2">
                <i class="fa fa-sync" :class="{ 'fa-spin': loading }"></i> تحديث
              </button>
            </div>
          </div>

          <!-- Data Table -->
          <div class="overflow-x-auto overflow-y-auto max-h-[70vh]">
            <table class="w-full text-right border-collapse">
              <thead class="bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-200 sticky top-0 z-10">
                <tr>
                  <th v-for="col in columns" :key="col" class="p-3 text-sm font-bold border-b dark:border-gray-700">
                    {{ col }}
                  </th>
                  <th
                    class="p-3 text-sm font-bold border-b dark:border-gray-700 sticky left-0 bg-gray-100 dark:bg-gray-800">
                    العمليات</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-200 dark:divide-gray-700">
                <tr v-for="row in data" :key="row.id" class="hover:bg-gray-50 dark:hover:bg-gray-800/50 transition">
                  <td v-for="col in columns" :key="col"
                    class="p-3 text-sm text-gray-600 dark:text-gray-400 max-w-[200px] truncate">
                    {{ formatValue(row[col]) }}
                  </td>
                  <td class="p-3 sticky left-0 bg-white dark:bg-secondary-dark flex gap-2">
                    <button @click="openEditModal(row)" class="text-blue-500 hover:text-blue-700 transition">
                      <i class="fa fa-edit"></i>
                    </button>
                    <button @click="deleteRow(row)" class="text-red-500 hover:text-red-700 transition">
                      <i class="fa fa-trash"></i>
                    </button>
                  </td>
                </tr>
                <tr v-if="data.length === 0 && !loading">
                  <td :colspan="columns.length + 1" class="p-8 text-center text-gray-500">
                    لا توجد بيانات متاحة في هذا الجدول
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Pagination -->
          <div
            class="p-4 border-t border-gray-200 dark:border-gray-700 flex justify-between items-center bg-gray-50 dark:bg-gray-900/50">
            <span class="text-sm text-gray-500">إجمالي السجلات: {{ total }}</span>
            <div class="flex gap-2">
              <button :disabled="page === 1" @click="page--; loadTableData()"
                class="px-3 py-1 rounded border dark:border-gray-600 disabled:opacity-50">
                السابق
              </button>
              <span class="px-3 py-1 bg-white dark:bg-gray-800 border dark:border-gray-600 rounded">{{ page }}</span>
              <button :disabled="page * limit >= total" @click="page++; loadTableData()"
                class="px-3 py-1 rounded border dark:border-gray-600 disabled:opacity-50">
                التالي
              </button>
            </div>
          </div>
        </div>
        <div v-else class="h-full flex items-center justify-center text-gray-500 italic">
          اختر جدولاً من القائمة الجانبية لعرض بياناته
        </div>
      </main>
    </div>

    <!-- Edit/Add Modal -->
    <div v-if="showModal"
      class="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-[100] p-4">
      <div class="my-card w-full max-w-2xl max-h-[90vh] overflow-y-auto p-6 rounded-xl shadow-2xl">
        <h3 class="text-xl font-bold mb-6 text-gray-800 dark:text-white border-b pb-4">
          {{ isEdit ? 'تعديل سجل' : 'إضافة سجل جديد' }} في {{ translateTableName(activeTable) }}
        </h3>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
          <div v-for="col in formColumns" :key="col" class="form-group">
            <label class="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">{{ col }}</label>
            <input v-if="col !== 'id' && col !== 'created_at' && col !== 'updated_at'" v-model="formData[col]"
              class="w-full p-2.5 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-secondary-dark text-gray-900 dark:text-gray-100" />
            <input v-else :value="formData[col]" disabled
              class="w-full p-2.5 border border-gray-300 dark:border-gray-600 rounded-lg bg-gray-100 dark:bg-gray-800 text-gray-500 cursor-not-allowed" />
          </div>
        </div>

        <div class="flex justify-end gap-3 pt-4 border-t border-gray-200 dark:border-gray-700">
          <button @click="showModal = false"
            class="px-6 py-2 bg-gray-500 hover:bg-gray-600 text-white rounded-lg transition font-bold">
            إلغاء
          </button>
          <button @click="saveRow"
            class="px-6 py-2 bg-primary hover:bg-primary-dark text-white rounded-lg transition font-bold">
            {{ isEdit ? 'حفظ التعديلات' : 'إضافة السجل' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import api from '../services/api';
import { notifySuccess, notifyError, confirmAction } from '../utils/alerts';

const tables = ref([]);
const activeTable = ref(null);
const data = ref([]);
const total = ref(0);
const page = ref(1);
const limit = 50;
const loading = ref(false);

const showModal = ref(false);
const isEdit = ref(false);
const formData = ref({});

// استخراج الأعمدة من أول سجل متاح
const columns = computed(() => {
  if (data.value.length > 0) {
    return Object.keys(data.value[0]);
  }
  // إذا كان الجدول فارغاً، قد نحتاج لطريقة أخرى لجلب الأعمدة
  // هنا سنفترض أننا سنحصل عليها من قاعدة البيانات لاحقاً
  return [];
});

// الأعمدة التي ستظهر في النموذج (نستثني الأعمدة التلقائية في حالة الإضافة)
const formColumns = computed(() => {
  if (isEdit.value) return columns.value;
  return columns.value.filter(c => !['id', 'created_at', 'updated_at'].includes(c));
});

onMounted(async () => {
  try {
    const res = await api.get('/db/tables');

    // التحقق من أن البيانات هي مصفوفة (Array) وليست نص HTML
    if (Array.isArray(res.data)) {
      tables.value = res.data;
      if (tables.value.length > 0) {
        selectTable(tables.value[0]);
      }
    } else {
      console.error('API returned non-array data:', res.data);
      notifyError('فشل في جلب قائمة الجداول: استجابة غير صالحة من السيرفر');
    }
  } catch (e) {
    console.error('Failed to fetch tables:', e);
    notifyError('فشل في جلب قائمة الجداول: تأكد من تشغيل الباك-إند');
  }
});

const selectTable = (table) => {
  activeTable.value = table;
  page.value = 1;
  loadTableData();
};

const loadTableData = async () => {
  if (!activeTable.value) return;
  loading.value = true;
  try {
    const res = await api.get(`/db/${activeTable.value}`, {
      params: { page: page.value, limit }
    });
    data.value = res.data.data;
    total.value = res.data.total;
  } catch (e) {
    notifyError(`فشل في جلب بيانات جدول ${activeTable.value}`);
  } finally {
    loading.value = false;
  }
};

const translateTableName = (name) => {
  const map = {
    'medias': 'الأعمال (Medias)',
    'episodes': 'الحلقات (Episodes)',
    'links': 'الروابط (Links)',
    'genres': 'التصنيفات (Genres)',
    'seasons': 'المواسم (Seasons)',
    'media_genres': 'علاقة الأعمال بالتصنيفات'
  };
  return map[name] || name;
};

const formatValue = (val) => {
  if (val === null || val === undefined) return '-';
  if (typeof val === 'boolean') return val ? '✅' : '❌';
  if (typeof val === 'object') return JSON.stringify(val);
  return val;
};

const openAddModal = () => {
  isEdit.value = false;
  formData.value = {};
  // تهيئة قيم افتراضية بناءً على الأعمدة
  columns.value.forEach(c => {
    if (!['id', 'created_at', 'updated_at'].includes(c)) {
      formData.value[c] = '';
    }
  });
  showModal.value = true;
};

const openEditModal = (row) => {
  isEdit.value = true;
  formData.value = { ...row };
  showModal.value = true;
};

const saveRow = async () => {
  try {
    if (isEdit.value) {
      const id = formData.value.id;
      const cleanData = { ...formData.value };
      delete cleanData.id;
      delete cleanData.created_at;
      delete cleanData.updated_at;

      await api.post(`/db/${activeTable.value}/update/${id}`, cleanData);
      notifySuccess('تم تحديث السجل بنجاح');
    } else {
      await api.post(`/db/${activeTable.value}/insert`, formData.value);
      notifySuccess('تم إضافة السجل بنجاح');
    }
    showModal.value = false;
    loadTableData();
  } catch (e) {
    notifyError(e.response?.data?.detail || 'فشل في حفظ البيانات');
  }
};

const deleteRow = async (row) => {
  const result = await confirmAction("هل أنت متأكد من حذف هذا السجل؟ لا يمكن التراجع عن هذه الخطوة.");
  if (result.isConfirmed) {
    try {
      // معالجة الجداول التي لا تملك ID (مفاتيح مركبة)
      if (activeTable.value === 'media_genres') {
        // في Supabase، الحذف بدون ID يحتاج eq لكل الأعمدة الأساسية
        await api.post(`/db/${activeTable.value}/delete/composite`, {
          media_id: row.media_id,
          genre_id: row.genre_id
        });
      } else {
        await api.post(`/db/${activeTable.value}/delete/${row.id}`);
      }
      notifySuccess('تم حذف السجل');
      loadTableData();
    } catch (e) {
      notifyError('فشل في حذف السجل');
    }
  }
};
</script>

<style scoped>
.database-view {
  direction: rtl;
}

/* Custom Scrollbar for the table container */
.overflow-x-auto::-webkit-scrollbar {
  height: 8px;
  width: 8px;
}

.overflow-x-auto::-webkit-scrollbar-track {
  background: transparent;
}

.overflow-x-auto::-webkit-scrollbar-thumb {
  background: #ccc;
  border-radius: 4px;
}

.dark .overflow-x-auto::-webkit-scrollbar-thumb {
  background: #444;
}
</style>
