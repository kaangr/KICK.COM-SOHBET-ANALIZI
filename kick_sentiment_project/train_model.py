from datasets import load_dataset, Dataset
from transformers import AutoTokenizer, AutoModelForSequenceClassification, Trainer, TrainingArguments
import pandas as pd
from sklearn.preprocessing import LabelEncoder
import evaluate
import numpy as np
import os # dosya yollarını kontrol etmek için
import glob # tüm csv dosyalarını bulmak için
import torch

print("--- train_model.py (dinamik csv yükleme ile) başlıyor ---")

# temel veri dizinini tanımla
base_data_dir = "../data/labeled_data"

# dizindeki tüm csv dosyalarını bul
csv_files = glob.glob(os.path.join(base_data_dir, "*.csv"))

if not csv_files:
    print(f"{os.path.abspath(base_data_dir)} içinde csv dosyası bulunamadı. lütfen etiketli verilerinizi ekleyin.")
    exit()

print(f"{os.path.abspath(base_data_dir)} içinde aşağıdaki csv dosyaları bulundu:")
for f_path in csv_files:
    print(f"  - {os.path.basename(f_path)}")

all_dataframes = []

# csv oku ve birleştir
print(f"\ntüm csv dosyaları okunmaya çalışılıyor...")

try:
    for file_path in csv_files:
        print(f"{file_path} okunuyor...")
        temp_df = pd.read_csv(file_path)
        print(f"{file_path} başarıyla okundu. şekil: {temp_df.shape}. sütunlar: {temp_df.columns.tolist()}")
        
        processed_temp_df = None
        if not temp_df.empty:
            if "content" in temp_df.columns and "label" in temp_df.columns:
                print(f"{os.path.basename(file_path)} içinde 'content' ve 'label' sütunları bulundu.")
                processed_temp_df = temp_df[["content", "label"]]
            elif "message" in temp_df.columns and "label" in temp_df.columns:
                print(f"{os.path.basename(file_path)} içinde 'message' ve 'label' sütunları bulundu. 'message' 'content' olarak yeniden adlandırılıyor.")
                processed_temp_df = temp_df[["message", "label"]].rename(columns={"message": "content"})
            else:
                print(f"uyarı: {os.path.basename(file_path)} beklenen sütun çiftlerine sahip değil ('content', 'label') veya ('message', 'label').")
                print(f"  bulunan sütunlar: {temp_df.columns.tolist()}")
                print(f"  {os.path.basename(file_path)} atlanıyor.")
        else:
            print(f"uyarı: {os.path.basename(file_path)} boş. atlanıyor.")
        
        if processed_temp_df is not None:
            all_dataframes.append(processed_temp_df)
            
except FileNotFoundError as e:
    print(f"csv dosyaları okunurken hata: {e}")
    print(f"lütfen dosyaların train_model.py'ye göre '{base_data_dir}' dizininde olduğundan emin olun")
    print(f"geçerli çalışma dizini: {os.getcwd()}")
    exit()

if not all_dataframes:
    print("geçerli veri çerçevesi yüklenmedi. çıkılıyor.")
    exit()

print("\nyüklenen tüm veri çerçeveleri birleştiriliyor...")
df = pd.concat(all_dataframes, ignore_index=True)
print(f"birleştirilmiş veri çerçevesi şekli: {df.shape}")

# bu noktada, all_dataframes'teki tüm veri çerçevelerinin 'content' ve 'label' sütunlarına sahip olması gerekir.
# 'text' olarak yeniden adlandırma, bu birleştirilmiş df oluşturulduktan sonra gerçekleşir.
df = df.rename(columns={"content": "text"}) # model için 'content' 'text' olarak yeniden adlandırılıyor
print("'content' 'text' olarak yeniden adlandırıldı. birleştirilmiş veri çerçevesinin başı:")
print(df.head())

# etiketleri sayıya çevir
print("etiketler kodlanıyor...")
le = LabelEncoder()
df["label_id"] = le.fit_transform(df["label"])
print(f"etiket kodlaması tamamlandı. etiket sınıfları: {le.classes_}")
print("'label' için değer sayıları:")
print(df['label'].value_counts())
print("'label_id' için değer sayıları:")
print(df['label_id'].value_counts())

# trainer için 'label_id' 'labels' olarak yeniden adlandır
df = df.rename(columns={"label_id": "labels"})
print("'label_id' 'labels' olarak yeniden adlandırıldı.")

