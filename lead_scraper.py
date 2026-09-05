"""
ZVB Ultimate Lead Radar 10/10 - Sofia, Bulgaria
Automated scraper for Alo.bg & Bazar.bg with:
- Direct Bulgarian phone number extraction & WhatsApp / Call links
- Client intent scoring (Direct Client vs Contractor vs Renovation)
- Sofia geo-targeting priority
- Instant Telegram notifications
- Modern HTML dashboard with search, tabs, call buttons & 1-click B2B pitch copy
"""

import os
import sys
import re
import time
import json
import csv
import datetime
import urllib.parse
import requests
from bs4 import BeautifulSoup

# UTF-8 stdout
sys.stdout.reconfigure(encoding='utf-8')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept-Language': 'bg-BG,bg;q=0.9,en;q=0.8'
}

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
LEADS_JSON_PATH = os.path.join(DATA_DIR, "leads.json")
LEADS_CSV_PATH = os.path.join(DATA_DIR, "leads.csv")
DASHBOARD_HTML_PATH = os.path.join(DATA_DIR, "leads_dashboard.html")

DEFAULT_KEYWORDS = [
    "търся електротехник",
    "електротехник софия",
    "търся бригада електро",
    "строителна фирма софия",
    "довършителни ремонти софия",
    "груб строеж софия",
    "ремонт на апартамент софия",
    "ел инсталация софия",
    "монтаж на камери софия",
    "ел табло софия",
    "умен дом софия"
]

def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"telegram": {"enabled": False}, "keywords": DEFAULT_KEYWORDS}

def extract_phone_numbers(text):
    """Extracts and normalizes Bulgarian mobile phone numbers from text"""
    phones = re.findall(r'(?:(?:\+359|00359)\s*8[789]\d[\s\d-]{6,8}|08[789]\d[\s\d-]{6,8})', text)
    valid_phones = []
    for p in phones:
        digits = re.sub(r'\D', '', p)
        if digits.startswith("359") and len(digits) == 12:
            digits = "0" + digits[3:]
        elif digits.startswith("00359") and len(digits) == 14:
            digits = "0" + digits[5:]
        if len(digits) == 10 and digits.startswith("08") and digits not in valid_phones:
            valid_phones.append(digits)
    return valid_phones

def classify_lead(title, keyword):
    combined = (title + " " + keyword).lower()
    
    # 1. Direct Urgent Client (تلفن/درخواست مستقیم فوری)
    urgent_words = ["търся", "търсим", "нуждая", "трябва", "спешно", "авария", "наемам", "търси се", "възлагам"]
    if any(w in combined for w in urgent_words):
        return "urgent_client", "🎯 Директно клиентско търсене (Спешно)"
    
    # 2. Construction companies & Developers (شرکت‌های ساختمانی)
    contractor_words = ["строителна фирма", "строителство", "груб строеж", "инвеститор", "главен изпълнител", "подизпълнител"]
    if any(w in combined for w in contractor_words):
        return "contractor", "🏗️ Строителна фирма / Инвеститор"
    
    # 3. Renovation & Finishing (بازسازی)
    renovation_words = ["ремонт", "довършителн", "апартамент", "къща", "офис", "шпакловка", "бояджия"]
    if any(w in combined for w in renovation_words):
        return "renovation", "🔨 Ремонти и довършителни работи"
    
    return "direct_electrical", "⚡ Директни електроуслуги и камери"

