<template>
  <div class="media-card" v-if="media" :id="'media-' + media.id">
    <div class="card-image">
      <img :src="media.poster_url || defaultPoster" :alt="media.title">
      <span class="category-badge">{{ media.category === 'tv' ? 'مسلسل' : 'فيلم' }}</span>
    </div>
    <div class="card-content">
      <h3>{{ media.title }}</h3>
      <p class="story-preview">{{ media.story ? media.story.slice(0, 100) : 'لا يوجد وصف' }}...</p>

      <div class="card-meta">
        <span><i class="fa fa-calendar"></i> {{ media.year }}</span>
      </div>

      <div class="card-actions">
        <button @click="$emit('edit', media.id)" class="btn-edit"><i class="fa fa-edit"></i></button>

        <button @click="toggleBlogger(media.blogger_post_id, media.id)" class="btn-blogger"
          :class="media.blogger_status === 'published' ? 'is-live' : 'is-draft'">
          <i class="fab fa-blogger"></i>
        </button>

        <button @click="$emit('delete', media.id)" class="btn-delete"><i class="fa fa-trash"></i></button>
      </div>
    </div>
  </div>
</template>

<script setup>
import api from '../services/api';

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
/* التنسيقات هنا */
</style>