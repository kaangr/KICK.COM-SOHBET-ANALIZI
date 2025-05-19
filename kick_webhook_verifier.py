#!/usr/bin/env python
import requests
import json
import time
import sys
import os
from datetime import datetime

"""
kick webhook doğrulama aracı
----------------------------
bu araç, kick webhook ayarlarınızı doğrulamanıza yardımcı olur.
webhook sunucunuzu test etmek ve kick'in webhook gönderimi için doğru yapılandırılıp
yapılandırılmadığını kontrol etmek için kullanabilirsiniz.
"""

# renkli çıktı için
class Colors:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    ENDC = "\033[0m"

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.BLUE}=== {text} ==={Colors.ENDC}")

def print_success(text):
    print(f"{Colors.GREEN}✓ {text}{Colors.ENDC}")

def print_warning(text):
    print(f"{Colors.YELLOW}⚠ {text}{Colors.ENDC}")

def print_error(text):
    print(f"{Colors.RED}✗ {text}{Colors.ENDC}")

def print_info(text):
    print(f"{Colors.BLUE}ℹ {text}{Colors.ENDC}")

def test_connectivity(base_url):
    """webhook sunucusuna bağlantıyı test eder"""
    print_header("webhook sunucusu bağlantı testi")
    
    try:
        print_info(f"bağlanılıyor: {base_url}")
        response = requests.get(base_url, timeout=10)
        
        if response.status_code == 200:
            print_success(f"sunucu yanıt veriyor. durum kodu: {response.status_code}")
            try:
                # basit bir json parse etme denemesi
                data = response.json()
                status = data.get("status")
                if status == "ok":
                    print_success("sunucu doğru formatta yanıt veriyor.")
                else:
                    print_warning(f"sunucu yanıt verdi, ancak beklenen formatın dışında: {status}")
                
                # endpoint'leri göster
                endpoints = data.get("endpoints", {})
                if endpoints:
                    print_info("kullanılabilir endpoint'ler:")
                    for endpoint, desc in endpoints.items():
                        print(f"  • {endpoint}: {desc}")
            except json.JSONDecodeError:
                print_warning("sunucu yanıt verdi, ancak yanıt json formatında değil.")
                print(f"  yanıt: {response.text[:100]}...")
            
            return True
        else:
            print_error(f"sunucu erişilebilir ancak hata döndürüyor. durum kodu: {response.status_code}")
            print(f"  yanıt: {response.text[:100]}...")
            return False
    
    except requests.exceptions.ConnectionError:
        print_error(f"sunucuya bağlanılamadı: {base_url}")
        print("  webhook sunucunuz çalışıyor mu?")
        print("  url doğru mu?")
        return False
    
    except Exception as e:
        print_error(f"bağlantı hatası: {e}")
        return False

def check_ngrok_url(base_url):
    """url'in ngrok url'i olup olmadığını kontrol eder"""
    print_header("ngrok url doğrulaması")
    
    if "ngrok" in base_url:
        print_success("ngrok url'i tespit edildi.")
        if "https" in base_url:
            print_success("https protokolü kullanılıyor.")
        else:
            print_warning("http protokolü kullanılıyor. kick https gerektirebilir.")
        return True
    else:
        print_warning("url, ngrok url'i değil gibi görünüyor.")
        print_info("kick, geliştirme aşamasında ngrok gibi bir tünel hizmeti gerektirir.")
        if "localhost" in base_url or "127.0.0.1" in base_url:
            print_error("localhost url'i kullanıyorsunuz! kick localhost'a erişemez.")
            print("  ngrok veya benzer bir tünel hizmeti kullanmalısınız.")
        return False

def send_test_webhook(webhook_url):
    """test webhook'u gönderir"""
    print_header("test webhook'u gönderme")
    
    headers = {
        "Content-Type": "application/json",
        "Kick-Event-Type": "chat.message.sent",
        "Kick-Event-Version": "1",
        "User-Agent": "Kick-Webhook-Verifier-Tool"
    }
    
    test_message = f"test mesajı {datetime.now().isoformat()}"
    
    test_data = {
        "message_id": f"verify_test_{datetime.now().timestamp()}",
        "broadcaster": {
            "username": "verifier_broadcaster"
        },
        "sender": {
            "username": "webhook_verifier"
        },
        "content": test_message
    }
    
    try:
        print_info(f"webhook url'ine post gönderiliyor: {webhook_url}")
        print_info(f"test mesajı: '{test_message}'")
        
        response = requests.post(webhook_url, json=test_data, headers=headers, timeout=10)
        
        if response.status_code == 200:
            print_success(f"webhook başarıyla alındı. durum kodu: {response.status_code}")
            try:
                data = response.json()
                print_info(f"yanıt: {json.dumps(data, indent=2)}")
            except:
                print_info(f"yanıt: {response.text}")
            return test_message
        else:
            print_error(f"webhook alınamadı. durum kodu: {response.status_code}")
            print(f"  yanıt: {response.text}")
            return None
    
    except Exception as e:
        print_error(f"test webhook'u gönderilirken hata: {e}")
        return None

