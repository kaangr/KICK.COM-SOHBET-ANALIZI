# bu dosya, canlı kick sohbet analizcisi için streamlit kullanıcı arayüzünü ve mantığını içerecektir.
import streamlit as st
import pandas as pd
import os
import time
import queue
from datetime import datetime
from scraper.kick_scraper import KickScraper # Assuming kick_scraper.py is in a 'scraper' subfolder

def display_live_kick_chat_interface():
    st.header("canlı kick sohbet kaydedici ve görüntüleyici")
    # bu modüle özgü oturum durumu değişkenlerini, mevcut değillerse başlat
    # bu modül daha büyük bir uygulamanın parçasıysa çakışmaları önlemek için ön ek kullanmak iyi bir uygulamadır
    # örneğin: 'live_kick_log_messages', 'live_kick_scraper_running'

    if 'lk_log_messages' not in st.session_state:
        st.session_state.lk_log_messages = []
    if 'lk_scraper_running' not in st.session_state:
        st.session_state.lk_scraper_running = False
    if 'lk_kick_scraper' not in st.session_state:
        st.session_state.lk_kick_scraper = None
    if 'lk_message_queue' not in st.session_state:
        st.session_state.lk_message_queue = None
    if 'lk_last_channel_name' not in st.session_state:
        st.session_state.lk_last_channel_name = ""
    if 'lk_raw_queue_log' not in st.session_state: # sıra mesajlarını ayıklamak için
        st.session_state.lk_raw_queue_log = []

    # --- kick kanalı girişi ve kontrolleri için kenar çubuğu --- 
    # kullanıcı arayüzünün bu kısmı, ana uygulamanın kenar çubuğunda veya burada koşullu olarak bulunabilir.
    # modülerlik için burada tutulur ve bu işlev çağrıldığında görünür.
    st.sidebar.subheader("canlı kick sohbet kontrolleri")
    kick_channel_name_input = st.sidebar.text_input(
        "canlı kayıt için kick kanal adı",
        value=st.session_state.get("lk_last_channel_name", ""),
        key="lk_kick_channel_name_input_key"
    )

    col1, col2 = st.sidebar.columns(2)
    start_button = col1.button("canlı kaydı başlat", key="lk_start_button_key", use_container_width=True, disabled=st.session_state.lk_scraper_running)
    stop_button = col2.button("canlı kaydı durdur", key="lk_stop_button_key", disabled=not st.session_state.lk_scraper_running, use_container_width=True)
    st.sidebar.markdown("----") # ayırıcı

    status_placeholder = st.sidebar.empty()

    # ham sıra günlükleri için genişletici (ayıklama için)
    with st.sidebar.expander("geliştirici: ham sıra günlükleri", expanded=False):
        if st.button("ham günlükleri temizle", key="clear_raw_logs_btn"):
            st.session_state.lk_raw_queue_log = []
            st.rerun()
        st.caption(f"ham günlükte {len(st.session_state.lk_raw_queue_log)} öğe var. en eskisi en üstte.")
        # ham günlükleri en yenisi en üstte olacak şekilde ters sırada veya en eskisi en üstte olacak şekilde normal sırada görüntüle
        # bir günlük için genellikle en yenisi en altta veya en alta kaydırmaya izin ver
        raw_log_display_area = st.empty()
        with raw_log_display_area.container():
            if st.session_state.lk_raw_queue_log:
                # performans sorunlarını önlemek için sınırlı sayıda ham günlük göster
                max_raw_logs_to_show = 100
                log_to_show = st.session_state.lk_raw_queue_log[-max_raw_logs_to_show:]
                for log_item in log_to_show:
                    st.json(log_item, expanded=False) # daraltılmış json olarak göster
            else:
                st.write("henüz ham sıra öğesi kaydedilmedi.")
    st.sidebar.markdown("----")

    if not st.session_state.lk_scraper_running and not kick_channel_name_input and not st.session_state.lk_last_channel_name:
        status_placeholder.info("bir kick kanal adı girin ve kaydı başlatın.")
    elif not st.session_state.lk_scraper_running and kick_channel_name_input:
        status_placeholder.info(f"'{kick_channel_name_input}' için kayıt başlatmaya hazır.")

    # --- günlükler için ana panel --- 
    log_area_title = st.empty()
    log_placeholder = st.empty()

    def save_lk_logs_to_csv(channel_name_for_file):
        if st.session_state.lk_log_messages:
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            safe_channel_name = "".join(c if c.isalnum() else "_" for c in channel_name_for_file)
            if not safe_channel_name: safe_channel_name = "unknown_kick_channel"
            
            log_dir = "data"
            if not os.path.exists(log_dir):
                try:
                    os.makedirs(log_dir)
                except OSError as e:
                    status_placeholder.error(f"'{log_dir}' oluşturulurken hata: {e}")
                    return False

            filename = f"{log_dir}/live-kick-data-{safe_channel_name}-{timestamp}.csv"
            try:
                df = pd.DataFrame(st.session_state.lk_log_messages)

                # 'content' varsa 'message' olarak yeniden adlandır
                if 'content' in df.columns:
                    df.rename(columns={'content': 'message'}, inplace=True)
                
                # csv'de kesinlikle istediğimiz sütunları tanımla
                desired_columns = ['timestamp', 'username', 'message']
                final_df_columns = []

                for col in desired_columns:
                    if col in df.columns:
                        final_df_columns.append(col)
                    else:
                        # i̇stenen bir sütun eksikse, boş olarak ekle ve kullanıcıyı uyar
                        df[col] = "" # veya uygunsa daha yeni pandas sürümleri için pd.na
                        final_df_columns.append(col)
                        status_placeholder.warning(f"uyarı: '{col}' sütunu canlı günlüklerde eksikti. boş olarak eklendi.")
                
                # yalnızca istenen sütunları belirtilen sırada içeren yeni bir dataframe oluştur
                df_to_save = df[final_df_columns]
                
                df_to_save.to_csv(filename, index=False, encoding='utf-8-sig')
                status_placeholder.success(f"canlı günlükler {filename} dosyasına şu sütunlarla kaydedildi: {', '.join(final_df_columns)}")
                st.session_state.lk_log_messages = [] 
                return True
            except Exception as e:
                status_placeholder.error(f"csv kaydedilemedi: {e}")
                return False
        else:
            status_placeholder.info("kaydedilecek yeni canlı mesaj yok.")
            return False

    # --- düğme eylemleri --- 
    if start_button and kick_channel_name_input:
        if not st.session_state.lk_scraper_running:
            st.session_state.lk_last_channel_name = kick_channel_name_input
            st.session_state.lk_log_messages = [] 
            st.session_state.lk_raw_queue_log = [] # yeni başlangıçta ham günlükleri temizle
            log_placeholder.empty() 
            status_placeholder.info(f"'{kick_channel_name_input}' için canlı kayıt başlatılıyor...")
            
            st.session_state.lk_message_queue = queue.Queue()
            st.session_state.lk_kick_scraper = KickScraper(kick_channel_name_input, st.session_state.lk_message_queue)
            st.session_state.lk_kick_scraper.start()
            
            st.session_state.lk_scraper_running = True
            st.rerun() 

    if stop_button:
        if st.session_state.lk_scraper_running and st.session_state.lk_kick_scraper:
            status_placeholder.info("canlı kaydedici durduruluyor...")
            st.session_state.lk_kick_scraper.stop() 
            st.session_state.lk_scraper_running = False
            
            time.sleep(0.5) 
            while st.session_state.lk_message_queue and not st.session_state.lk_message_queue.empty():
                try:
                    msg_obj = st.session_state.lk_message_queue.get_nowait()
                    st.session_state.lk_raw_queue_log.append(msg_obj) # ham nesneyi günlüğe kaydet
                    if len(st.session_state.lk_raw_queue_log) > 200: # ham günlük boyutunu sınırla
                        st.session_state.lk_raw_queue_log.pop(0)
                    
                    if msg_obj["type"] == "message":
                        st.session_state.lk_log_messages.append(msg_obj["data"])
                    else:
                        msg_data = msg_obj.get("data", "bilinmeyen durum mesajı")
                        if msg_obj["type"] == "status": status_placeholder.info(msg_data)
                        elif msg_obj["type"] == "error": status_placeholder.error(msg_data)
                        elif msg_obj["type"] == "warning": status_placeholder.warning(msg_data)
                except queue.Empty:
                    break
                except Exception as e:
                    status_placeholder.warning(f"durdurma sırasında sıra mesajı işlenirken hata: {e}")
                    break
            
            save_lk_logs_to_csv(st.session_state.lk_last_channel_name)
            st.session_state.lk_kick_scraper = None 
            st.session_state.lk_message_queue = None 
            st.rerun()

    # --- mesaj sırasını işle ve günlükleri görüntüle --- 
    if st.session_state.lk_scraper_running and st.session_state.lk_message_queue:
        log_area_title.subheader(f"canlı kick sohbeti: {st.session_state.lk_last_channel_name}")
        messages_processed_this_cycle = 0
        max_messages_per_cycle = 100 
        
        while not st.session_state.lk_message_queue.empty() and messages_processed_this_cycle < max_messages_per_cycle:
            try:
                msg_obj = st.session_state.lk_message_queue.get_nowait()
                st.session_state.lk_raw_queue_log.append(msg_obj) # ham nesneyi günlüğe kaydet
                if len(st.session_state.lk_raw_queue_log) > 200: # ham günlük boyutunu sınırla
                    st.session_state.lk_raw_queue_log.pop(0)
                messages_processed_this_cycle += 1

                if msg_obj["type"] == "message":
                    st.session_state.lk_log_messages.append(msg_obj["data"])
                elif msg_obj["type"] == "status":
                    status_placeholder.info(msg_obj["data"])
                elif msg_obj["type"] == "error":
                    current_error_message = msg_obj.get("data", "").lower()
                    status_placeholder.error(msg_obj.get("data", "bilinmeyen hata"))
                    critical_errors = [
                        "kazıyıcı durduruluyor", "404", "tarayıcı başlatılamadı", 
                        "kazıma döngüsünde işlenmeyen hata", "sayfa kaynağı alınamadı"
                    ]
                    if any(err_keyword in current_error_message for err_keyword in critical_errors):
                        if st.session_state.lk_scraper_running:
                            st.session_state.lk_scraper_running = False 
                            if st.session_state.lk_kick_scraper: 
                               if hasattr(st.session_state.lk_kick_scraper, 'running') and st.session_state.lk_kick_scraper.running:
                                   st.session_state.lk_kick_scraper.stop() 
                               st.session_state.lk_kick_scraper = None
                            status_placeholder.error("Scraper stopped due to a critical error. Try restarting.")
                            st.rerun() 
                            break 
                elif msg_obj["type"] == "warning":
                    status_placeholder.warning(msg_obj["data"])
            except queue.Empty:
                break 
            except Exception as e:
                status_placeholder.error(f"General error while processing queue: {e}")
                break 

        if st.session_state.lk_log_messages:
            with log_placeholder.container():
                df_display = pd.DataFrame(st.session_state.lk_log_messages)
                display_columns = ['timestamp', 'username', 'content'] 
                df_display_filtered = df_display[[col for col in display_columns if col in df_display.columns]]
                st.dataframe(df_display_filtered.tail(100), height=400, use_container_width=True)
        elif st.session_state.lk_scraper_running:
            with log_placeholder.container():
                st.info("Waiting for new messages...")

        if st.session_state.lk_scraper_running:
            time.sleep(0.3)
            st.rerun()

    elif not st.session_state.lk_scraper_running:
        if st.session_state.lk_last_channel_name:
             log_area_title.subheader(f"Live Log for {st.session_state.lk_last_channel_name} (Stopped)")
             # Check if any log messages were actually saved in the last session before clearing status
             # This logic can be refined based on how save_lk_logs_to_csv returns status
             if not st.session_state.lk_log_messages: 
                # This message will show if stop was pressed and logs (if any) were saved and cleared OR if it stopped with no messages.
                status_placeholder.info("Live logging stopped.") 
        else:
            log_area_title.empty()

        with log_placeholder.container():
            if not kick_channel_name_input and not st.session_state.lk_last_channel_name:
                st.info("Select 'Analyze Live Kick Chat (Attempt)' mode and enter a channel name to start live logging.")
            elif st.session_state.lk_log_messages: 
                 st.info("Displaying previously captured live logs (logger is stopped).")
                 df_display = pd.DataFrame(st.session_state.lk_log_messages)
                 display_columns = ['timestamp', 'username', 'content'] 
                 df_display_filtered = df_display[[col for col in display_columns if col in df_display.columns]]
                 st.dataframe(df_display_filtered.tail(100), height=400, use_container_width=True)
            # else: # This case is implicitly covered by status_placeholder or log_area_title updates
            #    st.info("Live logger is not active.")

# To test this module standalone (optional)
if __name__ == "__main__":
    # Minimal setup for testing this module directly
    # In a real app, the main app (main.py) would call display_live_kick_chat_interface()
    st.set_page_config(layout="wide", page_title="Test Live Kick Logger")
    st.sidebar.title("Test Controls")
    display_live_kick_chat_interface() 