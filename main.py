import streamlit as st
import pandas as pd
import analysis # yorum satırı kaldırıldı
import plotly.express as px # yorum satırı kaldırıldı
from wordcloud import WordCloud # eklendi
import matplotlib.pyplot as plt # eklendi
from live_kick_chat_module import display_live_kick_chat_interface # yeni̇ modülümüzü i̇çe aktarma
from analysis import run_sentiment_analysis # bu i̇çe aktarmanın doğru olduğundan emin olun

st.set_page_config(layout="wide")

st.title("kick sohbet topluluğu etkileşim analizcisi")

# --- mod seçimi --- 
st.sidebar.header("analiz modu")
analysis_mode = st.sidebar.radio(
    "nasıl analiz edeceğinizi seçin:",
    ("kick csv dosyasından analiz et", "canlı kick sohbetini analiz et (deneme)", "twitch günlük dosyasından analiz et"),
    key="main_analysis_mode_radio" # netlik için bir anahtar eklendi
)

# --- kick csv analiz modu ---
if analysis_mode == "kick csv dosyasından analiz et":
    st.sidebar.header("kick sohbet günlüğünü yükle")
    uploaded_file = st.sidebar.file_uploader("kick sohbet günlüğü csv dosyanızı yükleyin", type=["csv"], key="kick_csv_uploader")

    # --- yeni̇: duygu modeli seçimi --- 
    st.sidebar.subheader("duygu analizi seçenekleri")
    analysis_method_options = {
        "bert (türkçe modeli - genel)": "bert",
        "özel kick ayarlı bert": "custom_kick_bert",
        "textblob (genel amaçlı)": "textblob",
        "vader (i̇ngilizce odaklı, sosyal medya için iyi)": "vader"
    }
    chosen_display_name = st.sidebar.selectbox(
        "duygu analizi modelini seçin:",
        options=list(analysis_method_options.keys()),
        index=0
    )
    chosen_method_key = analysis_method_options[chosen_display_name]
    st.sidebar.markdown("---") # ayırıcı

    if uploaded_file is not None:
        st.sidebar.success("dosya başarıyla yüklendi!")
        
        try:
            # csv dosyasını oku
            df = pd.read_csv(uploaded_file)
            
            # --- esnek sütun işleme --- 
            # zaman damgasını kontrol et (her zaman gerekli)
            if 'timestamp' not in df.columns:
                st.error("hata: csv 'timestamp' sütununu içermelidir.")
                df = None # daha fazla i̇şlemi engelle
            else:
                # mesaj i̇çeriğini kontrol et: 'message' tercih et, 'content'e geri dön
                if 'message' not in df.columns:
                    if 'content' in df.columns:
                        st.info("'content' sütunu bulundu, analiz için 'message' olarak yeniden adlandırılıyor.")
                        df.rename(columns={'content': 'message'}, inplace=True)
                    else:
                        # ne 'message' ne de 'content' bulundu
                        st.error("hata: csv, sohbet metni için 'message' veya 'content' adlı bir sütun içermelidir.")
                        # daha fazla i̇şlemi engellemek için df'yi none olarak ayarla veya bir i̇stisna oluştur
                        df = None # veya st.stop() veya raise valueerror(...)
                
                # yalnızca df geçerliyse ve gerekli sütunlara sahipse devam et
                if df is not None and 'message' in df.columns: 
                    # --- temel veri doğrulama (orijinal kontrol biraz değiştirildi) ---
                    # required_columns = ['timestamp', 'message'] # yukarıda zaten kontrol edildi
                    # if not all(col in df.columns for col in required_columns):
                    #     st.error(f"hata: csv şu sütunları i̇çermelidir: {', '.join(required_columns)}")
                    # else:
                    st.header("sohbet verisi önizlemesi")
                    # i̇lgili sütunları görüntüle, mesajın görünür olduğundan emin ol
                    preview_cols = ['timestamp', 'username', 'message'] if 'username' in df.columns else ['timestamp', 'message']
                    st.dataframe(df[preview_cols].head())
                    st.info(f"{len(df)} mesaj yüklendi.")
    
                    if st.button("sohbet etkileşimlerini analiz et", key="analyze_csv_button"):
                        st.header(f"analiz sonuçları ({chosen_display_name} kullanılarak)") # kullanılan modeli belirt
                        
                        # --- duygu analizi (birleşik çağrı) --- 
                        sentiment_column_name = 'sentiment' # varsayılan sütun adı
                        with st.spinner(f"{chosen_display_name} kullanılarak duygular analiz ediliyor..."):
                            # bu tek çağrı artık chosen_method_key aracılığıyla bert, textblob veya vader'ı işliyor
                            df[sentiment_column_name] = run_sentiment_analysis(df['message'], method=chosen_method_key)
                            
                            # duygu analizinin başarısız olup olmadığını genel kontrol et (örneğin, model yükleme sorunları)
                            # analysis.py'deki run_sentiment_analysis i̇şlevi i̇deal olarak
                            # kendi hatalarını işlemeli ve başarısızlık durumunda 'nötr' veya 'bilinmeyen' bir seri döndürmelidir.
                            # bu nedenle, analysis.py sağlamsa burada df[sentiment_column_name].empty için açık bir kontrole her zaman gerek olmayabilir.
                            # 
                            if df[sentiment_column_name].empty:
                                st.error(f"{chosen_display_name} kullanılarak yapılan duygu analizi başarısız oldu veya sonuç döndürmedi. tam analizle devam edilemiyor.")
                                st.stop() 

                        st.success(f"{chosen_display_name} kullanılarak duygu analizi tamamlandı!")
                        
                        # --- konu modelleme --- # değiştirildi
                        topics = {}
                        coherence_score = None # değişkeni başlat
                        topic_duration = 0 # süreyi başlat
                        with st.spinner("konu modellemesi yapılıyor..."): 
                            # döndürülen değerleri doğru şekilde aç (artık süreyi içeriyor)
                            # en iyi tutarlılık puanını verdiği için num_topics = 4'e geri dönülüyor
                            lda_model, topics, coherence_score, topic_duration = analysis.perform_topic_modeling(df['message'], num_topics=4, num_words=5)
                        if topics:
                            st.success(f"konu modellemesi tamamlandı! (süre: {topic_duration:.2f} saniye)") # süreyi göster
                        else:
                            st.warning("konu modellemesi tamamlanamadı...")
                        
                        # --- öneri oluştur --- # eklendi
                        suggestions = []
                        with st.spinner("öneriler oluşturuluyor..."): 
                            suggestions = analysis.generate_content_suggestions(df, topics)
                        
                        st.header("analiz sonuçları") 
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.subheader(f"duygu analizi ({chosen_display_name}) ")
                            if sentiment_column_name in df.columns:
                                sentiment_counts = df[sentiment_column_name].value_counts()
                                st.write("duygu dağılımı:")
                                st.dataframe(sentiment_counts)
                                
                                # --- duygu eğilim grafiği --- # eklendi
                                st.subheader("zamana göre duygu eğilimi")
                                try:
                                    # zaman damgasını datetime'a dönüştürmeyi dene
                                    df['timestamp_dt'] = pd.to_datetime(df['timestamp'])
                                    df = df.sort_values('timestamp_dt') # zamana göre sırala
                                    
                                    # veriyi yeniden örnekle (örneğin, dakika başına veya uyarlanabilir şekilde)
                                    # dakika başına frekans için 't' kullanılıyor
                                    # frekansı (örneğin, 5 dakika için '5t', saat için 'h') 
                                    # tipik sohbet günlüğü süresine bağlı olarak ayarlayabilirsiniz
                                    sentiment_over_time = df.set_index('timestamp_dt')\
                                                           .groupby(pd.Grouper(freq='min'))[[sentiment_column_name]]\
                                                           .value_counts()\
                                                           .unstack(fill_value=0)
                                    
                                    if not sentiment_over_time.empty:
                                         # gerekirse netlik için sütunları yeniden adlandır (örneğin, çoklu dizini kaldır)
                                        sentiment_over_time.columns = [col[1] for col in sentiment_over_time.columns]
                                        
                                        # olası duygu etiketleri için renkleri tanımla
                                        color_map = {'positive': 'green', 'negative': 'red', 'neutral': 'blue', 'unknown': 'grey'}
                                        # haritayı yalnızca veride bulunan sütunları içerecek şekilde filtrele
                                        current_colors = {k: v for k, v in color_map.items() if k in sentiment_over_time.columns}

                                        fig_sentiment = px.line(sentiment_over_time, 
                                                                x=sentiment_over_time.index, 
                                                                y=sentiment_over_time.columns,
                                                                title="duygu eğilimi",
                                                                labels={'value': 'mesaj sayısı', 'timestamp_dt': 'zaman', 'variable': 'duygu'},
                                                                color_discrete_map=current_colors)
                                        fig_sentiment.update_layout(xaxis_title='zaman', yaxis_title='mesaj sayısı')
                                        st.plotly_chart(fig_sentiment, use_container_width=True)
                                    else:
                                        st.write("yeniden örneklemeden sonra duygu eğilimini çizmek için yeterli veri noktası yok.")
                                    
                                except Exception as e:
                                    st.warning(f"duygu eğilim grafiği oluşturulamadı. zaman damgası işlenirken hata: {e}")
                                    st.write("'timestamp' sütununun tanınabilir bir tarih/saat biçiminde olduğundan emin olun (örneğin, yyyy-aa-gg ss:dd:ss).")
                            else:
                                st.warning("duygu analizi yapılamadı veya sonuçlar eksik.")

                        with col2:
                            st.subheader("konu modelleme sonuçları") 
                            if topics:
                                st.write(f"en iyi {len(topics)} konu belirlendi:")
                                # tutarlılık puanını ve süreyi görüntüle
                                col_metric1, col_metric2 = st.columns(2)
                                with col_metric1:
                                    if coherence_score:
                                         st.metric(label="konu tutarlılığı (c_v)", value=f"{coherence_score:.4f}")
                                         st.caption("tutarlılık (c_v) konu yorumlanabilirliğini ölçer (daha yüksek genellikle daha iyidir).")
                                    else:
                                        st.write("tutarlılık puanı hesaplanamadı.")
                                with col_metric2:
                                    st.metric(label="modelleme süresi", value=f"{topic_duration:.2f} s")
                                    st.caption("konu modellemesi için geçen süre.")
                                
                                topic_words_for_cloud = {} # kelime bulutu için
                                for topic_id, keywords in topics.items():
                                    st.write(f"**konu {topic_id+1}:**")
                                    keyword_str_list = []
                                    for word, weight in keywords:
                                        keyword_str_list.append(f"{word} ({weight})")
                                        # bulut sözlüğüne kelime ve ağırlık (float olarak) ekle
                                        try: # ağırlığın float'a dönüştürülebilir olduğundan emin ol
                                            topic_words_for_cloud[word] = topic_words_for_cloud.get(word, 0.0) + float(weight) 
                                        except ValueError:
                                            pass # ağırlık float değilse yoksay
                                    st.write(", ".join(keyword_str_list))
                                    
                                # --- konu kelime bulutu --- # eklendi
                                st.subheader("konu kelime bulutu")
                                if topic_words_for_cloud:
                                    try:
                                        wordcloud = WordCloud(width=800, 
                                                              height=400, 
                                                              background_color='white', 
                                                              colormap='viridis', # Choose a colormap
                                                              max_words=100 # Limit number of words
                                                              ).generate_from_frequencies(topic_words_for_cloud)
                                        
                                        fig_wc, ax = plt.subplots()
                                        ax.imshow(wordcloud, interpolation='bilinear')
                                        ax.axis("off")
                                        st.pyplot(fig_wc)
                                    except Exception as e:
                                        st.error(f"Error generating word cloud: {e}")
                                else:
                                     st.write("Not enough topic data to generate word cloud.")
                                 
                            else:
                                 st.write("No topics were identified.")   
                                # Placeholder for topic word cloud (removed - now implemented)

                            # --- Display Suggestions --- # Modified
                            st.subheader("Content Suggestions")
                            if suggestions:
                                for suggestion in suggestions:
                                    st.info(suggestion) # Display each suggestion using st.info
                            else:
                                 st.write("No suggestions generated.")
                            
                            st.header(f"Data with Calculated Sentiment ({chosen_display_name}) ") 
                            # Display relevant columns including the calculated sentiment
                            display_cols = preview_cols + [sentiment_column_name]
                            st.dataframe(df[[col for col in display_cols if col in df.columns]])
                            
                            # --- Placeholder for Export ---
                            # Add Streamlit download button for PNG export if needed

        except Exception as e:
            st.error(f"An error occurred while processing the file: {e}")

    else:
        st.info("Please upload a CSV file using the sidebar to begin analysis.")

