# Metodoloji — LSTM + Bootstrap Ensemble × MC Dropout ile Belirsizlik Tahminli Güneş Işınımı Öngörüsü

> **Bu belge ne işe yarar?**
> Makalenin "Materyal ve Yöntem" bölümünü yazarken kullanılacak referans dokümandır.
> Depodaki kodun (`src/merve_solar/`) birebir karşılığıdır: burada anlatılan her adımın
> hangi dosyada uygulandığı belirtilmiştir. **Kod değişirse bu belge de güncellenmelidir.**
> Sayısal değerler (satır sayıları, tarihler, pencere sayıları) mevcut veri kümesi ve
> varsayılan konfigürasyon (`ExperimentConfig` varsayılanları) ile doğrulanmıştır.

---

## 0. Bir paragraflık özet

Bu çalışmada Türkiye'nin farklı iklim kuşaklarında yer alan beş ili (Ankara, Antalya, Konya,
Rize, Van) için saatlik küresel yatay güneş ışınımının (`ALLSKY_SFC_SW_DWN`, W/m²) 24 saat
ileriye dönük tahmini yapılmaktadır. Tahmin modeli, şehir kimliğini öğrenilebilir bir gömme
(embedding) vektörü olarak alan **tek bir küresel (global) LSTM** ağıdır; model 24 saatlik
geçmiş pencereden 24 saatlik geleceği **tek bir ileri geçişte doğrudan** üretir. Nokta
tahmininin üzerine, kaynak makalenin önerdiği **Bootstrap Ensemble × Monte Carlo (MC) Dropout
hibrit belirsizlik katmanı** eklenmiştir: zaman serisine uygun *moving block bootstrap* ile
yeniden örneklenmiş $B$ adet eğitim kümesi üzerinde $B$ model eğitilir, her model çıkarım
sırasında dropout açık tutularak $T$ kez çalıştırılır ve elde edilen $B \times T$ tahmin tek bir
öngörü dağılımı olarak havuzlanır. Bu dağılımdan ortalama tahmin, standart sapma ve **yüzdelik
(percentile) tabanlı %95 güven aralığı** hesaplanır. Model başarımı hem nokta tahmini (RMSE,
MAE) hem de aralık kalitesi (CP, PINW, MPIW, Reliability, CWC, CRPS) metrikleriyle; toplulaştırılmış,
il bazında ve tahmin ufkunun her adımı için ayrı ayrı raporlanır.

---

## 1. Problem tanımı

$c \in \{1,\dots,C\}$ ile ili (il sayısı $C=5$), $t$ ile saatlik zaman adımını gösterelim.
$\mathbf{x}^{(c)}_t \in \mathbb{R}^{F}$ , $c$ ilinde $t$ saatindeki $F$ boyutlu meteorolojik
öznitelik vektörü; $y^{(c)}_t \in \mathbb{R}_{\ge 0}$ ise aynı an için güneş ışınımı olsun.

Model, geçmiş $L$ saatlik pencereden gelecek $H$ saati kestirir:

$$
\hat{\mathbf{y}}^{(c)}_{t+1:t+H} \;=\; f_\theta\!\left(\mathbf{x}^{(c)}_{t-L+1:t},\; c\right),
\qquad
\hat{\mathbf{y}} \in \mathbb{R}^{H}
$$

Varsayılan olarak $L = 24$ saat (`lookback_hours`), $H = 24$ saat (`horizon_hours`),
$F = 18$ sayısal öznitelik.

**Doğrudan çok-çıkışlı (direct multi-output) tahmin:** 24 saatin tamamı tek bir ileri geçişte
üretilir; özyinelemeli (recursive/iterated) tahmin kullanılmaz. Gerekçe: özyinelemeli yaklaşımda
her adımın hatası bir sonraki adımın girdisine taşınır ve hata birikimi 24 saatlik ufukta
ciddi bozulmaya yol açar; ayrıca özyineleme, belirsizlik dağılımının ufuk boyunca yayılımını
analitik olarak izlenemez hâle getirir. Doğrudan yaklaşımda her ufuk adımı için belirsizlik
doğrudan gözlemlenebilir (bkz. `cp_vs_horizon.png`).

**Küresel (global) model:** İl başına ayrı model eğitilmez. Beş ilin verisi tek bir modelde
birleştirilir ve il kimliği yalnızca öğrenilen bir gömme vektörü olarak modele girer. Bu,
makalenin iddialarından biridir: farklı iklim rejimleri arasında bilgi transferi sağlanır ve
her il için ayrı ayrı eğitilmiş modellere kıyasla veri verimliliği artar.

---

## 2. Kaynak makaleden uyarlama

Bu çalışma, referans makalenin (`main_methodology_paper.pdf`) belirsizlik tahmini metodolojisini
temel alır. Kritik nokta şudur:

> **Belirsizlik katmanı, tahmin modelinden bağımsızdır.**
> Kaynak makale PCNN kullanmış olsa da, aynı UQ yöntemi LSTM ile birebir uygulanabilir.
> Tahmin = LSTM · Belirsizlik = Bootstrap Ensemble + MC Dropout.

| Bileşen                  | Kaynak makale                            | Bu çalışma                                         | Gerekçe                                                                                                            |
| ------------------------ | ---------------------------------------- | -------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| Tahmin modeli (backbone) | PCNN                                     | **LSTM**                                           | Saatlik, uzun bağımlılıklı tek değişkenli-çok değişkenli zaman serisi yapısı için tekrarlayan mimari daha uygundur |
| Hedef değişken           | Fotovoltaik güç çıkışı                   | **Küresel yatay ışınım (`ALLSKY_SFC_SW_DWN`)**     | Santral bazlı güç verisi yerine, tesis bağımsız ve genelleştirilebilir meteorolojik büyüklük                       |
| Belirsizlik yöntemi      | Bootstrap Ensemble × MC Dropout          | **Aynen korunmuştur**                              | Metodolojinin özü                                                                                                  |
| Güven aralığı            | Yüzdelik tabanlı (%2.5 – %97.5)          | **Aynen korunmuştur**                              | Normallik varsayımı gerektirmez; bootstrap dağılımıyla tutarlıdır                                                  |
| Bootstrap türü           | Zaman serisine duyarlı yeniden örnekleme | **Moving Block Bootstrap (MBB)**                   | Klasik i.i.d. yeniden örnekleme zamansal otokorelasyonu yok eder                                                   |
| Fiziksel kısıt           | Negatif olmama + kapasite tavanı         | **Yalnızca negatif olmama cezası**                 | Işınım da negatif olamaz; ancak "kurulu güç tavanı" kısıtının ışınımda karşılığı yoktur                            |
| Metrikler                | PICP/PINW + tablo metrikleri             | **CP (=PICP), PINW, MPIW, Reliability, CWC, CRPS** | Kaynak makalenin raporlama formatı korunmuş, standart literatür tanımlarıyla tamamlanmıştır                        |

