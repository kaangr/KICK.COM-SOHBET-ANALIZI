import requests

def test_webhook(webhook_url):
    """Basit bir test mesajı gönderir"""
    print(f"Webhook test ediliyor: {webhook_url}")
    
    # Kick formatında test verisi
    headers = {
        "Content-Type": "application/json",
        "Kick-Event-Type": "chat.message.sent",
        "Kick-Event-Version": "1"
    }
    
    # Test verisi
    test_data = {
        "message_id": "test_123",
        "broadcaster": {
            "username": "test_broadcaster"
        },
        "sender": {
            "username": "test_sender"
        },
        "content": "Bu bir test mesajıdır!"
    }
    
    try:
        response = requests.post(webhook_url, json=test_data, headers=headers)
        
        print(f"Durum Kodu: {response.status_code}")
        print(f"Yanıt: {response.text}")
        
        if response.status_code == 200:
            print("✅ Webhook başarıyla test edildi!")
            return True
        else:
            print("❌ Webhook testi başarısız oldu!")
            return False
            
    except Exception as e:
        print(f"❌ Hata: {e}")
        return False

def check_messages(base_url):
    """Webhook sunucusundaki mesajları kontrol eder"""
    get_url = base_url + "get-messages"
    print(f"Mesajlar kontrol ediliyor: {get_url}")
    
    try:
        response = requests.get(get_url)
        
        print(f"Durum Kodu: {response.status_code}")
        
        if response.status_code == 200:
            messages = response.json().get("messages", [])
            print(f"Bulunan mesaj sayısı: {len(messages)}")
            if messages:
                print("İlk birkaç mesaj:")
                for i, msg in enumerate(messages[:3]):
                    print(f"  {i+1}. {msg.get('username', 'Bilinmeyen')}: {msg.get('message', '')}")
            else:
                print("Henüz mesaj yok.")
            return True
        else:
            print("❌ Mesajlar alınamadı!")
            return False
            
    except Exception as e:
        print(f"❌ Hata: {e}")
        return False

if __name__ == "__main__":
    print("=== Basit Webhook Test Aracı ===")
    
    # ngrok URL'si al
    ngrok_url = input("ngrok URL'nizi girin (örn: https://xxxx.ngrok.io): ").strip()
    
    # Sonundaki slash'ı temizle
    if ngrok_url.endswith("/"):
        ngrok_url = ngrok_url[:-1]
    
    # Test edilecek URL'ler
    webhook_url = f"{ngrok_url}/kick-webhook"
    base_url = ngrok_url + "/"
    
    # İlk olarak mesajları kontrol et
    print("\n=== Mevcut Mesajları Kontrol Etme ===")
    check_messages(base_url)
    
    # Mesaj göndermeyi dene
    print("\n=== Webhook Test Mesajı Gönderme ===")
    if test_webhook(webhook_url):
        # Tekrar mesajları kontrol et
        print("\n=== Yeni Mesajları Kontrol Etme ===")
        check_messages(base_url) 