# --- Live Kick Chat Analysis Mode (New Selenium-based logger) ---
elif analysis_mode == "Analyze Live Kick Chat (Attempt)":
    # Call the function from our new module to display its UI and handle its logic
    display_live_kick_chat_interface()
    # The existing webhook-based UI below is now effectively replaced by the module.
    # If you want to offer both, you might need another sub-selection here.

    # Existing Webhook based UI (can be commented out or removed if new module is preferred)
    # st.header("Live Kick Chat Analysis (Webhook Method - Experimental)")
    # st.warning("Note: Connecting to live Kick chat via webhooks can be unreliable due to platform limitations.")
    # st.info("This feature attempts to use webhooks to analyze live chat messages from Kick.")
    # col1, col2 = st.columns(2)
    # with col1:
    #     st.subheader("Webhook Configuration")
    #     st.write("To use this feature (webhook method):")
    #     st.markdown("""
    #     1. Run the webhook server (app.py) in a separate terminal: `uvicorn app:app --host 0.0.0.0 --port 8000 --reload`
    #     2. Set up ngrok: `ngrok http 8000`
    #     3. Configure your webhook in the Kick Developer Panel with your ngrok URL + `/kick_webhook`
    #     4. Ensure your Kick App is subscribed to the `chat.message.sent` event.
    #     """)
    # with col2:
    #     st.subheader("Live Chat Sentiment Summary (via Webhook)")
    #     webhook_server_url = st.text_input("Enter your backend server BASE URL (e.g., https://xxxx.ngrok.io):", key="webhook_url_input_clarified")
    #     if webhook_server_url:
    #         if not webhook_server_url.startswith(("http://", "https://")):
    #              webhook_server_url = "http://" + webhook_server_url
    #         if webhook_server_url.endswith('/'):
    #             webhook_server_url = webhook_server_url[:-1]
    #         summary_endpoint = f"{webhook_server_url}/sentiment_summary"
    #         st.write(f"Fetching data from: `{summary_endpoint}`")
    #         if st.button("Refresh Webhook Summary"):
    #             try:
    #                 import requests
    #                 response = requests.get(summary_endpoint, timeout=10)
    #                 if response.status_code == 200:
    #                     summary_data = response.json()
    #                     if "message" in summary_data:
    #                          st.warning(summary_data["message"])
    #                     elif "average_sentiment_score" in summary_data:
    #                         st.success("Webhook summary data fetched!")
    #                         st.metric("Total Messages Stored (Webhook)", summary_data.get("total_messages_stored", "N/A"))
    #                         st.metric("Average Sentiment (Webhook)", f"{summary_data.get('average_sentiment_score', 0):.4f}")
    #                         sub_col1, sub_col2, sub_col3 = st.columns(3)
    #                         with sub_col1: st.metric("Positive (Webhook)", summary_data.get("positive_messages", 0))
    #                         with sub_col2: st.metric("Negative (Webhook)", summary_data.get("negative_messages", 0))
    #                         with sub_col3: st.metric("Neutral (Webhook)", summary_data.get("neutral_messages", 0))
    #                         last_messages = summary_data.get('last_messages', [])
    #                         if last_messages:
    #                             st.subheader("Recent Messages (Webhook)")
    #                             messages_df = pd.DataFrame(last_messages)[['timestamp', 'sender', 'message', 'sentiment_label', 'sentiment_score']]
    #                             messages_df = messages_df.rename(columns={'sentiment_label': 'Sentiment', 'sentiment_score': 'Score'})
    #                             st.dataframe(messages_df, use_container_width=True)
    #                         else:
    #                             st.write("No recent messages in webhook summary.")
    #                     else:
    #                         st.error("Unexpected data from webhook server.")
    #                         st.json(summary_data)
    #                 else:
    #                     st.error(f"Error connecting to webhook server: Status {response.status_code} - {response.text}")
    #             except requests.exceptions.RequestException as e:
    #                 st.error(f"Error fetching from webhook backend: {e}")
    #             except Exception as e:
    #                 st.error(f"An unexpected error occurred with webhook: {e}")
    #     else:
    #         st.warning("Enter backend server URL for webhook summary.")

