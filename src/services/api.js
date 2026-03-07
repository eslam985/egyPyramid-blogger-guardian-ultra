// src/services/api.js
import axios from 'axios';

const api = axios.create({
    baseURL: '/api'
});

// إضافة "مستمع" يضيف التوكن تلقائياً لكل طلب
api.interceptors.request.use((config) => {
    const token = localStorage.getItem('user_token'); // التوكن الذي سيأتي بعد تسجيل الدخول
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});
// في ملف api.js
api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response && error.response.status === 401) {
            // التوكن انتهى أو غير صالح
            localStorage.removeItem('user_token');
            window.location.href = '/#/login'; // تحويل للـ login
        }
        return Promise.reject(error);
    }
);
export default api;