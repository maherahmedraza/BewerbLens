import time
import requests
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '../../.env'))

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
LINK_SECRET = os.getenv("TELEGRAM_LINK_SECRET")
# Dashboard is running on 3001 locally
COMPLETE_URL = "http://localhost:3001/api/integrations/telegram/link/complete"

def poll_updates():
    print(f"Polling Telegram for messages to bot... (Token: {BOT_TOKEN[:10]}...)")
    offset = None
    while True:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
        params = {"timeout": 10, "allowed_updates": ["message"]}
        if offset:
            params["offset"] = offset

        try:
            resp = requests.get(url, params=params, timeout=15)
            data = resp.json()
            if not data.get("ok"):
                print("Error from Telegram API:", data)
                time.sleep(5)
                continue

            for result in data.get("result", []):
                offset = result["update_id"] + 1
                msg = result.get("message", {})
                text = msg.get("text", "")
                chat_id = msg.get("chat", {}).get("id")

                if text.startswith("/start "):
                    code = text.split(" ")[1].strip()
                    print(f"Received link code: {code} from chat {chat_id}")
                    
                    # Call dashboard to complete linking
                    res = requests.post(
                        COMPLETE_URL,
                        headers={"x-telegram-link-secret": LINK_SECRET},
                        json={"code": code, "chatId": str(chat_id)}
                    )
                    
                    if res.status_code == 200:
                        print("Successfully linked in dashboard!")
                        requests.post(
                            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                            json={"chat_id": chat_id, "text": "✅ Successfully connected to BewerbLens!"}
                        )
                        return # Exit after successful link
                    else:
                        print(f"Failed to link: {res.status_code} {res.text}")
                        requests.post(
                            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                            json={"chat_id": chat_id, "text": f"❌ Linking failed: {res.text}"}
                        )
        except Exception as e:
            print("Exception during polling:", e)
            time.sleep(5)

if __name__ == "__main__":
    poll_updates()