# --- Twitch Log File Analysis Mode ---
elif analysis_mode == "Analyze from Twitch Log File":
    st.sidebar.header("Upload Twitch Chat Log")
    uploaded_file_twitch = st.sidebar.file_uploader("Upload your Twitch chat log file (.log, .txt)", type=["log", "txt"], key="twitch_log_uploader")

    if uploaded_file_twitch is not None:
        st.sidebar.success("Twitch log file uploaded successfully!")

        try:
            # Read the content of the uploaded file
            # Decoding might need adjustments based on typical log file encodings
            log_content = uploaded_file_twitch.getvalue().decode("utf-8")
            st.header("Twitch Log Preview (Raw)")
            st.text_area("Raw Log Content", log_content[:1000] + "..." if len(log_content) > 1000 else log_content, height=200)

            # --- Placeholder for Parsing Logic ---
            st.subheader("Parsing (Work in Progress)")
            st.info("Need to implement parsing logic for Twitch log format.")
            # Example: Define regex or parsing function here
            # parsed_data = parse_twitch_log(log_content)
            # df_twitch = pd.DataFrame(parsed_data, columns=['timestamp', 'username', 'message'])

            # --- Placeholder for Analysis Trigger ---
            st.warning("Analysis part for Twitch logs is not yet implemented.")
            # if st.button("Analyze Twitch Chat Interactions"):
            #    # Perform analysis using df_twitch
            #    # Display results
            #    pass

        except Exception as e:
            st.error(f"An error occurred while processing the Twitch log file: {e}")
    else:
        st.info("Please upload a Twitch log file (.log or .txt) using the sidebar to begin analysis.")