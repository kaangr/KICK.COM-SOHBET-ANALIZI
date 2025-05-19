#!/usr/bin/env python
import requests
import json
import time
import sys
from datetime import datetime, timedelta

def check_for_messages(base_url, interval=10, max_duration=300):
    """
    belirli bir süre boyunca webhook sunucusunu kontrol eder ve
    yeni mesajları gösterir.
    
    args:
        base_url: webhook sunucusunun url'i
        interval: kontrol aralığı (saniye)
        max_duration: maksimum süre (saniye)
    """
    # base url'i temizle
    if not base_url.startswith(("http://", "https://")):
        base_url = "https://" + base_url
    
    base_url = base_url.rstrip("/")
    messages_url = f"{base_url}/get-messages"
    stats_url = f"{base_url}/stats"
    
    print(f"webhook sunucusu: {base_url}")
    print(f"{interval} saniye aralıklarla {max_duration} saniye boyunca mesajlar kontrol edilecek.")
    print("ctrl+c ile istediğiniz zaman çıkabilirsiniz.")
    print("-" * 60)
    
    # başlangıç zamanı
    start_time = datetime.now()
    end_time = start_time + timedelta(seconds=max_duration)
    
    # son görülen mesaj id'lerini saklayacak set
    seen_message_ids = set()
    
    # i̇statistikler
    stats = {
        "total_checks": 0,
        "new_messages": 0,
        "real_messages": 0,
        "test_messages": 0,
        "kick_events": 0
    }
    
    # i̇lk çalıştırmada mevcut mesajları al
    try:
        response = requests.get(messages_url, timeout=10)
        if response.status_code == 200:
            messages = response.json().get("messages", [])
            for msg in messages:
                seen_message_ids.add(msg.get("id", ""))
            
            print(f"mevcut mesaj sayısı: {len(messages)}")
        else:
            print(f"hata: mesajlar alınamadı. durum kodu: {response.status_code}")
            return
    except Exception as e:
        print(f"hata: {e}")
        return
    
    # ana döngü
    while datetime.now() < end_time:
        stats["total_checks"] += 1
        
        try:
            # mesajları kontrol et
            response = requests.get(messages_url, timeout=10)
            if response.status_code == 200:
                messages = response.json().get("messages", [])
                
                # yeni mesajları bul
                new_messages = []
                for msg in messages:
                    msg_id = msg.get("id", "")
                    if msg_id and msg_id not in seen_message_ids:
                        new_messages.append(msg)
                        seen_message_ids.add(msg_id)
                
                # yeni mesaj varsa göster
                if new_messages:
                    stats["new_messages"] += len(new_messages)
                    print(f"\n[{datetime.now().strftime('%h:%m:%s')}] {len(new_messages)} yeni mesaj bulundu!")
                    
                    for i, msg in enumerate(new_messages, 1):
                        username = msg.get("username", "bilinmeyen")
                        message = msg.get("message", "")
                        timestamp = msg.get("timestamp", "")
                        is_test = msg.get("is_test", False)
                        
                        if is_test:
                            stats["test_messages"] += 1
                            print(f"  {i}. [test] {username}: {message}")
                        else:
                            stats["real_messages"] += 1
                            print(f"  {i}. [gerçek] {username}: {message}")
            
            # i̇statistikleri kontrol et
            try:
                stats_response = requests.get(stats_url, timeout=5)
                if stats_response.status_code == 200:
                    stats_data = stats_response.json()
                    kick_events = stats_data.get("stats", {}).get("kick_events", 0)
                    
                    # kick events sayısı değiştiyse bildir
                    if kick_events > stats["kick_events"]:
                        print(f"\n[{datetime.now().strftime('%h:%m:%s')}] yeni kick olayı algılandı!")
                        print(f"  toplam kick olayları: {kick_events}")
                        stats["kick_events"] = kick_events
            except:
                pass
            
            # kalan süreyi göster
            remaining = end_time - datetime.now()
            mins, secs = divmod(remaining.seconds, 60)
            sys.stdout.write(f"\rsonraki kontrol: {interval} saniye içinde... (kalan süre: {mins:02d}:{secs:02d})")
            sys.stdout.flush()
            
            # bekle
            time.sleep(interval)
            
        except KeyboardInterrupt:
            print("\n\ni̇şlem kullanıcı tarafından durduruldu.")
            break
        except Exception as e:
            print(f"\nhata: {e}")
            time.sleep(interval)
    
    # özet
    print("\n" + "=" * 60)
    print("i̇zleme tamamlandı!")
    print(f"toplam kontrol: {stats['total_checks']}")
    print(f"algılanan yeni mesajlar: {stats['new_messages']}")
    print(f"  • gerçek mesajlar: {stats['real_messages']}")
    print(f"  • test mesajları: {stats['test_messages']}")
    print(f"algılanan kick olayları: {stats['kick_events']}")
    
    # yeni mesaj alınmadıysa tavsiye ver
    if stats["new_messages"] == 0:
        print("\nhiç yeni mesaj alınmadı. olası sorunlar:")
        print("  1. webhook sunucusu düzgün çalışmıyor olabilir")
        print("  2. kick developer dashboard'da webhook ayarları doğru yapılmamış olabilir")
        print("  3. kick'te canlı yayın/aktif sohbet olmayabilir")
        print("  4. webhook sisteminin aktif olması için zamana ihtiyaç olabilir")

if __name__ == "__main__":
    print("kick webhook mesaj i̇zleyici")
    print("============================")
    
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = input("ngrok url'inizi girin (örn: https://xxxx.ngrok.io): ").strip()
    
    duration = input("kaç dakika boyunca i̇zlemek istersiniz? (varsayılan: 5): ").strip()
    try:
        duration = int(duration) * 60 if duration else 300
    except:
        duration = 300
        print("geçersiz süre, varsayılan 5 dakika kullanılacak.")
    
    interval = input("kontrol aralığı kaç saniye olsun? (varsayılan: 10): ").strip()
    try:
        interval = int(interval) if interval else 10
    except:
        interval = 10
        print("geçersiz aralık, varsayılan 10 saniye kullanılacak.")
    
    check_for_messages(url, interval, duration) 