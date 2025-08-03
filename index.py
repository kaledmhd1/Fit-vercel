from flask import Flask, request, jsonify, Response
import requests
import json
import threading
import time
import os
import urllib3
from concurrent.futures import ThreadPoolExecutor

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

LIKE_API_URL = "https://like-bjwt-bngx.onrender.com/send_like"
PLAYER_INFO_URL = "https://razor-info.vercel.app/player-info"
MAX_PARALLEL_REQUESTS = 40
LIKE_TARGET_EXPIRY = 86400  # 24 ساعة

group_accounts = [
    {
        "4016272811": "7C9B67FD6A47A62C04FCD7BB68EF479168B7520A3E3F4EDA1415DCCF10F46311",
        "3686947614": "BBCB287183F61B1D6987DF3CC8F63BE5DF02497D10D61FD8A690AEA9EEC9D7C6",
        "3231016672": "FAB40727917046A4C9792FC693690F21C75B48DC2432984960E31DF794B114C9"
    }
]

accounts_passwords = {}
for group in group_accounts:
    accounts_passwords.update(group)

skipped_accounts = {}
jwt_tokens_cache = {}
liked_targets_cache = {}

liked_targets_lock = threading.Lock()
cache_lock = threading.Lock()
skipped_lock = threading.Lock()
group_index_lock = threading.Lock()

group_index = 0
last_tokens_refresh_time = 0
last_skipped_refresh_time = 0

def add_to_skipped(uid):
    with skipped_lock:
        skipped_accounts[uid] = time.time()
    with cache_lock:
        if uid in jwt_tokens_cache:
            del jwt_tokens_cache[uid]

def is_skipped(uid):
    with skipped_lock:
        now = time.time()
        if uid in skipped_accounts:
            if now - skipped_accounts[uid] < 86400:
                return True
            else:
                del skipped_accounts[uid]
        return False

def get_jwt_token(uid, password):
    url = f"https://ffwlxd-access-jwt.vercel.app/api/get_jwt?guest_uid={uid}&guest_password={password}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('success') and data.get('BearerAuth'):
                return data['BearerAuth']
    except:
        pass
    return None

def refresh_all_tokens(group=None):
    global jwt_tokens_cache
    if isinstance(group, int) and 0 <= group < len(group_accounts):
        accounts = group_accounts[group]
    else:
        accounts = accounts_passwords

    new_cache = {}
    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_REQUESTS) as executor:
        futures = {
            executor.submit(get_jwt_token, uid, pwd): uid
            for uid, pwd in accounts.items() if not is_skipped(uid)
        }
        for future in futures:
            uid = futures[future]
            token = future.result()
            if token:
                new_cache[uid] = token

    with cache_lock:
        for uid in new_cache:
            jwt_tokens_cache[uid] = new_cache[uid]
        for uid in list(jwt_tokens_cache.keys()):
            if is_skipped(uid):
                del jwt_tokens_cache[uid]

def FOX_RequestAddingFriend(token, target_id):
    try:
        params = {"token": token, "id": target_id}
        headers = {
            "Accept": "*/*",
            "Authorization": f"Bearer {token}",
            "User-Agent": "Free Fire/2019117061 CFNetwork/1399 Darwin/22.1.0",
            "X-GA": "v1 1",
            "ReleaseVersion": "OB50",
        }
        response = requests.get(LIKE_API_URL, params=params, headers=headers, timeout=10)
        try:
            return response.status_code, response.json()
        except:
            return response.status_code, response.text
    except Exception as e:
        return 0, str(e)

def get_player_info(uid):
    try:
        url = f"{PLAYER_INFO_URL}?uid={uid}&region=me"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            basic = data.get('basicInfo', {})
            nickname = basic.get('nickname', 'Unknown')
            liked = basic.get('liked', 0)
            accountId = basic.get('accountId', uid)
            return {"nickname": nickname, "liked": liked, "accountId": accountId}
    except:
        pass
    return {"nickname": "Unknown", "liked": 0, "accountId": uid}

