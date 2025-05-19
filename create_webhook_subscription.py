import requests
import json
import time
import random

# kick api endpointleri
TOKEN_URL_1 = "https://id.kick.com/oauth/token"  # i̇lk denenecek endpoint
TOKEN_URL_2 = "https://kick.com/api/v1/oauth2/token"  # alternatif endpoint
SUBSCRIPTIONS_URL = "https://kick.com/api/v1/events/subscriptions"

# browser benzeri http headers
BROWSER_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9,tr;q=0.8',
    'Origin': 'https://kick.com',
    'Referer': 'https://kick.com/dashboard/developer',
    'sec-ch-ua': '"Google Chrome";v="123", "Not:A-Brand";v="8"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-site'
}

def get_app_access_token(client_id, client_secret, use_alternative=False):
    """app access token almak için oauth isteği yapar"""
    # hangi endpoint'in kullanılacağını belirle
    token_url = TOKEN_URL_2 if use_alternative else TOKEN_URL_1
    
    data = {
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret
    }
    
    # content-type headeri ve browser benzeri headerleri birleştir
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        **BROWSER_HEADERS
    }
    
    try:
        print(f"\ntoken i̇steği gönderiliyor: {token_url}")
        print(f"başlıklar: {headers}")
        print(f"veri: {data}")
        
        # rastgele kısa bir gecikme ekle (bot tespitini azaltmak için)
        time.sleep(random.uniform(1.0, 2.0))
        
        response = requests.post(token_url, data=data, headers=headers, timeout=30)
        
        # ham yanıtı yazdır
        print(f"\ndurum kodu: {response.status_code}")
        print(f"yanıt başlıkları: {dict(response.headers)}")
        
        # ham i̇çeriği yazdır
        raw_content = response.content.decode('utf-8', errors='replace')
        print(f"ham yanıt i̇çeriği: {raw_content}")
        
        # json olarak parse etmeyi dene
        try:
            response_data = response.json()
            print(f"ayrıştırılmış json yanıtı: {response_data}")
            
            if response.status_code != 200:
                print(f"token alınamadı. hata: {response_data}")
                
                # eğer i̇lk endpoint başarısız olursa ve henüz alternatifi denemediyse
                if not use_alternative:
                    print(f"\ni̇lk endpoint başarısız oldu, alternatif endpoint deneniyor: {TOKEN_URL_2}")
                    return get_app_access_token(client_id, client_secret, use_alternative=True)
                return None
            
            access_token = response_data.get('access_token')
            if access_token:
                print(f"access token alındı: {access_token[:10]}...{access_token[-10:]} (güvenlik için kısaltıldı)")
                return access_token
            else:
                print("access token anahtarı yanıtta bulunamadı.")
                
                # eğer i̇lk endpoint başarısız olursa ve henüz alternatifi denemediyse
                if not use_alternative:
                    print(f"\ni̇lk endpoint başarısız oldu, alternatif endpoint deneniyor: {TOKEN_URL_2}")
                    return get_app_access_token(client_id, client_secret, use_alternative=True)
                return None
                
        except json.JSONDecodeError as json_err:
            print(f"json parse hatası: {json_err}")
            print("yanıt json formatında değil.")
            
            # eğer i̇lk endpoint başarısız olursa ve henüz alternatifi denemediyse
            if not use_alternative:
                print(f"\ni̇lk endpoint başarısız oldu, alternatif endpoint deneniyor: {TOKEN_URL_2}")
                return get_app_access_token(client_id, client_secret, use_alternative=True)
            return None
    
    except Exception as e:
        print(f"token alınırken hata oluştu: {e}")
        
        # eğer i̇lk endpoint başarısız olursa ve henüz alternatifi denemediyse
        if not use_alternative:
            print(f"\ni̇lk endpoint başarısız oldu, alternatif endpoint deneniyor: {TOKEN_URL_2}")
            return get_app_access_token(client_id, client_secret, use_alternative=True)
        return None

def create_webhook_subscription(access_token, client_id, webhook_url, event_type="chat.message.sent"):
    """api kullanarak webhook aboneliği oluşturur"""
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Client-Id': client_id,
        'Content-Type': 'application/json',
        **BROWSER_HEADERS
    }
    
    data = {
        'webhook_url': webhook_url,
        'event_type': event_type
    }
    
    try:
        print(f"webhook aboneliği oluşturuluyor: {webhook_url} için {event_type} olayı")
        print(f"başlıklar: {headers}")
        print(f"veri: {data}")
        print(f"url: {SUBSCRIPTIONS_URL}")
        
        # rastgele kısa bir gecikme ekle
        time.sleep(random.uniform(1.0, 2.0))
        
        response = requests.post(SUBSCRIPTIONS_URL, json=data, headers=headers, timeout=30)
        
        # ham yanıtı yazdır
        print(f"durum kodu: {response.status_code}")
        print(f"yanıt başlıkları: {dict(response.headers)}")
        
        try:
            response_data = response.json()
            print(f"abonelik yanıtı: {json.dumps(response_data, indent=2)}")
            
            if response.status_code == 200 or response.status_code == 201:
                print("webhook aboneliği başarıyla oluşturuldu!")
                return True
            else:
                print(f"webhook aboneliği oluşturulamadı. hata: {response_data}")
                return False
                
        except json.JSONDecodeError:
            print(f"json parse hatası. ham yanıt: {response.content.decode('utf-8', errors='replace')}")
            return False
    
    except Exception as e:
        print(f"webhook aboneliği oluşturulurken hata oluştu: {e}")
        return False

def list_webhook_subscriptions(access_token, client_id):
    """mevcut webhook aboneliklerini listeler"""
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Client-Id': client_id,
        **BROWSER_HEADERS
    }
    
    try:
        print(f"abonelik listesi alınıyor...")
        print(f"başlıklar: {headers}")
        print(f"url: {SUBSCRIPTIONS_URL}")
        
        # rastgele kısa bir gecikme ekle
        time.sleep(random.uniform(1.0, 2.0))
        
        response = requests.get(SUBSCRIPTIONS_URL, headers=headers, timeout=30)
        
        # ham yanıtı yazdır
        print(f"durum kodu: {response.status_code}")
        print(f"yanıt başlıkları: {dict(response.headers)}")
        
        try:
            response_data = response.json()
            print(f"mevcut abonelikler: {json.dumps(response_data, indent=2)}")
            return response_data
            
        except json.JSONDecodeError:
            print(f"json parse hatası. ham yanıt: {response.content.decode('utf-8', errors='replace')}")
            return None
    
    except Exception as e:
        print(f"abonelikler listelenirken hata oluştu: {e}")
        return None

if __name__ == "__main__":
    print("kick webhook aboneliği oluşturma aracı")
    print("=====================================")
    
    # kullanıcıdan bilgileri al
    client_id = input("client id'nizi girin: ")
    client_secret = input("client secret'ınızı girin: ")
    
    # token al
    access_token = get_app_access_token(client_id, client_secret)
    
    if access_token:
        webhook_url = input("webhook url'nizi girin (örn: https://xxxx.ngrok.io/kick-webhook): ")
        
        # mevcut abonelikleri listele
        list_webhook_subscriptions(access_token, client_id)
        
        # abonelik oluştur
        if create_webhook_subscription(access_token, client_id, webhook_url):
            print("\ni̇şlem tamamlandı!")
        else:
            print("\ni̇şlem başarısız oldu.")
    else:
        print("access token alınamadı, i̇şlem durduruldu.") 