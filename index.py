from PIL import Image, ImageDraw, ImageFont
import os
from io import BytesIO
import requests
import traceback
import base64

BASE_IMAGE_URL = "https://iili.io/39iE4rF.jpg"
API_KEYS = {
    "BNGX": True,
    "20DAY": True,
    "busy": False
}

def handler(event, context):
    try:
        query = event.get("queryStringParameters", {}) or {}
        region = query.get("region")
        uid = query.get("uid")
        api_key = query.get("key")

        if not region or not uid or not api_key:
            return {"statusCode": 400, "body": "Missing region, uid, or key"}

        if not API_KEYS.get(api_key, False):
            return {"statusCode": 403, "body": "Invalid or inactive API key"}

        data = fetch_data(region, uid)
        if not data or "profileInfo" not in data:
            return {"statusCode": 500, "body": "Failed to fetch valid profile data"}

        profile = data["profileInfo"]
        item_ids = profile.get("equipedSkills", [])
        avatar_id = profile.get("avatarId")

        weapon_skin_raw = profile.get("weaponSkinShows")
        weapon_skin_id = weapon_skin_raw[0] if isinstance(weapon_skin_raw, list) and weapon_skin_raw else None

        if not item_ids or not avatar_id:
            return {"statusCode": 500, "body": "Missing equipped skills or avatar data"}

        image = overlay_images(BASE_IMAGE_URL, item_ids, avatar_id, weapon_skin_id)
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        base64_image = base64.b64encode(buffer.getvalue()).decode("utf-8")

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "image/png"
            },
            "body": base64_image,
            "isBase64Encoded": True
        }

    except Exception:
        return {"statusCode": 500, "body": traceback.format_exc()}


def fetch_data(region, uid):
    url = f"https://razor-info.vercel.app/player-info?uid={uid}&region={region}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        return None
    except:
        return None


def overlay_images(base_image, item_ids, avatar_id=None, weapon_skin_id=None):
    base_resp = requests.get(base_image)
    if base_resp.status_code != 200:
        raise Exception("Failed to load base image")

    base = Image.open(BytesIO(base_resp.content)).convert("RGBA")

    positions = [
        (485, 473), (295, 546), (290, 40),
        (479, 100), (550, 280), (100, 470),
        (600, 50)
    ]
    sizes = [(130, 130)] * len(positions)

    if avatar_id:
        avatar_url = f"https://pika-ffitmes-api.vercel.app/?item_id={avatar_id}&watermark=TaitanApi&key=PikaApis"
        avatar_resp = requests.get(avatar_url)
        if avatar_resp.status_code == 200:
            avatar = Image.open(BytesIO(avatar_resp.content)).convert("RGBA").resize((130, 130))
            cx = (base.width - avatar.width) // 2
            cy = (base.height - avatar.height) // 2
            base.paste(avatar, (cx, cy), avatar)

    for i, item_id in enumerate(item_ids[:6]):
        try:
            item_url = f"https://pika-ffitmes-api.vercel.app/?item_id={item_id}&watermark=TaitanApi&key=PikaApis"
            item_resp = requests.get(item_url)
            if item_resp.status_code == 200:
                item = Image.open(BytesIO(item_resp.content)).convert("RGBA").resize(sizes[i])
                base.paste(item, positions[i], item)
        except:
            continue

    if weapon_skin_id:
        try:
            weapon_url = f"https://pika-ffitmes-api.vercel.app/?item_id={weapon_skin_id}&watermark=TaitanApi&key=PikaApis"
            weapon_resp = requests.get(weapon_url)
            if weapon_resp.status_code == 200:
                weapon = Image.open(BytesIO(weapon_resp.content)).convert("RGBA").resize((130, 130))
                base.paste(weapon, positions[6], weapon)
        except:
            pass

    return base
