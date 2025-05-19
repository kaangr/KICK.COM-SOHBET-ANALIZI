from fastapi import FastAPI, Request
import uvicorn
import json

app = FastAPI()

@app.post("/{full_path:path}")
async def handle_any_post(full_path: str, request: Request):
    """Gelen tüm POST isteklerini yakalar ve loglar"""
    # Client IP ve tam URL yolu
    client_host = request.client.host if request.client else "unknown"
    
    print("\n=== GELEN POST İSTEĞİ ===")
    print(f"Zaman: {uvicorn.logging.logging.Formatter().formatTime(None, None)}")
    print(f"İstemci: {client_host}")
    print(f"Yol: /{full_path}")
    
    # Tüm başlıkları logla
    print("\n--- BAŞLIKLAR ---")
    for header_name, header_value in request.headers.items():
        print(f"{header_name}: {header_value}")
    
    # İstek gövdesini al
    try:
        body = await request.body()
        if body:
            print("\n--- İSTEK GÖVDESİ ---")
            try:
                # JSON olarak parse etmeyi dene
                json_body = json.loads(body)
                print(json.dumps(json_body, indent=2, ensure_ascii=False))
            except json.JSONDecodeError:
                # JSON değilse düz metin olarak göster
                print(f"(Raw) {body.decode('utf-8', errors='replace')}")
    except Exception as e:
        print(f"\nGövde okunurken hata: {e}")
    
    # Yanıt
    print("\n--- YANIT GÖNDERİLİYOR ---")
    return {"status": "success", "message": "Debug webhook received"}

@app.get("/{full_path:path}")
async def handle_any_get(full_path: str, request: Request):
    """Gelen tüm GET isteklerini yakalar ve loglar"""
    # Client IP ve tam URL yolu
    client_host = request.client.host if request.client else "unknown"
    
    print("\n=== GELEN GET İSTEĞİ ===")
    print(f"Zaman: {uvicorn.logging.logging.Formatter().formatTime(None, None)}")
    print(f"İstemci: {client_host}")
    print(f"Yol: /{full_path}")
    
    # Tüm başlıkları logla
    print("\n--- BAŞLIKLAR ---")
    for header_name, header_value in request.headers.items():
        print(f"{header_name}: {header_value}")
    
    # Query parametrelerini logla
    print("\n--- QUERY PARAMETRELERİ ---")
    for param_name, param_value in request.query_params.items():
        print(f"{param_name}: {param_value}")
    
    # Yanıt
    return {"status": "success", "message": "Debug endpoint", "path": full_path}

if __name__ == "__main__":
    print("=== DEBUG WEBHOOK SUNUCUSU ===")
    print("Tüm gelen istekleri loglamak için başlatılıyor...")
    print("NORMAL webhook_server.py KULLANMIYORSUNUZ!")
    print("Bu debug aracı sadece sorun giderme içindir.")
    print("Tüm yollar ve istekler kabul edilecek.")
    print("==========================================")
    
    uvicorn.run("debug_webhook_server:app", host="0.0.0.0", port=8000, reload=True) 