import requests
import json

# Webhook test için sahte mesaj gönderme
def test_webhook(webhook_url):
    # Kick webhook formatında test verisi oluştur
    headers = {
        "Content-Type": "application/json",
        "Kick-Event-Type": "chat.message.sent",
        "Kick-Event-Version": "1"
    }
    
    # Örnek bir chat.message.sent olayı
    payload = {
        "message_id": "test_message_123",
        "broadcaster": {
            "is_anonymous": False,
            "user_id": 123456789,
            "username": "test_broadcaster",
            "is_verified": True,
            "profile_picture": "https://example.com/avatar.jpg",
            "channel_slug": "test_channel",
            "identity": None
        },
        "sender": {
            "is_anonymous": False,
            "user_id": 987654321,
            "username": "test_sender",
            "is_verified": False,
            "profile_picture": "https://example.com/avatar.jpg",
            "channel_slug": "test_sender_channel",
            "identity": {
                "username_color": "#FF5733",
                "badges": []
            }
        },
        "content": "Bu bir test mesajıdır!",
        "emotes": []
    }
    
    try:
        # POST isteği gönder
        response = requests.post(webhook_url, headers=headers, json=payload)
        
        # Yanıtı yazdır
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    # Ngrok URL'nizi buraya yapıştırın - "/kick-webhook" eklenmiş olmalı
    webhook_url = input("Webhook URL'nizi girin (örn: https://xxxx.ngrok.io/kick-webhook): ")
    
    print(f"Webhook test ediliyor: {webhook_url}")
    result = test_webhook(webhook_url)
    
    if result:
        print("Test başarılı! Webhook sunucusu çalışıyor.")
    else:
        print("Test başarısız. Webhook sunucusu yanıt vermiyor veya hata döndürdü.")
    
    # Ayrıca mesajları kontrol et
    check_messages = input("Mesajları kontrol etmek istiyor musunuz? (e/h): ")
    if check_messages.lower() == "e":
        # Webhook sunucusundan alınan mesajları kontrol et
        get_url = webhook_url.replace("/kick-webhook", "/get-messages")
        try:
            response = requests.get(get_url)
            print(f"Status Code: {response.status_code}")
            print(f"Messages: {json.dumps(response.json(), indent=2)}")
        except Exception as e:
            print(f"Error checking messages: {e}") 