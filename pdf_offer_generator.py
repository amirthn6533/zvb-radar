import os, sys, datetime, json, requests
sys.stdout.reconfigure(encoding='utf-8')

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Register Fonts
FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
if not os.path.exists(FONT_DIR):
    # Try parent directory
    FONT_DIR = os.path.join(r"c:\Users\AMIR\OneDrive\دسکتاپ\New folder (3)", "fonts")

arial_path = os.path.join(FONT_DIR, "arial.ttf")
arial_bold_path = os.path.join(FONT_DIR, "arialbd.ttf")

if os.path.exists(arial_path):
    pdfmetrics.registerFont(TTFont("ArialCustom", arial_path))
    pdfmetrics.registerFont(TTFont("ArialBoldCustom", arial_bold_path if os.path.exists(arial_bold_path) else arial_path))
    FONT_REGULAR = "ArialCustom"
    FONT_BOLD = "ArialBoldCustom"
else:
    FONT_REGULAR = "Helvetica"
    FONT_BOLD = "Helvetica-Bold"

def generate_pdf_offer(output_path, client_name="Клиент", location="гр. София", project_title="Електромонтажни дейности", items=None, notes=""):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    styles = getSampleStyleSheet()
    
    # Custom Styles
    style_company = ParagraphStyle('Company', fontName=FONT_BOLD, fontSize=18, leading=22, textColor=colors.HexColor("#0f2b48"))
    style_subtitle = ParagraphStyle('Subtitle', fontName=FONT_REGULAR, fontSize=9, leading=12, textColor=colors.HexColor("#555555"))
    style_doc_title = ParagraphStyle('DocTitle', fontName=FONT_BOLD, fontSize=15, leading=18, textColor=colors.HexColor("#d97706"), alignment=2)
    style_doc_num = ParagraphStyle('DocNum', fontName=FONT_REGULAR, fontSize=9, leading=12, textColor=colors.HexColor("#666666"), alignment=2)
    
    style_heading = ParagraphStyle('Heading', fontName=FONT_BOLD, fontSize=11, leading=14, textColor=colors.HexColor("#0f2b48"))
    style_normal = ParagraphStyle('NormalText', fontName=FONT_REGULAR, fontSize=9, leading=12, textColor=colors.HexColor("#222222"))
    style_table_header = ParagraphStyle('TableHeader', fontName=FONT_BOLD, fontSize=9, leading=11, textColor=colors.white)
    style_table_cell = ParagraphStyle('TableCell', fontName=FONT_REGULAR, fontSize=8.5, leading=11, textColor=colors.HexColor("#333333"))
    style_table_cell_bold = ParagraphStyle('TableCellBold', fontName=FONT_BOLD, fontSize=9, leading=11, textColor=colors.HexColor("#0f2b48"))
    
    story = []
    
    # 1. Header (ZVB Logo/Name on Left, Offer info on Right)
    today_str = datetime.datetime.now().strftime("%d.%m.%Y")
    quote_id = f"ZVB-{datetime.datetime.now().strftime('%y%m%d')}-{abs(hash(project_title)) % 1000:03d}"
    
    header_data = [
        [
            Paragraph("<b>ZVB ЕЛЕКТРОИНЖЕНЕРИНГ</b>", style_company),
            Paragraph("<b>ОФИЦИАЛНА ОФЕРТА</b>", style_doc_title)
        ],
        [
            Paragraph("Електроинсталации • Ел. Табла • Видеонаблюдение • Smart Home<br/>гр. София | Тел: <b>+359 87 7944353</b> | <b>https://zvb.bg</b>", style_subtitle),
            Paragraph(f"Номер: <b>{quote_id}</b><br/>Дата: <b>{today_str} г.</b><br/>Валидност: <b>30 дни</b>", style_doc_num)
        ]
    ]
    t_header = Table(header_data, colWidths=[330, 190])
    t_header.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))
    story.append(t_header)
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#0f2b48"), spaceAfter=12))
    
    # 2. Client & Project Info
    info_data = [
        [
            Paragraph("<b>ДАННИ ЗА ВЪЗЛОЖИТЕЛЯ:</b>", style_heading),
            Paragraph("<b>ДАННИ ЗА ОБЕКТА:</b>", style_heading)
        ],
        [
            Paragraph(f"Възложител: <b>{client_name}</b><br/>Град: <b>София</b><br/>Статут: <b>Частно / Юридическо лице</b>", style_normal),
            Paragraph(f"Обект: <b>{location}</b><br/>Дейност: <b>{project_title}</b><br/>Изпълнител: <b>ZVB София (+359 87 7944353)</b>", style_normal)
        ]
    ]
    t_info = Table(info_data, colWidths=[260, 260])
    t_info.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8fafc")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#e2e8f0")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_info)
    story.append(Spacer(1, 14))
    
    # 3. Itemized Table
    if not items:
        items = [
            ("1", "Демонтаж на съществуващи елементи и обезопасяване", "к-т", 1, 80.0),
            ("2", "Штробоване (канали) в тухла/бетон и полагане на гофрирани тръби", "м.", 45, 12.0),
            ("3", "Полагане на силови мостови кабели ПВВ-МБ1 (3x2.5 mm² за контакти)", "м.", 80, 4.5),
            ("4", "Полагане на кабели за осветление ПВВ-МБ1 (3x1.5 mm²)", "м.", 50, 3.5),
            ("5", "Монтаж на конзолни кутии и подвързване на контакти/ключове", "бр.", 28, 14.0),
            ("6", "Доставка и асемблиране на ново ел. табло (Schneider Resi9)", "бр.", 1, 190.0),
            ("7", "Монтаж на Дефектнотокова защита (ДТЗ 40A / 30mA, Тип A)", "бр.", 1, 110.0),
            ("8", "Замерване, прозвъняване, пуск в експлоатация и маркиране", "к-т", 1, 90.0)
        ]
        
    table_data = [
        [
            Paragraph("№", style_table_header),
            Paragraph("ОПИСАНИЕ НА ДЕЙНОСТТА / МАТЕРИАЛИТЕ", style_table_header),
            Paragraph("МЯРКА", style_table_header),
            Paragraph("КОЛ.", style_table_header),
            Paragraph("ЕД. ЦЕНА", style_table_header),
            Paragraph("ОБЩО (ЛВ)", style_table_header)
        ]
    ]
    
    total_bgn = 0.0
    for idx, name, unit, qty, price in items:
        sub = qty * price
        total_bgn += sub
        table_data.append([
            Paragraph(str(idx), style_table_cell),
            Paragraph(name, style_table_cell),
            Paragraph(unit, style_table_cell),
            Paragraph(str(qty), style_table_cell),
            Paragraph(f"{price:.2f} лв", style_table_cell),
            Paragraph(f"{sub:.2f} лв", style_table_cell_bold)
        ])
        
    table_data.append([
        Paragraph("", style_table_cell),
        Paragraph("<b>ОБЩА КРАЙНА СТОЙНОСТ (ТРУД И МАТЕРИАЛИ):</b>", style_table_cell_bold),
        Paragraph("", style_table_cell),
        Paragraph("", style_table_cell),
        Paragraph("", style_table_cell),
        Paragraph(f"<b>{total_bgn:.2f} лв</b>", ParagraphStyle('Tot', fontName=FONT_BOLD, fontSize=11, textColor=colors.HexColor("#d97706")))
    ])
    
    t_items = Table(table_data, colWidths=[24, 260, 45, 40, 75, 76])
    t_items.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0f2b48")),
        ('ALIGN', (0,0), (0,-1), 'CENTER'),
        ('ALIGN', (2,0), (4,-1), 'CENTER'),
        ('ALIGN', (5,0), (5,-1), 'RIGHT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-2), 0.5, colors.HexColor("#cbd5e1")),
        ('LINEBELOW', (0,-1), (-1,-1), 1.5, colors.HexColor("#0f2b48")),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#f1f5f9")),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_items)
    story.append(Spacer(1, 14))
    
    # 4. Guarantee & Terms Box
    terms_text = (
        "<b>ПРЕДИМСТВА И ГАРАНЦИОННИ УСЛОВИЯ НА ZVB:</b><br/>"
        "• <b>5 Години пълна писмена гаранция</b> с приемо-предавателен двустранен протокол.<br/>"
        "• Изпълнение стриктно по стандарти <b>БДС EN 60364</b> и пожарна безопасност.<br/>"
        "• Вложени материали от висок клас: кабели 100% мед, автоматика Schneider Electric / Noark.<br/>"
        "• Безплатно етикетиране и схема на токовите кръгове в таблото.<br/>"
        "• Чистота и извозване на работните строителни отпадъци след монтажа."
    )
    t_terms = Table([[Paragraph(terms_text, style_normal)]], colWidths=[520])
    t_terms.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#eff6ff")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#bfdbfe")),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_terms)
    story.append(Spacer(1, 16))
    
    # 5. Signatures
    sig_data = [
        [
            Paragraph("<b>Възложител:</b><br/><br/>...................................................<br/>/ Подпис /", style_normal),
            Paragraph("<b>Изпълнител (ZVB София):</b><br/><br/><b>Инж. Екип ZVB | Печат: [ ZVB София ]</b><br/>/ Подпис и печат /", style_normal)
        ]
    ]
    t_sig = Table(sig_data, colWidths=[260, 260])
    story.append(t_sig)
    
    doc.build(story)
    return output_path, total_bgn

def parse_project_with_ai(description, gemini_key):
    """
    Uses Gemini 2.5 Flash to parse user description into itemized Bulgarian quote items.
    """
    if not gemini_key:
        return None

    prompt = (
        f"کاربر درخواست صدور پیش‌فاکتور برای این پروژه در صوفیه، بلغارستان را دارد:\n"
        f"«««\n{description}\n»»»\n\n"
        "لطفاً به عنوان مهندس ارشد ZVB صوفیه، این شرح کار را به یک لیست کامل از آیتم‌های استاندارد، مقادیر و قیمت‌های منصفانه بازار صوفیه (به لِوا BGN) تبدیل کن.\n"
        "خروجی را فقط و فقط به صورت یک JSON معتبر آرایه‌ای بازگردان (بدون هیچ توضیح اضافه یا مارک‌داون اضافی):\n"
        "[\n"
        "  {\n"
        "    \"name\": \"عنوان فعالیت یا متریال به زبان بلغاری\",\n"
        "    \"unit\": \"мярка (бр. или м. или к-т)\",\n"
        "    \"qty\": 1,\n"
        "    \"price\": 100.0\n"
        "  }\n"
        "]"
    )

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 1500,
                "thinkingConfig": {"thinkingBudget": 0}
            }
        }
        r = requests.post(url, json=payload, timeout=12)
        if r.status_code == 200:
            res_text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            if res_text.startswith("```json"):
                res_text = res_text[7:]
            if res_text.startswith("```"):
                res_text = res_text[3:]
            if res_text.endswith("```"):
                res_text = res_text[:-3]
            data = json.loads(res_text.strip())
            if isinstance(data, list) and len(data) > 0:
                items = []
                for i, it in enumerate(data, 1):
                    items.append((
                        str(i),
                        it.get("name", ""),
                        it.get("unit", "бр."),
                        float(it.get("qty", 1)),
                        float(it.get("price", 10.0))
                    ))
                return items
    except Exception as e:
        print(f"AI quote parsing error: {e}")

    return None

