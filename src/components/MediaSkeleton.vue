<template>
  <div class="skeleton-card">
    <div class="skeleton-image"></div>
    <div class="skeleton-title"></div>
    <div class="skeleton-actions"></div>
  </div>
</template>

<style scoped>
.skeleton-card {
  background: #f0f0f0;
  border-radius: 12px;
  padding: 10px;
  animation: pulse 1.5s infinite;
}
.skeleton-image { height: 200px; background: #e0e0e0; border-radius: 8px; }
.skeleton-title { height: 20px; width: 80%; margin: 15px auto; background: #e0e0e0; }
.skeleton-actions { height: 30px; background: #e0e0e0; margin-top: 10px; }

@keyframes pulse {
  0% { opacity: 0.6; }
  50% { opacity: 1; }
  100% { opacity: 0.6; }
}
</style>