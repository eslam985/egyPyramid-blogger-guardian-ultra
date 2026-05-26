# /media/es/DDrive/projects/apps-python/egyPyramid-guardian-ultra/downloader_new/media/processor.py
import os
import subprocess
from bidi.algorithm import get_display
import arabic_reshaper
from downloader_new.shared.logger import get_beast_logger

log = get_beast_logger("GuardianUltra")


def apply_media_disguise(vid_path, idx, display_title, LOGO_FILE):
    """
    تقوم هذه الدالة بتطبيق فلتر FFmpeg لكسر بصمة الفيديو وإضافة الشعارات.
    """
    try:
        # إنشاء مسار للملف المموه في نفس مجلد الفيديو الحالي
        extract_dir_current = os.path.dirname(vid_path)
        disguised_file = os.path.join(extract_dir_current, f"disguised_{idx}.mp4")

        log.info(f"🕵️ جاري تطبيق التمويه لكسر البصمة: {os.path.basename(vid_path)}")

        def get_duration(file):
            cmd = [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                file,
            ]
            result = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            return float(result.stdout.strip()) if result.stdout.strip() else 0.0

        # تجهيز النص العربي
        raw_text = "To see more, please search on Google for EGY PYRAMID"
        reshaped_text = arabic_reshaper.reshape(raw_text)
        bidi_text = get_display(reshaped_text)  # النص الآن جاهز للعرض الصحيح

        # 1. حساب المدة والتحكم الديناميكي في الجودة والمساحة
        duration = get_duration(vid_path)
        mid_time = duration / 2
        duration_mins = duration / 60

        if duration_mins > 150:
            # إعدادات للأفلام الطويلة جداً (أمان ضد التقسيم)
            t_maxrate, t_bufsize, t_crf = "1.5M", "1.5M", 28
            log.info(f"🎬 فيلم طويل ({duration_mins:.1f}m) -> ضبط: 1.5M/CRF28")
        else:
            # إعدادات للأفلام العادية (أعلى جودة ممكنة)
            t_maxrate, t_bufsize, t_crf = "1.8M", "3M", 26
            log.info(f"🎬 فيلم عادي ({duration_mins:.1f}m) -> ضبط: 1.8M/CRF26")

        # 2. بناء أمر FFmpeg بالقيم الجديدة
        ffmpeg_cmd = (
            f'ffmpeg -loglevel error -y -i "{vid_path}" -i "{LOGO_FILE}" -filter_complex '
            f'"[0:v]scale=iw*1.05:-1,crop=iw/1.05:ih/1.05,eq=gamma=1.05:contrast=1.03[v_final]; '
            f"[v_final]drawtext=text='EGY PYRAMID':fontcolor=0xFFD700:fontsize=80:x=(w-text_w)/2:y=(h-text_h)/2:enable='between(t,0,10)'[txt1]; "
            f"[txt1]drawtext=text='{bidi_text}':fontcolor=0xFFD700:fontsize=w/35:x=(w-text_w)/2:y=h-th-40:"
            f"enable='between(t,{mid_time},{mid_time+10})'[txt2]; "
            f"[1:v]format=rgba,colorchannelmixer=aa=1.0[logo_bright]; "
            f"[txt2][logo_bright]overlay=W-w-20:20[outv]"
            f'" '
            f'-map "[outv]" -map 0:a -c:a copy '  # نسخ مسار الصوت الأصلي مباشرة دون إعادة معالجة
            f"-c:v libx264 -preset ultrafast -crf {t_crf} "
            f"-maxrate {t_maxrate} -bufsize {t_bufsize} -threads 0 -pix_fmt yuv420p "
            f'"{disguised_file}"'
        )
        # ultrafast → superfast → veryfast → faster → fast → medium → slow → slower → veryslow
        # تنفيذ العملية
        subprocess.run(ffmpeg_cmd, shell=True, check=True)

        # الاستبدال المادي: حذف الأصلي وتسمية المموه باسم الأصلي
        if os.path.exists(disguised_file):
            os.remove(vid_path)
            os.rename(disguised_file, vid_path)
            log.info(f"✅ تم تحصين الحلقة {idx} بنجاح!")

    except Exception as e:
        log.warning(f"⚠️ خطأ في التمويه، سيتم الرفع الأصلي: {e}")


def is_compressed(file_path: str) -> bool:
    """فحص إذا كان الملف مضغوطاً باستخدام أمر file."""
    file_info = subprocess.getoutput(f'file "{file_path}"').lower()
    return "rar archive" in file_info or "zip archive" in file_info


def extract_archive(archive_path: str, extract_dir: str) -> None:
    """استخراج ملف مضغوط باستخدام unrar."""
    subprocess.run(
        ["unrar", "e", "-y", archive_path, os.path.join(extract_dir, "")],
        capture_output=True,
    )
    if os.path.exists(archive_path):
        os.remove(archive_path)
