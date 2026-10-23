#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
allegro_device.py — OAuth Device Flow لأليغرو ساندبوكس
للاستخدام المصرح به فقط: برنامج Intigriti / بيئة الساندبوكس الرسمية.

الاستخدام:
    python allegro_device.py

ماذا يفعل:
  1) يطلب رمز جهاز (device code) من أليغرو ساندبوكس
  2) يفتح المتصفح على صفحة الموافقة — سجّل الدخول بحسابك في الساندبوكس ووافق
  3) يلتقط التوكن تلقائيًا ويحفظه في allegro_token.txt
  4) يختبر GET /me فورًا (الخطوة 3 من قائمة بوابة أليغرو)
لا يحتاج أي مكتبات خارجية — بايثون القياسي فقط.
"""
import base64
import getpass
import json
import sys
import time
import webbrowser
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

CLIENT_ID_DEFAULT = "111627973"
UA = "jaber-55/1.0 (+https://github.com/jsiadyarslan-lab/leakmatrix)"
BASE = "https://allegro.pl.allegrosandbox.pl"
DEVICE = BASE + "/auth/oauth/device"
TOKEN = BASE + "/auth/oauth/token"
ME = "https://api.allegro.pl.allegrosandbox.pl/me"


def post_form(url, data, auth=None):
    headers = {
        "User-Agent": UA,
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }
    if auth:
        headers["Authorization"] = auth
    req = Request(url, data=urlencode(data).encode("utf-8"), headers=headers, method="POST")
    with urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def basic_header(client_id, secret):
    raw = "%s:%s" % (client_id, secret)
    return "Basic " + base64.b64encode(raw.encode("utf-8")).decode("ascii")


def main():
    client_id = sys.argv[1].strip() if len(sys.argv) > 1 else CLIENT_ID_DEFAULT
    # وسيط ثانٍ اختياري: اسم لاحقة لملفات التوكن حتى لا يُطمس توكن حساب بآخر
    # مثال: python allegro_device.py <client_id> victim  → allegro_token_victim.txt
    suffix = sys.argv[2].strip() if len(sys.argv) > 2 else ""
    token_file = "allegro_token%s.txt" % (("_" + suffix) if suffix else "")
    refresh_file = "allegro_refresh%s.txt" % (("_" + suffix) if suffix else "")
    print("=== LeakMatrix | Allegro Sandbox — Device Flow ===")
    if suffix:
        print("وضع اللاحقة: %s — سيُحفظ التوكن في %s (لن يُطمس توكن الحساب الآخر)" % (suffix, token_file))
    print("Client ID: %s" % client_id)
    # التوثيق الرسمي: طلب رمز الجهاز يستوجب ترويسة Authorization: Basic
    # بترميز base64(client_id:client_secret). السر يُقرأ تفاعليًا فقط:
    # لا يُحفظ في ملف، ولا يُرسل لأي طرف، ولا يظهر على الشاشة.
    secret = getpass.getpass("الصق client_secret ثم Enter (لن يظهر أثناء الكتابة): ").strip()
    if not secret:
        print("client_secret مطلوب — موجود في صفحة تطبيقك في البوابة")
        sys.exit(1)
    auth = basic_header(client_id, secret)

    print("[1/3] طلب رمز الجهاز من:", DEVICE)
    try:
        d = post_form(DEVICE, {"client_id": client_id}, auth=auth)
    except HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", "replace")[:300]
        except Exception:
            pass
        print("فشل HTTP %s" % e.code)
        if body:
            print("الرد: %s" % body)
        www = e.headers.get("WWW-Authenticate") if e.headers else None
        if www:
            print("ترويسة WWW-Authenticate: %s" % www)
        print("تلميحات إن تكرر الرفض:")
        print("  1) تحقق من client_secret: انسخه من صفحة تطبيقك من جديد")
        print("  2) نوع التطبيق يجب أن يكون 'بدون متصفح/لوحة مفاتيح' ليقبل Device Flow")
        print("     (التوثيق: لا يمكن تغيير النوع بعد التسجيل — أنشئ تطبيقًا جديدًا")
        print("     بالنوع الصحيح ثم شغّل: python scripts\\allegro_device.py <client_id_الجديد>)")
        print("  3) جرّب لاحقًا أو من شبكة الهاتف (Hotspot) إن ظهرت صفحة JS بدل الخطأ")
        sys.exit(1)
    except (URLError, json.JSONDecodeError) as e:
        print("الرد ليس JSON (تحويل لصفحة دخول أو حماية DataDome): %s" % e)
        print("تلميح: جرّب لاحقًا أو من شبكة الهاتف (Hotspot).")
        sys.exit(1)

    user_code = d.get("user_code", "?")
    vurl = d.get("verification_uri_complete") or d.get("verification_uri")
    print("    رمز الجهاز صالح لـ %s ثانية" % d.get("expires_in", 600))
    print("[2/3] سأفتح المتصفح على صفحة الموافقة:")
    print("      %s" % vurl)
    print("      رمز التأكيد: %s" % user_code)
    print("      سجّل الدخول بحسابك في الساندبوكس (allegrosandbox) ووافق على الطلب.")
    try:
        if vurl:
            webbrowser.open(vurl)
    except Exception:
        print("      تعذر فتح المتصفح تلقائيًا — انسخ الرابط أعلاه يدويًا.")

    interval = int(d.get("interval", 5) or 5)
    deadline = time.time() + int(d.get("expires_in", 600) or 600)
    print("[3/3] أنتظر موافقتك (كل %s ثانية)... اضغط Ctrl+C للإلغاء" % interval)

    token = None
    while time.time() < deadline:
        time.sleep(interval)
        try:
            t = post_form(
                TOKEN,
                {
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "device_code": d["device_code"],
                    "client_id": client_id,
                },
                auth=auth,
            )
        except HTTPError as e:
            try:
                err = json.loads(e.read().decode("utf-8"))
            except Exception:
                err = {}
            ec = err.get("error", "")
            if ec == "authorization_pending":
                print("    ... ما زلت أنتظر موافقتك في المتصفح", flush=True)
                continue
            if ec == "slow_down":
                interval += 5
                continue
            print("خطأ من الخادم: %s" % err)
            sys.exit(1)
        except (URLError, TimeoutError) as e:
            print("    خطأ شبكة عابر، أعيد المحاولة: %s" % e, flush=True)
            continue
        except json.JSONDecodeError:
            print("    رد غير JSON (حماية DataDome؟) — أعيد المحاولة...", flush=True)
            continue

        token = t.get("access_token")
        if not token:
            print("رد غير متوقع: %s" % t)
            sys.exit(1)
        with open(token_file, "w", encoding="utf-8") as f:
            f.write("Bearer " + token + "\n")
        if t.get("refresh_token"):
            with open(refresh_file, "w", encoding="utf-8") as f:
                f.write(t["refresh_token"] + "\n")
        print("")
        print("نجح التوكن! حُفظ في %s (لا تشارك هذا الملف مع أحد)" % token_file)
        if t.get("refresh_token"):
            print("refresh_token حُفظ أيضًا في %s" % refresh_file)
        break
    else:
        print("انتهت المهلة دون موافقة — شغّل السكربت من جديد.")
        sys.exit(1)

    print("--- اختبار GET /me (الخطوة 3 من بوابة أليغرو) ---")
    req = Request(
        ME,
        headers={
            "User-Agent": UA,
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.allegro.public.v1+json",
            "Accept-Language": "pl-PL",
        },
    )
    try:
        with urlopen(req, timeout=30) as r:
            me = json.loads(r.read().decode("utf-8"))
            print(json.dumps(me, indent=2, ensure_ascii=False))
            print("")
            print("المعرف/الاسم أعلاه = حسابك (المهاجم B) الذي سنستخدمه في الواجهة.")
    except HTTPError as e:
        print("/me رجعت HTTP %s — تحقق من الترويسة User-Agent المسجلة" % e.code)
    except (URLError, json.JSONDecodeError) as e:
        print("/me فشل قراءة الرد: %s" % e)


if __name__ == "__main__":
    main()
