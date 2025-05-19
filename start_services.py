import subprocess
import time
import sys
import os

# renkli çıktı için (kick_webhook_verifier.py dosyasından alındı)
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

def get_python_executable():
    """aktif python yorumlayıcısının yolunu döndürür."""
    return sys.executable

def start_services():
    print_header("servis başlatma otomasyonu")

    # 1. ngrok için talimatlar
    print_info("lütfen ayrı bir terminal penceresi açın ve aşağıdaki komutu çalıştırın:")
    print(f"{Colors.YELLOW}  ngrok http 8000{Colors.ENDC}")
    print_info("ngrok başladıktan sonra, 'forwarding' satırındaki https url'yi kopyalayın.")
    print_info("(örn: https://xxxx-xxxx-xxxx.ngrok-free.app)")
    
    ngrok_url = ""
    while not ngrok_url:
        try:
            ngrok_url_input = input(f"{Colors.BOLD}lütfen ngrok https url'sini yapıştırın: {Colors.ENDC}").strip()
            if "ngrok" in ngrok_url_input and ngrok_url_input.startswith("https://"):
                ngrok_url = ngrok_url_input
            else:
                print_warning("geçersiz ngrok url'si. lütfen 'https://' ile başlayan doğru url'yi girin.")
        except KeyboardInterrupt:
            print_error("\ni̇şlem kullanıcı tarafından iptal edildi.")
            return

    print_success(f"ngrok url'si alındı: {ngrok_url}")

    # webhook sunucusu için tam url
    kick_webhook_url = ngrok_url.rstrip('/') + "/kick-webhook"
    print_info(f"kick geliştirici paneli için webhook url'niz: {Colors.BOLD}{kick_webhook_url}{Colors.ENDC}")
    print_warning("lütfen kick geliştirici paneli'ndeki webhook url'nizi bu adresle güncellediğinizden emin olun!")

    python_executable = get_python_executable()
    webhook_server_script = "webhook_debug_server.py" # veya webhook_server.py

    # 2. webhook sunucusunu başlatma
    print_header(f"{webhook_server_script} başlatılıyor")
    print_info(f"'{python_executable} {webhook_server_script}' komutu ayrı bir süreçte çalıştırılacak.")
    print_info("bu betik kapatıldığında webhook sunucusu da durabilir.")
    print_info("webhook sunucusunu izlemek için ayrı bir terminal kullanmanız önerilir.")

    try:
        # subprocess.popen kullanarak webhook sunucusunu non-blocking şekilde başlat
        # windows'ta yeni bir konsol penceresi açmak için creationflags kullanılır
        if os.name == 'nt': # windows
            webhook_process = subprocess.Popen(
                [python_executable, webhook_server_script],
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
        else: # macos/linux
            # bu komut yeni bir terminal penceresi açmayabilir, kullanıcıya bilgi verelim.
            print_warning("webhook sunucusu arka planda başlatılıyor. çıktısını görmek için ayrı bir terminalde manuel çalıştırabilirsiniz.")
            webhook_process = subprocess.Popen([python_executable, webhook_server_script])
        
        print_success(f"{webhook_server_script} başlatıldı (pid: {webhook_process.pid}).")
        time.sleep(3) # sunucunun başlaması için kısa bir bekleme
    except Exception as e:
        print_error(f"{webhook_server_script} başlatılırken hata: {e}")
        print_info("lütfen webhook sunucusunu manuel olarak ayrı bir terminalde çalıştırın:")
        print(f"{Colors.YELLOW}  {python_executable} {webhook_server_script}{Colors.ENDC}")
        return

    # 3. streamlit uygulamasını başlatma
    print_header("streamlit uygulaması başlatılıyor")
    streamlit_command = [
        python_executable, "-m", "streamlit", "run", "main.py",
        "--", "--webhook_url", ngrok_url.rstrip('/') # streamlit'e argüman geçirme
    ]
    streamlit_command_str = " ".join(streamlit_command)
    print_info(f"streamlit uygulaması şu komutla çalıştırılacak:")
    print(f"{Colors.YELLOW}  {streamlit_command_str}{Colors.ENDC}")
    
    try:
        print_info("streamlit başlatılıyor... bu işlem biraz zaman alabilir.")
        # streamlit'i aynı konsolda çalıştır, çünkü kullanıcı arayüzünü burada görecek.
        subprocess.run(streamlit_command, check=True)
    except subprocess.CalledProcessError as e:
        print_error(f"streamlit uygulaması çalıştırılırken hata: {e}")
    except FileNotFoundError:
        print_error("streamlit bulunamadı. lütfen 'pip install streamlit' ile kurun.")
    except KeyboardInterrupt:
        print_info("\nstreamlit kullanıcı tarafından durduruldu.")
    finally:
        print_info("başlangıç betiği tamamlandı.")
        # webhook sunucusunu sonlandırma (isteğe bağlı, genelde kullanıcı manuel kapatır)
        # print_info(f"webhook sunucusu (pid: {webhook_process.pid}) durduruluyor...")
        # webhook_process.terminate()
        # webhook_process.wait()

if __name__ == "__main__":
    start_services() 