---

## 3. Veri kümesi

**Kaynak:** NASA POWER (Prediction Of Worldwide Energy Resources) saatlik veri servisi.
Dosya: `SolarData_Merve_All(16July).xlsx`, her il için ayrı bir sayfa (sheet).

**Kapsam (temizleme sonrası):**

| Özellik                      | Değer                               |
| ---------------------------- | ----------------------------------- |
| İller                        | Ankara, Antalya, Konya, Rize, Van   |
| Zaman çözünürlüğü            | Saatlik                             |
| Tarih aralığı                | 2019-06-30 00:00 – 2026-03-30 23:00 |
| İl başına satır              | 59.184 saat (≈ 6 yıl 9 ay)          |
| Toplam satır                 | 295.920                             |
| Ham satır (temizleme öncesi) | 61.392 / il                         |
| Kesilen satır                | 2.208 / il                          |

**İllerin seçimi** rastgele değildir: Antalya (Akdeniz, yüksek ışınım), Konya ve Ankara (İç
Anadolu karasal, yüksek ışınım–düşük nem), Van (Doğu Anadolu, yüksek rakım), Rize (Karadeniz,
yüksek bulutluluk ve yağış) farklı iklim rejimlerini temsil eder. Hedef değişkenin il bazında
betimleyici istatistikleri bu farkı doğrular:

| İl      | Ortalama (W/m²) | Std. sapma | Min  | Maks    |
| ------- | --------------- | ---------- | ---- | ------- |
| Ankara  | 193,97          | 275,26     | 0,00 | 1029,10 |
| Antalya | 206,03          | 287,01     | 0,00 | 1043,07 |
| Konya   | 203,01          | 284,44     | 0,00 | 1054,35 |
| Rize    | **153,57**      | 231,54     | 0,00 | 988,15  |
| Van     | 207,57          | 287,75     | 0,00 | 1215,88 |

Rize'nin belirgin şekilde düşük ortalaması, bulutluluğun ışınım üzerindeki etkisini gösterir ve
modelin il gömme vektöründen ne öğrenmesi gerektiğine dair doğrudan kanıttır.

**Ham değişkenler:**

| Sütun                    | Açıklama                                                           | Birim   |
| ------------------------ | ------------------------------------------------------------------ | ------- |
| `YEAR`, `MO`, `DY`, `HR` | Zaman damgası bileşenleri                                          | —       |
| `ALLSKY_SFC_SW_DWN`      | **Hedef.** Tüm gökyüzü koşullarında yüzeye gelen kısa dalga ışınım | W/m²    |
| `CLRSKY_SFC_SW_DWN`      | Açık gökyüzü (bulutsuz) referans ışınımı                           | W/m²    |
| `T2M`                    | 2 m sıcaklık                                                       | °C      |
| `RH2M`                   | 2 m bağıl nem                                                      | %       |
| `QV2M`                   | 2 m özgül nem                                                      | g/kg    |
| `T2MDEW`                 | 2 m çiy noktası sıcaklığı                                          | °C      |
| `PS`                     | Yüzey basıncı                                                      | kPa     |
| `WS10M`, `WS50M`         | 10 m / 50 m rüzgâr hızı                                            | m/s     |
| `WD10M`, `WD50M`         | 10 m / 50 m rüzgâr yönü                                            | derece  |
| `PRECTOTCORR`            | Düzeltilmiş toplam yağış                                           | mm/saat |
| `ALLSKY_KT`              | Açıklık indeksi — **kullanılmadı, silindi**                        | —       |

---

## 4. Veri ön işleme

**Uygulama:** `src/merve_solar/data.py`. Bu adım konfigürasyondan bağımsızdır: bir kez
çalıştırılıp `outputs/processed/base_features.parquet` olarak önbelleğe alınır ve tüm deneyler
aynı önbelleği kullanır. Böylece tüm deneyler *aynı* veri temeli üzerinde karşılaştırılabilir.

### 4.1 Zaman damgası oluşturma

`YEAR`, `MO`, `DY`, `HR` sütunlarından tek bir `datetime` sütunu üretilir ve seri kronolojik
olarak sıralanır.

### 4.2 Eksik veri sentinel'i (-999) ve kuyruk kesme

NASA POWER, eksik değerleri `-999` ile kodlar. Veri setinde iki tür `-999` bulunmaktadır:

1. **Kuyruk boşluğu (near-real-time gecikmesi):** 2026-03-31 00:00 – 2026-06-30 23:00 aralığında
   `ALLSKY_SFC_SW_DWN` ve `CLRSKY_SFC_SW_DWN` sütunları *tüm sayfalarda* `-999`'dur. Bu, NASA
   POWER'ın ışınım ürünlerini gerçek zamanlıya yakın modda geç yayınlamasından kaynaklanır.
   → Bu aralık **tamamen kesilmiştir** (`LAST_VALID_TIMESTAMP = 2026-03-30 23:00`, il başına
   2.208 satır).
2. **`ALLSKY_KT` sütunu:** Açıklık indeksi gece saatlerinde tanımsızdır; sütunun yaklaşık
   %50'si `-999`'dur. → Sütun **tümüyle düşürülmüştür**.

### 4.3 Doğrulama (fail-fast)

Ön işleme adımı sessizce düzeltme yapmaz; beklenmeyen durumda **hata fırlatır**:

- Kesilen satır sayısı tam olarak 2.208 değilse → `ValueError`
- Kesme sonrası herhangi bir `-999` kalırsa → `ValueError`
- Herhangi bir `NaN` varsa → `ValueError`

Gerekçe: kaynak dosya güncellendiğinde eksik veri deseni değişebilir; sessizce devam etmek
yayımlanmış sayıları geçersiz kılacak bir hataya yol açar. Bu davranış `tests/test_data.py` ile
gerçek veri üzerinde test edilmektedir.

> **Not (kayıp veri doldurma yapılmamıştır):** Kuyruk kesmesi sonrasında seride hiçbir eksik
> değer veya saat atlaması kalmamaktadır. Bu nedenle interpolasyon/doldurma (imputation)
> uygulanmamıştır — makalede bu durum açıkça belirtilmelidir, çünkü zaman serisi çalışmalarında
> doldurma yöntemi genellikle sorgulanan bir tercihtir.

---

## 5. Öznitelik mühendisliği

### 5.1 Döngüsel (cyclical) kodlama

Saat, yılın günü ve rüzgâr yönü **döngüsel** büyüklüklerdir: 23. saat ile 0. saat komşudur,
359° ile 1° komşudur. Ham sayısal değer olarak verildiğinde model bu komşuluğu göremez ve
yapay bir süreksizlik oluşur. Bu nedenle her biri sinüs–kosinüs çiftine dönüştürülmüştür:

$$
\text{hour\_sin} = \sin\!\left(\frac{2\pi \cdot \text{HR}}{24}\right), \qquad
\text{hour\_cos} = \cos\!\left(\frac{2\pi \cdot \text{HR}}{24}\right)
$$

$$
\text{doy\_sin} = \sin\!\left(\frac{2\pi \cdot \text{DOY}}{365{,}25}\right), \qquad
\text{doy\_cos} = \cos\!\left(\frac{2\pi \cdot \text{DOY}}{365{,}25}\right)
$$

$$
\text{WD\_sin} = \sin(\text{WD} \cdot \pi/180), \qquad
\text{WD\_cos} = \cos(\text{WD} \cdot \pi/180)
$$

`doy` için 365,25 kullanılması artık yılları hesaba katar. Saat kodlaması günlük (diurnal)
döngüyü, gün-of-year kodlaması ise mevsimsel döngüyü modele açıkça sunar — güneş ışınımı için
bu iki döngü sinyalin baskın bileşenleridir.

### 5.2 Nihai öznitelik kümesi ($F = 18$)

`NUMERIC_FEATURE_COLUMNS` (`src/merve_solar/config.py`) — sıra kodda tanımlı sıradır:

| #     | Öznitelik                                          | Tür                                                        |
| ----- | -------------------------------------------------- | ---------------------------------------------------------- |
| 1     | `ALLSKY_SFC_SW_DWN`                                | **Hedefin kendi gecikmeli değerleri (özbağlanımlı girdi)** |
| 2     | `CLRSKY_SFC_SW_DWN`                                | Açık gökyüzü referans ışınımı                              |
| 3–7   | `T2M`, `RH2M`, `QV2M`, `T2MDEW`, `PS`              | Sıcaklık, nem, basınç                                      |
| 8–10  | `WS10M`, `WS50M`, `PRECTOTCORR`                    | Rüzgâr hızı, yağış                                         |
| 11–14 | `WD10M_sin`, `WD10M_cos`, `WD50M_sin`, `WD50M_cos` | Rüzgâr yönü (döngüsel)                                     |
| 15–16 | `hour_sin`, `hour_cos`                             | Günlük (diurnal) döngü                                     |
| 17–18 | `doy_sin`, `doy_cos`                               | Mevsimsel döngü                                            |

Hedef değişkenin kendisi girdi penceresinde yer alır (özbağlanımlı yapı); bu **veri sızıntısı
değildir**, çünkü pencere yalnızca geçmiş $L$ saati içerir, tahmin edilen $H$ saat penceredeki
hiçbir girdide bulunmaz (bkz. §8).

### 5.3 İl gömmesi (city embedding)

İl kimliği one-hot olarak değil, **öğrenilebilir yoğun vektör** olarak modele girer:
$\mathbf{e}_c \in \mathbb{R}^{d}$, $d = 4$ (`city_embedding_dim`). Bu vektör LSTM girdisine her
zaman adımında eklenir (bkz. §9). One-hot yerine gömme kullanılmasının nedeni, modelin iller
arasında *benzerlik* öğrenebilmesidir (örn. Konya–Ankara'nın birbirine, Rize'ye kıyasla daha
yakın konumlanması); one-hot temsilde tüm iller birbirine eşit uzaklıktadır.

---

## 6. Kronolojik veri bölme

**Uygulama:** `compute_split_boundaries()`, `src/merve_solar/windows.py`.

Rastgele bölme **kullanılmamıştır**; zaman serilerinde rastgele bölme geleceği geçmişe sızdırır.
Veri kronolojik olarak üçe ayrılır (en eski → en yeni):

| Küme                   | Oran                           | Tarih aralığı (varsayılan)          |
| ---------------------- | ------------------------------ | ----------------------------------- |
| Eğitim (train)         | `train_ratio = 0,74`           | 2019-06-30 00:00 – 2024-06-27 19:00 |
| Doğrulama (validation) | `val_ratio = 0,11`             | 2024-06-27 20:00 – 2025-03-26 01:00 |
| Test                   | $1 - 0{,}74 - 0{,}11 = 0{,}15$ | 2025-03-26 02:00 – 2026-03-30 23:00 |

Sınırlar ilk ilin saat sayısı üzerinden hesaplanır ve tüm illere aynı tarih sınırları uygulanır
(tüm iller aynı zaman aralığını kapsadığı için bu tutarlıdır).

> **Bölme oranlarının gerekçesi (makalede mutlaka belirtilmeli):**
> `0,74 / 0,11 / 0,15` oranları keyfi değildir. Bu oranlarla test kümesi **tam olarak bir
> mevsimsel yıla** (369 gün) denk gelir. Güneş ışınımında bu kritik bir tasarım kararıdır:
> test kümesi yalnızca yaz aylarına düşerse model olduğundan iyi, yalnızca kışa düşerse
> olduğundan kötü görünür. Tam bir yıl, tüm mevsimleri dengeli biçimde içerir ve mevsimsel
> yanlılığı ortadan kaldırır. Kaynak makalenin kendi 64/16/20 bölmesi karşılaştırma amacıyla
> ayrı bir deney konfigürasyonu olarak (`config_split_paper_64_16_20`) korunmuştur.

---

## 7. Ölçekleme ve sızıntı kontrolü

**Uygulama:** `src/merve_solar/scaling.py`.

18 sayısal öznitelik `StandardScaler` ile standartlaştırılır:

$$
z = \frac{x - \mu_{\text{train}}}{\sigma_{\text{train}}}
$$

**Kritik nokta:** $\mu$ ve $\sigma$ **yalnızca eğitim tarih aralığındaki satırlardan** hesaplanır
($\text{datetime} \le \text{train\_end}$), ardından tüm veriye (eğitim, doğrulama, test)
uygulanır. Ölçekleyicinin tüm veri üzerinde fit edilmesi, test kümesinin istatistiklerinin
eğitime sızması demektir ve yayımlanacak sonuçları geçersiz kılar.

Ölçekleyici tek ve **küreseldir** (iller havuzlanarak fit edilir), il başına ayrı ölçekleyici
kullanılmaz — bu, tek küresel model tasarımıyla tutarlıdır.

Ölçekleyici her deneyde `checkpoints/scaler.joblib` olarak kaydedilir. Model çıktıları
ölçeklenmiş uzayda üretildiği için, tüm metrikler hesaplanmadan önce hedef değişkenin ölçeği
tersine çevrilir:

$$
\hat{y}_{\text{W/m}^2} = \hat{z} \cdot \sigma_{\text{target}} + \mu_{\text{target}}
$$

**Tüm metrikler ve şekiller fiziksel birimde (W/m²) raporlanır**, ölçeklenmiş birimde değil.

---

## 8. Kayan pencere (sliding window) oluşturma

