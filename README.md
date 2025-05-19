# Topluluk Etkileşim Analizcisi

Yayıncılara izleyici etkileşimleri hakkında içgörüler sağlamak amacıyla Kick.com sohbet günlüklerini analiz etmek için kullanılan hafif bir NLP tabanlı araçtır.

## Kurulum

1.  Depoyu klonlayın.
2.  Sanal bir ortam oluşturun: `python -m venv venv`
3.  Sanal ortamı etkinleştirin:
    - Windows: `.\venv\Scripts\activate`
    - macOS/Linux: `source venv/bin/activate`
4.  Bağımlılıkları yükleyin: `pip install -r requirements.txt`
5.  NLTK verilerini indirin (bunu Python yorumlayıcısında çalıştırın):
    ```python
    import nltk
    nltk.download('punkt')
    nltk.download('stopwords')
    nltk.download('wordnet')
    ```

## Kullanım

Streamlit uygulamasını çalıştırın:
`streamlit run main.py`

Arka ucu çalıştırın:
 `uvicorn app:app --host 0.0.0.0 --port 8000 --reload `


Sohbet günlüğü CSV dosyanızı arayüz üzerinden yükleyin. ![0520(1)](https://github.com/user-attachments/assets/09510447-c5b6-41da-8e89-265ec222cbac)
