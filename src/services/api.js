// src/services/api.js
import axios from 'axios';

const api = axios.create({
    // استخدم مساراً نسبياً فقط، والمتصفح سيكمله تلقائياً
    baseURL: '/api', 
    auth: {
        username: 'ee17172@gmail.com',
        password: 'Eslamsayed@98'
    }
});

export default api;