**Uygulama:** `build_experiment_windows()`, `src/merve_solar/windows.py`.

Her pencere $(L + H)$ saatlik kesintisiz bir dilimdir: ilk $L$ saat girdi, sonraki $H$ saat
hedeftir. Pencereler `window_stride` adımıyla kaydırılır (varsayılan: 1 saat).

$$
\mathbf{X}_i \in \mathbb{R}^{L \times F}, \qquad
\mathbf{y}_i \in \mathbb{R}^{H}, \qquad
c_i \in \{0,\dots,4\}
$$

**İki katı kural:**

1. **Pencereler il sınırını aşamaz.** Pencereler her il için ayrı ayrı üretilir, sonra
   havuzlanır. (Aksi hâlde Van'ın son saatleri Ankara'nın ilk saatleriyle aynı pencerede
   birleşirdi.) Ayrıca her il içinde saatlerin kesintisiz ardışık olduğu doğrulanır; kesinti
   varsa hata fırlatılır.

2. **Pencereler bölme sınırını aşamaz.** Bir pencere ancak *tüm* $(L+H)$ süresi ilgili bölmenin
   tarih aralığına düşüyorsa o bölmeye atanır:
   
   - eğitim: $\text{pencere\_sonu} \le \text{train\_end}$
   - doğrulama: $\text{pencere\_başı} > \text{train\_end}$ **ve** $\text{pencere\_sonu} \le \text{val\_end}$
   - test: $\text{pencere\_başı} > \text{val\_end}$
   
   Sınırı kesen (straddling) pencereler **atılır**. Bu, eğitim penceresinin hedefinin doğrulama
   dönemine taşmasını, yani sızıntıyı engeller. Kayıp, bölme başına en fazla $(L+H-1)$ penceredir
   ve toplam veri hacmi yanında ihmal edilebilir.

**Varsayılan konfigürasyonla elde edilen pencere sayıları (5 il toplamı):**

| Küme      | Pencere sayısı | Tensör boyutu          |
| --------- | -------------- | ---------------------- |
| Eğitim    | 218.745        | $(218745,\, 24,\, 18)$ |
| Doğrulama | 32.315         | $(32315,\, 24,\, 18)$  |
| Test      | 44.155         | $(44155,\, 24,\, 18)$  |

Test kümesindeki toplam skaler tahmin sayısı: $44.155 \times 24 = 1.059.720$.

---

## 9. Model mimarisi

**Uygulama:** `SolarLSTM`, `src/merve_solar/model.py`.

```
Girdi: X (batch, L=24, F=18)   ve   city_id (batch,)
   │
   ├─ Embedding(5 → 4) ──► e_c, her zaman adımına kopyalanır: (batch, 24, 4)
   │
   ├─ concat([X, e_c])  ──────────────────────────────► (batch, 24, 22)
   │
   ├─ LSTM(input=22, hidden=64, num_layers=2, dropout=0.3, batch_first=True)
   │        └─► son zaman adımının gizli durumu: (batch, 64)
   │
   ├─ Dropout(0.3)
   │
   └─ Head: Linear(64→32) → ReLU → Dropout(0.3) → Linear(32→24)
                                                        │
                                            Çıktı: ŷ (batch, H=24)
```

### 9.1 `hidden_sizes` parametresinin yorumu (dikkat)

`hidden_sizes` listesi **iki işi birden** yapar:

- `hidden_sizes[0]` → LSTM'in gizli durum boyutu
- `len(hidden_sizes)` → **yığılmış LSTM katmanı sayısı**
- `hidden_sizes[1:]` → çıkış başlığındaki (head) ek `Linear` katmanların boyutları

Varsayılan `[64, 32]` şu anlama gelir: **2 katmanlı** LSTM (gizli boyut 64) + `Linear(64→32)`
→ ReLU → Dropout → `Linear(32→24)` başlığı. Toplam öğrenilebilir parametre: **58.700**.
`[128, 64, 32]` ise 3 katmanlı LSTM(128) + iki katmanlı başlık demektir.

> Makalede mimari tablosu verilirken bu yorum açıkça yazılmalıdır; aksi hâlde `[64, 32]`
> gösterimi "64 ve 32 nöronlu iki LSTM katmanı" gibi yanlış okunabilir.

### 9.2 Dropout'un konumu

Dropout üç yerde bulunur ve **hepsi MC Dropout'un rastgelelik kaynağıdır**:
LSTM katmanları arasında (yalnızca `num_layers > 1` iken PyTorch bunu uygular), LSTM çıkışından
sonra (`head_dropout`) ve başlıktaki her gizli katmandan sonra.

### 9.3 BatchNorm neden yok?

Modelde hiçbir yerde `BatchNorm` **kullanılmamıştır**. Gerekçe: MC Dropout çıkarımı modeli
`.train()` modunda tutar (§11.1); bu modda `BatchNorm` çalışan istatistiklerini (running mean/var)
güncellemeye devam eder ve çıkarım sırasında modelin durumunu bozar. Normalizasyon ihtiyacı
girdi tarafında `StandardScaler` ile karşılanmıştır.

---

## 10. Eğitim yordamı

**Uygulama:** `train_model()`, `src/merve_solar/train.py`.

### 10.1 Kayıp fonksiyonu — fiziksel kısıtlı MSE

$$
\mathcal{L}(\hat{\mathbf{y}}, \mathbf{y}) \;=\;
\underbrace{\frac{1}{N H}\sum_{i,h}\left(\hat{y}_{ih} - y_{ih}\right)^2}_{\text{MSE}}
\;+\;
\lambda \cdot \underbrace{\frac{1}{N H}\sum_{i,h}\left[\max(0,\, -\hat{y}_{ih})\right]^2}_{\text{negatif olmama cezası}}
$$

$\lambda = 0{,}1$ (`nonneg_penalty_weight`). İkinci terim yalnızca **negatif** tahminleri
cezalandırır; pozitif tahminlerde katkısı sıfırdır. Güneş ışınımı fiziksel olarak negatif
olamayacağı için bu, kaynak makalenin fizik-bilgili (physics-informed) kısıt mekanizmasının
ışınım problemine doğrudan aktarılabilen bileşenidir. Kaynak makaledeki "kurulu güç tavanı"
kısıtının ışınımda karşılığı olmadığından uygulanmamıştır.

> **Uyarı (uygulama detayı):** Ceza terimi *ölçeklenmiş* uzayda hesaplanır. Standartlaştırma
> sonrası gece saatlerinin ışınım değeri negatif bir $z$ skoruna karşılık gelir; dolayısıyla
> bu terim "fiziksel sıfır" değil, "ölçeklenmiş sıfır" altını cezalandırır. Terim düzenlileştirici
> (regularizer) olarak çalışmaktadır; kesin fiziksel yorum için cezanın ters ölçekleme sonrası
> uygulanması gerekir. Makalede bu terim "yumuşak negatiflik düzenlileştiricisi" olarak
> tanımlanmalıdır.