def create_and_send_pdf_offer(token, chat_id, description, client_name="Клиент", location="гр. София"):
    """
    End-to-end function: parses input with AI, builds branded PDF, and sends via Telegram sendDocument.
    """
    cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    gemini_key = ""
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                gemini_key = cfg.get("gemini_api_key", "")
        except Exception:
            pass

    items = parse_project_with_ai(description, gemini_key)
    
    pdf_filename = f"ZVB_Oferta_Sofia_{datetime.datetime.now().strftime('%H%M%S')}.pdf"
    pdf_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), pdf_filename)
    
    out_file, total_sum = generate_pdf_offer(
        output_path=pdf_path,
        client_name=client_name,
        location=location,
        project_title=description[:50],
        items=items
    )
    
    caption = (
        f"📄 <b>ОФИЦИАЛНА ОФЕРТА ZVB (гр. София)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>Обект:</b> {description[:60]}\n"
        f"💰 <b>Крайна стойност:</b> <b>{total_sum:,.2f} лв.</b> (BGN)\n"
        f"🛡️ <b>Гаранция:</b> 5 години пълна с приемо-предавателен протокол\n\n"
        f"مهندس جان، فایل رسمی PDF پیش‌فاکتور با سربرگ ZVB آماده شد! می‌تونی مستقیم برای کارفرما در واتساپ یا ایمیل بفرستیش 🚀"
    )
    
    try:
        with open(pdf_path, "rb") as f:
            r = requests.post(
                f"https://api.telegram.org/bot{token}/sendDocument",
                data={"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"},
                files={"document": ("ZVB_Oficialna_Oferta_Sofia.pdf", f, "application/pdf")},
                timeout=15
            )
            ok = r.status_code == 200
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        return ok
    except Exception as e:
        print(f"Error sending PDF to Telegram: {e}")
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        return False

