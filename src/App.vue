<script setup>
import { ref, provide, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router' // 1. استيراد useRoute
import Navbar from './components/Navbar.vue'
import DownloadMonitor from './components/DownloadMonitor.vue'
import AddMediaModal from './components/AddMediaModal.vue'

const route = useRoute() // 2. تعريف الـ route

// 3. عرض الـ Navbar فقط إذا لم نكن في صفحة الـ login
const showNavbar = computed(() => route.path !== '/login')

const showModal = ref(false)
const globalSearch = ref('')
const isDarkMode = ref(false)

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
    <div
        class="min-h-screen p-1 bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 transition-colors duration-300">

        <Navbar v-if="showNavbar" @open-add-modal="showModal = true" @update-search="handleSearch" />

        <button v-if="showNavbar" @click="toggleTheme"
            class="fixed bottom-4 left-4 px-4 py-3 bg-primary text-white rounded-full z-50">
            <i class="fa" :class="isDarkMode ? 'fa-sun' : 'fa-moon'"></i>
        </button>

        <router-view :search="globalSearch" />

        <DownloadMonitor v-if="showNavbar" />
        <AddMediaModal v-if="showModal" @close="showModal = false" />
    </div>
</template>