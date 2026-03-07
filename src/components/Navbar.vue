<template>
  <nav class=" flex items-center justify-between p-4 shadow-md  z-50 sticky top-px my-card">

    <div
      class="font-bold text-3xl text-yellow-500 tracking-[-0.5px] whitespace-nowrap px-4 py-1 rounded-lg shadow-md bg-[linear-gradient(135deg,#8a8000_0,#000000_80%)]">
      EGY PYRMID
    </div>

<div class="flex flex-[0_1_500px] mx-6">
  <form @submit.prevent="searchMedia" class="flex flex-row-reverse w-full">
    
    <button type="submit" 
      class="px-5 py-2.5 bg-primary text-white border border-primary rounded-l-lg hover:bg-primary-dark transition-colors flex items-center justify-center">
      <i class="fa fa-search"></i>
    </button>

    <input v-model="searchQuery" type="text" placeholder="ابحث..." 
      class="w-full px-4 py-2.5 border border-gray-300 dark:border-gray-600 rounded-r-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 transition-all focus:outline-none focus:border-primary focus:ring-4 focus:ring-blue-500/10">
      
  </form>
</div>

    <div class=" flex gap-2">
      <button class=" relative z-60 bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600 cursor-pointer"
        @click="triggerOpen">
        <i class="fa fa-plus"></i> إضافة عمل
      </button>


      <button class="bg-[#ea580c] text-white px-4 py-0 rounded hover:bg-yellow-600 cursor-pointer" @click="triggerPublisher">
        🚀 تشغيل محرك النشر
      </button>
    </div>
  </nav>
</template>

<script setup>
import { ref } from 'vue';
import api from '../services/api';

const searchQuery = ref('');
const isPublishing = ref(false);
const emit = defineEmits(['update-search', 'open-add-modal']);

const searchMedia = () => {
  emit('update-search', searchQuery.value);
};

const triggerPublisher = async () => {
  isPublishing.value = true;
  try {
    const response = await api.post('/publisher/run');
    alert("✅ " + response.data.message);
  } catch (e) {
    alert("❌ فشل الاتصال");
  } finally {
    isPublishing.value = false;
  }
};
const triggerOpen = () => {
  console.log("الزرار تم الضغط عليه!");
  emit('open-add-modal');
};
</script>