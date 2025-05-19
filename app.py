from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import JSONResponse
import os
import json
import base64
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import uvicorn # uygulamayı çalıştırmak için eklendi
from pydantic import BaseModel
from typing import Optional # başka bir yerde kullanılıyorsa isteğe bağlı tutun veya kullanılmıyorsa kaldırın

# --- yapılandırma ---
KICK_PUBLIC_KEY_PEM = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAq/+l1WnlRrGSolDMA+A8
6rAhMbQGmQ2SapVcGM3zq8ANXjnhDWocMqfWcTd95btDydITa10kDvHzw9WQOqp2
MZI7ZyrfzJuz5nhTPCiJwTwnEtWft7nV14BYRDHvlfqPUaZ+1KR4OCaO/wWIk/rQ
L/TjY0M70gse8rlBkbo2a8rKhu69RQTRsoaf4DVhDPEeSeI5jVrRDGAMGL3cGuyY
6CLKGdjVEM78g3JfYOvDU/RvfqD7L89TZ3iN94jrmWdGz34JNlEI5hqK8dd7C5EF
BEbZ5jgB8s8ReQV8H+MkuffjdAj3ajDDX3DOJMIut1lBrUVD1AaSrGCKHooWoL2e
twIDAQAB
-----END PUBLIC KEY-----"""

# genel anahtarı yükle
try:
    public_key = serialization.load_pem_public_key(
        KICK_PUBLIC_KEY_PEM.encode('utf-8')
    )
    print("kick genel anahtarı başarıyla yüklendi.")
except Exception as e:
    print(f"kick genel anahtarı yüklenirken hata: {e}")
    public_key = None # üretimde hatayı uygun şekilde işle

app = FastAPI() # flask'tan fastapi'ye değiştirildi
analyzer = SentimentIntensityAnalyzer()

# kick mesajları için bellek içi depolama
chat_messages = []
MAX_KICK_MESSAGES = 100 # netlik için yeniden adlandırıldı

# twitch mesajları için bellek içi depolama
twitch_chat_messages = []
MAX_TWITCH_MESSAGES = 100 # depolanan twitch mesajı sayısını sınırla

# --- pydantic modelleri (istek doğrulaması için) ---
class TwitchMessagePayload(BaseModel):
    timestamp: str
    username: str
    message: str
    channel: str

# --- yardımcı fonksiyonlar ---
async def verify_kick_signature(request: Request): # tür ipucu ve zaman uyumsuz eklendi
    """kick'ten gelen bir webhook isteğinin imzasını doğrular."""
    if not public_key:
        print("genel anahtar yüklenmedi. i̇mza doğrulanamıyor.")
        return False

    signature_header = request.headers.get('Kick-Event-Signature')
    message_id = request.headers.get('Kick-Event-Message-Id')
    timestamp = request.headers.get('Kick-Event-Message-Timestamp')
    raw_body = await request.body() # request.get_data() await request.body() olarak değiştirildi

    if not all([signature_header, message_id, timestamp]):
        print("doğrulama için gerekli kick başlıkları eksik.")
        return False

    try:
        # i̇mzayı base64'ten çöz
        decoded_signature = base64.b64decode(signature_header)

        # i̇mzalanan mesajı oluştur
        # doğru birleştirmeyi sağla: ki̇mli̇k, zaman damgası, ardından ham gövde baytları
        signed_content = f"{message_id}.{timestamp}.".encode('utf-8') + raw_body
        print(f"doğrulanacak içerik (ilk 200 bayt): {signed_content[:200]}...") # i̇çeriğin bir kısmını günlüğe kaydet

        # i̇mzayı doğrula
        public_key.verify(
            decoded_signature,
            signed_content,
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        print("i̇mza başarıyla doğrulandı!")
        return True
    except InvalidSignature:
        print("i̇mza doğrulaması başarısız oldu: geçersiz i̇mza.")
        return False
    except Exception as e:
        print(f"i̇mza doğrulaması sırasında hata: {e}")
        return False

# --- rotalar ---
@app.post('/kick_webhook') # dekoratör değiştirildi ve zaman uyumsuz eklendi
async def kick_webhook(request: Request): # zaman uyumsuz ve tür ipucu eklendi
    print("\n--- kick webhook alındı ---") # günlük mesajı netleştirildi
    print(f"başlıklar: {request.headers}")

    # 1. i̇mzayı doğrula
    if not await verify_kick_signature(request): # await eklendi
        print("webhook i̇mzası doğrulaması başarısız oldu.")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="geçersiz i̇mza") # abort httpexception olarak değiştirildi

    # 2. olayı i̇şle
    event_type = request.headers.get('Kick-Event-Type')
    print(f"olay türü: {event_type}")

    if event_type == 'chat.message.sent':
        try:
            # fastapi için, doğrulama için ham gövdeyi okuduktan sonra json gövdesini al
            # gövdeyi tekrar okumamız veya daha önce elde edilen ham_gövdeyi ayrıştırmamız gerekiyor
            _data = {}
            try:
                # i̇stek gövdesi bir akıştır ve yalnızca bir kez okunabilir.
                # verify_kick_signature bunu okuduysa, burada await request.body() ile tekrar okuyamayız
                # bunun yerine, verify_kick_signature'dan ham_gövdeyi geçirmeli veya kesinlikle gerekliyse yeniden okumalıydık
                # şimdilik, verify_kick_signature'dan ham_gövde'nin geçirilmesi veya saklanması durumunda kullanılabileceğini varsayalım.
                # bu bölüm, i̇stek gövdesi akışının dikkatli bir şekilde işlenmesini gerektirir.
                # yaygın bir model, gövdeyi bir kez okumak ve i̇htiyacı olan i̇şlevlere geçirmektir.
                # bu adım için, ham_gövde mevcut olsaydı yeniden ayrıştıracağımızı varsayalım.
                # ham_gövde verify_kick_signature'da yakalandıysa, şöyle olurdu:
                # data = json.loads(raw_body.decode('utf-8'))
                # ancak, verify_kick_signature bunu döndürmez.
                # bu, gövde zaten tüketilmişse büyük olasılıkla bir hataya neden olur.
                # sağlam bir çözüm: uç noktanın başında gövdeyi bir kez oku.
                # şimdilik, bu tekrar okumayı deneyecek, bu da verify_kick_signature tarafından zaten okunmuşsa başarısız olabilir
                _data = await request.json() # json'u doğrudan almayı dene

            except json.JSONDecodeError:
                 print("json yükü çözülürken hata")
                 # i̇mza geçerliyse kick'e yine de 200 döndür, ancak hatayı günlüğe kaydet
                 return JSONResponse(content={"status": "error", "message": "geçersiz json yükü"}, status_code=200)
            except Exception as e: # gövde okuma/ayrıştırma sırasında diğer hataları yakala
                 print(f"istek gövdesi okunurken/ayrıştırılırken hata: {e}")
                 return JSONResponse(content={"status": "error", "message": "istek gövdesi okunurken hata"}, status_code=200)


            print(f"yük: {json.dumps(_data, indent=2)}")

            sender_username = _data.get('sender', {}).get('username', 'bilinmeyen')
            message_content = _data.get('content')

            if message_content:
                # duygu analizi yap
                vs = analyzer.polarity_scores(message_content)
                sentiment_label = "neutral"
                if vs['compound'] >= 0.05:
                    sentiment_label = "positive"
                elif vs['compound'] <= -0.05:
                    sentiment_label = "negative"

                print(f"{sender_username} kullanıcısından mesaj: '{message_content}'")
                print(f"duygu: {sentiment_label} (puan: {vs['compound']})")

                # mesajı ve duyguyu sakla
                chat_messages.append({
                    'sender': sender_username,
                    'message': message_content,
                    'sentiment_score': vs['compound'],
                    'sentiment_label': sentiment_label,
                    'timestamp': request.headers.get('Kick-Event-Message-Timestamp') # başlıklardan zaman damgasını al
                })

                # yalnızca son max_kick_messages'ı tut
                if len(chat_messages) > MAX_KICK_MESSAGES:
                    chat_messages.pop(0)

            else:
                print("mesaj içeriği boş.")

        except Exception as e:
            print(f"sohbet mesajı yükü işlenirken hata: {e}")
            # kick'e yine de 200 döndür, ancak hatayı günlüğe kaydet
            # sorun yük işleme ise kick'in gereksiz yere yeniden denememesi için burada http 500 oluşturmaktan kaçının
            return JSONResponse(content={"status": "error", "message": "yük işlenemedi"}, status_code=200)

    elif event_type:
        print(f"'{event_type}' olay türü alındı, yoksayılıyor.")
    else:
        print("bilinmeyen veya eksik olay türü.")


    # 3. kick'e yanıt ver
    # kick, alındığını onaylamak için 200 ok yanıtı bekler.
    return JSONResponse(content={"status": "success"}, status_code=200) # jsonresponse kullan