def verify_message_received(base_url, test_message, max_attempts=3):
    """test mesajının alınıp alınmadığını doğrular"""
    print_header("mesaj alındı mı?")
    
    messages_url = f"{base_url.rstrip('/')}/get-messages"
    
    print_info(f"mesajlar sorgulanıyor: {messages_url}")
    print_info(f"test mesajı: '{test_message}'")
    print_info("mesaj alınmış mı kontrol ediliyor...")
    
    for attempt in range(max_attempts):
        try:
            response = requests.get(messages_url, timeout=10)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    messages = data.get("messages", [])
                    
                    if not messages:
                        print_warning("mesaj listesi boş.")
                        if attempt < max_attempts - 1:
                            print_info(f"{attempt+1}. deneme başarısız. tekrar deneniyor...")
                            time.sleep(2)
                            continue
                        else:
                            print_error("webhook çalışıyor, ancak mesajlar kaydedilmiyor görünüyor.")
                            return False
                    
                    # test mesajını ara
                    for msg in messages:
                        if msg.get("message") == test_message:
                            print_success("test mesajı başarıyla alındı ve kaydedildi!")
                            return True
                    
                    print_warning("mesajlar var, ancak gönderilen test mesajı bulunamadı.")
                    if attempt < max_attempts - 1:
                        print_info(f"{attempt+1}. deneme başarısız. tekrar deneniyor...")
                        time.sleep(2)
                        continue
                    else:
                        print_error("webhook sunucusu mesajları alıyor, ancak test mesajını işleyemedi.")
                        return False
                
                except json.JSONDecodeError:
                    print_error("mesajlar json formatında değil.")
                    return False
            
            else:
                print_error(f"mesajlar alınamadı. durum kodu: {response.status_code}")
                return False
        
        except Exception as e:
            print_error(f"mesajlar sorgulanırken hata: {e}")
            return False
    
    return False

def get_real_messages(base_url):
    """gerçek mesajları alır ve görüntüler"""
    print_header("gerçek mesajları al")
    real_messages_url = f"{base_url.rstrip('/')}/get-messages?real_only=true"
    
    try:
        print_info(f"gerçek kick mesajları sorgulanıyor: {real_messages_url}")
        response = requests.get(real_messages_url, timeout=10)
        
        if response.status_code == 200:
            try:
                data = response.json()
                messages = data.get("messages", [])
                
                if not messages:
                    print_info("alınan gerçek mesaj yok.")
                    print_info("kick'te sohbet etmeyi deneyin veya canlı bir kanaldan test edin.")
                    return
                
                print_success(f"{len(messages)} gerçek mesaj alındı:")
                for i, msg in enumerate(messages):
                    # daha kısa mesaj kimliği
                    msg_id_short = msg.get("id", "N/A")[-6:]
                    print(f"  [{i+1}] ID: ..{msg_id_short} | Zaman: {msg.get('timestamp')} | Kullanıcı: {msg.get('username')} | Mesaj: {msg.get('message')}")
            except json.JSONDecodeError:
                print_error("mesaj yanıtı json formatında değil.")
        else:
            print_error(f"gerçek mesajlar alınamadı. durum kodu: {response.status_code}")
            print(f"  yanıt: {response.text}")
    
    except Exception as e:
        print_error(f"gerçek mesajlar alınırken hata: {e}")

def check_kick_developer_settings():
    """kick geliştirici paneli ayarlarını kontrol etmeye yönelik bir hatırlatıcı"""
    print_header("kick geliştirici paneli ayarları")
    print_info("lütfen kick geliştirici panelinizde aşağıdakileri doğrulayın:")
    print("  1. Webhook URL'niz doğru ve aktif ngrok URL'nizle eşleşiyor.")
    print("  2. 'chat.message.sent' etkinliğine abone oldunuz.")
    print("  3. Uygulamanız etkinleştirildi.")
    print("  4. Gizli anahtarınız doğru şekilde ayarlandı (eğer kullanılıyorsa - bu araç şu anda gizli anahtar doğrulamasını yapmıyor).")
    print_info("bu araç, bu ayarları otomatik olarak kontrol edemez.")

def manual_test_with_curl(webhook_url):
    """curl kullanarak manuel test için bir komut oluşturur"""
    print_header("curl ile manuel test")
    curl_command = f"""\
curl -X POST {webhook_url} \
-H "Content-Type: application/json" \
-H "Kick-Event-Type: chat.message.sent" \
-H "Kick-Event-Version: 1" \
-d '{{
  "message_id": "curl_test_123",
  "broadcaster": {{ "username": "test_broadcaster" }},
  "sender": {{ "username": "curl_user" }},
  "content": "bu curl'den bir test mesajıdır"
}}'"""
    print_info("webhook sunucunuzu manuel olarak test etmek için aşağıdaki curl komutunu kullanabilirsiniz:")
    print(f"{Colors.YELLOW}{curl_command}{Colors.ENDC}")

