<script setup>
import { ref, provide, onMounted } from 'vue' // أضفنا onMounted
import Navbar from './components/Navbar.vue'
import DownloadMonitor from './components/DownloadMonitor.vue'
import AddMediaModal from './components/AddMediaModal.vue'

const showModal = ref(false)
const globalSearch = ref('')
const isDarkMode = ref(false) // المنطق الجديد هنا

const toggleTheme = () => {
    isDarkMode.value = !isDarkMode.value;
    document.documentElement.classList.toggle('dark-mode');
    localStorage.setItem('theme', isDarkMode.value ? 'dark' : 'light');
};

onMounted(() => {
    if (localStorage.getItem('theme') === 'dark') {
        isDarkMode.value = true;
        document.documentElement.classList.add('dark-mode');
    }
});

const handleSearch = (q) => { globalSearch.value = q }
provide('searchQuery', globalSearch) 
</script>

<template>
  <div class="app-container">
    <Navbar @open-add-modal="showModal = true" @update-search="handleSearch" />
    
    <button @click="toggleTheme" class="theme-toggle-btn">
        <i class="fa" :class="isDarkMode ? 'fa-sun' : 'fa-moon'"></i>
    </button>

    <router-view :search="globalSearch" />
    <DownloadMonitor />
    <AddMediaModal v-if="showModal" @close="showModal = false" />
  </div>
</template>