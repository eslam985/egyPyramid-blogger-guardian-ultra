import logging
import os
from datetime import datetime


def get_beast_logger(name="TheBeast"):
    # إضافة سطر جديد وفواصل منقطة بعد كل رسالة آلياً
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s\n" + "—" * 60

    date_format = "%I:%M:%S %p"

    # الآن بايثون سيفهم ما هو logging
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # منع التكرار المزعج في كولاب
    logger.propagate = False

    if not logger.handlers:
        # هاندلر الكونسول
        c_handler = logging.StreamHandler()
        c_handler.setFormatter(logging.Formatter(log_format, date_format))
        logger.addHandler(c_handler)

        # هاندلر الملف (الصندوق الأسود)
        log_filename = f"log_{datetime.now().strftime('%Y-%m-%d')}.log"
        f_handler = logging.FileHandler(log_filename, encoding="utf-8")
        f_handler.setFormatter(logging.Formatter(log_format, date_format))
        logger.addHandler(f_handler)

    return logger
