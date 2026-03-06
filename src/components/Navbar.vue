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
      <button class="btn-add" @click="$emit('open-add-modal')">
        <i class="fa fa-plus"></i> إضافة عمل 
      </button>
      
      <button class="publish-btn" @click="triggerPublisher" :disabled="isPublishing">
        {{ isPublishing ? '⏳ جاري النشر...' : '🚀 تشغيل محرك النشر' }}
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
</script>