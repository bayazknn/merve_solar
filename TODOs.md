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
- [x] Tüm değişkenlerin solar radiatona (predicted variable) ile scatter diagram
- [x] Tüm değişkenlerin correlation matris  grafiği
- [x] Aylık 5 bölgenin solar radiation verisinin montly olarak box plot (her 5 il için)
- [x] 3D diagram; x ekseninde ay, z ekseninde yıl, y ekseninde solar radiation diagram (her 5 il için)
- [x] Mevsimlere göre x ekseninde toplam gün y de radiation grafiği
- [x] Her il ve her sütun için betimsel istatistik tablosu (min/maks/ortalama/SS/çarpıklık/basıklık)
- Mervenin gönderdiği makalelerden lstm optimal konfigürasyon dosyası oluştur. 
- MAE, RMSE, R2 performans tablosu ekle
- SVM, Prophet, GRU (prophet olmazsa random forest regressşon veya mlp) alternatif methodlarla karşılaştırma



## Betimsel istatistik: TAMAMLANDI (2026-08-28)
`scripts/02_descriptive_analysis.py` → `outputs/eda/` (tablolar + figürler, Türkçe).
Ayrıntı ve uyarılar: `outputs/eda/README.md`. Üç karar makaleye yazılmalı:
- "Gündüz" klimatolojik tanımlı ((il, ay, saat) hücre ortalaması > 0); `ışınım > 0` filtresi
  bağımlı değişkene koşullama yapıp 5 266 bulutlu saati siliyordu.
- Aylık kutu grafiği günlük toplam üzerinden; saatlik değerlerle kışın daha stabil görünüyordu.
- Saat ekseni il-bazlı yerel güneş saati (LST); saatler iller arasında karşılaştırılamaz.
