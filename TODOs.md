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

---

## EDA bulgularından çıkan görevler (2026-08-28)

Kaynak: `outputs/eda/tables/` — hepsi **tam veri** (2019-06-30 → 2026-03-30, 6 yıl 9 ay)
üzerinde hesaplandı. Tek istisna `monthly_target_stats.csv` (son 12 ay, kutu grafiğinin
verisi) ve 3B yüzey/anomali (2020–2025 tam takvim yılları).

### A. UYARI: gündüz-only eğitim mevcut pencere yapısını kırıyor (ÖNCELİKLİ)

Metodoloji paralel session'da "model eğitiminde ve tahminde sadece `TARGET_COLUMN > 0`
saatler kullanılacak" şeklinde güncelleniyor. **Gece satırları seriden fiziksel olarak
silinirse `windows.py` hiç pencere üretemez.** Ölçüldü:

- Gündüz satırları bırakıldığında seri il başına **2 466 ayrı bloğa** parçalanıyor
  (her gün bir blok).
- Blok uzunlukları: medyan **13 saat**, min 10, maks 15.
- **24 saat lookback + 24 saat horizon = 48 saatlik kesintisiz pencere gerekiyor.
  ≥24 saatlik blok oranı: 0.000.** Yani üretilebilecek pencere sayısı sıfır.

Ayrıca `windows.py` kesintisizliği assert ediyor, `bootstrap.py`'nin 168 saatlik hareketli
blok uzunluğu da saatlik kesintisiz seri varsayıyor.

**Önerilen çözüm — gece satırlarını silmek yerine maskelemek:**
girdi penceresi ve kronolojik yapı 24 saat kalsın (kesintisizlik, ölçekleyici, bootstrap
blok mantığı korunur), **kayıp fonksiyonu ve metrikler yalnızca gündüz adımları üzerinden
hesaplansın** (horizon içindeki gece adımları maskelensin). Bu, "model sadece gündüzü
öğrenir/skorlanır" amacını karşılar ve mevcut boru hattını bozmaz.

Alternatifler ve neden daha kötü oldukları:
- *Değişken uzunlukta gündüz dizileri (10–15 adım) + padding:* mevsime göre değişen dizi
  uzunluğu, padding maskesi ve horizon tanımının yeniden yazılması gerekir; `lookback_hours`
  ve `horizon_hours` semantiği bozulur, tüm ledger satırları karşılaştırılamaz hale gelir.
- *Girdide gece var, çıktıda yok:* maskeleme ile aynı şey, ama horizon tanımı bulanıklaşır.

Karar ne olursa olsun: bu değişiklik `NUMERIC_FEATURE_COLUMNS`'u değil pencere/kayıp
semantiğini değiştirdiği için **tüm mevcut ledger satırlarını karşılaştırılamaz yapar**;
yeni `experiment_id`'lerle yeniden koşulmalı.

### B. `PRECTOTCORR` için `log1p` dönüşümü (`scaling.py`)

**Bulgu.** Yağış, öznitelik setindeki en patolojik dağılım
(`descriptive_stats_by_city_daylight.csv`, havuzlanmış gündüz satırları):

| Ölçüt | PRECTOTCORR | Karşılaştırma: diğer öznitelikler |
|---|---|---|
| Çarpıklık | **8.24** | −0.65 … +1.13 |
| Fazlalık basıklık | **101.97** | −1.10 … +2.22 |
| Ortalama | 1.69 mm/saat | — |
| Std | 6.28 | — |
| Maks | 347.72 mm/saat | — |

İl bazında ortalama: Rize 3.74, Antalya 1.80, Ankara 1.04, Konya 0.97, Van 0.92 mm/saat.

**Sorun.** `scaling.py` `StandardScaler` kullanıyor; ortalama ve standart sapma birkaç uç
değer tarafından belirleniyor. Sonuçta ölçeklenmiş sütunun ezici çoğunluğu sıfıra yakın çok
dar bir aralıkta sıkışıyor, nadir uç değerler ise ±50 mertebesine gidiyor. LSTM'in girdi
katmanı için bu, fiilen "çoğu zaman sabit, arada bir patlayan" bir sütun demek — yani
öznitelik bilgisini büyük ölçüde kaybediyor.

**Neden ziyan.** Yağış boş bir sütun değil: güneş geometrisi sabitlendiğinde
(`target_correlation_by_city.csv`, `partial_r_within_hour`) hedefle korelasyonu
**−0.27 … −0.37** ve bu, ham korelasyonundan (−0.09 … −0.21) **daha güçlü**. Yani gerçek
bulut sinyali taşıyan az sayıdaki değişkenden biri; ölçekleme yüzünden kaybedilmesi ziyan.

**Öneri.** `scaling.py`'de ölçeklemeden önce `PRECTOTCORR` için `log1p` dönüşümü. Kritik
kısıt: dönüşüm sabit (parametresiz) olduğu için sızıntı riski yok, ama **`StandardScaler`
yine yalnızca train satırlarında fit edilmeli** — mevcut train-only sınırı korunmalı.
`inverse_transform_target` yalnız hedefi ters çevirdiği için etkilenmiyor.

