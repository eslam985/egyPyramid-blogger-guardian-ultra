<template>
  <div v-if="media" @click="goToDetails(media.id)"
    class="group relative flex flex-col rounded-2xl overflow-hidden border border-gray-200 dark:border-gray-700 bg-white dark:bg-secondary-dark shadow-card hover:shadow-xl transition-all duration-300 ease-out cursor-pointer hover:-translate-y-1">
    <!-- الجزء العلوي: الصورة والشارة -->
    <div class="relative aspect-[1/1] overflow-hidden bg-gray-100 dark:bg-gray-800">
      <img :src="media.poster_url || defaultPoster" :alt="media.title"
        class="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110" loading="lazy" />
      <!-- شارة التصنيف (فيلم / مسلسل) -->
      <span :class="[
        'absolute top-3 right-3 px-3 py-1.5 rounded-full text-xs font-bold uppercase tracking-wider text-white shadow-lg z-10 backdrop-blur-sm',
        media.category === 'tv' ? 'bg-blue-500/90' : 'bg-black/60'
      ]">
        {{ media.category === 'tv' ? 'مسلسل' : 'فيلم' }}
      </span>

      <!-- شارة السنة إذا كانت موجودة -->
      <span v-if="media.year"
        class="absolute bottom-3 left-3 px-2 py-1 rounded-md bg-black/50 text-white text-xs font-medium backdrop-blur-sm">
        {{ media.year }}
      </span>

      <!-- شارة التقييم إذا كانت موجودة -->
      <span v-if="media.rating"
        class="absolute top-3 left-3 px-2 py-1 rounded-md bg-yellow-500/90 text-white text-xs font-bold flex items-center gap-1 backdrop-blur-sm">
        <i class="fa fa-star text-yellow-200"></i>
        {{ media.rating }}
      </span>
    </div>

    <!-- الجزء السفلي: المحتوى والأزرار -->
    <div class="p-2 flex-1 flex flex-col text-center">
      <h3
        class="text-xs font-bold text-gray-900 dark:text-white line-clamp-2 group-hover:text-primary transition-colors duration-300 ">
        {{ media.title }}
      </h3>

      <!-- وصف مختصر إذا كان متوفراً -->
      <p v-if="media.overview" class="text-sm text-gray-600 dark:text-gray-400 line-clamp-2 mb-3 text-right">
        {{ media.overview }}
      </p>
    </div>

    <!-- شريط الأزرار -->
    <div @click.stop
      class="flex justify-between items-center gap-4 p-2 border-t border-gray-100 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">

      <button @click="goToDetails(media.id)"
        class="w-8 h-8 rounded-xl flex items-center justify-center text-[#708090] hover:bg-primary-dark hover:text-white transition-all duration-200 hover:scale-110 active:scale-95 shadow-md"
        title="تعديل">
        <i class="fa fa-edit"></i>
      </button>

      <button @click="$emit('delete', media.id)"
        class="w-8 h-8 rounded-xl flex items-center justify-center text-[#708090] hover:bg-red-600 hover:text-white transition-all duration-200 hover:scale-110 active:scale-95 shadow-md"
        title="حذف">
        <i class="fa fa-trash"></i>
      </button>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router';
// أزلنا import api لأنه لم يعد مستخدماً هنا
const emit = defineEmits(['delete']); // تم إبقاء 'delete' فقط
const props = defineProps({
  media: {
    type: Object,
    required: true
  },
  defaultPoster: {
    type: String,
    default: 'https://res.cloudinary.com/dbahqgo8j/image/upload/q_auto,f_auto,w_300,h_200,c_fill/blogger/logo.webp'
  }
});

const router = useRouter();
const goToDetails = (id) => {
  router.push(`/media/${id}`);
};
</script>