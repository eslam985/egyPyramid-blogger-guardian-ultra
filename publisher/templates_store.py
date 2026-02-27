# --- 2. قالب الـ HTML المطور للأفلام (فيديو واحد) ---
HTML_TEMPLATE = r"""
<meta name="theme-color" content="#1c4167">
<meta name="msapplication-navbutton-color" content="#1c4167">
<meta name="apple-mobile-web-app-status-bar-style" content="#1c4167">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Language" content="ar-eg">

<meta name="robots" content="follow, index, max-snippet:-1, max-video-preview:-1, max-image-preview:large" />
<meta name="revisit-after" content="1 hour">

<meta property="og:title" content="{{TITLE}}" />
<meta property="og:description" content="{{SEARCH_DESCRIPTION}}" />
<meta property="og:image" content="{{POSTER_URL}}" />
<meta property="og:image:width" content="1200" />
<meta property="og:image:height" content="630" />
<meta property="og:type" content="video.movie" />
<meta property="og:site_name" content="Egy Pyramid" />
<meta property="video:duration" content="{{DURATION_ISO}}" />
<meta property="og:rating" content="{{RATING}}" />

<meta name="twitter:label1" content="التقييم" />
<meta name="twitter:data1" content="{{RATING}}/10" />
<meta name="twitter:label2" content="مدة الفيلم" />
<meta name="twitter:data2" content="{{RUNTIME}}" />

<meta itemprop="name" content="{{TITLE}}">
<meta itemprop="description" content="{{SEARCH_DESCRIPTION}}">
<meta itemprop="image" content="{{POSTER_URL}}">
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "NewsArticle",
  "headline": "{{TITLE}}",
  "description": "{{SEARCH_DESCRIPTION}}",
  "image": ["{{POSTER_URL}}"],
  "datePublished": "{{CURRENT_DATE}}",
  "dateModified": "{{CURRENT_DATE}}",
  "author": {
    "@type": "Person",
    "name": "Egy Pyramid Admin"
  },
  "publisher": {
    "@type": "Organization",
    "name": "Egy Pyramid",
    "logo": {
      "@type": "ImageObject",
      "url": "{{LOGO_URL}}"
    }
  },
  "mainEntityOfPage": {
    "@type": "WebPage",
    "@id": "https://egy-pyramid-drama.blogspot.com"
  }
}
</script>
<style>
 .post-body h1 {
  color: #e74c3c;
  text-align: center;
  margin: 1rem 0;
  font-size: clamp(1rem, 2.5vw, 2.5rem);
 }


 .row {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  flex-direction: row-reverse;
  gap: 1rem;
  padding-bottom: 40px;
  margin-bottom: 40px;
  border-bottom: 1px solid var(--color-border-primary);
 }

 .info-container {
  width: 68%;
  border-radius: 12px;
  border: 1px solid var(--color-border-secondary);
  box-shadow: 0 4px 15px var(--color-shadow);
  display: flex;
  flex-direction: column;
  gap: 1rem;
 }

 /* ================================================= */
 /* POSTER & SEPARATOR - الصورة الرئيسية */
 /* ================================================= */
 .separator {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30%;
  text-align: center;
 }

 .separator img {
  width: 100%;
  height: auto;
  max-width: 350px;
  border-radius: 12px;
  box-shadow: 0 4px 15px var(--color-shadow);
  border: 1px solid var(--color-border-secondary);
  display: block;
  margin: 0 auto;
 }

 .separator img:hover {
  transform: scale(1.02);
 }

 /* ================================================= */
 /* SMART LINK AD - إعلان سمارت لينك */
 /* ================================================= */
 .smartlink-ad {
  text-align: center;
  padding: 30px;
  border-radius: 15px;
  border: 2px solid var(--color-primary);
  margin: 30px 0;
  box-shadow: 0 10px 20px rgba(0, 0, 0, 0.3);
  background-color: var(--color-bg-secondary);
 }

 .smartlink-title {
  font-size: 22px;
  color: #D4AF37;
  margin-bottom: 25px;
  font-weight: bold;
 }

 .smartlink-btn {
  display: inline-block;
  width: 90%;
  max-width: 350px;
  background: linear-gradient(145deg, #D4AF37, #B8860B);
  color: #000 !important;
  padding: 18px;
  border-radius: 50px;
  text-decoration: none;
  font-weight: 900;
  font-size: 18px;
  transition: all 0.3s ease;
  box-shadow: 0 4px 15px rgba(212, 175, 55, 0.4);
 }

 .smartlink-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(212, 175, 55, 0.6);
 }

 .smartlink-backup {
  display: inline-block;
  width: 90%;
  max-width: 350px;
  background: var(--color-bg-card);
  color: var(--color-text-primary);
  padding: 16px;
  border-radius: 50px;
  text-decoration: none;
  font-weight: bold;
  font-size: 16px;
  border: 1px solid var(--color-primary);
  margin-top: 10px;
  transition: all 0.3s ease;
 }

 .smartlink-backup:hover {
  background: var(--color-primary);
  color: var(--color-text-light);
 }

 /* ================================================= */
 /* STORY SECTION - قسم القصة */
 /* ================================================= */
 .story-section {
  padding: 8px 16px;
  border-right: 5px solid var(--color-primary);
  background-color: var(--color-bg-card);
  border-radius: 8px;
 }

 .story-title {
  margin: 0 0 10px 0;
  color: var(--color-primary);
  font-size: 1.2rem;
 }

 .story-text {
  font-style: italic;
  line-height: 1.6;
  margin: 0;
  font-size: clamp(12px, 3.6vw, 1rem);
 }

 /* ================================================= */
 /* INFO TABLE - جدول المعلومات */
 /* ================================================= */
 .info-table {
  background: var(--color-bg-primary);
  color: var(--color-text-primary);
  border: 1px solid var(--color-border-secondary);
  border-radius: 10px;
  padding: 0 16px;
 }

 .info-table table {
  width: 100%;
  border-collapse: collapse;
 }


 .info-table td:first-child {
  font-weight: bold;
  color: var(--color-primary);
  width: 40%;
 }


 /* ================================================= */
 /* VIDEO CONTAINER - حاوية الفيديو */
 /* ================================================= */
 .video-container {
  margin: auto;
  margin-bottom: 40px;
  width: 800px;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.15);
 }

 /* ================================================= */
 /* PLAYER HEADER - عنوان المشغل */
 /* ================================================= */
 .player-header {
  background: var(--color-footer-bg);
  padding: 12px 4px;
  color: var(--color-text-light);
  text-align: center;
  font-weight: bold;
  font-size: clamp(.9rem, 2.5vw, 1.9rem);
  border-bottom: 1px solid var(--color-border-primary);
 }

 .current-episode {
  color: var(--color-text-secondary);
  font-weight: bold !important;
 }

 /* ================================================= */
 /* SERVER BUTTONS - أزرار السيرفرات */
 /* ================================================= */
.server-buttons {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
  background: var(--color-footer-bg);
  padding: 12px 0;
 }

 .server-btn {
  cursor: pointer;
  color: #fff; /* تأكيد اللون الأبيض للنص */
  border: none;
  padding: 10px 20px;
  border-radius: 6px;
  font-weight: bold;
  font-size: 14px;
  transition: all 0.3s ease;
  min-width: 120px;
  opacity: 0.8; /* جعل الأزرار غير النشطة باهتة قليلاً */
 }

 .server-btn:hover {
  opacity: 1;
  transform: translateY(-2px);
  filter: brightness(1.2);
 }

 /* تخصيص ألوان السيرفرات */
 .server-btn-1 { background-color: #8e44ad !important; } /* Voe بنفسجي */
 .server-btn-2 { background-color: #e74c3c !important; } /* VidTube أحمر */
 .server-btn-3 { background-color: #f39c12 !important; } /* OK برتقالي */
 .server-btn-4 { background-color: #2980b9 !important; } /* VK أزرق */
 .extra-server { background-color: #27ae60 !important; } /* أي سيرفر إضافي أخضر */

 /* لون حالة النشاط (Active) - الحقيقة الصارمة: نستخدم !important لإلغاء ألوان السيرفرات المحددة أعلاه */
 .server-btn.active {
  background-color: var(--color-secondary) !important; /* اللون الذهبي أو المارون المعتاد في قالبك */
  opacity: 1;
  box-shadow: 0 0 15px var(--color-secondary);
  border: 2px solid #fff; /* تمييز إضافي للزر المختار */
 }

 /* ================================================= */
 /* PLAYER - مشغل الفيديو */
 /* ================================================= */
.player {
    width: 100%;
    background: #000;
    border: 1px solid var(--color-primary);
    border-top: none;
    position: relative;
    aspect-ratio: 16 / 9;
    overflow: hidden;
}
 #video-player-frame {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  border: none;
 }

 /* ================================================= */
 /* VIDEO CONTROLS - تحكمات الفيديو */
 /* ================================================= */
 .video-controls {
  display: flex;
  justify-content: center;
  gap: 15px;
  background: var(--color-footer-bg);
  padding: 15px;
  border: 1px solid var(--color-border-primary);
  flex-wrap: wrap;
 }

 .control-btn {
  cursor: pointer;
  background: var(--color-primary);
  color: var(--color-text-light);
  border: none;
  padding: 12px 25px;
  border-radius: 6px;
  font-weight: bold;
  font-size: 14px;
  transition: all 0.3s ease;
  min-width: 160px;
 }

 .control-btn:hover {
  background: var(--color-button-hover);
  transform: translateY(-2px);
 }

 .btn-skip {
  background: var(--color-control-secondary);
 }

 .btn-skip:hover {
  background: #e67e22;
 }

 /* ================================================= */
 /* DOWNLOAD SECTION - قسم التحميل */
 /* ================================================= */
 .download-section {
  background-color: var(--color-footer-bg);
  display: flex;
  justify-content: space-around;
  padding: 20px;
  border-top: none;
  gap: 15px;
 }

 .download-btn {
  flex: 1;
  max-width: 300px;
  display: inline-block;
  padding: 15px 35px;
  background: linear-gradient(180deg, #315482, #cc0000);
  color: white !important;
  color: white;
  font-weight: bold;
  font-size: clamp(.5rem, 2vw, .9rem);
  text-align: center;
  border-radius: 5px;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
  cursor: pointer;
  animation: pulse 1.5s infinite;
 }

 .download-btn:hover {
  background: #219653;
  transform: translateY(-2px);
  box-shadow: 0 5px 15px rgba(39, 174, 96, 0.3);
 }

 .theater-btn {
  background: var(--color-secondary);
  color: white;
  padding: 16px 30px;
  border-radius: 8px;
  border: none;
  cursor: pointer;
  font-weight: bold;
  font-size: clamp(.5rem, 2vw, .9rem);
  text-align: center;
  transition: all 0.3s ease;
  flex: 1;
  max-width: 300px;
 }

 .theater-btn:hover {
  background: #0d4550;
  transform: translateY(-2px);
  box-shadow: 0 5px 15px rgba(16, 82, 95, 0.3);
 }

 /* ================================================= */
 /* EPISODES SECTION - قسم الحلقات */
 /* ================================================= */
 .episodes-title {
  color: var(--color-text-light) !important;
  text-align: center;
  margin: 0 !important;
  background-color: var(--color-footer-bg);
  padding: 20px;
  font-size: 1.3rem;
  border-bottom: 1px solid var(--color-border-primary);
  border-top: 1px solid var(--color-border-primary);
 }

 .episodes-container {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: center;
  align-items: center;
  background: var(--color-footer-bg);
  color: var(--color-text-light);
  padding: 20px;
  border-radius: 0 0 12px 12px;
  border-top: none;
 }

 /* ================================================= */
 /* EPISODE BUTTONS - أزرار الحلقات */
 /* ================================================= */
 .ep-btn {
  cursor: pointer;
  background: #1a73e8;
  color: #fff;
  border: none;
  width: 50px;
  height: 50px;
  line-height: 50px;
  padding: 0;
  border-radius: 50%;
  text-align: center;
  font-weight: bold;
  transition: all 0.3s ease;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
  display: inline-block;
  opacity: .5;
  user-select: none;
  -webkit-user-select: none;
 }

 .ep-btn:hover {
  background: var(--color-button-hover);
  transform: translateY(-3px) scale(1.1);
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
  opacity: 1;
 }

 .ep-btn.active {
  background: #e74c3c !important;
  color: #fff !important;
  transform: scale(1.1);
  border: 2px solid #fff;
  width: 55px;
  height: 55px;
  line-height: 50px;
  opacity: 1;
  box-shadow: 0 0 15px rgba(231, 76, 60, 0.5);
 }

 .ep-btn.watched {
  background: var(--color-episode-watched) !important;
  opacity: 0.7;
 }

 .ep-btn.watched::after {
  content: "\2713";
  /* هذا هو الكود العالمي لعلامة الصح في الـ CSS */
  font-size: 10px;
  position: absolute;
  margin-top: -5px;
  margin-right: 3px;
  /* أضفت لك مسافة بسيطة عشان ماتلزقش في رقم الحلقة */
 }


 .animated-ads-wrapper {
  text-align: center;
  margin: 20px 0;
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 20px;
 }

 .pulse-btn {
  padding: 15px 35px;
  font-weight: bold;
  font-size: 18px;
  border-radius: 5px;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
  cursor: pointer;
  animation: pulse 1.5s infinite;
 }

 .pulse-btn a {
  color: white;
  text-decoration: none;
 }

 .red-gradient {
  background: linear-gradient(180deg, #ff0000, #cc0000);
 }

 .blue-gradient {
  background: linear-gradient(180deg, #315482, #cc0000);
 }

 @keyframes pulse {
  0% {
   transform: scale(1);
  }

  50% {
   transform: scale(1.05);
  }

  100% {
   transform: scale(1);
  }
 }

 /* ================================================= */
 /* RESPONSIVE DESIGN - التصميم المتجاوب */
 /* ================================================= */
 @media (max-width: 800px) {
  .row {
   display: flex;
   flex-direction: column;
   align-items: center;
  }

  .info-container {
   display: flex;
   flex-direction: column;
   justify-content: center;
   align-items: center;
   width: 100%;
   padding: 16px;
   border-radius: 12px;
   border: 1px solid var(--color-border-secondary);
   box-shadow: 0 4px 15px var(--color-shadow);
  }

  .separator {
   display: flex;
   align-items: center;
   justify-content: center;
   width: 100%;
   margin: 0;
   text-align: center;
  }

  .video-container {
   width: 95%;
  }

 }

 @media (max-width: 600px) {
  .video-container {
   width: 100% !important;
   max-width: 100% !important;
   padding: 0 0px;
   /* تقليل الحواف الجانبية للموبايل */
   margin: 0 auto;
  }

  .player {
        width: 100% !important;
        height: auto !important;
        min-height: 350px !important;
        aspect-ratio: 16 / 10 !important;
  }

  #video-player-frame {
   width: 100% !important;
   height: 100% !important;
   /* بلاش object-fit: cover مع الـ iframe لأنه بيقص الجوانب، الأفضل contain أو إزالته */
   object-fit: contain !important;
  }

  /* تحسين شكل أزرار التحكم في الموبايل */
  .video-controls {
   display: flex;
   justify-content: space-between;
   gap: 5px;
   padding: 10px 5px;
  }

  .control-btn {
   font-size: 12px !important;
   padding: 8px 2px !important;
  }

  .download-section {
   gap: 4px;
   padding: 10px;
   align-items: center;
  }

  .download-btn,
  .theater-btn {
   width: 49%;
   box-sizing: border-box;
   text-align: center;
  }
 }

 @keyframes pulse {
  0% {
   transform: scale(1);
  }

  50% {
   transform: scale(1.05);
  }

  100% {
   transform: scale(1);
  }
 }



 .seo-section {
  margin-top: 40px;
  padding: 20px;
  border-radius: 12px;
  background: var(--color-bg-primary, #f9f9f9);
  border: 1px solid var(--color-border-card, #eee);
 }

 .seo-title {
  margin-top: 0;
  color: #1c4167;
  font-size: 14px;
  border-bottom: 1px solid #eee;
  padding-bottom: 10px;
 }

 .seo-tags-wrapper {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
 }

 .seo-tag {
  border: 1px solid var(--color-border-card);
  padding: 4px 10px;
  border-radius: 20px;
  font-size: 11px;
  color: var(--color-accent);
  background: var(--color-bg-card);
 }

 @media (max-width: 480px) {
  .ep-btn {
   width: 40px;
   height: 40px;
   line-height: 40px;
   font-size: 13px;
  }

 }
</style>
<div class="post-body">
 <h1>{{TITLE}}</h1>

 <div class="row">
  <div class="separator">
   <a href="https://belongingstransform.com/ga4gj8416?key=eee839b2435cd4844da21654efab149f" target="_blank"
    rel="nofollow">
    <picture>
     <source media="(max-width: 480px)" srcset="{{POSTER_URL}}">
     <img src="{{POSTER_URL}}" alt="بوستر {{TITLE}}" fetchpriority="high" loading="eager" decoding="async" />
    </picture>
   </a>
  </div>

  <div class="info-container">
   <div class="story-section">
    <h3 class="story-title">وصف قصير :</h3>
    <p class="story-text">{{STORY}}</p>
   </div>

   <div class="info-table">
    <table>
     <tr>
      <td>📅 تاريخ النشر:</td>
      <td>{{DISPLAY_DATE}}</td>
     </tr>
     <tr>
      <td>📺 النوع:</td>
      <td>{{LABELS}}</td>
     </tr>
     <tr>
      <td>🌍 الجودة:</td>
      <td>Full HD 1080p</td>
     </tr>
     <tr>
      <td>🗣️ حالة العمل:</td>
      <td>{{LANGUAGE}}</td>
     </tr>
     <tr>
      <td>⭐ التقييم:</td>
      <td>{{RATING}}/10 ⭐</td>
     </tr>
     <tr>
      <td>⏳ المدة:</td>
      <td>{{RUNTIME}}</td>
     </tr>
    </table>

    <div class="animated-ads-wrapper">
     <div class="pulse-btn red-gradient">
      <a href="https://belongingstransform.com/ga4gj8416?key=eee839b2435cd4844da21654efab149f" target="_blank"
       rel="nofollow">
       ▶ سيرفر المشاهدة
      </a>
     </div>
     <div class="pulse-btn blue-gradient">
      <a href="https://belongingstransform.com/ga4gj8416?key=eee839b2435cd4844da21654efab149f" target="_blank"
       rel="nofollow">
       ▶ حمل الان من هنا
      </a>
     </div>
    </div>
   </div>
  </div>
 </div>
 <div class="video-container">
  <div class="player-header">
   جاري عرض: <span id="current-ep" class="current-episode">{{TITLE}}</span>
  </div>

<div class="server-buttons" id="server-list">
    <button class="server-btn active server-btn-1" onclick="changeS(this, currentVoe)">سيرفر Voe</button>
    <button class="server-btn server-btn-2" id="vid-btn" onclick="changeS(this, currentVid)">سيرفر VidTube</button>
    <button class="server-btn server-btn-3" onclick="changeS(this, currentOk)">سيرفر OK</button>
    <button class="server-btn server-btn-4" onclick="changeS(this, currentVk)">سيرفر VK</button>
<div class="player">
   <iframe id="video-player-frame" src="about:blank" data-src="{{VOE_URL}}" data-poster="{{POSTER_WIDE}}" allowfullscreen></iframe>
</div>

  <div class="download-section">
   <a href="{{DOWNLOAD_URL}}" id="download-btn" target="_blank" class="download-btn">
    📥 تحميل الفيلم HD
   </a>
   <button onclick="toggleTheater()" class="theater-btn">
    💡 وضع السينما للمشاهدة الليلية
   </button>
  </div>
 </div>
</div>

<div class="seo-section">
 <h4 class="seo-title">🏷️ وسوم البحث ذات الصلة:</h4>
 <div class="seo-tags-wrapper">
  {{TAGS_CONTENT}}
 </div>
</div>


<script>
 // JavaScript يبقى كما هو تمامًا دون تغيير
// تأكد أن التاجات داخل بلوجر مطابقة تماماً لمحتواها
// وضع الروابط في مصفوفة بدلاً من متغيرات صريحة لتشتيت الروبوتات
const _0xData = {
    v: "{{VOE_URL}}",
    vt: "{{VIDTUBE_URL}}",
    ok: "{{OK_URL}}",
    vk: "{{VK_URL}}"
};
let currentVoe = _0xData.v;
let currentVid = _0xData.vt;
let currentOk = _0xData.ok;
let currentVk = _0xData.vk;
 let blogPostId = "{{POST_ID}}";
 let currentEpNum = 1;

 window.onload = function () {
  // البحث عن الرابط المخفي في data-src وتفعيله برمجياً
const hiddenFrame = document.getElementById('video-player-frame');
if (hiddenFrame && hiddenFrame.getAttribute('data-src')) {
    currentVoe = hiddenFrame.getAttribute('data-src');
}
  markWatchedFromStorage();
  // فحص أولي لجميع السيرفرات
  checkServer(currentVid, '.server-btn-2');
  checkServer(currentOk, '.server-btn-3');
  checkServer(currentVk, '.server-btn-4');

  // فحص ما إذا كان قادماً من زر الإصلاح برقم حلقة معين
  const urlParams = new URLSearchParams(window.location.search);
  const targetEp = urlParams.get('ep');

  if (targetEp) {
   const epBtn = document.querySelector(`.ep-btn[onclick*="'${targetEp}'"]`);
   if (epBtn) {
    epBtn.click(); // تشغيل الحلقة المطلوبة تلقائياً
    return;
   }
  }

  // الحالة العادية: تشغيل السيرفر الافتراضي
// الحالة العادية: تشغيل السيرفر الافتراضي
  const firstBtn = document.querySelector('.server-btn.active');
  if (firstBtn) {
      changeS(firstBtn, currentVoe);
      // تأكيد التشفير عند أول تحميل
      if (typeof secureMedia === 'function') secureMedia();
  }
 };



 function playPrev() {
  let prevNum = currentEpNum - 1;
  let prevBtn = document.querySelector(`.ep-btn[onclick*="'${prevNum}'"]`);
  if (prevBtn) {
   prevBtn.click();
  } else {
   alert("هذه هي الحلقة الأولى.");
  }
 }

 // استبدل أو أضف هذه الدالة داخل الـ script
function playEp(btn, voeUrl, vidUrl, num, downUrl, ...extraUrls) {
  currentVoe = voeUrl;
  currentVid = vidUrl;
  // تحديث الروابط العالمية من المصفوفة الإضافية
  currentOk = extraUrls[0] || "nan"; 
  currentVk = extraUrls[1] || "nan";
  currentEpNum = parseInt(num);

  const downBtn = document.getElementById('download-btn');
  if (downBtn) downBtn.href = downUrl || "#";

  const serverList = document.getElementById('server-list');
  // حذف الأزرار القديمة المضافة ديناميكياً فقط
  const extraBtns = serverList.querySelectorAll('.extra-server');
  extraBtns.forEach(b => b.remove());

  // تحديث ظهور VidTube (الزر الثابت الثاني)
// تحديث ظهور السيرفرات الثابتة في القالب
  checkServer(vidUrl, '.server-btn-2');
  checkServer(extraUrls[0], '.server-btn-3'); // OK
  checkServer(extraUrls[1], '.server-btn-4'); // VK

  // إضافة سيرفرات OK و VK ديناميكياً
  const serverNames = ["سيرفر OK", "سيرفر VK", "سيرفر إضافي"];
  extraUrls.forEach((url, index) => {
    if (url && url !== "" && url !== "nan" && url.toLowerCase() !== "pending") {
      const newBtn = document.createElement('button');
      newBtn.className = "server-btn extra-server";
      newBtn.innerText = serverNames[index] || `سيرفر ${index + 1}`;
      newBtn.onclick = function() { changeS(this, url); };
      serverList.appendChild(newBtn);
    }
  });

  // تمييز Voe كافتراضي دائماً عند تغيير الحلقة
  const allSBtns = document.querySelectorAll('.server-btn');
  allSBtns.forEach(b => b.classList.remove('active'));
  if(allSBtns[0]) {
      allSBtns[0].classList.add('active');
      changeS(allSBtns[0], voeUrl);
  }

  saveToWatched(num);
  btn.classList.add('watched');
  document.querySelector('.video-container').scrollIntoView({ behavior: 'smooth', block: 'center' });
  document.getElementById('current-ep').innerText = "الحلقة " + num;

  document.querySelectorAll('.ep-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
}

 function playNext() {
  let nextNum = currentEpNum + 1;
  let nextBtn = document.querySelector(`.ep-btn[onclick*="'${nextNum}'"]`);
  if (nextBtn) {
   nextBtn.click();
  } else {
   alert("لقد وصلت لآخر حلقة متوفرة حالياً.");
  }
 }


function changeS(btn, url) {
  const frame = document.getElementById('video-player-frame');
  
  // --- الجزء الجديد لحل مشكلة OK.ru ---
  if (url.includes('ok.ru')) {
    frame.setAttribute('referrerpolicy', 'no-referrer');
  } else {
    frame.removeAttribute('referrerpolicy');
  }

  const isUnlocked = window.location.search.includes('unlocked=true');
		const ua = navigator.userAgent || navigator.vendor || window.opera;
		const isFB = /FBAN|FBAV|Messenger|FB_IAB|FB4A|FBIE/i.test(ua);

  // تحديث مطور: بناء الـ iframe من جديد لتغيير الـ Referrer Policy
  const newFrame = frame.cloneNode(true);
  
  if (url.includes("ok.ru")) {
   // خدعة OK.ru: منع إرسال مصدر الموقع
   newFrame.setAttribute('referrerpolicy', 'no-referrer');
   newFrame.setAttribute('sandbox', 'allow-forms allow-scripts allow-same-origin allow-popups allow-presentation');
  } else {
   // السيرفرات العادية
   newFrame.removeAttribute('sandbox');
   newFrame.setAttribute('referrerpolicy', 'strict-origin-when-cross-origin');
  }

  // تشفير الرابط في الذاكرة لمنع الزواحف من قنصه
// استبدل هذا الجزء في دالة changeS
const encodedUrl = btoa(url); 
newFrame.src = "about:blank"; // ابدأ بصفحة فارغة
newFrame.setAttribute('data-src', url); // ضع الرابط في attribute مخصص
// اترك سكريبت الحارس (SecureMedia) هو من يقوم بفتح الرابط بعد الضغط
  frame.parentNode.replaceChild(newFrame, frame);

  // تحديث حالة الأزرار
  let sBtns = document.querySelectorAll('.server-btn');
  sBtns.forEach(b => b.classList.remove('active'));
  btn.classList.add('active');

  const oldFix = document.getElementById('fb-fix-btn');
  if (oldFix) oldFix.remove();

  if (isFB && isUnlocked) {
   const manualFix = document.createElement('a');
   manualFix.id = 'fb-fix-btn';
   manualFix.className = 'no-lock';
   const currentUrl = window.location.href.split('?')[0];
   const finalRedirectUrl = currentUrl + "?unlocked=true&ep=" + currentEpNum + "&refresh=" + Date.now();
   const isAndroid = /Android/i.test(ua);

   if (isAndroid) {
    const cleanUrl = finalRedirectUrl.replace(/^https?:\/\//, '');
    manualFix.href = `intent://${cleanUrl}#Intent;scheme=https;package=com.android.chrome;end`;
   } else {
    manualFix.href = finalRedirectUrl;
   }

   if (isAndroid && !window.location.search.includes('ref=auto')) {
    setTimeout(() => { window.location.href = manualFix.href; }, 1000);
   }

   manualFix.target = "_blank";
   manualFix.innerText = "\u26A0\uFE0F حل مشكلة المشغل: اضغط للفتح في متصفح خارجي";
   manualFix.style = "display:block; text-decoration:none; text-align:center; padding:15px; background:#e74c3c; color:#fff !important; border-radius:12px; margin:15px auto; font-weight:bold; font-size:14px; width:100%; box-sizing:border-box; border: 2px solid #fff; box-shadow: 0 4px 15px rgba(0,0,0,0.3); animation: pulse-red 2s infinite;";

   if (!document.getElementById('fix-animation')) {
    const style = document.createElement('style');
    style.id = 'fix-animation';
    style.innerHTML = "@keyframes pulse-red { 0% {transform:scale(1);} 50% {transform:scale(1.03); background:#c0392b;} 100% {transform:scale(1);} }";
    document.head.appendChild(style);
   }

   const downloadWrapper = document.querySelector('.download-section');
   if (downloadWrapper) {
    downloadWrapper.after(manualFix);
   }
  }
  // تحفيز سكريبت الحارس لفحص العنصر الجديد وتأمينه فوراً
  if (typeof secureMedia === 'function') {
    secureMedia();
  }
 }

 function saveToWatched(num) {
  let watched = JSON.parse(localStorage.getItem('watched_' + blogPostId) || "[]");
  if (!watched.includes(num)) {
   watched.push(num);
   localStorage.setItem('watched_' + blogPostId, JSON.stringify(watched));
  }
 }

 function markWatchedFromStorage() {
  let watched = JSON.parse(localStorage.getItem('watched_' + blogPostId) || "[]");
  watched.forEach(num => {
   let btn = document.querySelector(`.ep-btn[onclick*="'${num}'"]`);
   if (btn) btn.classList.add('watched');
  });
 }

 function toggleTheater() {
  const videoContainer = document.querySelector('.video-container');
  let overlay = document.getElementById('theater-overlay');
  if (!overlay) {
   overlay = document.createElement('div');
   overlay.id = 'theater-overlay';
   overlay.setAttribute('style', 'position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.95); z-index:999; cursor:pointer;');
   overlay.onclick = toggleTheater;
   document.body.appendChild(overlay);
   videoContainer.style.position = 'relative';
   videoContainer.style.zIndex = '1000';
   videoContainer.scrollIntoView({ behavior: 'smooth', block: 'center' });
  } else {
   overlay.remove();
   videoContainer.style.zIndex = '1';
  }
 }

 function checkServer(url, selector) {
  const btn = document.querySelector(selector);
  if (btn) {
   if (!url || url === "" || url === "nan" || url.toLowerCase() === "pending") {
    btn.style.display = 'none';
   } else {
    btn.style.display = 'inline-block';
   }
  }
 }
</script>
"""