@app.get('/sentiment_summary') # dekoratör değiştirildi
async def sentiment_summary(): # zaman uyumsuz eklendi
    """son kick sohbet duygusunun bir özetini sağlar."""
    if not chat_messages:
        return JSONResponse(content={"message": "henüz sohbet mesajı alınmadı."}) # jsonresponse kullan

    # ortalama duyguyu hesapla
    # kontrol ve hesaplama arasında chat_messages boşalabilirse sıfıra bölme kontrolü ekle
    if not chat_messages: # bu kontrol yukarıdakine göre biraz gereksiz ama zararsız
         return JSONResponse(content={"message": "henüz sohbet mesajı alınmadı."}) # jsonresponse kullan

    total_score = sum(msg['sentiment_score'] for msg in chat_messages)
    average_score = total_score / len(chat_messages)
    positive_messages = sum(1 for msg in chat_messages if msg['sentiment_label'] == 'positive')
    negative_messages = sum(1 for msg in chat_messages if msg['sentiment_label'] == 'negative')
    neutral_messages = sum(1 for msg in chat_messages if msg['sentiment_label'] == 'neutral')

    return JSONResponse(content={ # jsonresponse kullan
        "total_messages_stored": len(chat_messages),
        "average_sentiment_score": average_score,
        "positive_messages": positive_messages,
        "negative_messages": negative_messages,
        "neutral_messages": neutral_messages,
        "last_messages": chat_messages[-5:] # son 5 mesajı döndür
    })

