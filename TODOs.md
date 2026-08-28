## Model Configurations
- Layer count and neuron sizes?
- time window lag (24h)?

## Dataset Yapılacaklar: (TAMAMLANDI - 2026-08-28)
- [x] "CLRSKY_SFC_SW_DWN" sütunu silinecek -> `DROPPED_COLUMNS` (src/merve_solar/config.py)
- [x] "ALLSKY_KT" sütunu silinecek -> `DROPPED_COLUMNS` (src/merve_solar/config.py)
- [x] "ALLSKY_SFC_SW_DWN" tahmin edilecek sütun -> `TARGET_COLUMN` olarak teyit edildi
- Not: Sütunlar xlsx dosyasindan fiziksel olarak silinmedi; okuma aninda data.py düşürüyor.
- Not: Öznitelik sayisi 18 -> 17 düştü. Bu degisiklikten önceki ledger satirlari
  karsilastirilabilir degil; tarama yeni experiment_id'lerle yeniden kosulmali.


## Makale Eklenecekler
- 5 ili gösteren harita
- 5 ilin iklim ve coğrafi farklılıkları anlatan paragraf
- Tüm değişkenlerin solar radiatona (predicted variable) ile scatter diagram
- Tüm değişkenlerin correlation matris  grafiği
- Aylık 5 bölgenin solar radiation verisinin montly olarak box plot (her 5 il için)
- 3D diagram; x ekseninde ay, z ekseninde yıl, y ekseninde solar radiation diagram (her 5 il için)
-  Mevsimlere göre x ekseninde toplam gün y de radiation grafiği
- Mervenin gönderdiği makalelerden lstm optimal konfigürasyon dosyası oluştur. 
- MAE, RMSE, R2 performans tablosu ekle
- SVM, Prophet, GRU (prophet olmazsa random forest regressşon veya mlp) alternatif methodlarla karşılaştırma