### 10.2 Optimizasyon ayarları

| Bileşen                  | Değer / Yöntem                                                                                                         |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------------- |
| Optimizasyon algoritması | Adam                                                                                                                   |
| Başlangıç öğrenme oranı  | $10^{-3}$ (`learning_rate`)                                                                                            |
| Yığın (batch) boyutu     | 128                                                                                                                    |
| Maksimum epok            | 100 (`max_epochs`)                                                                                                     |
| Öğrenme oranı planlayıcı | `ReduceLROnPlateau` — doğrulama kaybı 7 epok (`lr_reduce_patience`) iyileşmezse LR $\times 0{,}5$ (`lr_reduce_factor`) |
| Erken durdurma           | Doğrulama kaybı 10 epok (`early_stop_patience`) iyileşmezse eğitim durur                                               |
| Model seçimi             | **En iyi doğrulama kaybını veren epoktaki ağırlıklar** saklanır ve eğitim sonunda geri yüklenir (son epok değil)       |

Doğrulama kaybı da aynı kısıtlı kayıp fonksiyonuyla, `model.eval()` modunda ve `torch.no_grad()`
altında hesaplanır. Eğitim ve doğrulama kayıpları epok bazında kaydedilir (`history`) ve deney
günlüğüne (`log.txt`) yazılır.

---

## 11. Belirsizlik tahmini (UQ) katmanı

Bu bölüm çalışmanın metodolojik çekirdeğidir. İki bağımsız belirsizlik kaynağı ayrı ayrı
modellenir ve tek bir öngörü dağılımında birleştirilir.

```
                        Eğitim kümesi (218.745 pencere)
                                     │
        ┌────────────────┬───────────┴───────────┬────────────────┐
        │                │                       │                │
  MBB örneklem 1   MBB örneklem 2          MBB örneklem 3   ...  MBB örneklem B
        │                │                       │                │
     LSTM_1           LSTM_2                  LSTM_3           LSTM_B
        │                │                       │                │
   MC Dropout       MC Dropout              MC Dropout       MC Dropout
   T=100 geçiş      T=100 geçiş             T=100 geçiş      T=100 geçiş
        │                │                       │                │
        └────────────────┴───────────┬───────────┴────────────────┘
                                     ▼
                    Havuzlanmış tahmin dağılımı:  B × T = 800 örnek
                                     │
                ┌────────────────────┼────────────────────┐
                ▼                    ▼                    ▼
            Ortalama            Std. sapma      %2.5 / %97.5 yüzdelikleri
                │                    │                    │
                └────────────────────┴──────────┬─────────┘
                                                ▼
                          Nokta tahmini + %95 güven aralığı
```

### 11.1 Monte Carlo Dropout — *epistemik* (model parametresi) belirsizliği

**Uygulama:** `mc_dropout_predict()`, `src/merve_solar/mc_dropout.py`.

Standart çıkarımda `model.eval()` çağrılır ve dropout kapatılır. MC Dropout'ta ise **dropout
açık bırakılır**:

```python
model.train()          # dropout AKTİF — kasıtlı olarak .eval() değil
with torch.no_grad():  # gradyan hesabı yok; yalnızca ileri geçiş
    for _ in range(T):
        preds.append(model(X, city_id))
```

Her ileri geçişte farklı nöron alt kümesi kapatıldığı için, **aynı girdi $T$ kez verildiğinde
$T$ farklı tahmin** elde edilir. Bu, ağırlıklar üzerindeki sonsal (posterior) dağılımdan
yaklaşık örnekleme olarak yorumlanır (Gal & Ghahramani, 2016) ve modelin *kendi bilgisizliğini*,
yani epistemik belirsizliği yakalar.

Çıktı tensörü: $(T,\, N,\, H)$. Varsayılan $T = 100$ (`mc_dropout_passes`).

> `dropout_rate = 0` yapılırsa MC Dropout her geçişte özdeş tahmin üretir ve epistemik
> belirsizlik sıfırlanır. Bu nedenle dropout oranı daima pozitif olmalıdır.

### 11.2 Bootstrap Ensemble — *veri/örneklem* belirsizliği

**Uygulama:** `resample_train_split()`, `src/merve_solar/bootstrap.py`.

$B$ adet model, eğitim kümesinden yeniden örneklenmiş $B$ farklı veri kümesi üzerinde
eğitilir. Modeller arasındaki tahmin farkı, eğitim örnekleminin sonluluğundan kaynaklanan
belirsizliği temsil eder.

**Neden klasik bootstrap değil?** Klasik i.i.d. yeniden örnekleme (`sklearn.utils.resample`)
pencereleri bağımsızmış gibi ele alır ve zamansal otokorelasyon yapısını yok eder — kaynak
makale de zaman serisine duyarlı yeniden örnekleme önerir. Bu nedenle **Moving Block Bootstrap
(MBB)** kullanılmıştır:

$n$ pencerelik bir il dizisi ve $\ell$ blok uzunluğu için:

1. Blok sayısı $k = \lceil n/\ell \rceil$ hesaplanır.
2. $k$ adet başlangıç indisi $\{s_1,\dots,s_k\}$, $\mathcal{U}\{0, n-\ell\}$ dağılımından
   **yerine koyarak** çekilir.
3. Her $s_j$ için $[s_j,\, s_j+\ell)$ ardışık blok alınır, bloklar birleştirilir ve ilk $n$
   indise kırpılır.

Böylece blok *içinde* zamansal sıra korunur, bloklar *arası* ise yeniden örnekleme çeşitliliği
sağlanır. Varsayılan $\ell = 168$ pencere $\approx$ 1 hafta (`bootstrap_block_length`);
bu uzunluk günlük döngünün tamamını ve haftalık düzeydeki hava rejimlerini blok içinde tutar.

Yeniden örnekleme **il bazında bağımsız** yapılır ve sonuçlar havuzlanır; böylece her replikada
her ilin temsil edilmesi garanti altına alınır.

Varsayılan $B = 8$ (`n_bootstrap`); kaynak makale 5–10 aralığını önerir.

> **$B = 1$ özel durumu:** `n_bootstrap = 1` ayrı bir kod yolu değildir; yeniden örnekleme
> atlanır, tek bir LSTM eğitilir ve yalnızca MC Dropout ile skorlanır. Hızlı doğrulama
> (smoke test) ve "yalnızca MC Dropout" ablasyonu için kullanılır.

### 11.3 Hibrit havuzlama

Her replikanın $T$ geçişi, replikalar boyunca birleştirilerek tek bir dağılım oluşturur:

$$
\mathcal{P} = \left\{\hat{y}^{(b,t)}\right\}_{b=1..B,\; t=1..T}, \qquad
|\mathcal{P}| = B \cdot T = 8 \times 100 = 800 \text{ örnek}
$$

Havuzlama tensör boyutuyla: $(B \cdot T,\, N,\, H) = (800,\, 44155,\, 24)$. Havuzlama
**ölçeklenmiş uzayda** yapılır, ardından tüm dağılım W/m²'ye geri dönüştürülür.

### 11.4 Güven aralığı — yüzdelik tabanlı

$$
\hat{\mu}_{ih} = \frac{1}{|\mathcal{P}|}\sum_{s} \hat{y}^{(s)}_{ih}, \qquad
\hat{\sigma}_{ih} = \sqrt{\frac{1}{|\mathcal{P}|}\sum_{s}\left(\hat{y}^{(s)}_{ih} - \hat{\mu}_{ih}\right)^2}
$$

$$
\boxed{\;\ell_{ih} = Q_{2{,}5\%}\!\left(\mathcal{P}_{ih}\right), \qquad
u_{ih} = Q_{97{,}5\%}\!\left(\mathcal{P}_{ih}\right)\;}
$$

**Neden $\hat{\mu} \pm 1{,}96\hat{\sigma}$ değil?** $\pm 1{,}96\sigma$ formülü öngörü
dağılımının normal olduğunu varsayar. Bootstrap × MC Dropout dağılımı genellikle normal
değildir ve güneş ışınımında özellikle çarpıktır (gece saatlerinde dağılım sıfırda yığılır,
gündüz bulut geçişlerinde çok modlu olabilir). Yüzdelik tabanlı aralık dağılım varsayımı
gerektirmez ve bootstrap yaklaşımıyla tutarlıdır. **Bu, makalede vurgulanması gereken bilinçli
bir metodolojik tercihtir.**

---

## 12. Başarım metrikleri

**Uygulama:** `src/merve_solar/metrics.py`. Tüm metrikler ters ölçekleme sonrası, W/m² biriminde
hesaplanır. Hedef kapsama düzeyi $\mu_{\text{hedef}} = 0{,}95$.

### 12.1 Nokta tahmini metrikleri

$$
\text{RMSE} = \sqrt{\frac{1}{NH}\sum_{i,h}\left(y_{ih} - \hat{\mu}_{ih}\right)^2}
\qquad
\text{MAE} = \frac{1}{NH}\sum_{i,h}\left|y_{ih} - \hat{\mu}_{ih}\right|
$$

İkisi de W/m² birimindedir ve düşük olması iyidir. RMSE büyük hataları daha ağır cezalandırır;
MAE aykırı değerlere daha dayanıklıdır.

### 12.2 Aralık kalitesi metrikleri

**Coverage Probability (CP)** — kaynak makaledeki PICP ile aynıdır. Gerçek değerlerin öngörü
aralığına düşme oranı:

$$
\text{CP} = \frac{1}{NH}\sum_{i,h}\mathbb{1}\left\{\ell_{ih} \le y_{ih} \le u_{ih}\right\}
$$

Hedef $\approx 0{,}95$. Belirgin şekilde düşük olması aralıkların **aşırı dar/aşırı güvenli**
olduğunu gösterir.

**PINW (Prediction Interval Normalized Width)** — aralık genişliğinin, o alt kümedeki gerçek
değer aralığına normalize edilmiş hâli (iller ve ufuk adımları arası karşılaştırılabilirlik için):

$$
\text{PINW} = \frac{\frac{1}{NH}\sum_{i,h}\left(u_{ih}-\ell_{ih}\right)}{\max(y) - \min(y)}
$$

**MPIW (Mean Prediction Interval Width)** — aynı genişlik, fiziksel birimde:

$$
\text{MPIW} = \frac{1}{NH}\sum_{i,h}\left(u_{ih}-\ell_{ih}\right) \quad [\text{W/m}^2]
$$

**Reliability** — kalibrasyon açığı:

$$
\text{Reliability} = \left|\text{CP} - 0{,}95\right|
$$

> Bu tanım kaynak makalenin raporladığı PCNN değeriyle birebir örtüşmektedir
> ($|0{,}9472 - 0{,}95| = 0{,}0028$), dolayısıyla karşılaştırma geçerlidir.

**CWC (Coverage Width Criterion)** — kapsama ve genişliği tek skorda birleştiren Khosravi
ölçütü:

$$
\text{CWC} = \text{PINW}\cdot\left(1 + \gamma \cdot e^{-\eta\left(\text{CP}-\mu_{\text{hedef}}\right)}\right),
\qquad
\gamma = \begin{cases} 1, & \text{CP} < \mu_{\text{hedef}} \\ 0, & \text{CP} \ge \mu_{\text{hedef}}\end{cases}
$$

$\eta = 50$. Kapsama hedefin altına düştüğünde ceza **üstel** olarak büyür; bu nedenle çok
büyük bir CWC, dar ama güvenilmez aralıkların açık göstergesidir.

**CRPS (Continuous Ranked Probability Score)** — yalnızca aralığı değil, **öngörü dağılımının
tamamını** değerlendiren uygun (proper) skorlama kuralı:

$$
\text{CRPS}(F, y) = \mathbb{E}\left|X - y\right| - \tfrac{1}{2}\,\mathbb{E}\left|X - X'\right|,
\qquad X, X' \sim F \text{ (bağımsız)}
$$

Sonlu $S$ örnekli tahmin edici, sıralı örnekler $x_{(1)} \le \dots \le x_{(S)}$ ile
$O(S\log S)$ karmaşıklıkta hesaplanır:

$$
\mathbb{E}\left|X-X'\right| \approx \frac{2}{S^2}\sum_{i=1}^{S}(2i - S - 1)\,x_{(i)}
$$

W/m² birimindedir; düşük olması iyidir, mükemmel deterministik tahminde 0'dır.

### 12.3 Raporlama düzeyleri

Her metrik **üç düzeyde** hesaplanır:

| Düzey              | Dosya                            | İçerik                                    |
| ------------------ | -------------------------------- | ----------------------------------------- |
| Toplulaştırılmış   | ledger satırı                    | Tüm iller + tüm ufuk adımları havuzlanmış |
| İl bazında         | `metrics/results_summary.csv`    | Aggregate + 5 il için birer satır         |
| Ufuk adımı bazında | `metrics/results_by_horizon.csv` | 1 saat ileri … 24 saat ileri, 24 satır    |

### 12.4 Metriklerin birlikte yorumlanması

Metrikler **tek başına** yorumlanmamalıdır:

- Düşük PINW + düşük CP = **kötü model** (aşırı güvenli, dar aralık). CWC bu durumu yakalar.
- CP $\approx$ 1,0 + çok yüksek PINW = teknik olarak "güvenli" ama bilgi taşımayan aralık.
- İyi model: CP $\approx 0{,}95$, Reliability $\approx 0$, PINW/MPIW/CWC/CRPS mümkün olduğunca düşük.

