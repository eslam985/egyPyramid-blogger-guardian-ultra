<template>
  <div class="skeleton-card">
    <div class="skeleton-shimmer skeleton-image"></div>
    <div class="skeleton-shimmer skeleton-title"></div>
    <div class="skeleton-shimmer skeleton-actions"></div>
  </div>
</template>

<style scoped>
.skeleton-card {
  background: #ffffff;
  border-radius: 12px;
  padding: 10px;
  border: 1px solid #eee;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.skeleton-shimmer {
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite linear;
}

.skeleton-image {
  height: 200px;
  border-radius: 8px;
}

.skeleton-title {
  height: 20px;
  width: 80%;
  border-radius: 4px;
}

.skeleton-actions {
  height: 30px;
  border-radius: 6px;
}

@keyframes shimmer {
  0% {
    background-position: 200% 0;
  }

  100% {
    background-position: -200% 0;
  }
}
</style>