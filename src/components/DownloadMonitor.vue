<template>
    <div>
        <button @click="showModal = true" class="btn-add">➕ مهمة تحميل جديدة</button>

        <div class="modal-overlay" v-if="showModal" @click.self="showModal = false">
            <div class="modal-content">
                <header class="modal-header">
                    <h3>إضافة مهمة سحب جديدة</h3>
                    <span class="close-btn" @click="showModal = false">&times;</span>
                </header>

                <form @submit.prevent="submitTask">
                    <div class="form-group">
                        <input v-model="taskUrl" type="text" placeholder="رابط المصدر" required class="form-control">
                    </div>
                    <div class="form-group">
                        <input v-model="taskName" type="text" placeholder="اسم المهمة" required class="form-control">
                    </div>
                    <button type="submit" class="btn-primary">ابدأ السحب والمعالجة</button>
                </form>
            </div>
        </div>

        <div id="progress-container" v-if="activeTasks.length > 0">
            <div v-for="task in activeTasks" :key="task.id" class="progress-item"
                :class="{ 'is-uploading': task.status_message.includes('جاري الرفع') }">

                <span class="task-name">{{ task.task_name }}</span>:
                <span class="status-text">{{ task.status_message }}</span>
                <span class="percent">({{ task.progress_percent }}%)</span>

                <div class="mini-progress-bar">
                    <div class="fill" :style="{ width: task.progress_percent + '%' }"></div>
                </div>
            </div>
        </div>
    </div>
</template>
<style scoped>
.progress-item {
    padding: 12px;
    margin-bottom: 8px;
    background: linear-gradient(135deg, #1a1a1a 0%, #000 100%);
    border: 1px solid #daa52033;
    border-radius: 8px;
    color: #daa520;
}

.is-uploading .status-text {
    color: #00ffcc;
    /* لون مختلف لمرحلة الرفع */
    animation: blinker 1.5s linear infinite;
}

.mini-progress-bar {
    height: 4px;
    background: #333;
    margin-top: 8px;
    border-radius: 2px;
    overflow: hidden;
}

.fill {
    height: 100%;
    background: #daa520;
    transition: width 0.5s ease;
}

@keyframes blinker {
    50% {
        opacity: 0.3;
    }
}
</style>
<script setup>
import { ref, onMounted, onUnmounted } from 'vue';
import { supabaseClient } from '../services/supabase.js'

const showModal = ref(false); // التحكم في ظهور المودال
const taskUrl = ref('');
const taskName = ref('');
const activeTasks = ref([]);

const submitTask = async () => {
    const { error } = await supabaseClient.from('download_tasks').insert([{
        source_url: taskUrl.value,
        task_name: taskName.value,
        status: 'idle',
        status_message: 'Waiting for Beast...'
    }]);

    if (!error) {
        alert("تم الإرسال!");
        showModal.value = false; // إغلاق المودال بعد الإرسال
        taskUrl.value = ''; // تصفير الحقول
        taskName.value = '';
    }
};

// دالة التحديث (بدل updateDownloadProgress)
const fetchTasks = async () => {
    const { data } = await supabaseClient.from('download_tasks').select('*');
    activeTasks.value = data || [];
};

let interval;
onMounted(() => {
    fetchTasks();
    interval = setInterval(fetchTasks, 3000); // التحديث كل 3 ثواني
});

onUnmounted(() => clearInterval(interval)); // تنظيف الذاكرة لما الـ Component يختفي
</script>
