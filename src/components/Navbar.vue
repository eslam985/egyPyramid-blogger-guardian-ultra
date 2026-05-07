<template>

  <nav class=" max-w-500 mx-auto grid  grid-cols-1 md:grid-cols-2 gap-4 p-4 shadow-md  z-50 sticky top-px my-card">





    <div class=" flex gap-4">
      <router-link to="/database"
        class="bg-gray-700 text-white px-4 py-2 rounded hover:bg-gray-800 transition flex items-center gap-2">
        <i class="fa fa-database"></i> قاعدة البيانات
      </router-link>

      <button class=" relative z-60 bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600 cursor-pointer"
        @click="triggerOpen">
        <i class="fa fa-plus"></i> إضافة عمل
      </button>


      <button class="bg-[#ea580c] text-white px-4 py-0 rounded hover:bg-yellow-600 cursor-pointer"
        @click="triggerPublisher">
        🚀 تشغيل محرك النشر
      </button>
      <button :class="isWorkerRunning ? 'bg-red-600 hover:bg-red-700' : 'bg-green-600 hover:bg-green-700'"
        class="text-white px-4 py-0 rounded cursor-pointer transition-all flex items-center gap-2 font-bold"
        @click="toggleWorker" :disabled="loadingWorker">
        <span v-if="loadingWorker">🔄</span>
        <span v-else>{{ isWorkerRunning ? '🛑 إيقاف الوحش' : '🦾 تشغيل الوحش' }}</span>
      </button>
      <button @click="logout" class="bg-red-500 text-white px-4 py-2 rounded">
        تسجيل خروج
      </button>
    </div>

    <div class="flex flex-[0_1_500px] gap-4">
      <form @submit.prevent="searchMedia" class="flex flex-row-reverse w-full">

        <button type="submit"
          class="px-5 py-2.5 bg-primary text-white border border-primary rounded-l-lg hover:bg-primary-dark transition-colors flex items-center justify-center">
          <i class="fa fa-search"></i>
        </button>

        <input v-model="searchQuery" type="text" placeholder="ابحث..."
          class="w-full px-4 py-2.5 border border-gray-300 dark:border-gray-600 rounded-r-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 transition-all focus:outline-none focus:border-primary focus:ring-4 focus:ring-blue-500/10">

      </form>
      <div
        class="font-bold max-w-50 text-3xl text-yellow-500 tracking-[-0.5px] whitespace-nowrap px-4 py-1 rounded-lg shadow-md bg-[linear-gradient(135deg,#8a8000_0,#000000_80%)]">

        <a href="/"> EGY PYRMID</a>

      </div>
    </div>

  </nav>

</template>

<script setup>
import { ref } from 'vue';
import api from '../services/api';
import { onMounted } from 'vue'; // ضيف onMounted هنا

const isWorkerRunning = ref(true); // بنفترض إنه شغال في البداية
const loadingWorker = ref(false);

// دالة لجلب حالة الووركر الحقيقية عند فتح الصفحة
const getStatus = async () => {
  try {
    const res = await api.get('/api/worker/status');
    isWorkerRunning.value = !res.data.should_stop;
  } catch (e) {
    console.error("Status check failed");
  }
};

const toggleWorker = async () => {
  loadingWorker.value = true;
  const endpoint = isWorkerRunning.value ? '/api/worker/stop' : '/api/worker/start';
  try {
    const res = await api.post(endpoint);
    isWorkerRunning.value = !isWorkerRunning.value; // اعكس الحالة
    alert("✅ " + res.data.message);
  } catch (e) {
    alert("❌ فشل في التحكم في الووركر");
  } finally {
    loadingWorker.value = false;
  }
};

// أول ما المكون يفتح، شيك على الحالة
onMounted(() => {
  getStatus();
});
const searchQuery = ref('');
const isPublishing = ref(false);
const emit = defineEmits(['update-search', 'open-add-modal']);
import { useRouter } from 'vue-router';
const router = useRouter();

const logout = () => {
  localStorage.removeItem('user_token');
  router.push('/login');
};
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