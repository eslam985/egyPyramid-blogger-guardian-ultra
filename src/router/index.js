import { createRouter, createWebHashHistory } from 'vue-router';
import HomeView from '../views/HomeView.vue';
import MediaDetails from '../views/MediaDetails.vue';

const routes = [
  { path: '/', name: 'Home', component: HomeView },
  { path: '/media/:id', name: 'MediaDetails', component: MediaDetails, props: true }
];

const router = createRouter({
  history: createWebHashHistory(), // أفضل لبيئة Hugging Face و static hosting
  routes
});

export default router;