def send_telegram_alert(lead, bot_token, chat_id):
    category_icon = "⚡"
    if lead.get("category") == "urgent_client":
        category_icon = "🎯🔥"
    elif lead.get("category") == "contractor":
        category_icon = "🏗️"
    elif lead.get("category") == "renovation":
        category_icon = "🔨"

    phone = lead.get('phone')
    phone_str = f"📞 <b>Телефон:</b> <code>{phone}</code>\n" if phone else ""

    text = (
        f"{category_icon} <b>ZVB Радар: Нов електро проект!</b>\n\n"
        f"📌 <b>Заглавие:</b> {lead.get('title')}\n"
        f"🏷️ <b>Категория:</b> {lead.get('category_label')}\n"
        f"📍 <b>Локация:</b> {lead.get('location')}\n"
        f"{phone_str}"
        f"🌐 <b>Източник:</b> {lead.get('source')} ({lead.get('keyword')})\n\n"
        f"🏢 <i>ZVB Sofia - Електрически и умни системи</i>"
    )
    
    # Inline buttons: WhatsApp, Direct Call, View Ad
    buttons = []
    first_row = []
    
    if phone and phone.startswith("08") and len(phone) == 10:
        intl_phone = "359" + phone[1:]
        wa_text = urllib.parse.quote("Здравейте! Пиша Ви от ZVB (Електроуслуги & Умен дом, София) относно Вашия проект. https://zvb.bg")
        wa_url = f"https://wa.me/{intl_phone}?text={wa_text}"
        first_row.append({"text": "💬 WhatsApp (1-клик)", "url": wa_url})
        first_row.append({"text": f"📞 Обади се ({phone})", "url": f"tel:+{intl_phone}"})
        buttons.append(first_row)
        
    buttons.append([{"text": "🔗 Отвори обявата в сайта", "url": lead.get("url", "#")}])

    reply_markup = {"inline_keyboard": buttons}
    
    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "reply_markup": reply_markup
    }
    try:
        r = requests.post(api_url, json=payload, timeout=10)
        return r.status_code == 200
    except Exception:
        return False

