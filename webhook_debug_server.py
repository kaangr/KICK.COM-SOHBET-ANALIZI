from fastapi import FastAPI, Request, Header, HTTPException
import uvicorn
import json
import logging
import traceback
from datetime import datetime
import requests
import httpx

# loglama yapılandırması
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("webhook_debug.log")  # dosyaya da kaydet
    ]
)
logger = logging.getLogger("webhook_server")

app = FastAPI()

# mesaj depolama
latest_messages = []
MAX_MESSAGES = 50

# webhook alımı istatistikleri
webhook_stats = {
    "total_requests": 0,
    "kick_events": 0,
    "test_events": 0,
    "unknown_events": 0,
    "last_request_time": None
}

# middleware - tüm istekleri loglar
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """gelen tüm istekleri logla"""
    logger.info(f"istek: {request.method} {request.url.path}")
    # başlıkları logla
    headers = dict(request.headers.items())
    logger.info(f"başlıklar: {json.dumps(headers, indent=2)}")
    
    # istek gövdesini logla (kopyalayarak)
    body = await request.body()
    if body:
        try:
            # json olarak parse etmeyi dene
            decoded_body = json.loads(body)
            logger.info(f"gövde: {json.dumps(decoded_body, indent=2)}")
        except:
            # json değilse binary olarak göster
            logger.info(f"gövde (ham): {body}")
    
    # orijinal istek nesnesini yeniden oluştur
    request._body = body
    
    # asıl handler'ı çağır
    try:
        response = await call_next(request)
        logger.info(f"yanıt durumu: {response.status_code}")
        return response
    except Exception as e:
        logger.error(f"istek işlenirken hata: {e}")
        logger.error(traceback.format_exc())
        raise

@app.post("/kick-webhook")
async def handle_kick_webhook(request: Request):
    """kick'ten gelen webhook isteklerini işler."""
    logger.info("webhook alındı")
    
    # i̇statistikleri güncelle
    webhook_stats["total_requests"] += 1
    webhook_stats["last_request_time"] = datetime.now().isoformat()
    
    try:
        # kick-event-type ve version'ı manuel olarak headers'dan al
        kick_event_type = request.headers.get("Kick-Event-Type")
        kick_event_version = request.headers.get("Kick-Event-Version")
        user_agent = request.headers.get("User-Agent", "")
        logger.info(f"kick olayı: tür={kick_event_type}, sürüm={kick_event_version}, ua={user_agent}")
        
        # i̇stek gövdesini parse et
        try:
            payload = await request.json()
        except json.JSONDecodeError:
            # i̇steğin json olmaması durumunu ele al
            raw_body = await request.body()
            logger.warning(f"geçersiz json alındı: {raw_body}")
            # basit bir string ise ve "content=" gibi bir form içeriyorsa, basit parse et
            try:
                payload = dict(item.split("=") for item in raw_body.decode().split("&"))
                logger.info(f"ayrıştırılmış form verileri: {payload}")
            except:
                logger.error("istek gövdesi ayrıştırılamadı")
                return {"status": "error", "message": "geçersiz yük formatı"}
        
        logger.info(f"alınan webhook yükü: {json.dumps(payload, indent=2)}")
        
        # kick olayı mı yoksa test olayı mı olduğunu belirle
        is_test = False
        if isinstance(payload, dict):
            # test mesajını tanımak için bazı ipuçları
            test_indicators = ["test", "test_", "test123", "test_sender", "test_message", "debug_broadcaster", "debug_self_test", "verify_test_"]
            for key, value in payload.items():
                if isinstance(value, str) and any(indicator in value.lower() for indicator in test_indicators):
                    is_test = True
                    break
                elif isinstance(value, dict):
                    for subkey, subvalue in value.items():
                        if isinstance(subvalue, str) and any(indicator in subvalue.lower() for indicator in test_indicators):
                            is_test = True
                            break
                    if is_test: break # i̇ç döngüden de çık
        
        if is_test:
            webhook_stats["test_events"] += 1
            logger.info("test webhook olayı algılandı")
        elif kick_event_type:
            webhook_stats["kick_events"] += 1
            logger.info(f"kick webhook olayı algılandı: {kick_event_type}")
        else:
            webhook_stats["unknown_events"] += 1
            logger.warning("bilinmeyen webhook olay türü")
        
        # mesaj içeriğini ve göndereni farklı formatları ele alarak çıkarmaya çalış
        message_content = None
        sender_username = None
        message_id = None
        
        # kick formatını kontrol et
        if isinstance(payload, dict):
            # standart kick formatı
            message_content = payload.get('content')
            message_id = payload.get('message_id', f"msg_{datetime.now().timestamp()}")
            
            # gönderici bilgisini farklı formatlarda aramaya çalış
            sender_info = payload.get('sender', {})
            if isinstance(sender_info, dict):
                sender_username = sender_info.get('username')
            
            # alternatif formatları kontrol et
            if not message_content:
                message_content = payload.get('message', payload.get('text', payload.get('msg')))
            
            if not sender_username:
                sender_username = payload.get('username', payload.get('user', payload.get('sender')))
                
                # hala bulunamadıysa, diğer olası fieldlarda deneyelim
                if not sender_username and 'broadcaster' in payload:
                    broadcaster = payload.get('broadcaster', {})
                    if isinstance(broadcaster, dict):
                        sender_username = broadcaster.get('username')
        
        # mesajı işle
        if message_content and sender_username:
            logger.info(f"çıkarılan mesaj - gönderen: {sender_username}, i̇çerik: {message_content}")
            
            # mesajı sakla
            message_data = {
                "id": message_id,
                "username": sender_username,
                "message": message_content,
                "timestamp": datetime.now().isoformat(),
                "sentiment": "N/A",  # nlp entegrasyonu daha sonra yapılacak
                "is_test": is_test
            }
            latest_messages.append(message_data)
            if len(latest_messages) > MAX_MESSAGES:
                latest_messages.pop(0)
                
            logger.info(f"mesaj depoya eklendi. toplam mesaj: {len(latest_messages)}")
            return {"status": "success", "message": "mesaj i̇şlendi"}
            
        else:
            # i̇çerik veya gönderen bulanamazsa ham veriyi logla
            logger.warning("mesaj içeriği veya gönderen çıkarılamadı")
            logger.warning(f"ham yük: {json.dumps(payload, indent=2)}")
            return {"status": "warning", "message": "mesaj verisi çıkarılamadı"}
            
    except Exception as e:
        logger.error(f"webhook işlenirken hata: {e}")
        logger.error(traceback.format_exc())
        return {"status": "error", "message": str(e)}

