import base64
import json
import time
import urllib.error
import urllib.parse
import urllib.request

# ===== শুধু এই দুই জায়গায় তোমার টোকেন ও key বসাও =====
BOT_TOKEN = "8913068365:AAEoevp1MKY6iNLPA5X805I3PNyD-dXKTbw"
IMGBB_KEY = "ee3436e95f504358947b7e26567ead90"
# =====================================================

API = f"https://api.telegram.org/bot{BOT_TOKEN}"
FILE_API = f"https://api.telegram.org/file/bot{BOT_TOKEN}"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def tg(method, **params):
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(f"{API}/{method}", data=data, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def send(chat_id, text, buttons=None):
    params = {"chat_id": chat_id, "text": text, "disable_web_page_preview": "true"}
    if buttons:
        params["reply_markup"] = json.dumps({"inline_keyboard": buttons})
    try:
        return tg("sendMessage", **params)
    except Exception as e:
        print("send error:", e)
        if buttons:
            try:
                return tg("sendMessage", chat_id=chat_id, text=text)
            except Exception as e2:
                print("send error 2:", e2)


def url_buttons(url):
    share = "https://t.me/share/url?url=" + urllib.parse.quote(url, safe="")
    return [
        [{"text": "🔗 লিংক খুলুন", "url": url}],
        [
            {"text": "📋 কপি করুন", "copy_text": {"text": url}},
            {"text": "📤 শেয়ার করুন", "url": share},
        ],
    ]


def retry(fn, tries=3):
    last = None
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            last = e
            print(f"  try {i + 1} failed:", e)
            time.sleep(2)
    raise last


def download_from_telegram(file_id):
    info = tg("getFile", file_id=file_id)
    path = info["result"]["file_path"]
    req = urllib.request.Request(f"{FILE_API}/{path}", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        img = r.read()
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else "jpg"
    return img, ext


def imgbb_upload(img):
    body = urllib.parse.urlencode(
        {"key": IMGBB_KEY, "image": base64.b64encode(img).decode()}
    ).encode()
    req = urllib.request.Request(
        "https://api.imgbb.com/1/upload", data=body, headers=HEADERS
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            res = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        print("imgbb http error:", e.code, e.read().decode()[:300])
        raise
    return res["data"]["url"]


def catbox_upload(img, ext):
    b = "----bot" + str(int(time.time() * 1000))
    body = (
        f'--{b}\r\nContent-Disposition: form-data; name="reqtype"\r\n\r\nfileupload\r\n'.encode()
        + f'--{b}\r\nContent-Disposition: form-data; name="fileToUpload"; filename="image.{ext}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode()
        + img
        + f"\r\n--{b}--\r\n".encode()
    )
    headers = dict(HEADERS)
    headers["Content-Type"] = f"multipart/form-data; boundary={b}"
    req = urllib.request.Request(
        "https://catbox.moe/user/api.php", data=body, headers=headers
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        text = r.read().decode().strip()
    if not text.startswith("http"):
        raise Exception("catbox response: " + text[:200])
    return text


def upload_image(file_id):
    print("downloading from telegram...")
    img, ext = retry(lambda: download_from_telegram(file_id))

    print("trying imgbb...")
    try:
        return retry(lambda: imgbb_upload(img), tries=2)
    except Exception as e:
        print("imgbb failed:", e)

    print("trying catbox...")
    return retry(lambda: catbox_upload(img, ext), tries=3)


def handle(msg):
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "")

    if text.startswith("/start"):
        send(chat_id, "আমাকে যেকোনো ছবি পাঠাও, আমি ছবির URL দিয়ে দেব।")
        return

    file_id = None
    if "photo" in msg:
        file_id = msg["photo"][-1]["file_id"]
    elif "document" in msg and msg["document"].get("mime_type", "").startswith("image/"):
        file_id = msg["document"]["file_id"]

    if not file_id:
        send(chat_id, "দয়া করে একটা ছবি পাঠাও।")
        return

    send(chat_id, "আপলোড হচ্ছে...")
    try:
        url = upload_image(file_id)
        send(chat_id, url, url_buttons(url))
    except Exception as e:
        print("upload error:", e)
        send(chat_id, "আপলোড ব্যর্থ হয়েছে, আবার চেষ্টা করো।")


def main():
    print("Bot started...")
    offset = 0
    while True:
        try:
            res = tg("getUpdates", offset=offset, timeout=30)
            for upd in res.get("result", []):
                offset = upd["update_id"] + 1
                if "message" in upd:
                    handle(upd["message"])
        except Exception as e:
            print("loop error:", e)
            time.sleep(5)


if __name__ == "__main__":
    main()