########################################
########################################
########################################
########################################
########################################
########################################
########################################
########################################


# --- 2.2 قالب الـ HTML المطور للمسلسلات (متعدد الحلقات) ---
HTML_TEMPLATE_SERIES = r"""
<meta name="theme-color" content="#1c4167">
<meta name="msapplication-navbutton-color" content="#1c4167">
<meta name="apple-mobile-web-app-status-bar-style" content="#1c4167">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Language" content="ar-eg">

<meta name="robots" content="follow, index, max-snippet:-1, max-video-preview:-1, max-image-preview:large"/>
<meta name="revisit-after" content="1 hour">

<meta property="og:title" content="{{TITLE}}" />
<meta property="og:description" content="{{SEARCH_DESCRIPTION}}" />
<meta property="og:image" content="{{POSTER_URL}}" />
<meta property="og:image:width" content="1200" />
<meta property="og:image:height" content="630" />
<meta property="og:type" content="video.tv_show" />
<meta property="og:site_name" content="Egy Pyramid" />
<meta property="video:duration" content="{{DURATION_ISO}}" />
<meta property="og:rating" content="{{RATING}}" />

<meta name="twitter:label1" content="التقييم" />
<meta name="twitter:data1" content="{{RATING}}/10" />
<meta name="twitter:label2" content="عدد الحلقات" />
<meta name="twitter:data2" content="{{EPISODES_COUNT}} حلقة" />

<meta itemprop="name" content="{{TITLE}}">
<meta itemprop="description" content="{{SEARCH_DESCRIPTION}}">
<meta itemprop="image" content="{{POSTER_URL}}">
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "TVSeries",
  "name": "{{TITLE}} - جميع الحلقات",
  "description": "{{SEARCH_DESCRIPTION}}",
  "image": "{{POSTER_URL}}",
  "thumbnailUrl": ["{{POSTER_URL}}"],
  "numberOfEpisodes": "{{EPISODES_COUNT}}",
  "numberOfSeasons": "{{SEASONS_COUNT}}",
  "episode": {
    "@type": "TVEpisode",
    "name": "{{TITLE}} - الحلقة 1",
    "description": "شاهد الحلقة الأولى من {{TITLE}} بجودة عالية",
    "thumbnailUrl": "{{POSTER_URL}}",
    "uploadDate": "{{CURRENT_DATE}}",
    "embedUrl": "{{FIRST_EP_URL}}",
    "potentialAction": {
      "@type": "WatchAction",
      "target": "{{FIRST_EP_URL}}"
    }
  },
  "datePublished": "{{CURRENT_DATE}}",
  "dateModified": "{{CURRENT_DATE}}",
  "publisher": {
    "@type": "Organization",
    "name": "Egy Pyramid",
    "logo": {
      "@type": "ImageObject",
      "url": "{{LOGO_URL}}"
    }
  },
  "video": {
    "@id": "{{FIRST_EP_URL}}#video",
    "@type": "VideoObject",
    "name": "{{TITLE}} - الحلقة 1",
    "description": "شاهد الحلقة الأولى من {{TITLE}} بجودة عالية",
    "thumbnailUrl": "{{POSTER_URL}}",
    "uploadDate": "{{CURRENT_DATE}}",
    "embedUrl": "{{FIRST_EP_URL}}",
    "potentialAction": {
      "@type": "WatchAction",
      "target": "{{FIRST_EP_URL}}"
    }
  }
}
</script>

<style>
 .post-body h1 {
  color: #e74c3c;
  text-align: center;
  margin: 1rem 0;
  font-size: clamp(1rem, 2.5vw, 2.5rem);
 }


 .row {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  flex-direction: row-reverse;
  gap: 1rem;
  padding-bottom: 40px;
  margin-bottom: 40px;
  border-bottom: 1px solid var(--color-border-primary);
 }

 .info-container {
  width: 68%;
  border-radius: 12px;
  border: 1px solid var(--color-border-secondary);
  box-shadow: 0 4px 15px var(--color-shadow);
  display: flex;
  flex-direction: column;
  gap: 1rem;
 }

 /* ================================================= */
 /* POSTER & SEPARATOR - الصورة الرئيسية */
 /* ================================================= */
 .separator {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30%;
  text-align: center;
 }

 .separator img {
  width: 100%;
  height: auto;
  max-width: 350px;
  border-radius: 12px;
  box-shadow: 0 4px 15px var(--color-shadow);
  border: 1px solid var(--color-border-secondary);
  display: block;
  margin: 0 auto;
 }

 .separator img:hover {
  transform: scale(1.02);
 }

 /* ================================================= */
 /* SMART LINK AD - إعلان سمارت لينك */
 /* ================================================= */
 .smartlink-ad {
  text-align: center;
  padding: 30px;
  border-radius: 15px;
  border: 2px solid var(--color-primary);
  margin: 30px 0;
  box-shadow: 0 10px 20px rgba(0, 0, 0, 0.3);
  background-color: var(--color-bg-secondary);
 }

 .smartlink-title {
  font-size: 22px;
  color: #D4AF37;
  margin-bottom: 25px;
  font-weight: bold;
 }

 .smartlink-btn {
  display: inline-block;
  width: 90%;
  max-width: 350px;
  background: linear-gradient(145deg, #D4AF37, #B8860B);
  color: #000 !important;
  padding: 18px;
  border-radius: 50px;
  text-decoration: none;
  font-weight: 900;
  font-size: 18px;
  transition: all 0.3s ease;
  box-shadow: 0 4px 15px rgba(212, 175, 55, 0.4);
 }

 .smartlink-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(212, 175, 55, 0.6);
 }

 .smartlink-backup {
  display: inline-block;
  width: 90%;
  max-width: 350px;
  background: var(--color-bg-card);
  color: var(--color-text-primary);
  padding: 16px;
  border-radius: 50px;
  text-decoration: none;
  font-weight: bold;
  font-size: 16px;
  border: 1px solid var(--color-primary);
  margin-top: 10px;
  transition: all 0.3s ease;
 }

 .smartlink-backup:hover {
  background: var(--color-primary);
  color: var(--color-text-light);
 }

 /* ================================================= */
 /* STORY SECTION - قسم القصة */
 /* ================================================= */
 .story-section {
  padding: 8px 16px;
  border-right: 5px solid var(--color-primary);
  background-color: var(--color-bg-card);
  border-radius: 8px;
 }

 .story-title {
  margin: 0 0 10px 0;
  color: var(--color-primary);
  font-size: 1.2rem;
 }

 .story-text {
  font-style: italic;
  line-height: 1.6;
  margin: 0;
  font-size: clamp(12px, 3.6vw, 1rem);
 }

 /* ================================================= */
 /* INFO TABLE - جدول المعلومات */
 /* ================================================= */
 .info-table {
  background: var(--color-bg-primary);
  color: var(--color-text-primary);
  border: 1px solid var(--color-border-secondary);
  border-radius: 10px;
  padding: 0 16px;
 }

 .info-table table {
  width: 100%;
  border-collapse: collapse;
 }


 .info-table td:first-child {
  font-weight: bold;
  color: var(--color-primary);
  width: 40%;
 }


 /* ================================================= */
 /* VIDEO CONTAINER - حاوية الفيديو */
 /* ================================================= */
 .video-container {
  margin: auto;
  margin-bottom: 40px;
  width: 800px;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.15);
 }

 /* ================================================= */
 /* PLAYER HEADER - عنوان المشغل */
 /* ================================================= */
 .player-header {
  background: var(--color-footer-bg);
  padding: 12px 4px;
  color: var(--color-text-light);
  text-align: center;
  font-weight: bold;
  font-size: clamp(.9rem, 2.5vw, 1.9rem);
  border-bottom: 1px solid var(--color-border-primary);
 }

 .current-episode {
  color: var(--color-text-secondary);
  font-weight: bold !important;
 }

 /* ================================================= */
 /* SERVER BUTTONS - أزرار السيرفرات */
 /* ================================================= */
.server-buttons {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
  background: var(--color-footer-bg);
  padding: 12px 0;
 }

 .server-btn {
  cursor: pointer;
  color: #fff; /* تأكيد اللون الأبيض للنص */
  border: none;
  padding: 10px 20px;
  border-radius: 6px;
  font-weight: bold;
  font-size: 14px;
  transition: all 0.3s ease;
  min-width: 120px;
  opacity: 0.8; /* جعل الأزرار غير النشطة باهتة قليلاً */
 }

 .server-btn:hover {
  opacity: 1;
  transform: translateY(-2px);
  filter: brightness(1.2);
 }

 /* تخصيص ألوان السيرفرات */
 .server-btn-1 { background-color: #8e44ad !important; } /* Voe بنفسجي */
 .server-btn-2 { background-color: #e74c3c !important; } /* VidTube أحمر */
 .server-btn-3 { background-color: #f39c12 !important; } /* OK برتقالي */
 .server-btn-4 { background-color: #2980b9 !important; } /* VK أزرق */
 .extra-server { background-color: #27ae60 !important; } /* أي سيرفر إضافي أخضر */

 /* لون حالة النشاط (Active) - الحقيقة الصارمة: نستخدم !important لإلغاء ألوان السيرفرات المحددة أعلاه */
 .server-btn.active {
  background-color: var(--color-secondary) !important; /* اللون الذهبي أو المارون المعتاد في قالبك */
  opacity: 1;
  box-shadow: 0 0 15px var(--color-secondary);
  border: 2px solid #fff; /* تمييز إضافي للزر المختار */
 }
 /* ================================================= */
 /* PLAYER - مشغل الفيديو */
 /* ================================================= */
.player {
    width: 100%;
    background: #000;
    border: 1px solid var(--color-primary);
    border-top: none;
    position: relative;
    aspect-ratio: 16 / 9;
    overflow: hidden;
}
 #video-player-frame {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  border: none;
 }

 /* ================================================= */
 /* VIDEO CONTROLS - تحكمات الفيديو */
 /* ================================================= */
 .video-controls {
  display: flex;
  justify-content: center;
  gap: 15px;
  background: var(--color-footer-bg);
  padding: 15px;
  border: 1px solid var(--color-border-primary);
  flex-wrap: wrap;
 }

 .control-btn {
  cursor: pointer;
  background: var(--color-primary);
  color: var(--color-text-light);
  border: none;
  padding: 12px 25px;
  border-radius: 6px;
  font-weight: bold;
  font-size: 14px;
  transition: all 0.3s ease;
  min-width: 160px;
 }

 .control-btn:hover {
  background: var(--color-button-hover);
  transform: translateY(-2px);
 }

 .btn-skip {
  background: var(--color-control-secondary);
 }

 .btn-skip:hover {
  background: #e67e22;
 }

 /* ================================================= */
 /* DOWNLOAD SECTION - قسم التحميل */
 /* ================================================= */
 .download-section {
  background-color: var(--color-footer-bg);
  display: flex;
  justify-content: space-around;
  padding: 20px;
  border-top: none;
  gap: 15px;
 }

 .download-btn {
  flex: 1;
  max-width: 300px;
  display: inline-block;
  padding: 15px 35px;
  background: linear-gradient(180deg, #315482, #cc0000);
  color: white !important;
  color: white;
  font-weight: bold;
  font-size: clamp(.5rem, 2vw, .9rem);
  text-align: center;
  border-radius: 5px;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
  cursor: pointer;
  animation: pulse 1.5s infinite;
 }

 .download-btn:hover {
  background: #219653;
  transform: translateY(-2px);
  box-shadow: 0 5px 15px rgba(39, 174, 96, 0.3);
 }

 .theater-btn {
  background: var(--color-secondary);
  color: white;
  padding: 16px 30px;
  border-radius: 8px;
  border: none;
  cursor: pointer;
  font-weight: bold;
  font-size: clamp(.5rem, 2vw, .9rem);
  text-align: center;
  transition: all 0.3s ease;
  flex: 1;
  max-width: 300px;
 }

 .theater-btn:hover {
  background: #0d4550;
  transform: translateY(-2px);
  box-shadow: 0 5px 15px rgba(16, 82, 95, 0.3);
 }

 /* ================================================= */
 /* EPISODES SECTION - قسم الحلقات */
 /* ================================================= */
 .episodes-title {
  color: var(--color-text-light) !important;
  text-align: center;
  margin: 0 !important;
  background-color: var(--color-footer-bg);
  padding: 20px;
  font-size: 1.3rem;
  border-bottom: 1px solid var(--color-border-primary);
  border-top: 1px solid var(--color-border-primary);
 }

 .episodes-container {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: center;
  align-items: center;
  background: var(--color-footer-bg);
  color: var(--color-text-light);
  padding: 20px;
  border-radius: 0 0 12px 12px;
  border-top: none;
 }

 /* ================================================= */
 /* EPISODE BUTTONS - أزرار الحلقات */
 /* ================================================= */
 .ep-btn {
  cursor: pointer;
  background: #1a73e8;
  color: #fff;
  border: none;
  width: 50px;
  height: 50px;
  line-height: 50px;
  padding: 0;
  border-radius: 50%;
  text-align: center;
  font-weight: bold;
  transition: all 0.3s ease;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
  display: inline-block;
  opacity: .5;
  user-select: none;
  -webkit-user-select: none;
 }

 .ep-btn:hover {
  background: var(--color-button-hover);
  transform: translateY(-3px) scale(1.1);
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
  opacity: 1;
 }

 .ep-btn.active {
  background: #e74c3c !important;
  color: #fff !important;
  transform: scale(1.1);
  border: 2px solid #fff;
  width: 55px;
  height: 55px;
  line-height: 50px;
  opacity: 1;
  box-shadow: 0 0 15px rgba(231, 76, 60, 0.5);
 }

 .ep-btn.watched {
  background: var(--color-episode-watched) !important;
  opacity: 0.7;
 }

 .ep-btn.watched::after {
  content: "\2713";
  /* هذا هو الكود العالمي لعلامة الصح في الـ CSS */
  font-size: 10px;
  position: absolute;
  margin-top: -5px;
  margin-right: 3px;
  /* أضفت لك مسافة بسيطة عشان ماتلزقش في رقم الحلقة */
 }


 .animated-ads-wrapper {
  text-align: center;
  margin: 20px 0;
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 20px;
 }

 .pulse-btn {
  padding: 15px 35px;
  font-weight: bold;
  font-size: 18px;
  border-radius: 5px;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
  cursor: pointer;
  animation: pulse 1.5s infinite;
 }

 .pulse-btn a {
  color: white;
  text-decoration: none;
 }

 .red-gradient {
  background: linear-gradient(180deg, #ff0000, #cc0000);
 }

 .blue-gradient {
  background: linear-gradient(180deg, #315482, #cc0000);
 }

 @keyframes pulse {
  0% {
   transform: scale(1);
  }

  50% {
   transform: scale(1.05);
  }

  100% {
   transform: scale(1);
  }
 }

 /* ================================================= */
 /* RESPONSIVE DESIGN - التصميم المتجاوب */
 /* ================================================= */
 @media (max-width: 800px) {
  .row {
   display: flex;
   flex-direction: column;
   align-items: center;
  }

  .info-container {
   display: flex;
   flex-direction: column;
   justify-content: center;
   align-items: center;
   width: 100%;
   padding: 16px;
   border-radius: 12px;
   border: 1px solid var(--color-border-secondary);
   box-shadow: 0 4px 15px var(--color-shadow);
  }

  .separator {
   display: flex;
   align-items: center;
   justify-content: center;
   width: 100%;
   margin: 0;
   text-align: center;
  }

  .video-container {
   width: 95%;
  }

 }

 @media (max-width: 600px) {
  .video-container {
   width: 100% !important;
   max-width: 100% !important;
   padding: 0 0px;
   /* تقليل الحواف الجانبية للموبايل */
   margin: 0 auto;
  }
.server-buttons {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    padding: 12px 8px;
}

  .player {
        width: 100% !important;
        height: auto !important;
        min-height: 350px !important;
        aspect-ratio: 16 / 10 !important;
  }

  #video-player-frame {
   width: 100% !important;
   height: 100% !important;
   /* بلاش object-fit: cover مع الـ iframe لأنه بيقص الجوانب، الأفضل contain أو إزالته */
   object-fit: contain !important;
  }

  /* تحسين شكل أزرار التحكم في الموبايل */
  .video-controls {
   display: flex;
   justify-content: space-between;
   gap: 5px;
   padding: 10px 5px;
  }

  .control-btn {
   font-size: 12px !important;
   padding: 8px 2px !important;
  }

  .download-section {
   gap: 4px;
   padding: 10px;
   align-items: center;
  }

  .download-btn,
  .theater-btn {
   width: 49%;
   box-sizing: border-box;
   text-align: center;
  }
 }

 @keyframes pulse {
  0% {
   transform: scale(1);
  }

  50% {
   transform: scale(1.05);
  }

  100% {
   transform: scale(1);
  }
 }



 .seo-section {
  margin-top: 40px;
  padding: 20px;
  border-radius: 12px;
  background: var(--color-bg-primary, #f9f9f9);
  border: 1px solid var(--color-border-card, #eee);
 }

 .seo-title {
  margin-top: 0;
  color: #1c4167;
  font-size: 14px;
  border-bottom: 1px solid #eee;
  padding-bottom: 10px;
 }

 .seo-tags-wrapper {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
 }

 .seo-tag {
  border: 1px solid var(--color-border-card);
  padding: 4px 10px;
  border-radius: 20px;
  font-size: 11px;
  color: var(--color-accent);
  background: var(--color-bg-card);
 }

 @media (max-width: 480px) {
  .ep-btn {
   width: 40px;
   height: 40px;
   line-height: 40px;
   font-size: 13px;
  }

 }
</style>
<div class="post-body">
 <!-- العنوان الرئيسي -->
 <h1>{{TITLE}}</h1>

 <div class="row">
  <!-- الصورة الرئيسية -->
  <div class="separator">
   <a href="https://belongingstransform.com/ga4gj8416?key=eee839b2435cd4844da21654efab149f" target="_blank"
    rel="nofollow">
    <picture>
     <source media="(max-width: 480px)" srcset="{{POSTER_URL}}">
     <img src="{{POSTER_URL}}" alt="بوستر {{TITLE}}" fetchpriority="high" loading="eager" decoding="async" />
    </picture>
   </a>
  </div>

  <div class="info-container">
   <!-- قصة المسلسل -->
   <div class="story-section">
    <h3 class="story-title">وصف قصير :</h3>
    <p class="story-text">{{STORY}}</p>
   </div>
   <!-- معلومات المسلسل -->
   <div class="info-table">
    <table>
     <tr>
      <td>📅 تاريخ النشر:</td>
      <td>{{DISPLAY_DATE}}</td>
     </tr>
     <tr>
      <td>📺 النوع:</td>
      <td>{{LABELS}}</td>
     </tr>
     <tr>
      <td>🌍 الجودة:</td>
      <td>Full HD 1080p</td>
     </tr>
     <tr>
      <td>🗣️ حالة العمل:</td>
      <td>{{LANGUAGE}}</td>
     </tr>
     <tr>
      <td>⭐ التقييم:</td>
      <td>{{RATING}}/10 ⭐</td>
     </tr>
     <tr>
      <td>⏳ المدة:</td>
      <td>{{RUNTIME}}</td>
     </tr>
    </table>

    <!-- إعلان سمارت لينك الرئيسي -->
    <div class="animated-ads-wrapper">
     <div class="pulse-btn red-gradient">
      <a href="https://belongingstransform.com/ga4gj8416?key=eee839b2435cd4844da21654efab149f" target="_blank"
       rel="nofollow">
       ▶ سيرفر المشاهدة
      </a>
     </div>
     <div class="pulse-btn blue-gradient">
      <a href="https://belongingstransform.com/ga4gj8416?key=eee839b2435cd4844da21654efab149f" target="_blank"
       rel="nofollow">
       ▶ حمل الان من هنا
      </a>
     </div>
    </div>
   </div>
  </div>
 </div>
<!-- مشغل الفيديو -->
<div class="video-container">
  <!-- عنوان المشغل -->
  <div class="player-header">
    جاري عرض: <span id="current-ep" class="current-episode">{{TITLE}}</span>
  </div>
  <!-- أزرار السيرفرات -->
  <div class="server-buttons" id="dynamic-servers-container">
  </div>
  <!-- مشغل الفيديو -->
  <div class="player">
    <iframe id="video-player-frame" src="about:blank" data-src="{{VOE_URL}}" data-poster="{{POSTER_WIDE}}"
      allowfullscreen></iframe>
  </div>
  <!-- تحكمات الفيديو -->
  <div class="video-controls">
    <button class="control-btn" onclick="playPrev()">❮ الحلقة السابقة</button>
    <button class="control-btn" id="next-ep-btn" onclick="playNext()">الحلقة التالية ❯</button>
  </div>
  <!-- قسم التحميل -->
  <div class="download-section">
    <a href="{{DOWNLOAD_URL}}" id="download-btn" target="_blank" class="download-btn">
      📥 تحميل الحلقة HD
    </a>
    <button onclick="toggleTheater()" class="theater-btn">
      💡 وضع السينما للمشاهدة الليلية
    </button>
  </div>
</div>
<!-- عنوان قسم الحلقات -->

<h3 class="episodes-title">اختر الحلقة التي تريد مشاهدتها :</h3>
<div class="episodes-container ep-More" id="episodes-container">
  {{EPISODES_BUTTONS}}
</div>
<!-- إعلان سمارت لينك إضافي -->

<div class="smartlink-ad footer-ad">
  <h2 class="smartlink-title">📥 اختر سيرفر المشاهدة والتحميل</h2>
  <a href="https://semicolondriverelevated.com/ga4gj8416?key=eee839b2435cd4844da21654efab149f" target="_blank"
    rel="nofollow" class="smartlink-btn">
    ▶ سيرفر VIP (سريع جداً)
  </a>
  <a href="https://semicolondriverelevated.com/tszjr66n?key=7ac57491c7a686b5703eab322b3e4435" target="_blank"
    rel="nofollow" class="smartlink-backup">
    ▶ سيرفر احتياطي (جودة 1080p)
  </a>
  <p class="note-text">* ملاحظة: السيرفرات تدعم استكمال التحميل</p>
</div>

<div class="seo-section">
  <h4 class="seo-title">🏷️ وسوم البحث ذات الصلة:</h4>
  <div class="seo-tags-wrapper">
    {{TAGS_CONTENT}}
  </div>
</div>

<script>
  // تعريف المتغيرات العالمية المطلوبة للنظام الديناميكي
  let currentEpNum = 1;
  let blogPostId = "{{POST_ID}}";
  let currentVoe = "";
  window.onload = function () {
    markWatchedFromStorage();
    const urlParams = new URLSearchParams(window.location.search);
    const targetEp = urlParams.get('ep');

    // إذا وجد رقم حلقة في الرابط يشغلها فوراً
    if (targetEp) {
      const epBtn = document.querySelector(`.ep-btn[onclick*="'${targetEp}'"]`);
      if (epBtn) {
        epBtn.click();
        return;
      }
    }

    // إذا لم يجد، يشغل أول حلقة نشطة
    const firstEp = document.querySelector('.ep-btn.active');
    if (firstEp) {
      firstEp.click();
    }
  };


  function playPrev() {
    let prevNum = currentEpNum - 1;
    let prevBtn = document.querySelector(`.ep-btn[onclick*="'${prevNum}'"]`);
    if (prevBtn) {
      prevBtn.click();
    } else {
      alert("هذه هي الحلقة الأولى.");
    }
  }

  // استبدل أو أضف هذه الدالة داخل الـ script
  function playEpDynamic(btn, num, downloadUrl, linksJson) {
    // 1. تحويل النص القادم من بايثون إلى مصفوفة حقيقية
    const links = JSON.parse(linksJson);
    const container = document.getElementById('dynamic-servers-container');
    const epTitle = document.getElementById('current-ep');
    const dBtn = document.getElementById('download-btn');
    currentEpNum = parseInt(num);
    // 2. تحديث العناوين والتحميل
    if (epTitle) epTitle.innerText = "الحلقة " + num;
    if (dBtn) dBtn.href = downloadUrl;

    // 3. بناء أزرار السيرفرات ديناميكياً (هنا السحر!)
    container.innerHTML = ''; // مسح الأزرار القديمة تماماً

    links.forEach((link, index) => {
      const sBtn = document.createElement('button');
      sBtn.className = 'server-btn' + (index === 0 ? ' active' : '');
      sBtn.innerText = 'سيرفر ' + (link.name.toUpperCase());
      sBtn.onclick = function () {
        // تفعيل الزر النشط
        document.querySelectorAll('.server-btn').forEach(b => b.classList.remove('active'));
        sBtn.classList.add('active');
        // تغيير الفيديو
        changeS(sBtn, link.url);
      };
      container.appendChild(sBtn);
    });

    // 4. تشغيل أول سيرفر في القائمة تلقائياً
    if (links.length > 0) {
      changeS(null, links[0].url);
    }

    // 5. تمييز زر الحلقة
    document.querySelectorAll('.ep-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
  }

  function playNext() {
    let nextNum = currentEpNum + 1;
    let nextBtn = document.querySelector(`.ep-btn[onclick*="'${nextNum}'"]`);
    if (nextBtn) {
      nextBtn.click();
    } else {
      alert("لقد وصلت لآخر حلقة متوفرة حالياً.");
    }
  }


  function changeS(btn, url) {
    const frame = document.getElementById('video-player-frame');
    if (!frame) return;

    const isUnlocked = window.location.search.includes('unlocked=true');
    const ua = navigator.userAgent || navigator.vendor || window.opera;
    const isFB = /FBAN|FBAV/i.test(ua);

    const newFrame = frame.cloneNode(true);

    if (url.includes("ok.ru")) {
      newFrame.setAttribute('referrerpolicy', 'no-referrer');
      newFrame.setAttribute('sandbox', 'allow-forms allow-scripts allow-same-origin allow-popups allow-presentation');
    } else {
      newFrame.removeAttribute('sandbox');
      newFrame.setAttribute('referrerpolicy', 'strict-origin-when-cross-origin');
    }
    // استبدل الجزء الخاص بتحديث حالة الأزرار بهذا
    if (btn) {
      let sBtns = document.querySelectorAll('.server-btn');
      sBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
    }
    // --- التعديل الأمني الجوهري هنا ---
    newFrame.src = "about:blank"; // تفريغ الرابط الصريح
    newFrame.setAttribute('data-src', url); // إخفاء الرابط في الـ Attribute
    frame.parentNode.replaceChild(newFrame, frame);


    // استدعاء "الحارس" لتأمين الرابط الجديد فوراً
    if (typeof secureMedia === 'function') {
      secureMedia();
    }
    // ----------------------------------

    // بقية كود حل مشكلة فيسبوك (Manual Fix) تظل كما هي...
    const oldFix = document.getElementById('fb-fix-btn');
    if (oldFix) oldFix.remove();
    if (isFB && isUnlocked) {
      const manualFix = document.createElement('a');
      manualFix.id = 'fb-fix-btn';
      manualFix.className = 'no-lock';
      const currentUrl = window.location.href.split('?')[0];
      const finalRedirectUrl = currentUrl + "?unlocked=true&ep=" + currentEpNum + "&refresh=" + Date.now();
      const isAndroid = /Android/i.test(ua);

      if (isAndroid) {
        const cleanUrl = finalRedirectUrl.replace(/^https?:\/\//, '');
        manualFix.href = `intent://${cleanUrl}#Intent;scheme=https;package=com.android.chrome;end`;
      } else {
        manualFix.href = finalRedirectUrl;
      }

      if (isAndroid && !window.location.search.includes('ref=auto')) {
        setTimeout(() => { window.location.href = manualFix.href; }, 1000);
      }

      manualFix.target = "_blank";
      manualFix.innerText = "\u26A0\uFE0F حل مشكلة المشغل: اضغط للفتح في متصفح خارجي";
      manualFix.style = "display:block; text-decoration:none; text-align:center; padding:15px; background:#e74c3c; color:#fff !important; border-radius:12px; margin:15px auto; font-weight:bold; font-size:14px; width:100%; box-sizing:border-box; border: 2px solid #fff; box-shadow: 0 4px 15px rgba(0,0,0,0.3); animation: pulse-red 2s infinite;";

      if (!document.getElementById('fix-animation')) {
        const style = document.createElement('style');
        style.id = 'fix-animation';
        style.innerHTML = "@keyframes pulse-red { 0% {transform:scale(1);} 50% {transform:scale(1.03); background:#c0392b;} 100% {transform:scale(1);} }";
        document.head.appendChild(style);
      }

      const downloadWrapper = document.querySelector('.download-section');
      if (downloadWrapper) {
        downloadWrapper.after(manualFix);
      }
    }
  }

  function saveToWatched(num) {
    let watched = JSON.parse(localStorage.getItem('watched_' + blogPostId) || "[]");
    if (!watched.includes(num)) {
      watched.push(num);
      localStorage.setItem('watched_' + blogPostId, JSON.stringify(watched));
    }
  }

  function markWatchedFromStorage() {
    let watched = JSON.parse(localStorage.getItem('watched_' + blogPostId) || "[]");
    watched.forEach(num => {
      let btn = document.querySelector(`.ep-btn[onclick*="'${num}'"]`);
      if (btn) btn.classList.add('watched');
    });
  }

  function toggleTheater() {
    const videoContainer = document.querySelector('.video-container');
    let overlay = document.getElementById('theater-overlay');
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.id = 'theater-overlay';
      overlay.setAttribute('style', 'position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.95); z-index:999; cursor:pointer;');
      overlay.onclick = toggleTheater;
      document.body.appendChild(overlay);
      videoContainer.style.position = 'relative';
      videoContainer.style.zIndex = '1000';
      videoContainer.scrollIntoView({ behavior: 'smooth', block: 'center' });
    } else {
      overlay.remove();
      videoContainer.style.zIndex = '1';
    }
  }
</script>
"""

# أعد تسمية قالب الأفلام ليكون متميزاً:
HTML_TEMPLATE_MOVIE = HTML_TEMPLATE
