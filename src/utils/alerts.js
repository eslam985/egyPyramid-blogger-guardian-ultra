// هذا الملف سيكون "المركز الموحد" لجميع تنبيهات مشروعك.

// src/utils/alerts.js
import Swal from 'sweetalert2';

export const notifySuccess = (text) => {
    Swal.fire({ icon: 'success', title: 'تمت العملية', text, confirmButtonText: 'حسناً' });
};

export const notifyError = (text) => {
    Swal.fire({ icon: 'error', title: 'خطأ', text, confirmButtonText: 'إغلاق' });
};

export const notifyLoading = (text = 'جاري المعالجة...') => {
    return Swal.fire({
        title: text,
        allowOutsideClick: false,
        didOpen: () => Swal.showLoading()
    });
};

// src/utils/alerts.js
export const confirmAction = (text) => {
    return Swal.fire({
        title: 'هل أنت متأكد؟',
        text: text,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#d33',
        cancelButtonColor: '#3085d6',
        confirmButtonText: 'نعم، قم بالحذف',
        cancelButtonText: 'إلغاء'
    });
};