# veri kümesi için yalnızca gerekli sütunları seç: 'text' ve 'labels'
df_for_dataset = df[['text', 'labels']]
print("veri kümesi için seçilen sütunlar: 'text', 'labels'. df_for_dataset'in başı:")
print(df_for_dataset.head())

# huggingface dataset'e dönüştür
print("huggingface veri kümesine dönüştürülüyor...")
dataset = Dataset.from_pandas(df_for_dataset) # filtrelenmiş dataframe'i kullan
print(f"veri kümesi oluşturuldu. özellikler: {dataset.features}")
dataset = dataset.train_test_split(test_size=0.2, seed=42) # tekrarlanabilirlik için tohum eklendi
print(f"veri kümesi bölündü. eğitim boyutu: {len(dataset['train'])}, test boyutu: {len(dataset['test'])}")

# tokenizer ve model yükle
model_name = "dbmdz/bert-base-turkish-cased"
print(f"tokenizer yükleniyor: {model_name}...")
tokenizer = AutoTokenizer.from_pretrained(model_name)
print(f"sıra sınıflandırması için model yükleniyor: {model_name} ile {len(le.classes_)} etiket...")
model = AutoModelForSequenceClassification.from_pretrained(model_name, num_labels=len(le.classes_))

def tokenize(example):
    return tokenizer(example["text"], padding="max_length", truncation=True, max_length=512) # açık max_length

print("veri kümesi tokenize ediliyor...")
dataset = dataset.map(tokenize, batched=True) # verimlilik için batched=true eklendi
print("veri kümesi tokenizasyonu tamamlandı.")

# değerlendirme metriği
accuracy = evaluate.load("accuracy")

def compute_metrics(eval_pred):
    logits, labels = eval_pred
    predictions = np.argmax(logits, axis=-1)
    return accuracy.compute(predictions=predictions, references=labels)

print("eğitim argümanları ayarlanıyor...")
# eğitim ayarları
training_args = TrainingArguments(
    output_dir="./model",          # model ve kontrol noktaları için çıktı dizini
    eval_strategy="epoch",    # her epoch sonunda değerlendir
    save_strategy="epoch",          # her epoch sonunda model kontrol noktasını kaydet
    learning_rate=2e-5,             # öğrenme oranı
    per_device_train_batch_size=8,  # eğitim için toplu iş boyutu
    per_device_eval_batch_size=8,   # değerlendirme için toplu iş boyutu
    num_train_epochs=3,             # toplam eğitim epoch sayısı
    weight_decay=0.01,              # düzenlileştirme için ağırlık azalması
    load_best_model_at_end=True,    # eğitim sonunda en iyi modeli yükle
    metric_for_best_model="accuracy", # en iyi modeli belirlemek için metrik
    report_to="all",                # tüm entegrasyonlara rapor et (yapılandırılmışsa tensorboard, wandb gibi)
    # use_mps_device=torch.backends.mps.is_available() # macos'ta mps ile çalışıyorsanız yorum satırını kaldırın
)

print("trainer başlatılıyor...")
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=dataset["train"],
    eval_dataset=dataset["test"],
    tokenizer=tokenizer,
    compute_metrics=compute_metrics,
)

# --- eğitim öncesi gpu/cihaz kontrolü ---
if torch.cuda.is_available():
    device = torch.device("cuda")
    print(f"--- gpu mevcut. eğitim şurada çalışacak: {torch.cuda.get_device_name(0)} ---")
    # trainer başlatıldıktan sonra belirli model cihazını kontrol etmek için (isteğe bağlı, trainer bunu halleder)
    # print(f"model şu anda şu cihazda: {model.device}") 
else:
    device = torch.device("cpu")
    print("--- gpu mevcut değil. eğitim cpu'da çalışacak. ---")

print("--- model eğitimi başlıyor ---")
trainer.train()
print("--- model eğitimi tamamlandı ---")

# modeli kaydet
output_model_dir = "model/finetuned_kick_sentiment"
print(f"model {output_model_dir} dizinine kaydediliyor...")
trainer.save_model(output_model_dir)
print(f"tokenizer {output_model_dir} dizinine kaydediliyor...")
tokenizer.save_pretrained(output_model_dir)

print(f"--- model ve tokenizer {output_model_dir} dizinine kaydedildi ---")
print("--- train_model.py bitti ---") 