def run_full_verification(base_url):
    """tüm doğrulama adımlarını çalıştırır"""
    print_header("kick webhook tam doğrulaması")
    
    # webhook url'i oluştur
    webhook_url = base_url.rstrip('/') + "/kick-webhook"
    print_info(f"webhook url'si olarak kullanılacak: {webhook_url}")
    
    # 1. ngrok url'sini kontrol et
    ngrok_check_passed = check_ngrok_url(base_url)
    if not ngrok_check_passed:
        print_warning("ngrok url kontrolü başarısız oldu. bazı testler atlanabilir.")
    
    # 2. sunucu bağlantısını test et
    connectivity_passed = test_connectivity(base_url)
    if not connectivity_passed:
        print_error("sunucu bağlantı testi başarısız oldu. doğrulama durduruldu.")
        return

    # 3. test webhook'u gönder
    test_message_content = send_test_webhook(webhook_url)
    if not test_message_content:
        print_error("test webhook gönderme başarısız oldu. doğrulama durduruldu.")
        return
    
    # 4. mesajın alınıp alınmadığını doğrula (biraz gecikme ile)
    time.sleep(3) # kick'in webhook göndermesi ve sunucunun işlemesi için zaman tanıyın
    message_verified = verify_message_received(base_url, test_message_content)
    
    print_header("doğrulama özeti")
    if ngrok_check_passed:
        print_success("ngrok url kontrolü: başarılı")
    else:
        print_warning("ngrok url kontrolü: başarısız/uyarılar")
        
    if connectivity_passed:
        print_success("sunucu bağlantısı: başarılı")
    else:
        print_error("sunucu bağlantısı: başarısız")
        
    if test_message_content:
        print_success("test webhook gönderme: başarılı")
    else:
        print_error("test webhook gönderme: başarısız")
        
    if message_verified:
        print_success("mesaj alımı doğrulama: başarılı")
    else:
        print_error("mesaj alımı doğrulama: başarısız")
        print_info("sunucunuz mesajları işlemiyor veya kaydetmiyor olabilir.")

    # 5. kick geliştirici ayarlarını kontrol etmeye yönelik hatırlatıcı
    check_kick_developer_settings()

    # 6. gerçek mesajları almaya çalış
    if message_verified: # yalnızca temel doğrulama başarılıysa deneyin
        get_real_messages(base_url)
    else:
        print_warning("temel doğrulama başarısız olduğu için gerçek mesajlar alınmıyor.")

    # 7. curl ile manuel test için komut
    manual_test_with_curl(webhook_url)

    print_header("doğrulama tamamlandı")
    if all([connectivity_passed, test_message_content, message_verified]):
        print_success("webhook kurulumunuz çalışıyor gibi görünüyor!")
    else:
        print_error("webhook kurulumunuzda sorunlar var. lütfen yukarıdaki hataları kontrol edin.")

def get_valid_url_input():
    """kullanıcıdan geçerli bir url alır."""
    while True:
        url = input(f"{Colors.BOLD}webhook sunucunuzun temel url'sini girin (örn: http://localhost:8000 veya https://xxxx.ngrok.io): {Colors.ENDC}").strip()
        if not url:
            print_warning("url boş olamaz. lütfen geçerli bir url girin.")
            continue
        if not url.startswith(("http://", "https://")):
            # kullanıcı http veya https eklemediyse, varsayılan olarak http eklemeyi dene
            # veya kullanıcıya sormayı düşün
            print_warning("url 'http://' veya 'https://' ile başlamalıdır. 'http://' varsayılıyor.")
            fixed_url = "http://" + url
            # kullanıcıya düzeltilmiş url'yi kabul edip etmediğini sor
            confirm = input(f"'{fixed_url}' mi demek istediniz? (e/h): ").lower()
            if confirm == 'e' or confirm == 'evet':
                url = fixed_url
            else:
                print_info("lütfen tam url'yi tekrar girin.")
                continue # kullanıcıdan tekrar girmesini iste
        return url

if __name__ == "__main__":
    # komut satırı argümanlarını kontrol et
    if len(sys.argv) > 1:
        base_url_arg = sys.argv[1]
        print_info(f"komut satırı argümanından url kullanılıyor: {base_url_arg}")
    else:
        base_url_arg = get_valid_url_input()

    run_full_verification(base_url_arg)

    # python betiğinin hemen kapanmasını önlemek için
    # input("çıkmak için enter tuşuna basın...") 