---

## 13. Deney protokolü ve tekrarlanabilirlik

**Uygulama:** `ExperimentConfig` (`config.py`), `run_experiment()` (`experiment.py`).

### 13.1 Konfigürasyon = deneyin birimi

Her eğitim+değerlendirme koşusu tek bir `ExperimentConfig` nesnesiyle tanımlanır ve JSON olarak
saklanır. `experiment_id` hem çıktı klasörünün hem de karşılaştırma tablosundaki satırın adıdır.
Bu sayede makaledeki her sayı, onu üreten tam konfigürasyona geri izlenebilir.

**Varsayılan hiperparametreler (makaledeki mimari tablosu için):**

| Parametre            | Varsayılan | Parametre                | Varsayılan |
| -------------------- | ---------- | ------------------------ | ---------- |
| `lookback_hours`     | 24         | `learning_rate`          | $10^{-3}$  |
| `horizon_hours`      | 24         | `batch_size`             | 128        |
| `window_stride`      | 1          | `max_epochs`             | 100        |
| `train_ratio`        | 0,74       | `early_stop_patience`    | 10         |
| `val_ratio`          | 0,11       | `lr_reduce_factor`       | 0,5        |
| `hidden_sizes`       | [64, 32]   | `lr_reduce_patience`     | 7          |
| `dropout_rate`       | 0,3        | `nonneg_penalty_weight`  | 0,1        |
| `city_embedding_dim` | 4          | `n_bootstrap`            | 8          |
| `seed`               | 42         | `mc_dropout_passes`      | 100        |
|                      |            | `bootstrap_block_length` | 168        |

### 13.2 Çıktılar

```
outputs/experiments/<experiment_id>/
├── config.json                     # koşunun tam konfigürasyonu
├── log.txt                         # cihaz, bölme tarihleri, replika bazında val loss, süre
├── checkpoints/
│   ├── bootstrap_model_<b>.pt      # her replikanın ağırlıkları
│   └── scaler.joblib               # fit edilmiş ölçekleyici
├── metrics/
│   ├── results_summary.csv         # Aggregate + il bazında
│   └── results_by_horizon.csv      # 1–24 saat ufuk adımları
└── figures/
    ├── forecast_ci_<il>.png        # temsilî 24 saatlik tahmin + %95 CI
    ├── rmse_vs_horizon.png
    └── cp_vs_horizon.png

outputs/experiments_ledger.csv      # KOŞU BAŞINA BİR SATIR — makale tablolarının kaynağı
```

`experiments_ledger.csv`, her koşunun temel konfigürasyon alanlarını ve toplulaştırılmış
metriklerini yan yana tutar; makaledeki karşılaştırma tabloları doğrudan bu dosyadan üretilir.

### 13.3 Tekrarlanabilirlik

- Tüm rastgelelik kaynakları tohumlanır: `random`, `numpy`, `torch` (`set_seed`).
- Her bootstrap replikası için tohum kaydırılır ($\text{seed} + b + 1$); böylece replikalar
  birbirinden farklı ama koşudan koşuya aynıdır.
- MBB yeniden örneklemesi tek bir `numpy.random.default_rng(seed)` üreticisiyle yapılır.
- Konfigürasyon, ölçekleyici ve tüm model ağırlıkları diske yazılır; sonuçlar yeniden
  üretilebilir.

### 13.4 Karşılaştırılabilirlik kuralları (makale tabloları için kritik)

- Bir `experiment_id` **yeniden kullanılmamalıdır**; ledger'a satır eklenir, üzerine yazılmaz.
- Bir koşuda **tek bir eksen** değiştirilmelidir; aksi hâlde tablodaki fark hangi değişikliğe
  ait olduğu belirlenemez.
- Varsayılan bir değer değiştirilirse, eski ledger satırları o değeri kaydetmediği için
  geçersizleşir — varsayılanı değiştirmek yerine yeni bir konfigürasyon eklenmelidir.
- Karşılaştırma modelleri (GRU, SVM, RF, MLP …) **aynı pencereler, aynı kronolojik bölme,
  aynı eğitim-üzerinde-fit ölçekleyici ve aynı metrik kodu** ile çalıştırılmalıdır.

### 13.5 Hiperparametre taraması

`configs/experiment_grid.py` içindeki eksenler:

