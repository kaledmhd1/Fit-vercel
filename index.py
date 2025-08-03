from fastapi import FastAPI, Request, Query
from fastapi.responses import StreamingResponse, JSONResponse
from PIL import Image, ImageDraw, ImageFont
import httpx
from io import BytesIO

app = FastAPI()

BASE_IMAGE_URL = "https://iili.io/39iE4rF.jpg"

API_KEYS = {
    "BNGX": True,
    "20DAY": True,
    "busy": False
}

def is_key_valid(api_key: str) -> bool:
    return API_KEYS.get(api_key, False)

async def fetch_data(region: str, uid: str):
    url = f"https://razor-info.vercel.app/player-info?uid={uid}&region={region}"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url)
            if response.status_code == 200:
                return response.json()
        except:
            return None

async def overlay_images(item_ids, avatar_id=None, weapon_skin_id=None):
    base_resp = await httpx.AsyncClient().get(BASE_IMAGE_URL)
    base = Image.open(BytesIO(base_resp.content)).convert("RGBA")
    draw = ImageDraw.Draw(base)

    positions = [
        (485, 473), (295, 546), (290, 40),
        (479, 100), (550, 280), (100, 470), (600, 50)
    ]
    sizes = [(130, 130)] * len(positions)

    if avatar_id:
        avatar_url = f"https://pika-ffitmes-api.vercel.app/?item_id={avatar_id}&watermark=TaitanApi&key=PikaApis"
        try:
            avatar_resp = await httpx.AsyncClient().get(avatar_url)
            avatar = Image.open(BytesIO(avatar_resp.content)).convert("RGBA").resize((130, 130))
            center_x = (base.width - 130) // 2
            center_y = (base.height - 130) // 2
            base.paste(avatar, (center_x, center_y), avatar)

            font = ImageFont.load_default()
            draw.text((center_x + 30, center_y + 135), "BNGX", fill="white", font=font)
        except:
            pass

    for i, item_id in enumerate(item_ids[:6]):
        item_url = f"https://pika-ffitmes-api.vercel.app/?item_id={item_id}&watermark=TaitanApi&key=PikaApis"
        try:
            item_resp = await httpx.AsyncClient().get(item_url)
            item = Image.open(BytesIO(item_resp.content)).convert("RGBA").resize((130, 130))
            base.paste(item, positions[i], item)
        except:
            continue

    if weapon_skin_id:
        try:
            weapon_url = f"https://pika-ffitmes-api.vercel.app/?item_id={weapon_skin_id}&watermark=TaitanApi&key=PikaApis"
            weapon_resp = await httpx.AsyncClient().get(weapon_url)
            weapon = Image.open(BytesIO(weapon_resp.content)).convert("RGBA").resize((130, 130))
            base.paste(weapon, positions[6], weapon)
        except:
            pass

    img_io = BytesIO()
    base.save(img_io, 'PNG')
    img_io.seek(0)
    return img_io

@app.get("/api")
async def generate_image(region: str = Query(...), uid: str = Query(...), key: str = Query(...)):
    if not is_key_valid(key):
        return JSONResponse({"error": "Invalid or inactive API key"}, status_code=403)

    data = await fetch_data(region, uid)
    if not data or "profileInfo" not in data:
        return JSONResponse({"error": "Failed to fetch profile"}, status_code=500)

    profile = data["profileInfo"]
    item_ids = profile.get("equipedSkills", [])
    avatar_id = profile.get("avatarId")

    weapon_skin_raw = profile.get("weaponSkinShows")
    weapon_skin_id = weapon_skin_raw[0] if isinstance(weapon_skin_raw, list) and weapon_skin_raw else None
    if isinstance(weapon_skin_raw, int):
        weapon_skin_id = weapon_skin_raw

    if not item_ids or not avatar_id:
        return JSONResponse({"error": "Missing data"}, status_code=500)

    image_stream = await overlay_images(item_ids, avatar_id, weapon_skin_id)
    return StreamingResponse(image_stream, media_type="image/png")
