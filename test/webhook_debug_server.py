from fastapi import FastAPI, Request, Header, HTTPException
import uvicorn
import json
import logging
import traceback
from datetime import datetime
import requests

# Loglama yapılandırması
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("webhook_debug.log")  # Dosyaya da kaydet
    ]
)
logger = logging.getLogger("webhook_server")

app = FastAPI()

# Mesaj depolama
latest_messages = []
MAX_MESSAGES = 50

# Webhook alımı istatistikleri
webhook_stats = {
    "total_requests": 0,
    "kick_events": 0,
    "test_events": 0,
    "unknown_events": 0,
    "last_request_time": None
}

# Middleware - Tüm istekleri loglar
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests"""
    logger.info(f"Request: {request.method} {request.url.path}")
    # Headers'ı logla
    headers = dict(request.headers.items())
    logger.info(f"Headers: {json.dumps(headers, indent=2)}")
    
    # İstek gövdesini logla (kopyalayarak)
    body = await request.body()
    if body:
        try:
            # JSON olarak parse etmeyi dene
            decoded_body = json.loads(body)
            logger.info(f"Body: {json.dumps(decoded_body, indent=2)}")
        except:
            # JSON değilse binary olarak göster
            logger.info(f"Body (raw): {body}")
    
    # Orijinal istek nesnesini yeniden oluştur
    request._body = body
    
    # Asıl handler'ı çağır
    try:
        response = await call_next(request)
        logger.info(f"Response status: {response.status_code}")
        return response
    except Exception as e:
        logger.error(f"Error handling request: {e}")
        logger.error(traceback.format_exc())
        raise

@app.post("/kick-webhook")
async def handle_kick_webhook(request: Request):
    """Handles incoming webhook requests from Kick."""
    logger.info("Webhook received")
    
    # İstatistikleri güncelle
    webhook_stats["total_requests"] += 1
    webhook_stats["last_request_time"] = datetime.now().isoformat()
    
    try:
        # Kick-Event-Type ve Version'ı manuel olarak headers'dan al
        kick_event_type = request.headers.get("Kick-Event-Type")
        kick_event_version = request.headers.get("Kick-Event-Version")
        user_agent = request.headers.get("User-Agent", "")
        logger.info(f"Kick event: type={kick_event_type}, version={kick_event_version}, UA={user_agent}")
        
        # İstek gövdesini parse et
        try:
            payload = await request.json()
        except json.JSONDecodeError:
            # İsteğin JSON olmaması durumunu ele al
            raw_body = await request.body()
            logger.warning(f"Invalid JSON received: {raw_body}")
            # Basit bir string ise ve "content=" gibi bir form içeriyorsa, basit parse et
            try:
                payload = dict(item.split("=") for item in raw_body.decode().split("&"))
                logger.info(f"Parsed form data: {payload}")
            except:
                logger.error("Could not parse request body")
                return {"status": "error", "message": "Invalid payload format"}
        
        logger.info(f"Received webhook payload: {json.dumps(payload, indent=2)}")
        
        # Kick event mi yoksa test event mi olduğunu belirle
        is_test = False
        if isinstance(payload, dict):
            # Test mesajını tanımak için bazı ipuçları
            test_indicators = ["test", "test_", "test123", "test_sender", "test_message"]
            for key, value in payload.items():
                if isinstance(value, str) and any(indicator in value.lower() for indicator in test_indicators):
                    is_test = True
                    break
                elif isinstance(value, dict):
                    for subkey, subvalue in value.items():
                        if isinstance(subvalue, str) and any(indicator in subvalue.lower() for indicator in test_indicators):
                            is_test = True
                            break
        
        if is_test:
            webhook_stats["test_events"] += 1
            logger.info("Detected TEST webhook event")
        elif kick_event_type:
            webhook_stats["kick_events"] += 1
            logger.info(f"Detected KICK webhook event: {kick_event_type}")
        else:
            webhook_stats["unknown_events"] += 1
            logger.warning("Unknown webhook event type")
        
        # Mesaj içeriğini ve göndereni farklı formatları ele alarak çıkarmaya çalış
        message_content = None
        sender_username = None
        message_id = None
        
        # Kick formatını kontrol et
        if isinstance(payload, dict):
            # Standard Kick format
            message_content = payload.get('content')
            message_id = payload.get('message_id', f"msg_{datetime.now().timestamp()}")
            
            # Sender bilgisini farklı formatlarda aramaya çalış
            sender_info = payload.get('sender', {})
            if isinstance(sender_info, dict):
                sender_username = sender_info.get('username')
            
            # Alternatif formatları kontrol et
            if not message_content:
                message_content = payload.get('message', payload.get('text', payload.get('msg')))
            
            if not sender_username:
                sender_username = payload.get('username', payload.get('user', payload.get('sender')))
                
                # Hala bulunamadıysa, diğer olası fieldlarda deneyelim
                if not sender_username and 'broadcaster' in payload:
                    broadcaster = payload.get('broadcaster', {})
                    if isinstance(broadcaster, dict):
                        sender_username = broadcaster.get('username')
        
        # Mesajı işle
        if message_content and sender_username:
            logger.info(f"Extracted message - From: {sender_username}, Content: {message_content}")
            
            # Mesajı sakla
            message_data = {
                "id": message_id,
                "username": sender_username,
                "message": message_content,
                "timestamp": datetime.now().isoformat(),
                "sentiment": "N/A",  # NLP entegrasyonu daha sonra yapılacak
                "is_test": is_test
            }
            latest_messages.append(message_data)
            if len(latest_messages) > MAX_MESSAGES:
                latest_messages.pop(0)
                
            logger.info(f"Added message to storage. Total messages: {len(latest_messages)}")
            return {"status": "success", "message": "Message processed"}
            
        else:
            # İçerik veya gönderen bulanamazsa ham veriyi logla
            logger.warning("Could not extract message content or sender")
            logger.warning(f"Raw payload: {json.dumps(payload, indent=2)}")
            return {"status": "warning", "message": "Could not extract message data"}
            
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        logger.error(traceback.format_exc())
        return {"status": "error", "message": str(e)}

@app.get("/get-messages")
async def get_latest_messages(test_only: bool = False, real_only: bool = False):
    """Returns the list of most recent messages received via webhook."""
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
    """Returns webhook statistics."""
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
    """Root endpoint - for health checks and documentation."""
    return {
        "status": "ok",
        "message": "Kick Webhook Debug Server is running",
        "endpoints": {
            "/kick-webhook": "POST - For receiving Kick webhooks",
            "/get-messages": "GET - Retrieve stored messages",
            "/get-messages?test_only=true": "GET - Retrieve only test messages",
            "/get-messages?real_only=true": "GET - Retrieve only real Kick messages",
            "/stats": "GET - View webhook statistics",
            "/clear-messages": "POST - Clear message history",
            "/test-webhook": "GET - Send a test webhook to yourself",
        }
    }

@app.post("/clear-messages")
async def clear_messages():
    """Clears the message history."""
    global latest_messages
    msg_count = len(latest_messages)
    latest_messages = []
    logger.info(f"Cleared {msg_count} messages")
    return {"status": "success", "message": f"Cleared {msg_count} messages"}

@app.get("/test-webhook")
async def test_webhook(request: Request):
    """Sends a test webhook to itself."""
    # Kendi URL'ini belirle
    base_url = str(request.base_url).rstrip('/')
    webhook_url = f"{base_url}/kick-webhook"
    
    logger.info(f"Self-testing webhook at {webhook_url}")
    
    # Test mesajı
    headers = {
        "Content-Type": "application/json",
        "Kick-Event-Type": "chat.message.sent",
        "Kick-Event-Version": "1",
        "User-Agent": "Debug-Self-Test"
    }
    
    # Kick formatında test verisi
    test_data = {
        "message_id": f"self_test_{datetime.now().timestamp()}",
        "broadcaster": {
            "username": "debug_broadcaster"
        },
        "sender": {
            "username": "debug_self_test"
        },
        "content": f"Self-test message from debug server at {datetime.now().isoformat()}"
    }
    
    try:
        # Kendi webhook endpoint'ine POST yap
        response = requests.post(webhook_url, json=test_data, headers=headers)
        
        if response.status_code == 200:
            logger.info(f"Self-test successful: {response.status_code}")
            return {
                "status": "success", 
                "message": "Self-test webhook sent successfully",
                "details": {
                    "status_code": response.status_code,
                    "response": response.text
                }
            }
        else:
            logger.error(f"Self-test failed: {response.status_code} {response.text}")
            return {
                "status": "error",
                "message": "Self-test webhook failed",
                "details": {
                    "status_code": response.status_code,
                    "response": response.text
                }
            }
    
    except Exception as e:
        logger.error(f"Self-test error: {e}")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    logger.info("Starting ENHANCED DEBUG Webhook Server on port 8000...")
    logger.info("This version includes improved diagnostics for Kick webhooks")
    logger.info("Logs are saved to webhook_debug.log")
    
    # Run on 0.0.0.0 to be accessible within the local network and for ngrok
    uvicorn.run("webhook_debug_server:app", host="0.0.0.0", port=8000, reload=True) 