| Eksen                   | Değerler                          | Kaynak                                    |
| ----------------------- | --------------------------------- | ----------------------------------------- |
| Gizli katman yapısı     | [32,16], [64,32], [128,64]        | Kaynak makale Tablo 6                     |
| Dropout oranı           | 0,1 / 0,2 / 0,3                   | Kaynak makale Tablo 6                     |
| Geçmiş pencere uzunluğu | 12 / 24 / 48 saat                 | Bu çalışmaya özgü (PCNN'de karşılığı yok) |
| Bölme oranı             | 0,74/0,11/0,15 vs. 0,64/0,16/0,20 | Bizim tasarımımız vs. kaynak makale       |

---

## 14. Hesaplama ortamı

- **Çatı:** PyTorch (≥2.2), scikit-learn (ölçekleme), pandas/numpy, matplotlib.
- **Cihaz seçimi otomatiktir:** MPS (Apple Silicon) → CUDA (Nvidia) → CPU sırasıyla denenir
  (`get_device()`); kullanılan cihaz her koşunun `log.txt` dosyasına yazılır.
- **Süre:** Tam konfigürasyon (8 replika × 100 MC geçiş) donanıma ve erken durdurmanın
  devreye girdiği epoğa göre yaklaşık 30 dakika – birkaç saat sürer. Hızlı doğrulama
  konfigürasyonu (`n_bootstrap=1`, `max_epochs=5`, `mc_dropout_passes=10`) birkaç dakikadır.
- **Bağımlılık yönetimi:** `uv` + `uv.lock` ile sürümler sabitlenmiştir (tekrarlanabilirlik).

---

## 15. Makale "Yöntem" bölümü için taslak paragraf

> Bu çalışmada, Türkiye'nin farklı iklim kuşaklarında yer alan beş ili için saatlik küresel
> yatay güneş ışınımının 24 saat ileriye dönük tahmini amacıyla, belirsizlik tahmini yeteneğine
> sahip bir derin öğrenme çerçevesi önerilmiştir. NASA POWER veri servisinden elde edilen
> 2019–2026 dönemine ait saatlik meteorolojik veriler (il başına 59.184 saat) kullanılmıştır.
> Saat, yılın günü ve rüzgâr yönü değişkenleri, döngüsel yapılarının korunması amacıyla
> sinüs–kosinüs çiftlerine dönüştürülmüş; toplam 18 sayısal öznitelik elde edilmiştir. Veri,
> zamansal sızıntıyı önlemek amacıyla kronolojik olarak %74 eğitim, %11 doğrulama ve %15 test
> olarak bölünmüş; bu oranlar test kümesinin tam bir mevsimsel yılı kapsayacak biçimde
> seçilmiştir. Standartlaştırma parametreleri yalnızca eğitim dönemi üzerinden hesaplanmıştır.
> Tahmin modeli, il kimliğini 4 boyutlu öğrenilebilir bir gömme vektörü olarak alan iki
> katmanlı bir LSTM ağıdır (gizli boyut 64) ve 24 saatlik girdi penceresinden 24 saatlik
> tahmini tek bir ileri geçişte üretmektedir. Model, ortalama kare hata ve ışınımın negatif
> olamayacağı fiziksel kısıtını yansıtan yumuşak bir düzenlileştirme teriminden oluşan bileşik
> bir kayıp fonksiyonu ile eğitilmiştir. Belirsizlik tahmini için Bootstrap Ensemble ve Monte
> Carlo Dropout yöntemleri hibrit biçimde kullanılmıştır: zamansal otokorelasyonun korunması
> amacıyla hareketli blok bootstrap (blok uzunluğu 168 saat) ile oluşturulan sekiz farklı
> eğitim kümesi üzerinde sekiz model eğitilmiş, her model çıkarım aşamasında dropout etkin
> tutularak 100 kez çalıştırılmış ve elde edilen 800 tahmin tek bir öngörü dağılımı olarak
> değerlendirilmiştir. %95 güven aralıkları, normallik varsayımı gerektirmemesi nedeniyle
> yüzdelik tabanlı olarak (%2,5–%97,5) hesaplanmıştır. Model başarımı RMSE ve MAE'nin yanı sıra
> kapsama olasılığı (CP), normalize edilmiş aralık genişliği (PINW), ortalama aralık genişliği
> (MPIW), güvenilirlik, kapsama-genişlik ölçütü (CWC) ve sürekli sıralı olasılık skoru (CRPS)
> metrikleriyle; toplulaştırılmış, il bazında ve tahmin ufkunun her adımı için ayrı ayrı
> değerlendirilmiştir.

---

## 16. Bilinen sınırlılıklar ve açık işler

**Makalede tartışılması gereken sınırlılıklar:**

1. **Gece saatleri metrikleri şişirir.** Işınımın sıfır olduğu gece saatleri tüm bölmelerde yer
   almaktadır. Bu saatler tahmin edilmesi kolay olduğundan MAE/RMSE'yi olduğundan iyi, CP'yi ise
   olduğundan yüksek gösterir. **Yalnızca gündüz saatlerini (örn. $\text{ALLSKY} > 0$ veya güneş
   yükseklik açısı $> 0$) kapsayan ek bir değerlendirme** literatürle adil karşılaştırma için
   gereklidir.
2. **Negatiflik cezası ölçeklenmiş uzayda uygulanmaktadır** (§10.1 uyarısı).
3. **Tek bir tohum (seed).** Sonuçlar tek bir tohumla üretilmiştir; çoklu tohumla ortalama ±
   standart sapma raporlanması istatistiksel olarak daha güçlü olur.
4. **Dış (exogenous) girdiler gerçek gözlemdir.** Model, tahmin ufkunda değil yalnızca geçmiş
   pencerede meteorolojik değişken kullanmaktadır; operasyonel bir sistemde bu değişkenlerin
   sayısal hava tahmini (NWP) çıktısı olarak gelmesi gerekir.
5. **Kalibrasyon sonrası düzeltme yapılmamıştır** (örn. conformal prediction); CP hedeften
   saparsa bu bir sonraki iyileştirme adayıdır.

**Açık işler (bkz. `TODOs.md`):**

- `CLRSKY_SFC_SW_DWN` sütununun çıkarılması kararı — hâlen aktif bir özniteliktir; güçlü fiziksel
  bir yordayıcı olduğundan çıkarılması sonuçları belirgin şekilde değiştirecektir, karar
  verildikten sonra tüm tarama yeniden koşulmalıdır.
- **R² metriği henüz uygulanmamıştır**; MAE/RMSE/R² tablosu için `metrics.py`'ye eklenmelidir.
- Karşılaştırma modelleri (SVM, Prophet, GRU; Prophet uygulanabilir değilse Random Forest veya
  MLP) — §13.4 kurallarına uygun biçimde eklenmelidir.
- Makale için betimleyici şekiller: beş ili gösteren harita, değişken–ışınım saçılım grafikleri,
  korelasyon matrisi, il bazında aylık kutu grafikleri, ay × yıl × ışınım 3B yüzeyi, mevsimsel
  grafikler.

---

## 17. Kod haritası (belge ↔ uygulama)

| Bölüm                     | Dosya                           | Ana fonksiyon/sınıf                                        |
| ------------------------- | ------------------------------- | ---------------------------------------------------------- |
| §3–4 Veri ve ön işleme    | `src/merve_solar/data.py`       | `load_city_sheet`, `load_all_cities`                       |
| §5 Öznitelikler, sabitler | `src/merve_solar/config.py`     | `NUMERIC_FEATURE_COLUMNS`, `ExperimentConfig`              |
| §6 Bölme sınırları        | `src/merve_solar/windows.py`    | `compute_split_boundaries`                                 |
| §7 Ölçekleme              | `src/merve_solar/scaling.py`    | `fit_scaler`, `inverse_transform_target`                   |
| §8 Pencereleme            | `src/merve_solar/windows.py`    | `build_experiment_windows`                                 |
| §9 Model                  | `src/merve_solar/model.py`      | `SolarLSTM`                                                |
| §10 Eğitim                | `src/merve_solar/train.py`      | `train_model`, `nonneg_penalty`                            |
| §11.1 MC Dropout          | `src/merve_solar/mc_dropout.py` | `mc_dropout_predict`                                       |
| §11.2 Bootstrap           | `src/merve_solar/bootstrap.py`  | `resample_train_split`                                     |
| §11.4, §12 Metrikler      | `src/merve_solar/metrics.py`    | `summarize_predictive_distribution`, `compute_all_metrics` |
| §13 Orkestrasyon          | `src/merve_solar/experiment.py` | `run_experiment`                                           |
| §13.5 Tarama              | `configs/experiment_grid.py`    | `build_experiment_grid`                                    |
| §13.2 Şekiller            | `src/merve_solar/utils.py`      | `plot_forecast_with_ci`, `plot_metric_vs_horizon`          |

**Çalıştırma:**

```bash
uv run python scripts/01_prepare_base_data.py                                    # bir kez
uv run python scripts/run_experiment.py --config configs/config_000_smoke.json   # tek deney
uv run python scripts/run_all_experiments.py                                     # tüm tarama
```
