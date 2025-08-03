from PIL import Image
import requests
from io import BytesIO
import base64
import traceback

BASE_IMAGE_URL = "https://iili.io/39iE4rF.jpg"
API_KEYS = {"BNGX": True, "20DAY": True, "busy": False}

def handler(event, context):
    try:
        query = event.get("queryStringParameters") or {}
        region = query.get("region")
        uid = query.get("uid")
        key = query.get("key")

        if not region or not uid or not key:
            return {"statusCode": 400, "body": "Missing region, uid, or key"}
        if not API_KEYS.get(key):
            return {"statusCode": 403, "body": "Invalid API key"}

        data = fetch_data(region, uid)
        if not data or "profileInfo" not in data:
            return {"statusCode": 500, "body": "Invalid profile data"}

        prof = data["profileInfo"]
        items = prof.get("equipedSkills", [])
        avatar = prof.get("avatarId")
        weapon_raw = prof.get("weaponSkinShows")
        weapon = weapon_raw[0] if isinstance(weapon_raw, list) and weapon_raw else weapon_raw if isinstance(weapon_raw, int) else None

        if not items or not avatar:
            return {"statusCode": 500, "body": "Missing equipedSkills or avatarId"}

        # توليد الصورة
        img = overlay(BASE_IMAGE_URL, items, avatar, weapon)
        buf = BytesIO()
        img.save(buf, format="PNG")
        img64 = base64.b64encode(buf.getvalue()).decode()

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "image/png"},
            "body": img64,
            "isBase64Encoded": True
        }
    except Exception:
        return {"statusCode": 500, "body": traceback.format_exc()}

def fetch_data(region, uid):
    try:
        resp = requests.get(f"https://razor-info.vercel.app/player-info?uid={uid}&region={region}")
        if resp.status_code == 200:
            return resp.json()
    except:
        pass
    return None

def overlay(base_url, items, avatar_id, weapon_id=None):
    resp = requests.get(base_url)
    if resp.status_code != 200:
        raise Exception("Failed base image")

    base = Image.open(BytesIO(resp.content)).convert("RGBA")
    pos = [(485,473),(295,546),(290,40),(479,100),(550,280),(100,470),(600,50)]
    size = (130,130)

    # صورة الأفاتار
    avat = requests.get(f"https://pika-ffitmes-api.vercel.app/?item_id={avatar_id}&watermark=TaitanApi&key=PikaApis")
    if avat.status_code == 200:
        avatar = Image.open(BytesIO(avat.content)).convert("RGBA").resize(size)
        cx, cy = (base.width - size[0])//2, (base.height - size[1])//2
        base.paste(avatar, (cx, cy), avatar)

    # العناصر
    for i, iid in enumerate(items[:6]):
        try:
            r = requests.get(f"https://pika-ffitmes-api.vercel.app/?item_id={iid}&watermark=TaitanApi&key=PikaApis")
            if r.status_code == 200:
                itm = Image.open(BytesIO(r.content)).convert("RGBA").resize(size)
                base.paste(itm, pos[i], itm)
        except:
            pass

    # سكن السلاح
    if weapon_id:
        try:
            rw = requests.get(f"https://pika-ffitmes-api.vercel.app/?item_id={weapon_id}&watermark=TaitanApi&key=PikaApis")
            if rw.status_code == 200:
                wp = Image.open(BytesIO(rw.content)).convert("RGBA").resize(size)
                base.paste(wp, pos[6], wp)
        except:
            pass

    return base