@app.route('/add_likes', methods=['GET'])
def send_likes():
    global last_tokens_refresh_time, last_skipped_refresh_time, group_index

    target_id = request.args.get('uid')
    if not target_id or not target_id.isdigit():
        return jsonify({"error": "uid is required and must be an integer"}), 400

    now = time.time()

    with group_index_lock:
        current_group = group_index % len(group_accounts)
        group_index += 1

    refresh_all_tokens(group=current_group)

    if now - last_skipped_refresh_time >= 10000:
        try:
            refresh_skipped_tokens()
        except:
            pass
        last_skipped_refresh_time = now

    player_info = get_player_info(target_id)
    likes_before = player_info["liked"]

    with liked_targets_lock:
        to_delete = [uid for uid, ts in liked_targets_cache.items() if now - ts > LIKE_TARGET_EXPIRY]
        for uid in to_delete:
            del liked_targets_cache[uid]

        if target_id in liked_targets_cache:
            return Response(json.dumps({
                "message": f"🚫 لا يمكن إرسال لايك لنفس الـ UID {target_id} إلا بعد مرور 24 ساعة من آخر مرة."
            }, ensure_ascii=False), mimetype='application/json'), 429

        liked_targets_cache[target_id] = now

    with cache_lock:
        tokens_to_use = {
            uid: token for uid, token in jwt_tokens_cache.items()
            if uid in group_accounts[current_group]
        }

        if not tokens_to_use:
            return Response(json.dumps({
                "message": "🚧 التوكنات لم تُجهز بعد، الرجاء المحاولة لاحقاً."
            }, ensure_ascii=False), mimetype='application/json'), 503

    success_count = 0
    skipped_count = 0
    failed_count = 0
    successful_uids = []
    stop_flag = threading.Event()

    def process(uid, token):
        nonlocal success_count, skipped_count, failed_count
        if stop_flag.is_set():
            return
        status, content = FOX_RequestAddingFriend(token, target_id)
        if isinstance(content, dict) and "BR_ACCOUNT_DAILY_LIKE_PROFILE_LIMIT" in str(content.get("response_text", "")):
            skipped_count += 1
            add_to_skipped(uid)
            return
        if status == 200:
            success_count += 1
            successful_uids.append(uid)
            if success_count >= 60:
                stop_flag.set()
        else:
            failed_count += 1

    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_REQUESTS) as executor:
        futures = [executor.submit(process, uid, token) for uid, token in tokens_to_use.items()]
        for future in futures:
            future.result()
            if stop_flag.is_set():
                break

    likes_after = likes_before + success_count

    message = (
        f"✅ الاسم: {player_info['nickname']}\n"
        f"🆔 UID: {player_info['accountId']}\n"
        f"👍 قبل: {likes_before} لايك\n"
        f"➕ المضافة: {success_count} لايك\n"
        f"💯 بعد: {likes_after} لايك"
    )

    return Response(json.dumps({
        "message": message
    }, ensure_ascii=False), mimetype='application/json')

def refresh_skipped_tokens():
    with skipped_lock:
        uids = list(skipped_accounts.keys())

    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_REQUESTS) as executor:
        futures = {}
        for uid in uids:
            pwd = accounts_passwords.get(uid)
            if pwd:
                futures[executor.submit(get_jwt_token, uid, pwd)] = uid
        for future in futures:
            uid = futures[future]
            token = future.result()
            if token:
                status, content = FOX_RequestAddingFriend(token, target_id="0")
                if status == 200:
                    if not (isinstance(content, dict) and "BR_ACCOUNT_DAILY_LIKE_PROFILE_LIMIT" in str(content.get("response_text", ""))):
                        with skipped_lock:
                            if uid in skipped_accounts:
                                del skipped_accounts[uid]
                        with cache_lock:
                            jwt_tokens_cache[uid] = token

# Vercel entrypoint
def handler(environ, start_response):
    return app(environ, start_response)
