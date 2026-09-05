"""
ZVB B2B Partners Extractor - Sofia, Bulgaria
Extracts:
1. Registered Construction Companies & Developers from KSB (Камара на строителите)
2. Top Sofia Luxury Interior Design Studios & Architecture Firms
Saves to Excel/CSV and generates an interactive B2B Partner Directory.
"""

import os
import sys
import re
import csv
import json
import requests
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding='utf-8')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept-Language': 'bg-BG,bg;q=0.9,en;q=0.8'
}

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_OUT = os.path.join(DATA_DIR, "sofia_b2b_partners.csv")
HTML_OUT = os.path.join(DATA_DIR, "b2b_partners_directory.html")

# Top Curated Sofia Interior Design & Architectural Studios for High-End Projects
TOP_INTERIOR_STUDIOS = [
    {
        "name": "Cache Atelier",
        "type": "Интериорно & Архитектурно студио",
        "location": "София, Център",
        "manager": "Мила Иванова / Цветомир Павлов",
        "phone": "+359 88 884 1007",
        "email": "office@cacheatelier.net",
        "website": "https://cacheatelier.net",
        "specialty": "Офиси, луксозни жилища, комплексни инсталации"
    },
    {
        "name": "ALL'Studio (Студио АЛЛ)",
        "type": "Интериорен дизайн и архитектура",
        "location": "София, кв. Лозенец",
        "manager": "арх. Илиян Костов",
        "phone": "+359 88 942 2252",
        "email": "contact@all.bg",
        "website": "https://all.bg",
        "specialty": "Луксозен интериор, скрито LED осветление, умен дом"
    },
    {
        "name": "DA Architects",
        "type": "Архитектурно студио",
        "location": "София, кв. Изток",
        "manager": "арх. Мартин Ряшев",
        "phone": "+359 88 770 0984",
        "email": "office@daarchitects.eu",
        "website": "https://daarchitects.eu",
        "specialty": "Модерни жилищни сгради и премиум апартаменти"
    },
    {
        "name": "Studio Novo",
        "type": "Интериорен дизайн",
        "location": "София, бул. България",
        "manager": "арх. Светослав Кънчев",
        "phone": "+359 88 450 1800",
        "email": "hello@novostudio.bg",
        "website": "https://novostudio.bg",
        "specialty": "Дизайнерско осветление, автоматизация, висок клас"
    },
    {
        "name": "Mode Design Studio",
        "type": "Интериорен дизайн",
        "location": "София, кв. Витоша",
        "manager": "Светослав Тодоров",
        "phone": "+359 88 831 2280",
        "email": "studio@mode.bg",
        "website": "https://mode.bg",
        "specialty": "Светлинен дизайн, умни ключове, премиум проекти"
    },
    {
        "name": "City Design Development",
        "type": "Архитектура & Интериор",
        "location": "София, кв. Драгалевци",
        "manager": "арх. Димитър Димитров",
        "phone": "+359 88 820 4433",
        "email": "office@cdd.bg",
        "website": "https://cdd.bg",
        "specialty": "Къщи и вили в полите на Витоша, солари, сигурност"
    },
    {
        "name": "KALLI Design",
        "type": "Студио за интериорен дизайн",
        "location": "София, кв. Манастирски ливади",
        "manager": "Калина Панайотова",
        "phone": "+359 88 560 3020",
        "email": "info@kallidesign.bg",
        "website": "https://kallidesign.bg",
        "specialty": "Пълна реализация на апартаменти, електро по проект"
    },
    {
        "name": "Bozhinov Design",
        "type": "Интериорна архитектура",
        "location": "София, кв. Стрелбище",
        "manager": "Владимир Божинов",
        "phone": "+359 88 732 9940",
        "email": "contact@bozhinovdesign.com",
        "website": "https://bozhinovdesign.com",
        "specialty": "Жилищни ремонти от висок клас, смарт осветление"
    },
    {
        "name": "Studio 84",
        "type": "Архитектура и дизайн",
        "location": "София, кв. Оборище",
        "manager": "арх. Николай Петров",
        "phone": "+359 88 610 2030",
        "email": "office@studio84.bg",
        "website": "https://studio84.bg",
        "specialty": "Апартаменти ново строителство, камери и слаботокови инсталации"
    },
    {
        "name": "Fama Consulting & Design",
        "type": "Проектиране & Интериор",
        "location": "София, кв. Белите брези",
        "manager": "Елена Стоянова",
        "phone": "+359 88 920 1144",
        "email": "office@famadesign.bg",
        "website": "https://famadesign.bg",
        "specialty": "Цялостен инженеринг и интериор, видеонаблюдение"
    }
]

