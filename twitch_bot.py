import os
import asyncio
from twitchio.ext import commands
import requests
import json
from dotenv import load_dotenv

load_dotenv()

# --- yapılandırma (güvenlik için ortam değişkenlerinden yükle) ---
TWITCH_OAUTH_TOKEN = os.environ.get('TWITCH_OAUTH_TOKEN')
TWITCH_NICKNAME = os.environ.get('TWITCH_NICKNAME') # bot'un twitch kullanıcı adı
TWITCH_CHANNEL = os.environ.get('TWITCH_CHANNEL')   # katılınacak kanal
BACKEND_URL = os.environ.get('BACKEND_URL', 'http://localhost:8000') # fastapi arka uç url'niz

# --- yapılandırmayı doğrula ---
if not all([TWITCH_OAUTH_TOKEN, TWITCH_NICKNAME, TWITCH_CHANNEL]):
    print("hata: gerekli ortam değişkenleri eksik:")
    print(" - TWITCH_OAUTH_TOKEN (örneğin, 'oauth:xxxxxxxx') - https://twitchapps.com/tmi/ adresinden alın")
    print(" - TWITCH_NICKNAME (bot'unuzun twitch kullanıcı adı)")
    print(" - TWITCH_CHANNEL (izlenecek twitch kanal adı)")
    print("bu değişkenlerle aynı dizinde bir .env dosyası oluşturun.")
    exit()

# arka uç url'sinin eğik çizgiyle bitmediğinden emin olun
if BACKEND_URL.endswith('/'):
    BACKEND_URL = BACKEND_URL[:-1]

# fastapi arka ucunuzdaki mesajların gönderileceği uç nokta
# bu uç noktayı daha sonra app.py dosyasında oluşturacağız
BACKEND_ENDPOINT = f"{BACKEND_URL}/twitch_message"

class TwitchBot(commands.Bot):

    def __init__(self):
        # bot'u belirteç, takma ad ve başlangıç kanalıyla başlat
        super().__init__(token=TWITCH_OAUTH_TOKEN, prefix='!', # önek gereklidir ancak komutları kullanmayacağız
                         initial_channels=[TWITCH_CHANNEL])
        print(f"kanal için bot başlatılıyor: {TWITCH_CHANNEL}")
        print(f"bot takma adı: {TWITCH_NICKNAME}")
        print(f"mesajların gönderileceği arka uç url'si: {BACKEND_ENDPOINT}")

    async def event_ready(self):
        # bot çevrimiçi olduğunda bir kez çağrılır
        print(f'{self.nick} olarak giriş yapıldı')
        print(f'kullanıcı kimliği: {self.user_id}')
        print(f'kanala başarıyla katıldı: {TWITCH_CHANNEL}')
        print("--- bot çalışıyor --- şimdi mesajlar dinleniyor...")

    async def event_message(self, message):
        # kanalda her mesaj gönderildiğinde çağrılır

        # bot'un kendisinden gelen mesajları yoksay
        if message.echo:
            return

        author_name = message.author.name if message.author else "bilinmeyen"
        content = message.content
        timestamp = message.timestamp.isoformat() # zaman damgasını al

        print(f"[{timestamp}] {author_name}: {content}")

        # --- mesaji arka uca gönder --- #
        try:
            payload = {
                "timestamp": timestamp,
                "username": author_name,
                "message": content,
                "channel": TWITCH_CHANNEL
            }
            # fastapi arka ucuna post isteği gönder
            response = requests.post(BACKEND_ENDPOINT, json=payload, timeout=5)

            if response.status_code == 200:
                print(f"  -> arka uca başarıyla gönderildi.")
            else:
                # hatayı günlüğe kaydet ancak bot'u çökertme
                print(f"  -> arka uca gönderirken hata: {response.status_code} - {response.text}")

        except requests.exceptions.RequestException as e:
            print(f"  -> arka uca bağlanılamadı: {e}")
        except Exception as e:
            print(f"  -> arka uca gönderirken beklenmeyen bir hata oluştu: {e}")

        # gerekirse komutları burada işleyebilirsiniz, ancak yalnızca dinliyoruz
        # await self.handle_commands(message)

    # isteğe bağlı: olası hataları veya bağlantı kesilmelerini işle
    async def event_error(self, error: Exception, data: str = None):
        print(f"\\n--- bot hatası ---")
        print(f"hata: {error}")
        if data:
            print(f"veri: {data}")
        print("devam etmeye çalışılıyor...")
        # hataya bağlı olarak yeniden bağlanma mantığı uygulamak isteyebilirsiniz

    async def event_close(self):
        print("\\n--- bot bağlantısı kapandı ---")
        # gerekirse temizleme veya yeniden bağlanma mantığı uygulayın
        await super().event_close()


if __name__ == "__main__":
    bot = TwitchBot()
    # zaman uyumsuz döngüyü işlemek için asyncio.run() kullanın
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        print("bot kullanıcı tarafından durduruldu.")
    except Exception as e:
        print(f"bot yürütülürken beklenmeyen bir hata oluştu: {e}") 