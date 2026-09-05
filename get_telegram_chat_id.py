"""
ZVB Telegram Chat ID Detector
Automatically discovers your Telegram Group/Channel ID and updates config.json
"""

import sys
import json
import os
import requests

sys.stdout.reconfigure(encoding='utf-8')

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"telegram": {}}

def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

def main():
    print("=" * 60)
    print("      ZVB - ابزار اتصال ربات تلگرام به گروه شرکت")
    print("=" * 60)
    
    cfg = load_config()
    current_token = cfg.get("telegram", {}).get("bot_token", "")
    
    if current_token and current_token != "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        print(f"توکن فعلی در کانفیگ: {current_token[:10]}...{current_token[-5:]}")
        use_curr = input("آیا از همین توکن استفاده شود؟ (y/n): ").strip().lower()
        if use_curr == 'y':
            bot_token = current_token
        else:
            bot_token = input("لطفاً توکن ربات جدید را وارد کنید: ").strip()
    else:
        bot_token = input("لطفاً توکن رباتی که از BotFather گرفتید را وارد کنید: ").strip()

    if not bot_token:
        print("❌ توکن وارد نشد!")
        return

    # Check bot info
    try:
        r = requests.get(f"https://api.telegram.org/bot{bot_token}/getMe", timeout=10)
        bot_info = r.json()
        if not bot_info.get("ok"):
            print("❌ خطا: توکن وارد شده معتبر نیست یا دسترسی به تلگرام مقدور نیست.")
            print("جزئیات:", bot_info.get("description"))
            return
        bot_username = bot_info["result"]["username"]
        print(f"\n✅ ربات شناسایی شد: @{bot_username}")
    except Exception as e:
        print(f"❌ خطا در برقراری ارتباط: {e}")
        return

    print("\n" + "-" * 60)
    print("📌 لطفاً مراحل زیر را در تلگرام انجام دهید:")
    print(f"۱. ربات @{bot_username} را به گروه یا کانال شرکت اضافه (Add) کنید.")
    print("۲. ربات را ادمین (Admin) کنید تا بتواند پیام بفرستد.")
    print("۳. یک پیام دلخواه (مثلاً کلمه 'سلام' یا 'test') داخل گروه بفرستید.")
    print("-" * 60)
    input("\nوقتی مراحل بالا را انجام دادید، دکمه Enter را بزنید تا گروه را شناسایی کنم...")

    try:
        r = requests.get(f"https://api.telegram.org/bot{bot_token}/getUpdates", timeout=10)
        data = r.json()
        if not data.get("ok"):
            print("خطا در دریافت پیام‌ها:", data)
            return
        
        updates = data.get("result", [])
        found_chats = {}

        for u in updates:
            msg = u.get("message") or u.get("channel_post") or u.get("my_chat_member")
            if msg:
                chat = msg.get("chat", {})
                chat_id = chat.get("id")
                chat_title = chat.get("title") or chat.get("username") or chat.get("first_name")
                chat_type = chat.get("type")
                if chat_id and chat_title:
                    found_chats[chat_id] = (chat_title, chat_type)

        if not found_chats:
            print("\n⚠️ پیامی در گروه پیدا نشد!")
            print("مطمئن شوید ربات را به گروه اضافه کرده‌اید و یک پیام جدید داخل گروه فرستاده‌اید.")
            return

        print("\n🎉 چت‌ها / گروه‌های شناسایی‌شده:")
        chat_list = list(found_chats.items())
        for idx, (cid, (ctitle, ctype)) in enumerate(chat_list, 1):
            print(f"{idx}. {ctitle} (نوع: {ctype}) -> Chat ID: {cid}")

        if len(chat_list) == 1:
            selected_id = chat_list[0][0]
            selected_title = chat_list[0][1][0]
        else:
            choice = int(input("\nشماره گروه مدنظر را انتخاب کنید (مثلاً 1): ").strip())
            selected_id = chat_list[choice - 1][0]
            selected_title = chat_list[choice - 1][1][0]

        # Update config.json
        if "telegram" not in cfg:
            cfg["telegram"] = {}
        cfg["telegram"]["enabled"] = True
        cfg["telegram"]["bot_token"] = bot_token
        cfg["telegram"]["chat_id"] = str(selected_id)
        save_config(cfg)

        print("\n" + "=" * 60)
        print(f"✅ تنظیمات با موفقیت ذخیره شد!")
        print(f"گروه متصل‌شده: {selected_title} (ID: {selected_id})")
        print("ارسال پیام تست به گروه...")

        test_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        test_msg = {
            "chat_id": selected_id,
            "text": "🚀 <b>ZVB Radar متصل شد!</b>\n\nاز این پس تمام پروژه‌ها و آگهی‌های کارفرمایان و شرکت‌های ساختمانی صوفیه در این گروه اطلاع‌رسانی خواهد شد.\n\n🌐 https://zvb.bg",
            "parse_mode": "HTML"
        }
        res = requests.post(test_url, json=test_msg, timeout=10)
        if res.status_code == 200:
            print("🎉 پیام تست با موفقیت به گروه ارسال شد! به گروه تلگرام خود سر بزنید.")
        else:
            print("خطا در ارسال پیام تست:", res.text)
        print("=" * 60)

    except Exception as e:
        print(f"خطا: {e}")

if __name__ == "__main__":
    main()
