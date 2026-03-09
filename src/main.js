import { createApp } from 'vue'
import App from './App.vue'
import router from './router' 
import 'sweetalert2/dist/sweetalert2.min.css' // استايل التنبيهات
import './assets/style.css' // الاستايل بتاعك (خلف الاستايل التاني عشان لو حبيت تعدل عليه)

createApp(App).use(router).mount('#app')