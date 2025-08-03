from PIL import Image, ImageDraw, ImageFont
import os
from io import BytesIO
import requests

BASE_IMAGE_URL = "https://iili.io/39iE4rF.jpg"
API_KEYS = {
    "BNGX": True,
    "20DAY": True,
    "busy": False
}

def handler(event, context):
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
    weapon_skin_id = None
    if isinstance(weapon_skin_raw, list) and weapon_skin_raw:
        weapon_skin_id = weapon_skin_raw[0]
    elif isinstance(weapon_skin_raw, int):
        weapon_skin_id = weapon_skin_raw

    if not item_ids or not avatar_id:
        return {"statusCode": 500, "body": "Missing equipped skills or avatar data"}

    try:
        image = overlay_images(BASE_IMAGE_URL, item_ids, avatar_id, weapon_skin_id)
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "image/png"
            },
            "body": buffer.read(),
            "isBase64Encoded": True
        }
    except Exception as e:
        return {"statusCode": 500, "body": f"Image generation failed: {str(e)}"}

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
    base = Image.open(BytesIO(requests.get(base_image).content)).convert("RGBA")
    draw = ImageDraw.Draw(base)

    positions = [
        (485, 473), (295, 546), (290, 40),
        (479, 100), (550, 280), (100, 470),
        (600, 50)
    ]
    sizes = [(130, 130)] * len(positions)

    if avatar_id:
        avatar_url = f"https://pika-ffitmes-api.vercel.app/?item_id={avatar_id}&watermark=TaitanApi&key=PikaApis"
        avatar = Image.open(BytesIO(requests.get(avatar_url).content)).convert("RGBA")
        avatar = avatar.resize((130, 130))
        cx = (base.width - avatar.width) // 2
        cy = (base.height - avatar.height) // 2
        base.paste(avatar, (cx, cy), avatar)

        try:
            font_path = os.path.join(os.path.dirname(__file__), "arial.ttf")
            font = ImageFont.truetype(font_path, 24)
        except:
            font = ImageFont.load_default()

        text = "BNGX"
        tw, th = draw.textsize(text, font=font)
        draw.text((cx + (130 - tw) // 2, cy + 130 + 5), text, fill="white", font=font)

    for i, item_id in enumerate(item_ids[:6]):
        try:
            item_url = f"https://pika-ffitmes-api.vercel.app/?item_id={item_id}&watermark=TaitanApi&key=PikaApis"
            item = Image.open(BytesIO(requests.get(item_url).content)).convert("RGBA")
            item = item.resize(sizes[i])
            base.paste(item, positions[i], item)
        except:
            continue

    if weapon_skin_id:
        try:
            weapon_url = f"https://pika-ffitmes-api.vercel.app/?item_id={weapon_skin_id}&watermark=TaitanApi&key=PikaApis"
            weapon = Image.open(BytesIO(requests.get(weapon_url).content)).convert("RGBA")
            weapon = weapon.resize((130, 130))
            base.paste(weapon, positions[6], weapon)
        except:
            pass

    return base
