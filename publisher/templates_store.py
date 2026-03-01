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
  :root {
    --poster-url: url('{{POSTER_URL}}');
  }

  /* إجبار الحارس على إظهار البوستر بوضوح */
  .pyramid-lock-box {
    background-image: var(--poster-url) !important;
    background-size: cover !important;
    background-position: center !important;
    background-color: #000 !important;
  }

  /* إضافة تأثير ضبابي خفيف خلف نص "إضغط لتنشيط المشاهدة" ليصبح أوضح */
  .pyramid-lock-box div[style*="background:rgba(0,0,0,0.5)"] {
    backdrop-filter: blur(3px);
    -webkit-backdrop-filter: blur(3px);
  }

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
  /* SERVER BUTTONS - أزرار السيرفرات المطورة */
  /* ================================================= */
  .server-buttons {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 12px;
    background: var(--color-footer-bg);
    padding: 20px 10px;
  }

  .server-btn {
    cursor: pointer;
    color: #fff !important;
    border: 2px solid rgba(255, 255, 255, 0.1);
    /* برواز خفيف جداً */
    padding: 10px 18px;
    border-radius: 8px;
    font-weight: bold;
    font-size: 13px;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    min-width: 110px;
    text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.5);

    /* اللمسة الاحترافية: تدرج ناعم يخلي اللون مش فاقع */
    background-image: linear-gradient(to bottom, rgba(255, 255, 255, 0.15), rgba(0, 0, 0, 0.15));
    opacity: 0.85;
  }

  .server-btn:hover {
    opacity: 1;
    transform: translateY(-3px);
    filter: brightness(1.1);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  }

  /* تعديل حالة النشاط (Active) */
  .server-btn.active {
    opacity: 1;
    /* الحقيقة الصارمة: شلنا اللون الثابت عشان نسيب لون الجافا سكريبت يظهر */
    border: 2px solid #fff !important;
    transform: scale(1.08);
    box-shadow: 0 0 20px rgba(255, 255, 255, 0.3);
    z-index: 2;
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
    <div style="display:none;">{{EPISODES_BUTTONS}}</div>

    <div class="server-buttons" id="dynamic-servers-container">
    </div>


    <div class="player">
      <iframe id="video-player-frame" src="about:blank" data-src="{{VOE_URL}}" allowfullscreen></iframe>
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

  <div class="seo-section">
    <h4 class="seo-title">🏷️ وسوم البحث ذات الصلة:</h4>
    <div class="seo-tags-wrapper">
      {{TAGS_CONTENT}}
    </div>
  </div>

  <input type="hidden" id="poster-source" value="{{POSTER_URL}}">
  <script>
    let currentEpNum = 1; // للفيلم نعتبره حلقة 1 دائماً
    let blogPostId = "{{POST_ID}}";

    window.onload = function () {
      const mainBtn = document.querySelector('.ep-btn');
      if (mainBtn) mainBtn.click();
      markWatchedFromStorage();
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

    // الاحتفاظ بداله الحلقات في قالب الافلام احطياطي!
    function playEpDynamic(btn, num, downloadUrl, linksJson) {
      const rawLinks = JSON.parse(linksJson);
      const container = document.getElementById('dynamic-servers-container');
      const epTitle = document.getElementById('current-ep');
      const dBtn = document.getElementById('download-btn');
      currentEpNum = parseInt(num);

      if (epTitle) epTitle.innerText = "الحلقة " + num;
      if (dBtn) dBtn.href = downloadUrl;

      // 1. خريطة الأولوية والألوان (الباب موارب لأي سيرفر جديد)
      const serverConfig = {
        'vk': { priority: 1, color: '#4c75a3' }, // أزرق VK
        'ok': { priority: 2, color: '#ee8208' }, // برتقالي OK
        'vidtube': { priority: 3, color: '#ff0000' }, // أحمر VidTube
        'voe': { priority: 4, color: '#00d0ff' }, // سماوي Voe
        'doodstream': { priority: 5, color: '#111827' }, // أسود ليلي
        'streamtape': { priority: 6, color: '#0056b3' }, // أزرق ملكي
        'mixdrop': { priority: 7, color: '#10b981' }, // أخضر زمردي
        'lulustream': { priority: 8, color: '#8b5cf6' }, // بنفسجي
        'default': { priority: 99, color: '#444' }    // رمادي لأي سيرفر جديد
      };

      // 2. ترتيب السيرفرات بناءً على الخريطة
      const sortedLinks = rawLinks.sort((a, b) => {
        const pA = serverConfig[a.name.toLowerCase()]?.priority || serverConfig.default.priority;
        const pB = serverConfig[b.name.toLowerCase()]?.priority || serverConfig.default.priority;
        return pA - pB;
      });

      container.innerHTML = '';

      // 3. إنشاء الأزرار بالألوان الجديدة
      sortedLinks.forEach((link, index) => {
        const sBtn = document.createElement('button');
        const cfg = serverConfig[link.name.toLowerCase()] || serverConfig.default;

        sBtn.className = 'server-btn' + (index === 0 ? ' active' : '');
        sBtn.innerText = 'سيرفر ' + (link.name.toUpperCase());

        // تطبيق اللون المخصص للباكجراوند
        sBtn.style.backgroundColor = cfg.color;
        sBtn.style.borderColor = 'rgba(255,255,255,0.2)';

        sBtn.onclick = function () {
          document.querySelectorAll('.server-btn').forEach(b => b.classList.remove('active'));
          sBtn.classList.add('active');
          changeS(sBtn, link.url);
        };
        container.appendChild(sBtn);
      });

      if (sortedLinks.length > 0) changeS(null, sortedLinks[0].url);

      document.querySelectorAll('.ep-btn').forEach(b => b.classList.remove('active'));
      if (btn) btn.classList.add('active');
      saveToWatched(num);
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

      // فحص القفل من الرابط أو من ذاكرة المتصفح مباشرة
      const isUnlocked = window.location.search.includes('unlocked=true') || localStorage.getItem('pyramid_unlocked_' + blogPostId) === 'true';

      const ua = navigator.userAgent || navigator.vendor || window.opera;
      const isFB = /FBAN|FBAV/i.test(ua);

      const newFrame = frame.cloneNode(true);

      // تحديث صلاحيات الـ Sandbox للسيرفرات لضمان العمل على الموبايل
      if (url.includes("ok.ru") || url.includes("vk") || url.includes("vidtube")) {
        newFrame.setAttribute('referrerpolicy', 'no-referrer');
        newFrame.setAttribute('sandbox', 'allow-forms allow-scripts allow-same-origin allow-popups allow-presentation allow-pointer-lock allow-popups-to-escape-sandbox');
      } else {
        newFrame.removeAttribute('sandbox');
        newFrame.setAttribute('referrerpolicy', 'strict-origin-when-cross-origin');
      }

      // إظهار أنيميشن "جاري التحميل" فوراً
      // إظهار أنيميشن "جاري التحميل" فوق البوستر
      newFrame.style.backgroundColor = "#000";
      newFrame.style.backgroundImage = `url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 50 50"><circle cx="25" cy="25" r="20" fill="none" stroke="%23e0a800" stroke-width="5" stroke-dasharray="95" stroke-dashoffset="0"><animateTransform attributeName="transform" type="rotate" from="0 25 25" to="360 25 25" dur="1s" repeatCount="indefinite"/></circle></svg>'), url('{{POSTER_URL}}')`;
      newFrame.style.backgroundRepeat = "no-repeat, no-repeat";
      newFrame.style.backgroundPosition = "center center, center center";
      newFrame.style.backgroundSize = "40px, cover";

      if (isUnlocked) {
        // تشغيل فوري إذا كان الزائر قد تخطى الروابط المختصرة سابقاً
        newFrame.src = url;
        newFrame.dataset.lastSrc = url;
        newFrame.classList.add('pyramid-unlocked');
      } else {
        newFrame.src = "about:blank";
        newFrame.style.background = "url('{{POSTER_URL}}') center center / cover no-repeat #000";
        newFrame.classList.remove('pyramid-unlocked');
      }

      newFrame.setAttribute('data-src', url);
      frame.parentNode.replaceChild(newFrame, frame);

      // توقيت دقيق لاستدعاء الحارس
      setTimeout(() => {
        if (typeof secureMedia === 'function') secureMedia();
      }, 100);

      // تحديث حالة الأزرار
      // تحديث حالة الأزرار
      let sBtns = document.querySelectorAll('.server-btn');
      sBtns.forEach(b => b.classList.remove('active'));

      // التعديل هنا: التأكد من وجود الزر قبل إضافة الكلاس
      if (btn) {
        btn.classList.add('active');
      }

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

    } // نهاية الدالة

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

<meta name="robots" content="follow, index, max-snippet:-1, max-video-preview:-1, max-image-preview:large" />
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
  /* SERVER BUTTONS - أزرار السيرفرات المطورة */
  /* ================================================= */
  .server-buttons {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 12px;
    background: var(--color-footer-bg);
    padding: 20px 10px;
  }

  .server-btn {
    cursor: pointer;
    color: #fff !important;
    border: 2px solid rgba(255, 255, 255, 0.1);
    /* برواز خفيف جداً */
    padding: 10px 18px;
    border-radius: 8px;
    font-weight: bold;
    font-size: 13px;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    min-width: 110px;
    text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.5);

    /* اللمسة الاحترافية: تدرج ناعم يخلي اللون مش فاقع */
    background-image: linear-gradient(to bottom, rgba(255, 255, 255, 0.15), rgba(0, 0, 0, 0.15));
    opacity: 0.85;
  }

  .server-btn:hover {
    opacity: 1;
    transform: translateY(-3px);
    filter: brightness(1.1);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  }

  /* تعديل حالة النشاط (Active) */
  .server-btn.active {
    opacity: 1;
    /* الحقيقة الصارمة: شلنا اللون الثابت عشان نسيب لون الجافا سكريبت يظهر */
    border: 2px solid #fff !important;
    transform: scale(1.08);
    box-shadow: 0 0 20px rgba(255, 255, 255, 0.3);
    z-index: 2;
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
    const url = data - posters[0].url;
    
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
    const rawLinks = JSON.parse(linksJson);
    const container = document.getElementById('dynamic-servers-container');
    const epTitle = document.getElementById('current-ep');
    const dBtn = document.getElementById('download-btn');
    currentEpNum = parseInt(num);

    if (epTitle) epTitle.innerText = "الحلقة " + num;
    if (dBtn) {
    dBtn.href = downloadUrl;
    dBtn.innerHTML = `📥 تحميل الحلقة ${num} HD`; // هنا التغيير الديناميكي للنص
}

    // 1. خريطة الأولوية والألوان (الباب موارب لأي سيرفر جديد)
    const serverConfig = {
      'vk': { priority: 1, color: '#4c75a3' }, // أزرق VK
      'ok': { priority: 2, color: '#ee8208' }, // برتقالي OK
      'vidtube': { priority: 3, color: '#ff0000' }, // أحمر VidTube
      'voe': { priority: 4, color: '#00d0ff' }, // سماوي Voe
      'doodstream': { priority: 5, color: '#111827' }, // أسود ليلي
      'streamtape': { priority: 6, color: '#0056b3' }, // أزرق ملكي
      'mixdrop': { priority: 7, color: '#10b981' }, // أخضر زمردي
      'lulustream': { priority: 8, color: '#8b5cf6' }, // بنفسجي
      'default': { priority: 99, color: '#444' }    // رمادي لأي سيرفر جديد
    };

    // 2. ترتيب السيرفرات بناءً على الخريطة
    const sortedLinks = rawLinks.sort((a, b) => {
      const pA = serverConfig[a.name.toLowerCase()]?.priority || serverConfig.default.priority;
      const pB = serverConfig[b.name.toLowerCase()]?.priority || serverConfig.default.priority;
      return pA - pB;
    });

    container.innerHTML = '';

    // 3. إنشاء الأزرار بالألوان الجديدة
    sortedLinks.forEach((link, index) => {
      const sBtn = document.createElement('button');
      const cfg = serverConfig[link.name.toLowerCase()] || serverConfig.default;

      sBtn.className = 'server-btn' + (index === 0 ? ' active' : '');
      sBtn.innerText = 'سيرفر ' + (link.name.toUpperCase());

      // تطبيق اللون المخصص للباكجراوند
      sBtn.style.backgroundColor = cfg.color;
      sBtn.style.borderColor = 'rgba(255,255,255,0.2)';

      sBtn.onclick = function () {
        document.querySelectorAll('.server-btn').forEach(b => b.classList.remove('active'));
        sBtn.classList.add('active');
        changeS(sBtn, link.url);
      };
      container.appendChild(sBtn);
    });

    if (sortedLinks.length > 0) changeS(null, sortedLinks[0].url);

    document.querySelectorAll('.ep-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    saveToWatched(num);
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

      const isUnlocked = window.location.search.includes('unlocked=true') || localStorage.getItem('pyramid_unlocked') === 'true';
      const ua = navigator.userAgent || navigator.vendor || window.opera;
      const isFB = /FBAN|FBAV/i.test(ua);

      const newFrame = frame.cloneNode(true);

      if (url.includes("ok.ru") || url.includes("vk") || url.includes("vidtube")) {
        newFrame.setAttribute('referrerpolicy', 'no-referrer');
        // صلاحيات متطورة لضمان العمل على الموبايل وفيسبوك
        newFrame.setAttribute('sandbox', 'allow-forms allow-scripts allow-same-origin allow-popups allow-presentation allow-pointer-lock allow-popups-to-escape-sandbox');
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
      // وضع خلفية سوداء مع أنيميشن التحميل فوراً
      newFrame.style.background = "#000 url('data:image/svg+xml;utf8,<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"40\" height=\"40\" viewBox=\"0 0 50 50\"><circle cx=\"25\" cy=\"25\" r=\"20\" fill=\"none\" stroke=\"%23e0a800\" stroke-width=\"5\" stroke-dasharray=\"95\" stroke-dashoffset=\"0\"><animateTransform attributeName=\"transform\" type=\"rotate\" from=\"0 25 25\" to=\"360 25 25\" dur=\"1s\" repeatCount=\"indefinite\"/></circle></svg>') no-repeat center center";

      if (isUnlocked) {
        // لو الزائر "Unlocked"، ابدأ تحميل الفيديو فوراً
        newFrame.src = url;
        newFrame.dataset.lastSrc = url;
        newFrame.classList.add('pyramid-unlocked');
      } else {
        newFrame.src = "about:blank";
        newFrame.classList.remove('pyramid-unlocked');
      }

      newFrame.setAttribute('data-src', url);
      frame.parentNode.replaceChild(newFrame, frame);

      // استدعاء الحارس بعد وقت كافٍ لضمان استقرار الإطار الجديد
      setTimeout(() => {
        if (typeof secureMedia === 'function') secureMedia();
      }, 100);
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