def send_offer_email(pdf_path, recipient_email, project_title="Електромонтажни дейности", total_sum=0.0):
    """
    Sends official PDF proposal to client's email via SMTP with full Bulgarian cover letter.
    """
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.application import MIMEApplication

    cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    cfg = {}
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            pass
            
    smtp_cfg = cfg.get("smtp", {})
    host = smtp_cfg.get("host", "smtp.gmail.com")
    port = smtp_cfg.get("port", 587)
    user = smtp_cfg.get("user")
    password = smtp_cfg.get("password")
    from_email = smtp_cfg.get("from_email", user)

    if not (user and password):
        return False, "SMTP credentials not configured in config.json (add 'smtp': {'user': '...', 'password': '...'})."

    try:
        msg = MIMEMultipart()
        msg['From'] = f"ZVB Electrical Systems <{from_email}>"
        msg['To'] = recipient_email
        msg['Subject'] = f"Официална оферта ZVB: {project_title} (гр. София)"

        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #1e293b; line-height: 1.6;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 8px;">
                <h2 style="color: #0f2b48; margin-top: 0;">ZVB — Електроинженеринг и Умни Системи</h2>
                <p>Уважаеми клиенти,</p>
                <p>Благодарим Ви за проявения интерес към услугите на <b>ZVB</b>. Прикачено ще намерите официалната подробна оферта и количествено-стойностна сметка за Вашия обект:</p>
                <div style="background-color: #f8fafc; border-left: 4px solid #f59e0b; padding: 12px; margin: 16px 0;">
                    <b>Обект:</b> {project_title}<br>
                    <b>Обща стойност:</b> {total_sum:,.2f} лв. с ДДС<br>
                    <b>Гаранция:</b> 5 години пълна с приемо-предавателен протокол
                </div>
                <p>Оставаме на Ваше разположение за безплатен оглед на място и уточняване на удобен за Вас график.</p>
                <br>
                <p style="margin-bottom: 2px;">С уважение,</p>
                <b>Инж. екип на ZVB София</b><br>
                📞 Телефон: +359 87 7944353<br>
                🌐 Уебсайт: <a href="https://zvb.bg">https://zvb.bg</a>
            </div>
        </body>
        </html>
        """
        msg.attach(MIMEText(body_html, 'html', 'utf-8'))

        with open(pdf_path, "rb") as f:
            part = MIMEApplication(f.read(), Name=os.path.basename(pdf_path))
            part['Content-Disposition'] = f'attachment; filename="{os.path.basename(pdf_path)}"'
            msg.attach(part)

        server = smtplib.SMTP(host, port, timeout=15)
        server.starttls()
        server.login(user, password)
        server.send_message(msg)
        server.quit()
        return True, "Имейлът е изпратен успешно!"
    except Exception as e:
        return False, str(e)

if __name__ == "__main__":
    out = "test_zvb_offer.pdf"
    p, tot = generate_pdf_offer(out, client_name="Иван Петров", location="гр. София, кв. Манастирски ливади", project_title="Ремонт на ел. инсталация и ново табло")
    print(f"Successfully generated {p}! Total: {tot:.2f} BGN. Size: {os.path.getsize(p)} bytes")
