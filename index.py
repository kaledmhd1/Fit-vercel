from flask import Flask, request, jsonify
import httpx
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from concurrent.futures import ThreadPoolExecutor
import threading
import json
import time

app = Flask(__name__)
executor = ThreadPoolExecutor(max_workers=40)

# --- تشفير UID ---
def Encrypt_ID(x):
    x = int(x)
    dec = ['80', '81', '82', '83', '84', '85', '86', '87', '88', '89', '8a', '8b', '8c', '8d', '8e', '8f']
    x = hex(x)[2:].zfill(8)
    enc = ''.join(dec[int(x[i], 16)] for i in range(8))
    return enc

# --- تحميل التوكنات ---
with open("token.json", "r") as f:
    accounts_passwords = json.load(f)

jwt_tokens_cache = {}
liked_targets_cache = {}
skipped_accounts = set()

liked_targets_lock = threading.Lock()
cache_lock = threading.Lock()

# --- تحميل التوكن ---
def get_token(uid, password):
    url = f"https://ffwlxd-access-jwt.vercel.app/api/get_jwt?guest_uid={uid}&guest_password={password}"
    try:
        r = httpx.get(url, timeout=10)
        return r.json().get("BearerAuth")
    except:
        return None

# --- تحديث كل التوكنات ---
def refresh_tokens():
    global jwt_tokens_cache
    with cache_lock:
        new_tokens = {}
        for uid, password in accounts_passwords.items():
            token = get_token(uid, password)
            if token:
                new_tokens[uid] = token
        jwt_tokens_cache = new_tokens

# --- بدء التحديث التلقائي كل 10 دقائق ---
def background_token_refresher():
    while True:
        refresh_tokens()
        time.sleep(600)

threading.Thread(target=background_token_refresher, daemon=True).start()

# --- endpoint الرئيسي ---
@app.route("/add_likes")
def add_likes():
    target_uid = request.args.get("uid")
    if not target_uid:
        return jsonify({"error": "uid is required"}), 400

    with liked_targets_lock:
        if target_uid in liked_targets_cache:
            return jsonify({"message": "Already liked recently"}), 200
        liked_targets_cache[target_uid] = True

    encrypted_id = Encrypt_ID(target_uid)
    url = "https://new-like2.onrender.com/like"

    results = []

    def send_like(uid, token):
        headers = {"Authorization": f"Bearer {token}"}
        data = {"id": encrypted_id}
        try:
            r = httpx.post(url, headers=headers, json=data, timeout=10)
            res = r.json()
            stats = res.get("stats", {})
            if stats.get("success"):
                results.append(uid)
        except:
            pass

    with cache_lock:
        for uid, token in jwt_tokens_cache.items():
            executor.submit(send_like, uid, token)

    return jsonify({"message": "Like process started", "target": target_uid}), 200

# --- نقطة اختبار ---
@app.route("/")
def home():
    return "✅ API is working"
