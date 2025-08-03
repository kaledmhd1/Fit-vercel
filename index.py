from flask import Flask, request, jsonify
import httpx
import threading
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import base64
import json

app = Flask(__name__)
lock = threading.Lock()

LIKE_API_URL = "https://new-like2.onrender.com/like"
INFO_API_URL = "https://info-ch9ayfa.vercel.app/{}"

with open("token.json", "r") as f:
    token_data = json.load(f)

tokens_cache = {}

def get_token(uid, password):
    try:
        url = f"https://ffwlxd-access-jwt.vercel.app/api/get_jwt?guest_uid={uid}&guest_password={password}"
        r = httpx.get(url, timeout=10)
        return r.json().get("BearerAuth", "")
    except:
        return ""

def encrypt_uid(uid):
    uid = int(uid)
    dec = ['80', '81', '82', '83', '84', '85', '86', '87', '88', '89', '8a', '8b', '8c', '8d', '8e', '8f']
    uid_hex = hex(uid)[2:].zfill(8)
    reversed_bytes = bytearray.fromhex(uid_hex)[::-1]
    padded = pad(bytes(reversed_bytes), AES.block_size)
    key = bytes.fromhex("2A57086C86EF54970C1E6EB37BFC72B1")
    cipher = AES.new(key, AES.MODE_ECB)
    encrypted = cipher.encrypt(padded)
    return ''.join([dec[b >> 4] + dec[b & 0xF] for b in encrypted])

@app.route("/add_likes", methods=["GET"])
def add_likes():
    target_uid = request.args.get("uid")
    if not target_uid:
        return jsonify({"error": "Missing uid"}), 400

    encrypted_id = encrypt_uid(target_uid)
    info = httpx.get(INFO_API_URL.format(target_uid)).json()
    nickname = info.get("nickname", "unknown")

    results = []

    for guest_uid, password in token_data.items():
        with lock:
            if guest_uid not in tokens_cache:
                tokens_cache[guest_uid] = get_token(guest_uid, password)

            token = tokens_cache[guest_uid]

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        payload = {"target": encrypted_id}
        try:
            r = httpx.post(LIKE_API_URL, headers=headers, json=payload, timeout=10)
            res_json = r.json()
            status = res_json.get("stats", {})
            results.append({
                "guest_uid": guest_uid,
                "success": status.get("success", 0),
                "daily_limited_reached": status.get("daily_limited_reached", 0),
            })
        except Exception as e:
            results.append({"guest_uid": guest_uid, "error": str(e)})

    return jsonify({"target": nickname, "results": results})

# لجعل Vercel يتعرف على التطبيق
def handler(request, context):
    return app(request, context)
