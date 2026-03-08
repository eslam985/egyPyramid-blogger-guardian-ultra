<template>
  <div
    class="rounded-2xl overflow-hidden border border-gray-200 dark:border-gray-700 bg-white dark:bg-secondary-dark shadow-card">
    <!-- الجزء العلوي: صورة Skeleton -->
    <div class="relative aspect-[3/2] overflow-hidden bg-gray-200 dark:bg-gray-700">
      <!-- يمكن إضافة تأثير shimmer هنا (اختياري) -->
      <div class="absolute inset-0 shimmer" v-if="useCustomShimmer"></div>
    </div>

    <!-- الجزء السفلي: محتوى وأزرار Skeleton -->
    <div class="p-4">
      <!-- سطر العنوان -->
      <div class="h-5 bg-gray-200 dark:bg-gray-700 rounded w-3/4 mb-2 animate-pulse"></div>
      <!-- سطر الوصف (اختياري) -->
      <div class="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/2 mb-3 animate-pulse"></div>
    </div>

    <!-- شريط الأزرار -->
    <div
      class="flex justify-around items-center p-3 border-t border-gray-100 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
      <div class="w-10 h-10 bg-gray-200 dark:bg-gray-700 rounded-xl animate-pulse"></div>
      <div class="w-10 h-10 bg-gray-200 dark:bg-gray-700 rounded-xl animate-pulse"></div>
      <div class="w-10 h-10 bg-gray-200 dark:bg-gray-700 rounded-xl animate-pulse"></div>
    </div>
  </div>
</template>

<script setup>
// يمكنك إضافة خاصية للتحكم في نوع التأثير
defineProps({
  useCustomShimmer: {
    type: Boolean,
    default: false // نستخدم animate-pulse كافتراضي
  }
});
</script>

<style scoped>
/* تأثير shimmer مخصص - اختياري */
@keyframes shimmer {
  0% {
    transform: translateX(-100%);
  }

  100% {
    transform: translateX(100%);
  }
}

.shimmer {
  background: linear-gradient(90deg,
      transparent 0%,
      rgba(255, 255, 255, 0.2) 50%,
      transparent 100%);
  animation: shimmer 1.5s infinite;
  pointer-events: none;
}

/* يمكن إضافة نسخة داكنة من الـ shimmer */
.dark .shimmer {
  background: linear-gradient(90deg,
      transparent 0%,
      rgba(255, 255, 255, 0.05) 50%,
      transparent 100%);
}
</style>