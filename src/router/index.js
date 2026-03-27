import { createRouter, createWebHashHistory } from 'vue-router';
import HomeView from '../views/HomeView.vue';
import MediaDetails from '../views/MediaDetails.vue';
import LoginView from '../views/LoginView.vue';
import DatabaseView from '../views/DatabaseView.vue'; // استيراد الصفحة الجديدة

const routes = [
  { path: '/', name: 'Home', component: HomeView },
  { path: '/media/:id', name: 'MediaDetails', component: MediaDetails, props: true },
  { path: '/login', name: 'Login', component: LoginView },
  { path: '/database', name: 'Database', component: DatabaseView } // إضافة المسار
];

const router = createRouter({
  history: createWebHashHistory(),
  routes
});

// 3. الحارس الأمني (Navigation Guard)
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('user_token');

  // إذا كان المستخدم لا يملك توكن ويحاول دخول صفحة غير الـ login
  if (to.name !== 'Login' && !token) {
    next({ name: 'Login' });
  }
  // إذا كان المستخدم مسجل دخول ويحاول العودة لصفحة الـ login
  else if (to.name === 'Login' && token) {
    next({ name: 'Home' });
  }
  else {
    next();
  }
});

export default router;