def load_existing_leads():
    if os.path.exists(LEADS_JSON_PATH):
        try:
            with open(LEADS_JSON_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_leads(leads_dict):
    with open(LEADS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(leads_dict, f, ensure_ascii=False, indent=2)
    
    leads_list = list(leads_dict.values())
    leads_list.sort(key=lambda x: x.get("found_at", ""), reverse=True)
    
    with open(LEADS_CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "Заглавие / Title", "Категория / Category", "Телефон / Phone", "Източник / Source", "Град / Location", "Ключова дума / Keyword", "Дата / Date", "Линк / URL"])
        for item in leads_list:
            writer.writerow([
                item.get("id", ""),
                item.get("title", ""),
                item.get("category_label", ""),
                item.get("phone", "В обявата"),
                item.get("source", ""),
                item.get("location", ""),
                item.get("keyword", ""),
                item.get("found_at", ""),
                item.get("url", "")
            ])

    generate_dashboard(leads_list)

def scrape_bazar(keyword, fetch_phone=True):
    results = []
    encoded_q = urllib.parse.quote(keyword)
    url = f"https://bazar.bg/obiavi?q={encoded_q}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
        if resp.status_code != 200:
            return results
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        links = soup.find_all('a', href=True)
        seen_links = set()

        for a in links:
            href = a['href']
            if '/obiava-' in href and href not in seen_links:
                seen_links.add(href)
                title = a.get_text(" ", strip=True)
                if not title or len(title) < 5:
                    continue
                
                ad_id_match = re.search(r'obiava-(\d+)', href)
                ad_id = f"bazar_{ad_id_match.group(1)}" if ad_id_match else f"bazar_{hash(href)}"
                full_url = urllib.parse.urljoin("https://bazar.bg", href)
                
                location = "София" if "софия" in (title + " " + keyword).lower() else "България / София"
                cat, cat_label = classify_lead(title, keyword)

                # Check phone in title/link
                phones = extract_phone_numbers(title)
                phone_val = phones[0] if phones else ""

                results.append({
                    "id": ad_id,
                    "title": title,
                    "url": full_url,
                    "source": "Bazar.bg",
                    "keyword": keyword,
                    "category": cat,
                    "category_label": cat_label,
                    "location": location,
                    "phone": phone_val,
                    "found_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                })
    except Exception as e:
        print(f"  [Bazar.bg] Error searching '{keyword}': {e}")
    return results

def scrape_alo(keyword):
    results = []
    try:
        url = "https://www.alo.bg/searchq/"
        resp = requests.get(url, params={"q": keyword}, headers=HEADERS, timeout=4)
        if resp.status_code != 200:
            return results
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        items = soup.select('.listvip-item, .list-item')
        
        for item in items:
            title = item.get('title', '')
            link_tag = item.select_one('a[href]')
            href = link_tag['href'] if link_tag else ''
            
            if not href:
                onclick = item.get('onclick', '')
                m = re.search(r"window\.location\s*=\s*'([^']+)'", onclick)
                if m:
                    href = m.group(1)
            
            if not href:
                continue
            
            if not title and link_tag:
                title = link_tag.get_text(" ", strip=True)
                
            clean_href = href.split('#')[0]
            full_url = urllib.parse.urljoin("https://www.alo.bg", clean_href)
            
            id_match = re.search(r'(\d{6,10})', clean_href)
            ad_id = f"alo_{id_match.group(1)}" if id_match else f"alo_{hash(full_url)}"
            
            addr_elem = item.select_one('.listvip-item-address, .list-item-address')
            addr_text = addr_elem.get_text(" ", strip=True) if addr_elem else ""
            
            if "софия" in addr_text.lower() or "софия" in title.lower():
                location = "София"
            elif addr_text:
                location = addr_text.split("»")[-1].strip()
            else:
                location = "България"
                
            cat, cat_label = classify_lead(title, keyword)

            # Check phones in card snippet
            phones = extract_phone_numbers(title + " " + item.text)
            phone_val = phones[0] if phones else ""

            results.append({
                "id": ad_id,
                "title": title or f"Обява в Alo.bg ({keyword})",
                "url": full_url,
                "source": "Alo.bg",
                "keyword": keyword,
                "category": cat,
                "category_label": cat_label,
                "location": location,
                "phone": phone_val,
                "found_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            })
    except Exception as e:
        print(f"  [Alo.bg] Error searching '{keyword}': {e}")
    return results

def scrape_maistorplus(username, password):
    results = []
    seen_ids = set()
    try:
        s = requests.Session()
        r1 = s.get('https://maistorplus.com/login', headers=HEADERS, timeout=12)
        soup = BeautifulSoup(r1.text, 'html.parser')
        token_input = soup.find('input', {'name': '_csrf_token'})
        if not token_input:
            return results
        csrf = token_input.get('value')
        
        login_resp = s.post('https://maistorplus.com/login_check', data={
            '_csrf_token': csrf,
            '_username': username,
            '_password': password,
            '_remember_me': 'on'
        }, headers=HEADERS, timeout=12)
        
        if login_resp.status_code != 200 and '/craftsman' not in login_resp.url:
            return results
            
        # 1. Fetch fresh jobs with NO exchanged phones first (hot opportunities)
        # 2. Then fetch latest general jobs
        endpoints = [
            'https://maistorplus.com/craftsman/jobs/no-exchanged-phones',
            'https://maistorplus.com/craftsman/jobs/all?page=1',
            'https://maistorplus.com/craftsman/jobs/all?page=2'
        ]
        
        mp_electrical_keywords = ['контакт', 'вентилатор', 'ел', 'електро', 'осветлен', 'табло', 'бойлер', 'кабел', 'ключ', 'лед', 'камер', 'умен дом']
        
        for ep in endpoints:
            try:
                r_jobs = s.get(ep, headers=HEADERS, timeout=12)
                soup_jobs = BeautifulSoup(r_jobs.text, 'html.parser')
                rows = soup_jobs.select('table tr')
                for tr in rows:
                    tds = tr.find_all('td')
                    if len(tds) >= 3:
                        title_td = tds[0]
                        city_td = tds[1] if len(tds) > 1 else None
                        budget_td = tds[2] if len(tds) > 2 else None
                        
                        link_tag = title_td.find('a', href=True) or tr.find('a', href=True)
                        if not link_tag:
                            continue
                        
                        href = link_tag['href']
                        clean_href = href.split('?')[0]
                        full_url = urllib.parse.urljoin('https://maistorplus.com', clean_href)
                        title = title_td.get_text(' ', strip=True)
                        city = city_td.get_text(' ', strip=True) if city_td else 'София'
                        budget = budget_td.get_text(' ', strip=True) if budget_td else ''
                        
                        m = re.search(r'/job/(\d+)', clean_href)
                        job_id = f"mp_{m.group(1)}" if m else f"mp_{hash(clean_href)}"
                        
                        if job_id in seen_ids:
                            continue
                        seen_ids.add(job_id)
                        
                        # Filter strictly for Sofia & electrical
                        if 'софия' not in city.lower():
                            continue
                        if not any(w in title.lower() for w in mp_electrical_keywords):
                            continue
                        
                        results.append({
                            "id": job_id,
                            "title": f"[MaistorPlus] {title} ({budget})",
                            "url": full_url,
                            "source": "MaistorPlus",
                            "keyword": "Заявка за електро проект",
                            "category": "urgent_client",
                            "category_label": "🎯 Директна клиентска заявка (MaistorPlus)",
                            "location": "София",
                            "phone": "",
                            "found_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                        })
            except Exception as e:
                print(f"  [MaistorPlus] Error on {ep}: {e}")
                
    except Exception as e:
        print(f"  [MaistorPlus] Error scraping: {e}")
    return results

def enrich_phones_for_leads(leads_list, max_to_fetch=25):
    """Fetches full page descriptions for classified ads to uncover direct phone numbers"""
    count = 0
    print(f"\n🔍 Извличане на директни телефонни номера за най-новите обяви (до {max_to_fetch} обяви)...")
    for item in leads_list:
        # Never scrape phones for MaistorPlus from public pages (avoids support number 0879590810)
        if item.get("source") == "MaistorPlus":
            continue
        if item.get("phone"):
            continue
        if count >= max_to_fetch:
            break
        try:
            r = requests.get(item["url"], headers=HEADERS, timeout=6)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                text = soup.get_text(" ", strip=True)
                phones = extract_phone_numbers(text)
                # Exclude blacklisted platform support lines
                clean_phones = [p for p in phones if p not in ['0879590810', '359879590810', '+359879590810']]
                if clean_phones:
                    item["phone"] = clean_phones[0]
                    print(f"   ↳ 📞 Намерен номер за '{item['title'][:30]}...': {item['phone']}")
            count += 1
            time.sleep(0.4)
        except Exception:
            pass

def generate_dashboard(leads):
    count_all = len(leads)
    count_urgent = sum(1 for l in leads if l.get("category") == "urgent_client")
    count_contractors = sum(1 for l in leads if l.get("category") == "contractor")
    count_renovation = sum(1 for l in leads if l.get("category") == "renovation")
    count_electrical = sum(1 for l in leads if l.get("category") == "direct_electrical")
    count_sofia = sum(1 for l in leads if "софия" in l.get("location", "").lower() or "софия" in l.get("title", "").lower())
    count_with_phone = sum(1 for l in leads if l.get("phone"))

    b2b_text = (
        "Здравейте! Пишем Ви от ZVB (Електрически и умни системи, гр. София). "
        "Предлагаме професионално подизпълнение за Вашите строителни и ремонтни обекти: "
        "пълно изграждане на ел. инсталации, прецизно асемблиране на ел. табла, видеонаблюдение (CCTV) и умен дом с 15г. опит. "
        "Работим изключително чисто, спазваме стриктно срокове и предлагаме преференциални цени за строителни фирми и инвеститори. "
        "Телефон за контакт: +359 87 7944353 | https://zvb.bg"
    )

    client_offer_text = (
        "Здравейте! Видяхме Вашето запитване. От ZVB (София) можем да поемем обекта с гаранция за качество. "
        "Предлагаме БЕЗПЛАТЕН оглед на място в рамките на София и бърза точна оферта. "
        "Моля, обадете се на +359 87 7944353 или вижте нашите завършени проекти на https://zvb.bg"
    )

    html_template = f"""<!DOCTYPE html>
<html lang="bg">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ZVB | Професионален радар за клиенти и строителни партньори</title>
    <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@600;700&family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {{
            --primary: #1A237E;
            --primary-dark: #0F172A;
            --secondary: #FFC107;
            --bg: #F8FAFC;
            --surface: #FFFFFF;
            --text: #0F172A;
            --muted: #64748B;
            --border: #E2E8F0;
            --success: #10B981;
            --urgent: #EF4444;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', sans-serif; }}
        body {{ background-color: var(--bg); color: var(--text); padding: 24px; line-height: 1.5; }}
        .container {{ max-width: 1350px; margin: 0 auto; }}
        
        header {{
            background: linear-gradient(135deg, #0F172A 0%, #1A237E 100%);
            color: white;
            padding: 28px 36px;
            border-radius: 20px;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 12px 30px -10px rgba(26, 35, 126, 0.35);
            border-bottom: 4px solid var(--secondary);
            flex-wrap: wrap;
            gap: 16px;
        }}
        header h1 {{ font-family: 'Space Grotesk', sans-serif; font-size: 26px; margin-bottom: 4px; }}
        header p {{ color: #C7D2FE; font-size: 14px; }}
        
        .header-stats {{ display: flex; gap: 16px; align-items: center; }}
        .stat-box {{
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.15);
            padding: 10px 18px;
            border-radius: 12px;
            text-align: right;
        }}
        .stat-box span {{ font-size: 24px; font-weight: 800; color: var(--secondary); display: block; }}
        .stat-box small {{ font-size: 11px; text-transform: uppercase; color: #E0E7FF; letter-spacing: 0.5px; }}

        .action-banner {{
            background: white;
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 18px 24px;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 20px;
            flex-wrap: wrap;
            box-shadow: 0 2px 8px rgba(0,0,0,0.03);
        }}
        .action-box {{ flex: 1; min-width: 300px; }}
        .action-box strong {{ font-size: 14px; display: block; margin-bottom: 4px; color: var(--primary); }}
        .action-box p {{ font-size: 13px; color: var(--muted); line-height: 1.4; }}
        .action-btns {{ display: flex; gap: 10px; flex-wrap: wrap; }}
        .btn-action {{
            border: none;
            padding: 10px 18px;
            border-radius: 10px;
            font-size: 13px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.2s;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }}
        .btn-b2b {{ background: #2563EB; color: white; }}
        .btn-b2b:hover {{ background: #1D4ED8; }}
        .btn-client {{ background: #059669; color: white; }}
        .btn-client:hover {{ background: #047857; }}

        .tabs {{
            display: flex;
            gap: 10px;
            margin-bottom: 18px;
            flex-wrap: wrap;
        }}
        .tab-btn {{
            background: white;
            border: 1px solid var(--border);
            padding: 10px 18px;
            border-radius: 12px;
            font-size: 13.5px;
            font-weight: 600;
            color: var(--muted);
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .tab-btn:hover {{ border-color: var(--primary); color: var(--primary); }}
        .tab-btn.active {{
            background: var(--primary);
            color: white;
            border-color: var(--primary);
            box-shadow: 0 4px 12px rgba(26, 35, 126, 0.2);
        }}
        .tab-count {{
            background: rgba(0,0,0,0.06);
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 12px;
        }}
        .tab-btn.active .tab-count {{
            background: rgba(255,255,255,0.22);
            color: white;
        }}

        .search-container {{ margin-bottom: 20px; }}
        input.search-bar {{
            width: 100%;
            padding: 14px 20px;
            border-radius: 12px;
            border: 1px solid var(--border);
            font-size: 14.5px;
            outline: none;
            background: white;
            box-shadow: 0 2px 6px rgba(0,0,0,0.02);
        }}
        input.search-bar:focus {{ border-color: var(--primary); box-shadow: 0 0 0 3px rgba(26, 35, 126, 0.1); }}

        .lead-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(390px, 1fr));
            gap: 18px;
        }}
        .lead-card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 22px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            transition: transform 0.2s, box-shadow 0.2s, border-color 0.2s;
            box-shadow: 0 2px 6px rgba(0,0,0,0.03);
            position: relative;
        }}
        .lead-card.card-urgent {{
            border-left: 5px solid var(--urgent);
            background: #FFFBFB;
        }}
        .lead-card:hover {{
            transform: translateY(-3px);
            box-shadow: 0 14px 24px -8px rgba(0, 0, 0, 0.09);
            border-color: #CBD5E1;
        }}
        .badges {{ display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }}
        .badge {{
            font-size: 11px;
            font-weight: 700;
            padding: 4px 10px;
            border-radius: 8px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .badge-urgent {{ background: #FEE2E2; color: #991B1B; border: 1px solid #FECACA; font-weight: 800; }}
        .badge-contractor {{ background: #E0E7FF; color: #3730A3; border: 1px solid #C7D2FE; }}
        .badge-renovation {{ background: #FEF3C7; color: #92400E; border: 1px solid #FDE68A; }}
        .badge-electrical {{ background: #DCFCE7; color: #166534; border: 1px solid #BBF7D0; }}
        .badge-source {{ background: #F1F5F9; color: #475569; }}
        .badge-sofia {{ background: #FFE4E6; color: #BE123C; font-weight: 800; }}
        .badge-phone {{ background: #D1FAE5; color: #065F46; font-weight: 800; }}

        .lead-title {{
            font-size: 15px;
            font-weight: 600;
            color: var(--text);
            line-height: 1.45;
            margin-bottom: 16px;
        }}
        
        .phone-row {{
            background: #F8FAFC;
            border: 1px dashed #CBD5E1;
            padding: 8px 12px;
            border-radius: 8px;
            margin-bottom: 14px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .phone-text {{ font-weight: 700; color: #0F172A; font-size: 14px; }}
        .phone-actions {{ display: flex; gap: 6px; }}
        .btn-call {{
            background: #10B981;
            color: white;
            text-decoration: none;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 700;
        }}
        .btn-wa {{
            background: #25D366;
            color: white;
            text-decoration: none;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 700;
        }}

        .lead-footer {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-top: 1px solid var(--border);
            padding-top: 14px;
            margin-top: auto;
            gap: 10px;
        }}
        .lead-date {{ font-size: 12px; color: var(--muted); }}
        
        .card-actions {{ display: flex; gap: 8px; }}
        .btn-view {{
            background: var(--primary);
            color: white;
            text-decoration: none;
            padding: 8px 16px;
            border-radius: 9px;
            font-size: 12px;
            font-weight: 700;
            transition: background 0.2s;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }}
        .btn-view:hover {{ background: #283593; }}
        .btn-pitch {{
            background: #F8FAFC;
            border: 1px solid var(--border);
            color: #334155;
            padding: 8px 12px;
            border-radius: 9px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }}
        .btn-pitch:hover {{ background: #E2E8F0; color: #0F172A; }}

        #copiedToast {{
            position: fixed;
            bottom: 24px;
            right: 24px;
            background: #10B981;
            color: white;
            padding: 14px 24px;
            border-radius: 12px;
            font-size: 14.5px;
            font-weight: 700;
            box-shadow: 0 10px 25px rgba(0,0,0,0.2);
            display: none;
            z-index: 1000;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>ZVB | Радар за строителни обекти и клиенти (10/10)</h1>
                <p>Електрически инсталации, камери, умни системи и подизпълнение в София и България</p>
            </div>
            <div class="header-stats">
                <div class="stat-box">
                    <span>{count_all}</span>
                    <small>Всички обяви</small>
                </div>
                <div class="stat-box">
                    <span style="color: #4ADE80;">{count_urgent}</span>
                    <small>Директни търсения</small>
                </div>
                <div class="stat-box">
                    <span style="color: #67E8F9;">{count_sofia}</span>
                    <small>В София</small>
                </div>
            </div>
        </header>

        <div class="action-banner">
            <div class="action-box">
                <strong>🤝 Готови текстове за бърз контакт:</strong>
                <p>Копирайте директно готово професионално съобщение за строителна фирма или за клиент с 1 клик.</p>
            </div>
            <div class="action-btns">
                <button class="btn-action btn-b2b" onclick="copyText('b2b')">📋 Копирай оферта за Строител</button>
                <button class="btn-action btn-client" onclick="copyText('client')">📋 Копирай оферта за Клиент</button>
            </div>
        </div>

        <div id="b2bText" style="display:none;">{b2b_text}</div>
        <div id="clientText" style="display:none;">{client_offer_text}</div>

        <div class="tabs">
            <button class="tab-btn active" onclick="setFilter('all', this)">Всички <span class="tab-count">{count_all}</span></button>
            <button class="tab-btn" onclick="setFilter('urgent_client', this)">🎯 Директни клиенти / Спешно <span class="tab-count">{count_urgent}</span></button>
            <button class="tab-btn" onclick="setFilter('contractor', this)">🏗️ Строителни фирми <span class="tab-count">{count_contractors}</span></button>
            <button class="tab-btn" onclick="setFilter('renovation', this)">🔨 Ремонти <span class="tab-count">{count_renovation}</span></button>
            <button class="tab-btn" onclick="setFilter('sofia', this)">📍 Само София <span class="tab-count">{count_sofia}</span></button>
            <button class="tab-btn" onclick="setFilter('with_phone', this)">📞 С телефонен номер <span class="tab-count">{count_with_phone}</span></button>
        </div>

        <div class="search-container">
            <input type="text" id="searchInput" class="search-bar" placeholder="Търсете по фирма, дейност, град (напр. София, Младост, Лозенец, Витоша, Люлин, Център)..." oninput="applyFilters()">
        </div>

        <div class="lead-grid" id="leadsGrid">
"""
    for l in leads:
        cat = l.get("category", "direct_electrical")
        is_urgent = (cat == "urgent_client")
        card_class = "card-urgent" if is_urgent else ""
        
        badge_cat = "badge-urgent" if is_urgent else ("badge-contractor" if cat == "contractor" else ("badge-renovation" if cat == "renovation" else "badge-electrical"))
        is_sofia = "софия" in l.get("location", "").lower() or "софия" in l.get("title", "").lower()
        sofia_badge = '<span class="badge badge-sofia">София</span>' if is_sofia else ''
        phone_badge = '<span class="badge badge-phone">📞 Телефон</span>' if l.get('phone') else ''

        phone_row_html = ""
        if l.get('phone'):
            raw_p = l['phone']
            intl_p = "359" + raw_p[1:] if raw_p.startswith("0") else raw_p
            phone_row_html = f"""
                <div class="phone-row">
                    <span class="phone-text">📞 {raw_p}</span>
                    <div class="phone-actions">
                        <a href="tel:+{intl_p}" class="btn-call">Обади се</a>
                        <a href="https://wa.me/{intl_p}" target="_blank" class="btn-wa">WhatsApp</a>
                    </div>
                </div>
            """
        
        html_template += f"""
            <div class="lead-card {card_class}" 
                 data-category="{cat}" 
                 data-sofia="{'true' if is_sofia else 'false'}"
                 data-hasphone="{'true' if l.get('phone') else 'false'}"
                 data-text="{l.get('title', '').lower()} {l.get('keyword', '').lower()} {l.get('location', '').lower()} {l.get('phone', '')}">
                <div>
                    <div class="badges">
                        <span class="badge {badge_cat}">{l.get('category_label', '')}</span>
                        <span class="badge badge-source">{l.get('source', '')}</span>
                        {sofia_badge}
                        {phone_badge}
                    </div>
                    <div class="lead-title">{l.get('title', '')}</div>
                    {phone_row_html}
                </div>
                <div class="lead-footer">
                    <span class="lead-date">{l.get('found_at', '')}</span>
                    <div class="card-actions">
                        <button class="btn-pitch" onclick="copyText('{'b2b' if cat == 'contractor' else 'client'}')" title="Копирай оферта">📋 Оферта</button>
                        <a href="{l.get('url', '#')}" target="_blank" class="btn-view">Отвори &rarr;</a>
                    </div>
                </div>
            </div>
"""

    html_template += """
        </div>
    </div>
    <div id="copiedToast">✅ Текстът на офертата е копиран успешно!</div>

    <script>
        let currentFilter = 'all';

        function setFilter(type, btn) {
            currentFilter = type;
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            applyFilters();
        }

        function applyFilters() {
            const query = document.getElementById('searchInput').value.toLowerCase();
            const cards = document.querySelectorAll('.lead-card');
            
            cards.forEach(card => {
                const text = card.getAttribute('data-text');
                const cat = card.getAttribute('data-category');
                const isSofia = card.getAttribute('data-sofia') === 'true';
                const hasPhone = card.getAttribute('data-hasphone') === 'true';

                let matchesFilter = true;
                if (currentFilter === 'urgent_client') matchesFilter = (cat === 'urgent_client');
                else if (currentFilter === 'contractor') matchesFilter = (cat === 'contractor');
                else if (currentFilter === 'renovation') matchesFilter = (cat === 'renovation');
                else if (currentFilter === 'sofia') matchesFilter = isSofia;
                else if (currentFilter === 'with_phone') matchesFilter = hasPhone;

                const matchesSearch = text.includes(query);
                card.style.display = (matchesFilter && matchesSearch) ? 'flex' : 'none';
            });
        }

        function copyText(type) {
            const elId = (type === 'b2b') ? 'b2bText' : 'clientText';
            const text = document.getElementById(elId).innerText;
            navigator.clipboard.writeText(text).then(() => {
                const toast = document.getElementById('copiedToast');
                toast.innerText = (type === 'b2b') ? '✅ Копирано: Оферта за строителна фирма!' : '✅ Копирано: Оферта за клиент!';
                toast.style.display = 'block';
                setTimeout(() => { toast.style.display = 'none'; }, 3000);
            });
        }
    </script>
</body>
</html>
"""
    with open(DASHBOARD_HTML_PATH, "w", encoding="utf-8") as f:
        f.write(html_template)

def run_scan():
    config = load_config()
    telegram_cfg = config.get("telegram", {})
    telegram_enabled = telegram_cfg.get("enabled", False)
    bot_token = telegram_cfg.get("bot_token", "")
    chat_id = telegram_cfg.get("chat_id", "")
    keywords = config.get("keywords", DEFAULT_KEYWORDS)

    print("=" * 65)
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] ZVB Ultimate Radar 10/10 Sweep...")
    print(f"Telegram Alerts: {'ENABLED ✅' if telegram_enabled and bot_token else 'DISABLED ❌ (configure in config.json)'}")
    print("=" * 65)
    
    existing_leads = load_existing_leads()
    new_leads = []
    
    for kw in keywords:
        print(f"\n🔍 Scanning: '{kw}'...")
        import daily_digest
        
        # 1. Scrape Bazar.bg
        bazar_items = scrape_bazar(kw)
        valid_bazar = [it for it in bazar_items if daily_digest.is_strictly_electrical_sofia(it)]
        print(f"   ↳ Bazar.bg: {len(bazar_items)} raw -> {len(valid_bazar)} strictly verified Sofia client leads")
        for item in valid_bazar:
            if item['id'] not in existing_leads:
                existing_leads[item['id']] = item
                new_leads.append(item)
                
        time.sleep(0.5)
        
        # 2. Scrape Alo.bg
        alo_items = scrape_alo(kw)
        valid_alo = [it for it in alo_items if daily_digest.is_strictly_electrical_sofia(it)]
        print(f"   ↳ Alo.bg: {len(alo_items)} raw -> {len(valid_alo)} strictly verified Sofia client leads")
        for item in valid_alo:
            if item['id'] not in existing_leads:
                existing_leads[item['id']] = item
                new_leads.append(item)
                
        time.sleep(0.5)
        
    # 3. Scrape MaistorPlus if configured
    mp_cfg = config.get("maistorplus", {})
    if mp_cfg.get("enabled") and mp_cfg.get("username") and mp_cfg.get("password"):
        print("\n🔍 Scanning MaistorPlus (Заявки от клиенти в София)...")
        mp_items = scrape_maistorplus(mp_cfg["username"], mp_cfg["password"])
        print(f"   ↳ MaistorPlus: {len(mp_items)} active electrical projects found")
        for item in mp_items:
            if item['id'] not in existing_leads:
                existing_leads[item['id']] = item
                new_leads.append(item)

    # Enrich phone numbers for new urgent leads (excluding MaistorPlus)
    enrich_phones_for_leads(new_leads, max_to_fetch=20)

    save_leads(existing_leads)

    # Dispatch telegram alerts for newly discovered leads (strictly electrical Sofia projects only)
    if telegram_enabled and bot_token and chat_id and new_leads:
        import daily_digest
        strict_new_leads = [nl for nl in new_leads if daily_digest.is_strictly_electrical_sofia(nl)]
        print(f"\n📲 Sending Telegram alerts for {len(strict_new_leads)} verified electrical Sofia opportunities...")
        sent_count = 0
        for nl in strict_new_leads[:15]:
            if send_telegram_alert(nl, bot_token, chat_id):
                sent_count += 1
            time.sleep(0.4)
        print(f"   ↳ Sent {sent_count} alerts to Telegram.")

    print("\n" + "=" * 65)
    print(f"Scan complete! New leads added: {len(new_leads)} | Total database: {len(existing_leads)}")
    print(f"📁 Interactive Dashboard: leads_dashboard.html")
    print(f"📊 Excel CSV Database: leads.csv")
    print("=" * 65)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ZVB Ultimate Lead Radar")
    parser.add_argument("--interval", type=int, default=0, help="Run continuously every N minutes (0 = run once)")
    args = parser.parse_args()

    if args.interval > 0:
        print(f"Running in continuous radar mode. Scans every {args.interval} minutes.")
        while True:
            run_scan()
            print(f"\nWaiting {args.interval} minutes until next radar sweep...")
            time.sleep(args.interval * 60)
    else:
        run_scan()