@app.get("/get-messages")
async def get_latest_messages(test_only: bool = False, real_only: bool = False):
    """webhook aracılığıyla alınan en son mesajların listesini döndürür."""
    if test_only:
        filtered_messages = [msg for msg in latest_messages if msg.get("is_test", False)]
        logger.info(f"Returning {len(filtered_messages)} test messages")
        return {"messages": filtered_messages}
    elif real_only:
        filtered_messages = [msg for msg in latest_messages if not msg.get("is_test", False)]
        logger.info(f"Returning {len(filtered_messages)} real messages")
        return {"messages": filtered_messages}
    else:
        logger.info(f"Returning all {len(latest_messages)} messages")
        return {"messages": latest_messages}

@app.get("/stats")
async def get_stats():
    """webhook alım istatistiklerini döndürür."""
    return {
        "stats": webhook_stats,
        "message_counts": {
            "total": len(latest_messages),
            "test": sum(1 for msg in latest_messages if msg.get("is_test", False)),
            "real": sum(1 for msg in latest_messages if not msg.get("is_test", False))
        }
    }

@app.get("/")
async def root():
    """basit bir karşılama mesajı ve temel talimatlar döndürür."""
    return {
        "message": "kick webhook hata ayıklama sunucusuna hoş geldiniz!",
        "endpoints": {
            "/kick-webhook": "(post) kick'ten webhook'ları alır",
            "/get-messages": "(get) alınan son mesajları gösterir",
            "/get-messages?test_only=true": "(get) yalnızca test mesajlarını gösterir",
            "/get-messages?real_only=true": "(get) yalnızca gerçek mesajları gösterir",
            "/stats": "(get) webhook istatistiklerini gösterir",
            "/clear-messages": "(post) depolanan tüm mesajları temizler",
            "/test-webhook": "(get/post) bu sunucuya bir test webhook'u göndermek için (manuel test için)"
        },
        "log_file": "webhook_debug.log"
    }

@app.post("/clear-messages")
async def clear_messages():
    """depolanan tüm mesajları temizler."""
    global latest_messages
    latest_messages = []
    logger.info("tüm depolanan mesajlar temizlendi.")
    return {"status": "success", "message": "mesajlar temizlendi"}

@app.get("/test-webhook")
async def test_webhook_endpoint(request: Request): # dış kapsamdaki test_webhook değişkeniyle çakışmayı önlemek için yeniden adlandırıldı
    """bu uç noktaya bir test webhook'u gönderir (manuel test)."""
    logger.info("manuel /test-webhook çağrısı alındı.")
    test_payload = {
        "event": "message_sent",
        "data": {
            "message_id": f"test_msg_{datetime.now().timestamp()}",
            "content": "bu manuel bir test mesajıdır.",
            "sender": {
                "username": "test_user",
                "id": "12345"
            },
            "channel": "test_channel",
            "timestamp": datetime.now().isoformat()
        },
        "kick_event_type": "ChatMessage", # bunu gerçekçi hale getir
        "is_test_manual": True # manuel testi belirtmek için bayrak
    }
    
    target_url = str(request.url.replace(path="/kick-webhook"))
    logger.info(f"/kick-webhook adresine test yükü gönderiliyor: {target_url}")
    
    # test yükünü /kick-webhook'a göndermek için httpx kullanın
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(target_url, json=test_payload)
            logger.info(f"test webhook gönderme yanıtı: {response.status_code} - {response.text}")
            return {"status": "test_sent", "target_response_status": response.status_code, "target_response_body": response.text}
        except httpx.RequestError as e:
            logger.error(f"test webhook gönderilirken hata: {e}")
            return {"status": "error", "message": f"test webhook gönderilemedi: {e}"}

# ana sunucuyu başlat
if __name__ == "__main__":
    logger.info("hata ayıklama webhook sunucusu başlatılıyor...")
    uvicorn.run(
        "webhook_debug_server:app", 
        host="0.0.0.0", 
        port=8001, 
        reload=True, 
        log_level="info" # uvicorn log level'ını da ayarla
    ) 