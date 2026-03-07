<template>

 <div class="fixed inset-0 bg-black/60 flex justify-center items-center z-[999] p-16 text-black"
  @click.self="$emit('close')">

  <div class="bg-white p-6 rounded-xl w-full max-w-[700px] max-h-[90vh] overflow-y-auto">
   <h2 class="text-xl font-bold mb-4 p-2 ">إضافة عمل جديد</h2>

   <div class="grid grid-cols-3 gap-3 mb-4">
    <div
     v-for="field in ['title', 'tmdb_id', 'year', 'duration_iso', 'labels', 'blogger_status', 'category', 'rating', 'runtime']"
     :key="field" class="mb-2">
     <label class="block text-sm font-medium mb-1">{{ getLabel(field) }}</label>

     <select v-if="field === 'blogger_status'" v-model="newMedia[field]"
      class="w-full p-2 border border-gray-300 rounded-md">
      <option value="draft">مسودة</option>
      <option value="published">منشور</option>
     </select>

     <select v-else-if="field === 'category'" v-model="newMedia[field]"
      class="w-full p-2 border border-gray-300 rounded-md">
      <option value="movie">فيلم</option>
      <option value="tv">مسلسل</option>
     </select>

     <input v-else v-model="newMedia[field]" class="w-full p-2 border border-gray-300 rounded-md"
      :placeholder="getPlaceholder(field)">
    </div>
   </div>

   <div class="mb-2">
    <label class="block text-sm font-medium mb-1">رابط البوستر</label>
    <input v-model="newMedia.poster_url" class="w-full p-2 border border-gray-300 rounded-md">
   </div>

   <div class="mb-2">
    <label class="block text-sm font-medium mb-1">قصة العمل</label>
    <textarea v-model="newMedia.story" class="w-full h-20 p-2 border border-gray-300 rounded-md"></textarea>
   </div>

   <div class="flex gap-3 justify-end mt-4">
    <button @click="$emit('close')" class="px-4 py-2 bg-gray-200 rounded-md hover:bg-gray-300">إلغاء</button>
    <button @click="saveNewMedia"
     class="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50" :disabled="isSaving">
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
 title: '', tmdb_id: '', year: '', category: 'movie',
 poster_url: '', story: '', duration_iso: '', labels: '',
 blogger_status: 'draft', rating: '', runtime: ''
});

// دوال مساعدة لتقليل التكرار
const getLabel = (f) => ({ title: 'عنوان العمل', tmdb_id: 'TMDB ID', year: 'سنة الإنتاج', duration_iso: 'المدة (ISO)', labels: 'التصنيفات', blogger_status: 'حالة البلوجر', category: 'النوع', rating: 'التقييم', runtime: 'وقت العرض' })[f];
const getPlaceholder = (f) => ({ duration_iso: 'PT1H30M', labels: 'أكشن, دراما', rating: '8.5', runtime: '120 دقيقة' })[f] || '';

const saveNewMedia = async () => {
 isSaving.value = true;
 try {
  await api.post('/media/create', newMedia.value);
  alert("✅ تم إضافة العمل بنجاح");
  emit('saved');
  emit('close');
 } catch (e) { alert("❌ فشل في إضافة العمل"); }
 finally { isSaving.value = false; }
};
</script>