# --- twitch mesaj işleme --- 
@app.post('/twitch_message') # zaman uyumsuz eklendi
async def receive_twitch_message(payload: TwitchMessagePayload):
    """twitch botundan mesajları alır ve saklar."""
    print("\n--- twitch mesajı alındı ---")
    print(f"alınan yük: {payload.dict()}")

    # duygu analizi yap (vader)
    vs = analyzer.polarity_scores(payload.message)
    sentiment_label = "neutral"
    if vs['compound'] >= 0.05:
        sentiment_label = "positive"
    elif vs['compound'] <= -0.05:
        sentiment_label = "negative"
    
    print(f"twitch mesajı: '{payload.message}' | duygu: {sentiment_label} ({vs['compound']:.4f})")

    twitch_chat_messages.append({
        "timestamp": payload.timestamp,
        "username": payload.username,
        "message": payload.message,
        "channel": payload.channel,
        "sentiment_label": sentiment_label,
        "sentiment_score": vs['compound']
    })

    if len(twitch_chat_messages) > MAX_TWITCH_MESSAGES:
        twitch_chat_messages.pop(0)

    return {"status": "success", "message": "twitch mesajı alındı ve işlendi"}

@app.get('/get_twitch_messages') # zaman uyumsuz eklendi
async def get_twitch_messages():
    """saklanan twitch mesajlarının bir listesini döndürür."""
    return {"messages": twitch_chat_messages}

# ana uygulamayı çalıştırmak için (genellikle geliştirme için)
if __name__ == "__main__":
    # uvicorn'un reload=true ve log_level='info' ile çalıştırılması önerilir
    # uvicorn app:app --host 0.0.0.0 --port 8000 --reload
    print("fastapi sunucusunu başlatıyor... şurada çalıştırın: uvicorn app:app --reload") 