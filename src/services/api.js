// src/services/api.js
import axios from 'axios';

const api = axios.create({
    baseURL: 'http://localhost:7860/api', // رابط مباشر
    auth: {
        username: 'ee17172@gmail.com',
        password: 'Eslamsayed@98'
    }
});

export default api;