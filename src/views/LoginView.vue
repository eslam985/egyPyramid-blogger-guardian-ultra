<template>
    <div class="min-h-screen flex items-center justify-center bg-gray-900 px-4">
        <div class="max-w-md w-full bg-gray-800 p-8 rounded-2xl shadow-2xl border border-gray-700">
            <h2 class="text-3xl font-bold text-white text-center mb-8">تسجيل الدخول</h2>

            <form @submit.prevent="handleLogin" class="space-y-6">
                <div>
                    <label class="block text-sm font-medium text-gray-400 mb-2">البريد الإلكتروني</label>
                    <input v-model="email" type="email" required
                        class="w-full px-4 py-3 bg-gray-900 border border-gray-700 rounded-lg text-white focus:ring-2 focus:ring-blue-500 focus:outline-none transition-all" />
                </div>

                <div>
                    <label class="block text-sm font-medium text-gray-400 mb-2">كلمة المرور</label>
                    <input v-model="password" type="password" required
                        class="w-full px-4 py-3 bg-gray-900 border border-gray-700 rounded-lg text-white focus:ring-2 focus:ring-blue-500 focus:outline-none transition-all" />
                </div>

                <button type="submit" :disabled="loading"
                    class="w-full py-3 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-lg transition-colors flex justify-center items-center">
                    <span v-if="loading">جاري التحقق...</span>
                    <span v-else>دخول</span>
                </button>
            </form>
        </div>
    </div>
</template>

<script>
import api from '../services/api';
export default {
    data() { return { email: '', password: '', loading: false }; },
    methods: {
        async handleLogin() {
            this.loading = true;
            const formData = new URLSearchParams();
            formData.append('username', this.email);
            formData.append('password', this.password);

            try {
                const res = await api.post('/login', formData);
                localStorage.setItem('user_token', res.data.access_token);
                this.$router.push('/');
            } catch (e) {
                alert('خطأ: بيانات الدخول غير صحيحة أو السيرفر لا يستجيب');
            } finally {
                this.loading = false;
            }
        }
    }
};
</script>