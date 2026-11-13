# -*- coding: utf-8 -*-
"""
ZVB Executive Daily Digest & Zero-Duplicate Publisher v3.0
Representative: Амир (Amir) | Company: „Загрос Витоша България“ ЕООД (ZVB)

Strictly enforces:
1. 100% Phone-Verified Projects Only (No Phone = Never Sent)
2. Zero Duplicate Guarantee (Tracks digest_sent in alert_history.json so no project is ever repeated)
3. Dual-Tier Breakdown:
   - Small & Medium Projects (Renovations, Apartments, Switchboards, CCTV, Fast Repairs)
   - Large & Turnkey Construction Projects (General Contractors, KSB Builders, Residential Complexes & Villas)
"""

import os
import sys
import json
import time
import datetime
import requests

import lead_scraper
import lead_filter_engine

sys.stdout.reconfigure(encoding='utf-8')

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
LEADS_JSON_PATH = os.path.join(DATA_DIR, "leads.json")


def load_config():
    return lead_scraper.load_config()


def is_strictly_electrical_sofia(lead):
    """
    Validates that a lead is in Sofia, has a valid Bulgarian phone number,
    and is not closed/expired or irrelevant.
    """
    if not isinstance(lead, dict):
        return False
    has_p, _ = lead_filter_engine.has_valid_bg_phone(lead)
    if not has_p:
        return False
    closed, _ = lead_filter_engine.is_project_closed_or_expired(lead)
    if closed:
        return False
    in_sofia, _ = lead_filter_engine.is_valid_sofia_region(lead)
    return in_sofia


def send_telegram(text, token, chat_id):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        r = requests.post(url, json=payload, timeout=15)
        return r.status_code == 200
    except Exception as e:
        print(f"Telegram send error: {e}")
        return False


