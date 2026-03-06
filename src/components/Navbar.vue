<template>
  <nav class="main-nav">
    <div class="logo">EGY PYRMID</div>
    <div class="search-bar">
      <form @submit.prevent="searchMedia">
        <input v-model="searchQuery" type="text" placeholder="ابحث عن مسلسل أو فيلم..." @input="searchMedia">
        <button type="submit"><i class="fa fa-search"></i></button>
      </form>
    </div>
    <div class="nav-actions">
      <button @click="$emit('open-add-modal')" class="btn-add">
        <i class="fa fa-plus"></i> إضافة عمل
      </button>
      <button ref="publishBtnRef" class="publish-btn" @click="triggerPublisher">
        🚀 تشغيل محرك النشر
      </button>
      
    </div>
  </nav>
</template>

<script setup>
import { ref } from 'vue';
import api from '../services/api';

const searchQuery = ref('');
const publishBtnRef = ref(null);

// تعريف الـ Emit
const emit = defineEmits(['update-search', 'open-add-modal']);

// عند كتابة أي حرف، نرسله فوراً (أو عند الضغط على زر البحث)
const searchMedia = () => {
  emit('update-search', searchQuery.value);
};

const triggerPublisher = async () => {
  const btn = publishBtnRef.value; // الوصول للزر عبر الـ ref
  btn.disabled = true;
  btn.innerHTML = "⏳ جاري البدء...";

  try {
    const response = await api.post('/publisher/run');
    alert("✅ " + response.data.message);
  } catch (e) {
    alert("❌ خطأ: " + (e.response?.data?.message || "فشل الاتصال"));
  } finally {
    btn.disabled = false;
    btn.innerHTML = "🚀 تشغيل محرك النشر";
  }
};
</script>