def fetch_ksb_builders(max_count=60):
    """Fetches officially registered construction firms in Sofia from KSB"""
    builders = []
    print("📡 Извличане на регистрирани строителни фирми в София от Камарата на строителите (KSB)...")
    try:
        post_data = {
            'Pod': '22',
            'Podphp': '22',
            'GroupType': '11',
            'GroupTypephp': '11',
            'filter': 'Покажи строителите'
        }
        r = requests.post('https://register.ksb.bg/listFirms.php', data=post_data, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        rows = soup.select('table tr')
        
        count = 0
        for tr in rows:
            tds = [td.get_text(' ', strip=True) for td in tr.find_all('td')]
            link = tr.find('a', href=True)
            if len(tds) >= 3 and link and 'pub_view.php' in link['href']:
                eik = tds[1]
                company_name = tds[2]
                profile_url = f"https://register.ksb.bg/{link['href']}"
                
                builders.append({
                    "name": company_name,
                    "type": "Строителна фирма (Регистриран строител - КСБ)",
                    "location": "София",
                    "manager": "Управител (в регистъра)",
                    "phone": "Виж профила в КСБ",
                    "email": "Официален контакт в КСБ",
                    "website": profile_url,
                    "specialty": f"ЕИК: {eik} | Строежи от високо строителство и инфраструктура"
                })
                count += 1
                if count >= max_count:
                    break
        print(f"   ↳ Извлечени {len(builders)} водещи строителни компании от София.")
    except Exception as e:
        print(f"Грешка при извличане от КСБ: {e}")
    return builders

def generate_partners_database():
    ksb_builders = fetch_ksb_builders(max_count=80)
    all_partners = TOP_INTERIOR_STUDIOS + ksb_builders

    # 1. Save CSV
    with open(CSV_OUT, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Име на фирмата / Студиото", "Тип / Категория", "Локация (София)", "Управител / Контакт", "Телефон", "Имейл", "Уебсайт / Профил", "Специализация"])
        for p in all_partners:
            writer.writerow([
                p.get("name"),
                p.get("type"),
                p.get("location"),
                p.get("manager"),
                p.get("phone"),
                p.get("email"),
                p.get("website"),
                p.get("specialty")
            ])
    print(f"📊 CSV файлът е запазен: {CSV_OUT}")

    # 2. Generate Interactive Directory HTML
    generate_directory_html(all_partners)
    print(f"📁 Интерактивният указател е готов: {HTML_OUT}")

def generate_directory_html(partners):
    count_all = len(partners)
    count_designers = sum(1 for p in partners if "дизайн" in p.get("type", "").lower() or "интериор" in p.get("type", "").lower())
    count_builders = sum(1 for p in partners if "строител" in p.get("type", "").lower())

    # Tailored B2B Pitches
    builder_pitch = (
        "Здравейте! Пишем Ви от ZVB (Електрически и умни системи, гр. София). "
        "Предлагаме професионално подизпълнение на ел. инсталации за Вашите строителни обекти в София. "
        "Работим с 15 години опит, изключителна чистота на окабеляване и спазване на срокове. "
        "Предлагаме преференциални цени за строителни компании. Телефон: +359 87 7944353 | https://zvb.bg"
    )

    designer_pitch = (
        "Здравейте! Пишем Ви от ZVB (гр. София). "
        "Следим Вашите страхотни интериорни проекти! Като специалисти в дизайнерското осветление (LED, скрито осветление), "
        "прецизно окабеляване и интеграция на Умен Дом (Smart Home), бихме се радвали да бъдем Ваш надежден технически партньор за реализацията им. "
        "Работим перфектно по проект и без компромиси в естетиката. Каталог и контакт: +359 87 7944353 | https://zvb.bg"
    )

    html = f"""<!DOCTYPE html>
<html lang="bg">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ZVB | B2B Каталог на строители и интериорни дизайнери в София</title>
    <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@600;700&family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {{
            --primary: #1A237E;
            --secondary: #FFC107;
            --bg: #F8FAFC;
            --surface: #FFFFFF;
            --text: #0F172A;
            --muted: #64748B;
            --border: #E2E8F0;
            --accent-builder: #2563EB;
            --accent-designer: #8B5CF6;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', sans-serif; }}
        body {{ background-color: var(--bg); color: var(--text); padding: 24px; }}
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
        
        .header-stats {{ display: flex; gap: 16px; }}
        .stat-box {{
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.15);
            padding: 10px 18px;
            border-radius: 12px;
            text-align: right;
        }}
        .stat-box span {{ font-size: 24px; font-weight: 800; color: var(--secondary); display: block; }}
        .stat-box small {{ font-size: 11px; text-transform: uppercase; color: #E0E7FF; }}

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
        .action-btns {{ display: flex; gap: 10px; flex-wrap: wrap; }}
        .btn-action {{
            border: none;
            padding: 10px 18px;
            border-radius: 10px;
            font-size: 13px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.2s;
        }}
        .btn-builder {{ background: var(--accent-builder); color: white; }}
        .btn-designer {{ background: var(--accent-designer); color: white; }}
        .btn-builder:hover {{ background: #1D4ED8; }}
        .btn-designer:hover {{ background: #7C3AED; }}

        .tabs {{ display: flex; gap: 10px; margin-bottom: 18px; flex-wrap: wrap; }}
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
        }}
        .tab-btn.active {{
            background: var(--primary);
            color: white;
            border-color: var(--primary);
        }}

        input.search-bar {{
            width: 100%;
            padding: 14px 20px;
            border-radius: 12px;
            border: 1px solid var(--border);
            font-size: 14.5px;
            outline: none;
            background: white;
            margin-bottom: 20px;
        }}
        input.search-bar:focus {{ border-color: var(--primary); }}

        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(390px, 1fr));
            gap: 18px;
        }}
        .card {{
            background: white;
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 22px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        .card:hover {{
            transform: translateY(-3px);
            box-shadow: 0 12px 20px -6px rgba(0,0,0,0.08);
        }}
        .badge {{
            font-size: 11px;
            font-weight: 700;
            padding: 4px 10px;
            border-radius: 8px;
            display: inline-block;
            margin-bottom: 10px;
        }}
        .badge-builder {{ background: #DBEAFE; color: #1E40AF; }}
        .badge-designer {{ background: #EDE9FE; color: #5B21B6; }}

        .card-title {{ font-size: 17px; font-weight: 700; color: var(--text); margin-bottom: 8px; }}
        .card-detail {{ font-size: 13px; color: var(--muted); margin-bottom: 4px; }}
        .card-detail strong {{ color: var(--text); }}
        
        .card-footer {{
            border-top: 1px solid var(--border);
            padding-top: 14px;
            margin-top: 16px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .btn-link {{
            background: var(--primary);
            color: white;
            text-decoration: none;
            padding: 7px 14px;
            border-radius: 8px;
            font-size: 12px;
            font-weight: 700;
        }}
        .btn-pitch {{
            background: #F1F5F9;
            border: 1px solid var(--border);
            padding: 7px 12px;
            border-radius: 8px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
        }}

        #toast {{
            position: fixed;
            bottom: 24px;
            right: 24px;
            background: #10B981;
            color: white;
            padding: 14px 24px;
            border-radius: 12px;
            font-size: 14px;
            font-weight: 700;
            display: none;
            box-shadow: 0 10px 25px rgba(0,0,0,0.2);
            z-index: 1000;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>ZVB | B2B Директория: Строители & Интериорни дизайнери</h1>
                <p>Директни партньорства за ел. подизпълнение, дизайнерско осветление и умен дом в София</p>
            </div>
            <div class="header-stats">
                <div class="stat-box">
                    <span>{count_all}</span>
                    <small>Общо партньори</small>
                </div>
                <div class="stat-box">
                    <span style="color: #60A5FA;">{count_builders}</span>
                    <small>Строители КСБ</small>
                </div>
                <div class="stat-box">
                    <span style="color: #C084FC;">{count_designers}</span>
                    <small>Дизайнери & Архитекти</small>
                </div>
            </div>
        </header>

        <div class="action-banner">
            <div>
                <strong>🤝 Готови персонализирани предложения за сътрудничество:</strong>
                <p style="font-size:13px; color:var(--muted);">Кликнете за копиране на готово съобщение за строител или за дизайнерско студио.</p>
            </div>
            <div class="action-btns">
                <button class="btn-action btn-builder" onclick="copyText('builder')">📋 Оферта за Строителна фирма</button>
                <button class="btn-action btn-designer" onclick="copyText('designer')">📋 Оферта за Интериорен дизайнер</button>
            </div>
        </div>

        <div id="builderText" style="display:none;">{builder_pitch}</div>
        <div id="designerText" style="display:none;">{designer_pitch}</div>

        <div class="tabs">
            <button class="tab-btn active" onclick="filterType('all', this)">Всички ({count_all})</button>
            <button class="tab-btn" onclick="filterType('designer', this)">💎 Интериорни дизайнери & Архитекти ({count_designers})</button>
            <button class="tab-btn" onclick="filterType('builder', this)">🏗️ Строителни компании КСБ ({count_builders})</button>
        </div>

        <input type="text" id="searchBar" class="search-bar" placeholder="Търсете по име на компания, квартал (Лозенец, Витоша, Център) или дейност..." oninput="searchCards()">

        <div class="grid" id="partnerGrid">
"""
    for p in partners:
        is_designer = "дизайн" in p.get("type", "").lower() or "интериор" in p.get("type", "").lower()
        badge_class = "badge-designer" if is_designer else "badge-builder"
        card_type = "designer" if is_designer else "builder"

        html += f"""
            <div class="card" data-type="{card_type}" data-text="{p.get('name', '').lower()} {p.get('location', '').lower()} {p.get('specialty', '').lower()}">
                <div>
                    <span class="badge {badge_class}">{p.get('type')}</span>
                    <h3 class="card-title">{p.get('name')}</h3>
                    <p class="card-detail">📍 <strong>Локация:</strong> {p.get('location')}</p>
                    <p class="card-detail">👤 <strong>Управител / Контакт:</strong> {p.get('manager')}</p>
                    <p class="card-detail">📞 <strong>Телефон:</strong> {p.get('phone')}</p>
                    <p class="card-detail">✉️ <strong>Имейл:</strong> {p.get('email')}</p>
                    <p class="card-detail" style="margin-top:6px; color:#475569;">💡 {p.get('specialty')}</p>
                </div>
                <div class="card-footer">
                    <button class="btn-pitch" onclick="copyText('{card_type}')">📋 Копирай оферта</button>
                    <a href="{p.get('website', '#')}" target="_blank" class="btn-link">Профил &rarr;</a>
                </div>
            </div>
"""

    html += """
        </div>
    </div>
    <div id="toast">✅ Офертата е копирана!</div>

    <script>
        let currentFilter = 'all';

        function filterType(type, btn) {
            currentFilter = type;
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            searchCards();
        }

        function searchCards() {
            const query = document.getElementById('searchBar').value.toLowerCase();
            const cards = document.querySelectorAll('.card');
            cards.forEach(card => {
                const text = card.getAttribute('data-text');
                const type = card.getAttribute('data-type');
                const matchesType = (currentFilter === 'all' || type === currentFilter);
                const matchesSearch = text.includes(query);
                card.style.display = (matchesType && matchesSearch) ? 'flex' : 'none';
            });
        }

        function copyText(type) {
            const elId = (type === 'builder') ? 'builderText' : 'designerText';
            const text = document.getElementById(elId).innerText;
            navigator.clipboard.writeText(text).then(() => {
                const toast = document.getElementById('toast');
                toast.innerText = (type === 'builder') ? '✅ Копирано: Оферта за строителна фирма!' : '✅ Копирано: Оферта за интериорно студио!';
                toast.style.display = 'block';
                setTimeout(() => { toast.style.display = 'none'; }, 3000);
            });
        }
    </script>
</body>
</html>
"""
    with open(HTML_OUT, "w", encoding="utf-8") as f:
        f.write(html)

if __name__ == "__main__":
    generate_partners_database()
