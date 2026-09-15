╔══════════════════════════════════════════════════════════════╗
║         Advanced Multi-Agent C2 — Android Edition            ║
║                       README.txt                             ║
╚══════════════════════════════════════════════════════════════╝

نظرة عامة
─────────
أداة تحكم عن بُعد (C2) متعددة الوكلاء لاختبار الاختراق المصرّح به
على أجهزة Android. تتكون من:

  • listener.py  → السيرفر (Kali)
  • agent.py     → الوكيل (Android/Termux)

المتطلبات
─────────
  Kali:    pip install pycryptodome
  Android: pkg install python && pip install pycryptodome

الإعداد
───────
  في listener.py:
      LISTEN_HOST = "0.0.0.0"
      LISTEN_PORT = 4444
      SECRET_KEY  = b"ChangeThisKey32BytesLong!!!!!!"

  في agent.py:
      C2_HOST     = "192.168.8.120"
      C2_PORT     = 4444
      SECRET_KEY  = b"ChangeThisKey32BytesLong!!!!!!"

  ⚠️ SECRET_KEY يجب أن يكون متطابقًا في الملفين.

التشغيل
───────
  Kali:    python3 listener.py
  Android: python ~/agent.py

أوامر سريعة
───────────
  agents                  عرض الأجهزة المتصلة
  use <id>                التبديل لجهاز
  send <id> <cmd>         أمر لجهاز محدد
  broadcast <cmd>         أمر لكل الأجهزة
  kill <id>               قطع اتصال
  upload <path.apk>       رفع APK من Kali
  help                    المساعدة الكاملة

أوامر الوكيل
────────────
  cd / ls / cat / pwd / tree        التنقل
  shell:<cmd>                       أمر shell
  rish:<cmd>                        أمر Shizuku
  info                              معلومات الجهاز
  screenshot                        لقطة شاشة
  install_url:<url>                 تثبيت APK من رابط
  uninstall:<pkg>                   حذف تطبيق
  list_apps                         قائمة التطبيقات

الأخطاء الشائعة
───────────────
  "Padding is incorrect"    → SECRET_KEY مختلف
  "no response or timeout"  → أعد تشغيل Agent
  "screencap: not found"    → استخدم /system/bin/screencap
  "Shizuku not running"     → افتح Shizuku → Start

التحذير
───────
  هذه الأداة للأغراض التعليمية واختبار الاختراق المصرّح به فقط.
  الاستخدام على أجهزة لا تملكها = جريمة إلكترونية.

═══════════════════════════════════════════════════════════════
                    نهاية README
═══════════════════════════════════════════════════════════════