**Doğrulama.** Aynı config'i biri log1p'li biri log1p'siz iki `experiment_id` ile koşup
ledger'da karşılaştırmak yeterli. Not: bu bir ölçekleme değişikliği olduğu için **mevcut
ledger satırlarını karşılaştırılamaz yapar**; ayrıca ledger satırı config'in bu alanını
taşımıyor, dolayısıyla eklenecekse `experiment.py`'deki ledger satır sözlüğüne bir sütun
girmeli (bkz. CLAUDE.md *Comparability rules*).

**Durum:** yapılacak. Model şu an fine-tune ediliyor, bu görev sıraya alındı.

### C. Öznitelik ablasyonu: 17 → 15 sütun

**Bulgu.** `collinear_pairs.csv` (gündüz satırları, havuzlanmış Pearson):

- `QV2M` ↔ `T2MDEW`: **r = 0.962**
- `WS10M` ↔ `WS50M`: **r = 0.962** (24 saat üzerinden 0.929)

Bu bir istatistik tesadüfü değil, fizik:

- **`T2MDEW` zaten `T2M` ve `RH2M`'nin deterministik bir fonksiyonu.** Magnus formülüyle
  ikisinden yeniden hesaplandığında gerçek `T2MDEW` ile **r = 0.9992**, ortalama mutlak
  fark **0.161 °C**. Yani sütun, sette hâlihazırda bulunan iki sütunun türevi; bağımsız
  hiçbir bilgi taşımıyor.
- **`WS50M` ≈ 1.33 × `WS10M`** (oran medyanı 1.330) — aynı sınır tabakasının logaritmik
  rüzgâr profili üzerinde iki farklı yüksekliği.

**"Çıkarılmış" ne demek.** Sütunlar veriden, xlsx'ten veya EDA tablolarından
silinmiyor. Yalnızca `src/merve_solar/config.py` içindeki **`NUMERIC_FEATURE_COLUMNS`**
listesinden — yani modele girdi olarak verilen öznitelik listesinden — çıkarılıyor.
Liste 17 elemandan 15'e iner; `SolarLSTM` girdi boyutu otomatik olarak
`len(NUMERIC_FEATURE_COLUMNS)`'tan geldiği için başka kod değişikliği gerekmiyor.

**Hangisi çıkarılmalı (ve neden partneri değil):**

| Çıkarılan | Kalan | Gerekçe |
|---|---|---|
| `T2MDEW` | `QV2M` | `QV2M` doğrudan nem *miktarı*; `T2MDEW` ise `T2M`+`RH2M`'den türetilebiliyor (r = 0.9992), yani sette zaten üç kez temsil edilen bir bilgi. |
| `WS50M` | `WS10M` | Yüzey ışınımı için ilgili yükseklik 10 m; 50 m rüzgârı standart yüzey ölçümü değil ve 10 m'nin sabit katı. |

**Beklenen etki.** LSTM için eşdoğrusallık zararsızdır, dolayısıyla RMSE'de büyük bir
değişiklik beklenmiyor — bu bir *performans* değil *gerekçelendirme* adımı:
(a) parametre sayısı ve gürültü azalır, (b) planlanan **SVM / RF / MLP baseline'ları için
kritik** (bu modeller eşdoğrusallıktan gerçekten etkilenir ve adil karşılaştırma için
aynı öznitelik setini kullanmak zorundalar), (c) makalede "öznitelik seçimi yapıldı ve
gerekçelendirildi" cümlesi kurulabilir.

**Nasıl koşulmalı.** Yeni bir `experiment_id` ile, tek eksen değiştirilerek. `n_features`
zaten ledger'da bir sütun olduğu için karşılaştırma izlenebilir olacak.

### D. Rize ayrı tartışılmalı

**Bulgu.** Beş il aslında iki rejim (`daily_clearness_by_city.csv`):

| | Ankara | Antalya | Konya | **Rize** | Van |
|---|---|---|---|---|---|
| Günlük toplam (kWh/m²/gün) | 4.66 | 4.94 | 4.87 | **3.69** | 4.98 |
| Berraklık oranı | 0.81 | 0.85 | 0.82 | **0.73** | 0.85 |
| Açık gün payı (>0.9) | %45 | %56 | %48 | **%37** | %52 |
| Kapalı gün payı (<0.5) | %11 | %8 | %10 | **%24** | %6 |
| Günlük toplam CV | 0.49 | 0.44 | 0.46 | **0.57** | 0.45 |
| Gündüz bağıl nem | %53.1 | %48.9 | %49.8 | **%73.7** | %46.2 |
| Saatin açıkladığı varyans (η², 24s) | 0.730 | 0.778 | 0.756 | **0.664** | 0.768 |

Dört il %6'lık bir bant içinde; Rize hepsinden ayrı bir rejim ve **her ölçütte en az
öngörülebilir olan**. Dolayısıyla:

- Agregat skor Rize'yi gizler (dört il onu 4'e 1 bastırır).
- Şehir gömülemesinin (`SolarLSTM.city_embedding`) öğrenmesi gereken asıl ayrım Rize'dir;
  cross-city transfer iddiasının gücü de Rize'deki performansa bağlıdır.

**Yapılacak.** (a) `results_summary.csv`'ye ek olarak "Rize hariç agregat" satırı — şehir
gömülemesinin katkısı ancak böyle görünür hale gelir; (b) makale metninde Rize'nin ayrı bir
paragrafta "en zor il" olarak tartışılması, yukarıdaki tablo ile birlikte.
