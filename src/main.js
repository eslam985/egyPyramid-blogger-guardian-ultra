import { createApp } from 'vue'
import App from './App.vue'
import router from './router' // استيراد الراوتر
import './assets/style.css'

createApp(App).use(router).mount('#app')