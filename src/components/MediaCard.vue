<template>
  <div class="media-card" v-if="media" @click="goToDetails(media.id)">
    <div class="card-image">
      <img :src="media.poster_url || defaultPoster" :alt="media.title">
      <span class="category-badge">{{ media.category === 'tv' ? 'مسلسل' : 'فيلم' }}</span>
    </div>

    <div class="card-content">
      <h3>{{ media.title }}</h3>
    </div>

    <div class="card-actions" @click.stop>
      <button @click="goToDetails(media.id)" class="btn-action edit" title="تعديل">
        <i class="fa fa-edit"></i>
      </button>

      <button @click="toggleBlogger(media.blogger_post_id, media.id)" class="btn-action blogger"
        :class="media.blogger_status === 'published' ? 'is-live' : 'is-draft'">
        <i class="fab fa-blogger"></i>
      </button>

      <button @click="$emit('delete', media.id)" class="btn-action delete" title="حذف">
        <i class="fa fa-trash"></i>
      </button>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'; // 1. استيراد الراوتر
import api from '../services/api';


const router = useRouter(); // 2. تعريف الراوتر
// 3. دالة التنقل
const goToDetails = (id) => {
  router.push(`/media/${id}`);
};
const toggleBlogger = async (postId, mediaId) => {
  if (!postId || postId === 'None') return alert("⚠️ لا يوجد ID لهذا المقال!");

  try {
    const response = await api.post(`/blogger/toggle/${postId}`);
    if (response.data.status === "success") {
      const isLive = response.data.new_status === 'live';
      alert(`✅ الحالة الجديدة: ${isLive ? 'منشور' : 'مسودة'}`);
      // قم بتحديث البيانات هنا لإعادة رسم الحالة
    }
  } catch (e) {
    alert("❌ فشل الاتصال بالسيرفر");
  }
};
// الـ script هنا خارج الـ template تماماً
defineProps(['media']);
const defaultPoster = 'https://res.cloudinary.com/dbahqgo8j/image/upload/q_auto,f_auto,w_300,h_200,c_fill/blogger/logo.webp';
</script>

<style scoped>


.media-card {
  background: var(--color-surface);
  /* تأكد أن المتغيرات معرفة */
  border-radius: 12px;
  overflow: hidden;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  flex-direction: column;
  border: 1px solid rgba(0, 0, 0, 0.1);
  cursor: pointer;

}

.media-card:hover {
  transform: translateY(-8px);
  box-shadow: 0 12px 24px rgba(0, 0, 0, 0.15);
  transform: scale(1.02);
}

.card-image {
  position: relative;
  aspect-ratio: 2/3;
}

.card-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.category-badge {
  position: absolute;
  top: 10px;

  background: rgba(0, 0, 0, 0.7);
  color: white;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 0.8rem;
}

.card-content {
  padding: 12px;
  text-align: center;
}

.card-content h3 {
  margin: 0;
  font-size: 1rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-actions {
  display: flex;
  justify-content: space-around;
  padding: 10px;
  border-top: 1px solid #eee;
}

.btn-action {
  background: none;
  border: none;
  padding: 8px;
  cursor: pointer;
  border-radius: 50%;
  transition: background 0.2s;
  color: #000;
}

.btn-action:hover {
  background: #e0e0e0;
}
</style>