def build_daily_digest(period_title="Електро и Строителен Бюлетин — София"):
    """
    Builds a non-repetitive, 100% phone-verified digest of new Small & Large Sofia projects.
    Marks every included lead as digest_sent in alert_history.json so it is NEVER repeated!
    """
    alert_history = lead_filter_engine.load_alert_history()
    existing_leads = lead_scraper.load_existing_leads()

    # Discover fresh leads if we don't have un-digested leads ready
    un_digested = []
    for lid, l in existing_leads.items():
        if not is_strictly_electrical_sofia(l):
            continue
        hist_entry = alert_history.get(lid, {})
        if not hist_entry.get("digest_sent"):
            un_digested.append(l)

    if len(un_digested) < 4:
        # Pull fresh verified Sofia leads from Business.bg & KSB & classifieds
        new_biz = lead_scraper.scrape_business_bg_sofia(existing_leads, alert_history, max_new=3)
        new_ksb = lead_scraper.scrape_ksb_sofia_builders(existing_leads, alert_history, max_new=3)
        new_zap = lead_scraper.scrape_zaplata_sofia_construction(existing_leads, alert_history, max_new=2)
        for item in (new_biz + new_ksb + new_zap):
            existing_leads[item["id"]] = item
            un_digested.append(item)
        lead_scraper.save_leads(existing_leads)

    if not un_digested:
        return None

    # Separate into Small/Medium vs Large/Turnkey B2B
    small_medium = []
    large_turnkey = []

    for l in un_digested:
        tier, _ = lead_filter_engine.calculate_project_value_tier(l)
        if tier == "LARGE_TURNKEY_B2B" or l.get("category") == "contractor":
            large_turnkey.append(l)
        else:
            small_medium.append(l)

    selected_small = small_medium[:4]
    selected_large = large_turnkey[:5]
    all_selected = selected_small + selected_large

    if not all_selected:
        return None

    now_str = datetime.datetime.now().strftime("%d.%m.%Y | %H:%M")
    msg = (
        f"⚡🏗 <b>{period_title} (ZVB София)</b>\n"
        f"📅 <i>Дата: {now_str} | Представител: <b>Амир (Amir)</b></i>\n"
        f"✅ <i>100% проверени нови обекти с директен телефон (Без дубликати)</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    if selected_small:
        msg += "🔧⚡ <b>МАЛКИ И СРЕДНИ ПРОЕКТИ / РЕМОНТИ (پروژه‌های کوچک، بازسازی و نصب):</b>\n\n"
        for idx, l in enumerate(selected_small, 1):
            lp, ip = lead_scraper.normalize_bg_phone(l.get("phone", ""))
            disp_p = l.get("phone") or lp
            budget = lead_filter_engine.estimate_project_budget(l)
            call_links = f"<a href='tel:+{ip}'>📞 Обади се</a> | <a href='viber://chat?number=%2B{ip}'>🟣 Viber</a> | <a href='https://wa.me/{ip}'>💬 WhatsApp</a>" if ip else ""
            msg += (
                f"{idx}. <b>{l.get('title')[:70]}</b>\n"
                f"   📍 {l.get('location')} | 💰 Обем: <b>{budget}</b>\n"
                f"   📞 Телефон: <code>{disp_p}</code>\n"
                f"   👉 {call_links} | <a href='{l.get('url')}'>🔗 Източник</a>\n\n"
            )

    if selected_large:
        msg += "🏗🏢 <b>ГОЛЕМИ ПРОЕКТИ И СТРОИТЕЛИ ДО КЛЮЧ (پروژه‌های بزرگ و سازندگان صفر تا صد):</b>\n\n"
        for idx, l in enumerate(selected_large, 1):
            lp, ip = lead_scraper.normalize_bg_phone(l.get("phone", ""))
            disp_p = l.get("phone") or lp
            mgr = f" | 👤 <b>{l.get('manager')}</b>" if l.get("manager") else ""
            call_links = f"<a href='tel:+{ip}'>📞 Обади се</a> | <a href='viber://chat?number=%2B{ip}'>🟣 Viber</a> | <a href='https://wa.me/{ip}'>💬 WhatsApp</a>" if ip else ""
            msg += (
                f"{idx}. <b>{l.get('title')[:75]}</b>\n"
                f"   📍 {l.get('location')}{mgr}\n"
                f"   📞 Директен телефон: <code>{disp_p}</code>\n"
                f"   👉 {call_links} | <a href='{l.get('url')}'>🔗 Досие</a>\n\n"
            )

    # Mark all selected leads as alerted AND digest_sent so they are never repeated!
    for l in all_selected:
        lead_filter_engine.record_alert_sent(l, alert_history)
        if l["id"] in alert_history:
            alert_history[l["id"]]["digest_sent"] = True
    lead_filter_engine.save_alert_history(alert_history)
    lead_filter_engine.sync_git_history()

    # Add ready-to-copy pitch in Amir's name
    msg += (
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💬 <b>Готов текст за контакт от името на Амир (Кликни за копиране):</b>\n"
        "<code>Здравейте! Казвам се Амир от фирма „Загрос Витоша България“ ЕООД (гр. София). "
        "Изпълняваме силнотокови и слаботокови ел. инсталации, монтаж на ел. табла, камери и соларно осветление за сгради и обекти в София. "
        "Ще се радваме да съдействаме като надежден подизпълнител по Ваши текущи проекти. Поздрави, Амир.</code>"
    )
    return msg


def send_digest_now(period="Бюлетин за нови обекти с директен телефон"):
    cfg = load_config()
    telegram_cfg = cfg.get("telegram", {})
    token = telegram_cfg.get("bot_token")
    chat_id = telegram_cfg.get("chat_id")

    if not token or not chat_id:
        print("❌ Telegram credentials not configured in config.json")
        return False

    digest_text = build_daily_digest(period)
    if digest_text:
        ok = send_telegram(digest_text, token, chat_id)
        if ok:
            print("✅ Phone-verified, zero-duplicate digest sent to Telegram!")
            return True
    else:
        print("ℹ️ No new un-sent leads with phone numbers to broadcast right now (Zero-Duplicate protection active).")
    return False


def run_schedule():
    print("=" * 65)
    print("   ZVB Daily Digest Scheduler v3.0 (Phone-Guaranteed & Zero-Dup)")
    print("=" * 65)

    lead_scraper.run_scan()
    sent_today = set()

    while True:
        now = datetime.datetime.now()
        current_date_str = now.strftime("%Y-%m-%d")

        morning_key = f"{current_date_str}_morning"
        if now.hour == 9 and morning_key not in sent_today:
            lead_scraper.run_scan()
            send_digest_now("Сутрешен бюлетин — Нови обекти в София")
            sent_today.add(morning_key)

        evening_key = f"{current_date_str}_evening"
        if now.hour == 18 and evening_key not in sent_today:
            lead_scraper.run_scan()
            send_digest_now("Вечерен бюлетин — Нови обекти в София")
            sent_today.add(evening_key)

        if now.minute % 20 == 0 and now.second < 30:
            lead_scraper.run_scan()

        time.sleep(30)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--now", action="store_true", help="Run scan and send digest if new phone-verified leads exist")
    args = parser.parse_args()

    if args.now:
        lead_scraper.run_scan()
    else:
        run_schedule()
