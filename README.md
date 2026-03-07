---
title: EgyPyramid Guardian Ultra
emoji: 🛡️
colorFrom: blue
colorTo: red
sdk: docker
app_file: app.py
pinned: false
---

# egyPyramid-blogger-guardian-ultra

---

title: EgyPyramid Guardian Ultra
emoji: 🛡️
colorFrom: blue
colorTo: red
sdk: docker
app_file: app.py
pinned: false

---

# 🚀 EgyPyramid Guardian Ultra

نظام أتمتة متكامل لإدارة وتحميل ونشر المحتوى المرئي.

## 🏗️ هندسة النظام (System Architecture)

يعتمد النظام على بنية **Event-Driven** تتكون من ثلاث طبقات رئيسية:

- **طبقة التحكم (Frontend):** واجهة **Vue.js** لإضافة المهام.
- **طبقة المعالجة (Worker):** بيئة **Google Colab/Kaggle** لتنفيذ العمليات الثقيلة.
- **طبقة النشر (Publisher):** محرك **Blogger API** للنشر التلقائي.

---

## 🛠️ التكنولوجيات المستخدمة

| المكون       | التقنية               |
| :----------- | :-------------------- |
| **Frontend** | Vue.js (Vite)         |
| **Backend**  | Python (FastAPI)      |
| **Database** | Supabase (PostgreSQL) |
| **Workers**  | Google Colab / Kaggle |

---

## ⚙️ كيف يعمل التدفق (Work Flow)

1. **الطلب:** إضافة رابط -> `download_tasks` (Supabase).
2. **المعالجة:** Worker يسحب الرابط -> تحليل بالذكاء الاصطناعي -> تحميل.
3. **النشر:** تجميع البيانات في قالب HTML -> النشر التلقائي عبر **Blogger API**.
