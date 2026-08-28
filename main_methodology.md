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
$F = 17$ sayısal öznitelik.

**Doğrudan çok-çıkışlı (direct multi-output) tahmin:** 24 saatin tamamı tek bir ileri geçişte
üretilir; özyinelemeli (recursive/iterated) tahmin kullanılmaz. Gerekçe: özyinelemeli yaklaşımda
her adımın hatası bir sonraki adımın girdisine taşınır ve hata birikimi 24 saatlik ufukta
ciddi bozulmaya yol açar; ayrıca özyineleme, belirsizlik dağılımının ufuk boyunca yayılımını
analitik olarak izlenemez hâle getirir. Doğrudan yaklaşımda her ufuk adımı için belirsizlik
ayrı ayrı gözlemlenebilir hâle gelir; ufka göre kapsama figürü (`cp_vs_horizon.png`) her
koşuda üretilir. (Şu ana dek yalnızca smoke koşuları tamamlandığından bu figürün mevcut
örnekleri boru hattı doğrulamasıdır, sonuç değildir — bkz. §11.3.)

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
| Van     | 207,57          | 287,75     | 0,00 | 1215,88* |

> \* **Van'ın 1215,88 W/m² maksimumu makalede alıntılanmamalıdır.** Bu saatte açıklık
> indeksi $k_t = 3{,}28$'dir, yani ölçüm açık gökyüzü referansının üç katıdır — fiziksel
> olarak imkânsız, bir NASA POWER geri-çatım (retrieval) artefaktı. Savunulabilir en yüksek
> değer 1068,7 W/m²'dir. Artefakt, hedefin kendi gecikmesi bir öznitelik olduğu için veri
> kümesinde bırakılmıştır (tek bir saatin silinmesi saatlik seriyi delerdi), ama betimleyici
> bir istatistik olarak raporlanamaz.

Rize'nin belirgin şekilde düşük ortalaması, bulutluluğun ışınım üzerindeki etkisini gösterir ve
modelin il gömme vektöründen ne öğrenmesi gerektiğine dair doğrudan kanıttır.

**Ham değişkenler:**

| Sütun                    | Açıklama                                                           | Birim   |
| ------------------------ | ------------------------------------------------------------------ | ------- |
| `YEAR`, `MO`, `DY`, `HR` | Zaman damgası bileşenleri                                          | —       |
| `ALLSKY_SFC_SW_DWN`      | **Hedef.** Tüm gökyüzü koşullarında yüzeye gelen kısa dalga ışınım | W/m²    |
| `CLRSKY_SFC_SW_DWN`      | Açık gökyüzü referansı — **öznitelik değil**, gündüz maskesi (§4.2) | W/m²    |
| `T2M`                    | 2 m sıcaklık                                                       | °C      |
| `RH2M`                   | 2 m bağıl nem                                                      | %       |
| `QV2M`                   | 2 m özgül nem                                                      | g/kg    |
| `T2MDEW`                 | 2 m çiy noktası sıcaklığı                                          | °C      |
| `PS`                     | Yüzey basıncı                                                      | kPa     |
| `WS10M`, `WS50M`         | 10 m / 50 m rüzgâr hızı                                            | m/s     |
| `WD10M`, `WD50M`         | 10 m / 50 m rüzgâr yönü                                            | derece  |
| `PRECTOTCORR`            | Düzeltilmiş toplam yağış                                           | mm/saat |
| `ALLSKY_KT`              | Açıklık indeksi — **kullanılmadı, silindi**                        | —       |

Silinen sütunlar kaynak `.xlsx` dosyasından fiziksel olarak çıkarılmamıştır; dosya ham NASA
POWER çıktısı olarak korunur ve sütunlar okuma sırasında `DROPPED_COLUMNS`
(`src/merve_solar/config.py`) listesine göre düşürülür.

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

`ALLSKY_KT` `DROPPED_COLUMNS` sabiti üzerinden okuma anında tümüyle düşürülür.

**`CLRSKY_SFC_SW_DWN` ise farklı işlem görür: öznitelik kümesinden çıkarılır ama çerçevede
kalır.** Modelden çıkarılmasının gerekçesi eksik veri değil, modelleme kararıdır: açık
gökyüzü ışınımı, hedefin neredeyse tümüyle geometrik olarak belirlenen üst zarfıdır; girdi
olarak tutulması problemi kısmen bir "açıklık indeksi regresyonuna" indirger ve operasyonel
olarak elde edilebilir bilgiden daha iyimser bir başarı tablosu üretir. Buna karşılık **aynı
özellik onu kusursuz bir gündüz göstergesi yapar**: NASA'nın açık gökyüzü modeli saf güneş
geometrisidir, içinde hiçbir hava durumu terimi yoktur, dolayısıyla
$\text{CLRSKY}_{ih} > 0$ koşulu "güneş ufkun üzerinde mi" sorusunun tam yanıtıdır ve
**gerçekleşen hedefi hiçbir biçimde okumaz** — yani seçim-sonuç üzerinden koşullama itirazı
doğmaz. Bu nedenle sütun `MASK_COLUMNS` sabitiyle çerçevede *üstveri* olarak tutulur;
gündüz alt kümesini (§12) ve gece kırpmasını (§11.3) tanımlar, ama **hiçbir zaman model
girdisi değildir**. `config.py` içindeki içe aktarma anında çalışan bir kontrol, bu iki
sabitteki hiçbir sütunun `NUMERIC_FEATURE_COLUMNS` içine ya da hedef olarak sızmadığını
doğrular ve aksi hâlde hata fırlatır.

> **Ölçüm.** `CLRSKY > 0` maskesi 295.920 saatin 151.643'ünü seçer; hedef eşiği
> ($y \ge 1$ W/m²) 151.638'ini. İkisi saatlerin **%99,9983'ünde** aynı fikirdedir, yani
> geometrik gösterge hiçbir bilgi kaybı olmadan kullanılabilmektedir. İklimsel
> (il, ay, saat) hücre ortalaması ise 156.909 satır seçerek 5.266 alacakaranlık saatini
> içeri alır (medyan ışınımları 12,0 W/m², gündüz iç bölgesinin medyanı 395,7 W/m²);
> metrik maskesi olarak bu nedenle kullanılmaz.

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

### 5.2 Nihai öznitelik kümesi ($F = 17$)

`NUMERIC_FEATURE_COLUMNS` (`src/merve_solar/config.py`) — sıra kodda tanımlı sıradır:

| #     | Öznitelik                                          | Tür                                                        |
| ----- | -------------------------------------------------- | ---------------------------------------------------------- |
| 1     | `ALLSKY_SFC_SW_DWN`                                | **Hedefin kendi gecikmeli değerleri (özbağlanımlı girdi)** |
| 2–6   | `T2M`, `RH2M`, `QV2M`, `T2MDEW`, `PS`              | Sıcaklık, nem, basınç                                      |
| 7–9   | `WS10M`, `WS50M`, `PRECTOTCORR`                    | Rüzgâr hızı, yağış                                         |
| 10–13 | `WD10M_sin`, `WD10M_cos`, `WD50M_sin`, `WD50M_cos` | Rüzgâr yönü (döngüsel)                                     |
| 14–15 | `hour_sin`, `hour_cos`                             | Günlük (diurnal) döngü                                     |
| 16–17 | `doy_sin`, `doy_cos`                               | Mevsimsel döngü                                            |

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
> `0,74 / 0,11 / 0,15` oranları keyfi değildir. Bu oranlarla test kümesi **yaklaşık bir tam
> yıla** denk gelir: 8.878 saatlik dilim, yani 369 gün 22 saat ≈ 370 gün
> (2025-03-26 02:00 → 2026-03-30 23:00), dolayısıyla dört mevsimi de içerir. Güneş ışınımında bu kritik bir tasarım kararıdır:
> test kümesi yalnızca yaz aylarına düşerse model olduğundan iyi, yalnızca kışa düşerse
> olduğundan kötü görünür. Tam bir yıl, tüm mevsimleri dengeli biçimde içerir ve mevsimsel
> yanlılığı ortadan kaldırır. Kaynak makalenin kendi 64/16/20 bölmesi karşılaştırma amacıyla
> ayrı bir deney konfigürasyonu olarak (`config_split_paper_64_16_20`) korunmuştur.

---

## 7. Ölçekleme ve sızıntı kontrolü

**Uygulama:** `src/merve_solar/scaling.py`.

17 sayısal öznitelik `StandardScaler` ile standartlaştırılır:

$$
z = \frac{x - \mu_{\text{train}}}{\sigma_{\text{train}}}
$$

**Kritik nokta:** $\mu$ ve $\sigma$ **yalnızca eğitim tarih aralığındaki satırlardan** hesaplanır
($\text{datetime} \le \text{train\_end}$), ardından tüm veriye (eğitim, doğrulama, test)
uygulanır. Ölçekleyicinin tüm veri üzerinde fit edilmesi, test kümesinin istatistiklerinin
eğitime sızması demektir ve yayımlanacak sonuçları geçersiz kılar.

Varsayılan (küresel) kolda ölçekleyici tek ve **küreseldir**: iller havuzlanarak fit edilir,
bu da tek küresel model tasarımıyla tutarlıdır.

> **Belgelenmiş iki istisna.** (i) `training_scope="per_city"` ablasyon kolunda
> `per_city_scaler` varsayılan olarak açıktır ve **her il kendi ölçekleyicisini** alır
> (`checkpoints/scaler_<il>.joblib`). Bu bilinçli bir tercihtir — o kolda il başına ayrı bir
> model eğitilir, dolayısıyla paylaşılan bir hedef ölçeği yapay bir bağ kurardı — ama
> **`training_scope` eksenine ikinci bir etki bindirir**: küresel ölçekte yüksek varyanslı
> iller kayba baskın gelirken, il bazında her ilin kaybı kendi varyansına normalize olur ve
> erken durdurma ile `ReduceLROnPlateau` farklı ölçekli doğrulama kayıplarına bakar. Etki
> il bazlı kolun **lehinedir**; `per_city_scaler=False` ile ayrı bir duyarlılık koşusu
> çalıştırılarak ölçülmesi gerekir. (ii) §12'deki naif referanslar (iklimsel ortalama,
> kalıcılık, akıllı kalıcılık) ham W/m² üzerinde çalışır ve **hiç ölçekleyici kullanmaz**.
> Her iki istisnada da sızıntı değişmezi korunur: ne fit edilirse yalnızca
> $\text{datetime} \le \text{train\_end}$ satırları üzerinde fit edilir.

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
   dönemine taşmasını, yani sızıntıyı engeller. Kayıp, **il ve sınır başına** en fazla
   $(L+H-1) = 47$ penceredir; varsayılan konfigürasyonda 2 sınır × 5 il × 47 = **470 pencere**
   (295.685 pencerenin ≈%0,16'sı) ve toplam veri hacmi yanında ihmal edilebilir.

**Varsayılan konfigürasyonla elde edilen pencere sayıları (5 il toplamı):**

| Küme      | Pencere sayısı | Tensör boyutu          |
| --------- | -------------- | ---------------------- |
| Eğitim    | 218.745        | $(218745,\, 24,\, 17)$ |
| Doğrulama | 32.315         | $(32315,\, 24,\, 17)$  |
| Test      | 44.155         | $(44155,\, 24,\, 17)$  |

Test kümesindeki toplam skaler tahmin sayısı: $44.155 \times 24 = 1.059.720$.

---

## 9. Model mimarisi

**Uygulama:** `SolarLSTM`, `src/merve_solar/model.py`.

```
Girdi: X (batch, L=24, F=17)   ve   city_id (batch,)
   │
   ├─ Embedding(5 → 4) ──► e_c, her zaman adımına kopyalanır: (batch, 24, 4)
   │
   ├─ concat([X, e_c])  ──────────────────────────────► (batch, 24, 21)
   │
   ├─ LSTM(input=21, hidden=64, num_layers=2, dropout=0.3, batch_first=True)
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
→ ReLU → Dropout → `Linear(32→24)` başlığı. Toplam öğrenilebilir parametre: **58.444**
($F = 17$ ve `city_embedding_dim = 4` ile, doğrudan modelden sayılarak doğrulanmıştır; 58.700 değeri $F = 18$ dönemine ait eskimiş bir sayıdır).
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
altında hesaplanır. Eğitim ve doğrulama kayıpları epok bazında **bellekte** tutulur
(`history`); deney günlüğüne (`log.txt`) replika başına yalnızca son doğrulama kaybı ve
çalışılan epok sayısı yazılır (`replica {b}: final val_loss=… epochs=…`). Epok bazlı eğitim
eğrisi hiçbir dosyaya kaydedilmemektedir; eğri figürü istenirse `history`'nin diske yazılması
gerekir.

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

> **Uyarı — bu değerler tasarım hedefidir, ölçüm değildir.** Varsayılan konfigürasyonun
> ($B=8$, $T=100$) tam koşusu bu ana dek tamamlanmamıştır; ledger'daki LSTM satırlarının
> tamamı hızlı doğrulama (smoke) koşularıdır ($B=1$, $T=10$). $T=10$ örnekten kestirilen
> %2,5/%97,5 yüzdelikleri anlamsızdır: **smoke koşularının aralık metrikleri (CP, PINW,
> MPIW, CWC) makaleye asla girmemelidir**, yalnızca boru hattı doğrulaması içindir.

**Gece kırpması (`clamp_night_to_zero`, varsayılan açık).** W/m²'ye geri dönüştürmeden hemen
sonra, $\text{CLRSKY}_{ih} = 0$ olan her $(i, h)$ elemanında havuzun **tamamı** sıfıra
çekilir. Bu bir uydurma (fitting) değil, bilinen bir fiziksel olgunun dayatılmasıdır: güneş
ufkun altındayken yüzeye gelen kısa dalga ışınım tam olarak sıfırdır ve bu, hedefe hiç
bakmadan yalnızca geometriden bilinir. Ölçülen etkisi büyüktür — MSE ile eğitilmiş bir
modelin gece medyan tahmini 29,3 W/m² iken gerçek değer 0'dır; kırpma tüm-saat MAE'sini
≈%27 düşürür. Kırpmanın **aralık metrikleri üzerindeki yan etkisi** §11.5'te ele alınmıştır
ve makalede mutlaka belirtilmelidir.

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

### 11.5 Tasarımın bilinen sınırları — aralıkların yorumu

Aşağıdakiler tasarımın *bilinen* sınırlarıdır; "gelecek iş" değil, sonuçların doğru
okunması için gereken ön koşullardır.

**1. Havuzlanan dağılım aleatorik bileşen içermez.** $\mathcal{P}$, bootstrap replikaları
(veri/örneklem belirsizliği) ile MC-Dropout geçişlerinden (model parametresi belirsizliği)
oluşur; **gözlem gürültüsü terimi hiçbir aşamada eklenmez**
(`metrics.py::summarize_predictive_distribution` doğrudan geçişlerin yüzdeliklerini alır).
Dolayısıyla aralıklar "gözlem nerede olabilir" sorusunu değil, "modelin ortalama tahmini
nerede olabilir" sorusunu yanıtlar ve %95 kapsamaya **ilkesel olarak** ulaşamayabilirler.
Ölçülen değerler bu beklentiyle uyumludur: ön koşularda gündüz CP $\approx 0{,}62$–$0{,}67$,
hedef ise $0{,}95$. Standart çare $\sigma^2_{\text{toplam}} = \sigma^2_{\text{model}} +
\sigma^2_{\text{gürültü}}$ biçiminde bir rezidüel-varyans eklentisi ya da split-conformal
bir kalibrasyon katmanıdır; **kaynak makalenin PICP $= 0{,}9472$ değeriyle karşılaştırma bu
düzeltme yapılmadan adil olmayacaktır.**

**2. Gece kırpması tüm-saat CP'sini yapısal olarak şişirir.** `clamp_night_to_zero`
varsayılan olarak açıktır (§11.3): $\text{CLRSKY} = 0$ olan adımlarda havuzun *tamamı* sıfıra
çekilir. Bu adımlarda aralık $[0,\,0]$ genişliğindedir ve gerçek değer de tam olarak 0
olduğundan **tanım gereği kapsanır**. Elemanların ≈%48,8'i gece olduğuna göre, tüm-saat CP'si
yaklaşık yarısı 1,0 olan bir karışımdır — ölçülen tüm-saat CP $\approx 0{,}80$'e karşılık
gündüz CP $\approx 0{,}62$–$0{,}67$. **Aralık kalitesi yalnızca gündüz alt kümesinden
okunmalıdır**; tüm-saat CP'si makalede raporlanacaksa bu yapısal şişme ile birlikte
verilmelidir.

**3. Doğrulama kümesi tüm replikalar için ortaktır.** Her replika aynı `splits["val"]`
üzerinde erken durdurulur, bu da replikaların bağımsızlığı varsayımını zayıflatır. Bootstrap
yalnızca eğitim bölmesine uygulandığı için sızıntı yoktur, ancak belirsizlik bandının bir
miktar dar kalmasına katkı verir.

**4. Test pencereleri bağımsız gözlem değildir.** `window_stride = 1` ile ardışık pencereler
48 saatlik açıklığın 47'sini paylaşır. `n_samples` sütunu makalede "bağımsız gözlem sayısı"
gibi okunmamalıdır; anlamlılık testi yapılacaksa (Diebold–Mariano vb.) bu blok yapısı HAC
varyansı ile hesaba katılmalıdır.

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

$$
R^2 = 1 - \frac{\sum_{i,h}\left(y_{ih} - \hat{\mu}_{ih}\right)^2}{\sum_{i,h}\left(y_{ih} - \bar{y}\right)^2}
$$

burada $\bar{y}$ **o alt kümenin** gerçek değer ortalamasıdır; alt küme sabit hedefliyse
tanımsızdır ve `nan` raporlanır. $R^2$ birimsizdir ve 1'e yakın olması iyidir — ancak
**paydası alt kümeye görelidir**, dolayısıyla tüm-saat ve gündüz $R^2$'leri aynı ölçekte
değildir: gece/gündüz salınımı toplam varyansı şişirdiği için tüm-saat $R^2$'si yapay olarak
yüksek çıkar (§16.1). Aynı gerekçe PINW için de geçerlidir. **Manşet değer gündüz
$R^2$'sidir.**

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

Her metrik **üç düzeyde** ve **iki alt küme** için hesaplanır. Alt küme, dosyalarda ayrı bir
`subset` sütunudur:

| Alt küme    | Maske                       | Eleman payı | Rolü                                  |
| ----------- | --------------------------- | ----------- | ------------------------------------- |
| `all_hours` | yok                         | %100        | Bütünlük için; gece tarafından şişer  |
| `daylight`  | $\text{CLRSKY}_{ih} > 0$    | ≈%51,2      | **Makalenin manşet sayıları buradan** |

Gündüz payı 24 ufuk adımının **her birinde** 0,515'tir, yani hiçbir adım gece/gündüz
bileşimi bakımından ayrıcalıklı değildir ve ufuk bazlı gündüz karşılaştırması anlamlıdır.

| Düzey              | Dosya                            | İçerik                                          |
| ------------------ | -------------------------------- | ----------------------------------------------- |
| Toplulaştırılmış   | ledger satırı                    | Tüm iller + tüm ufuk adımları havuzlanmış       |
| İl bazında         | `metrics/results_summary.csv`    | Alt küme × (Aggregate + Aggregate_excl_Rize + iller) |
| Ufuk adımı bazında | `metrics/results_by_horizon.csv` | Alt küme × (1 saat ileri … 24 saat ileri)       |

İki sütun kaç şeyin puanlandığını ayırır: `n_samples`, alt kümede **en az bir** puanlanan
elemanı olan **pencere** sayısıdır (`metrics.py`, `element_mask.any(axis=1).sum()`);
`n_elements` puanlanan $(pencere, ufuk adımı)$ çifti sayısıdır ve gündüz alt kümesinde
yaklaşık yarıya iner. Bu veri kümesinde iki alt kümenin `n_samples` değeri aynı çıkar
(ör. 44.155), ama bu tanım gereği değil bir sonuçtur: ufuk 24 saat olduğundan her pencere
tam bir günü kapsar ve içinde mutlaka en az bir gündüz adımı bulunur. `horizon_hours` bir
gece boyuna sığacak kadar kısaltılırsa gündüz `n_samples`'ı tüm-saat değerinin altına
düşer. Ledger, at-a-glance karşılaştırma için tüm-saat sütunlarının
yanına `RMSE_daylight`, `MAE_daylight`, `R2_daylight`, `CP_daylight` ve
`n_elements_daylight` sütunlarını da taşır; tam döküm `results_summary.csv`'dedir.

> **`Aggregate_excl_Rize` satırı neden var?** Rize, betimleyici analizde diğer dört ilden
> ayrı bir rejim çıkmıştır (günlük açıklık indeksi 0,697'ye karşı 0,806–0,840; kapalı gün
> payı %8,0'e karşı %1,0–2,8). Düz toplulaştırma Rize'yi 4'e 1 gömer — oysa il gömmesinin
> işini yapması gereken yer tam olarak orasıdır. Bu satır, iller arası transferin katkısını
> manşet sayıda görünür kılar.

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

`ExperimentConfig` bunların yanında **kol seçimi ve ölçüt eksenlerini** de taşır. Bu alanlar
tek bir koşunun neyi öğrendiğini ve neye göre puanlandığını belirlediği için hepsi ledger
sütunudur (§13.2) ve hepsi `__post_init__` içinde doğrulanır — yazım hatası konfigürasyon
yüklenirken düşer, saatler sonra eğitim ortasında değil.

| Parametre             | Varsayılan     | Ne seçer                                                                                                                                  |
| --------------------- | -------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `training_scope`      | `"global"`     | Havuzlanmış tek model (`global`, manşet konfigürasyon) mi, il başına bağımsız model seti (`per_city`, transfer ablasyon kolu) mi           |
| `model_family`        | `"lstm"`       | Ledger satırının model ailesi. `run_experiment` **yalnızca** `lstm` eğitir; `climatology`/`persistence`/`smart_persistence` satırları eğitimsiz olarak `scripts/03_run_naive_baselines.py` tarafından üretilir |
| `loss_function`       | `"mse"`        | Eğitim ölçütü: `mse` / `mae` / `huber` (§10.1)                                                                                             |
| `huber_delta`         | 1,0            | Yalnızca `loss_function="huber"` iken; geçiş noktası, **ölçeklenmiş** hedef uzayında                                                        |
| `loss_daylight_only`  | `False`        | Kayıp yalnız gündüz adımları üzerinden hesaplansın mı (raporlama değil, modelleme değişikliği)                                              |
| `per_city_scaler`     | `True`         | Yalnızca `training_scope="per_city"` iken; her il kendi ölçekleyicisini alır (§7'deki belgelenmiş istisna). `False` havuzlanmış ölçekleyiciyi paylaştırır |
| `clamp_night_to_zero` | `True`         | Ters ölçeklemeden sonra $\text{CLRSKY} = 0$ elemanlarını sıfıra kırp (§11.3)                                                                |
| `excluded_cities`     | `[]`           | Bu koşudan **tamamen** (eğitim, doğrulama ve test) çıkarılan iller; il kimlikleri yeniden numaralandırılmaz                                 |

### 13.2 Çıktılar

```
outputs/experiments/<experiment_id>/
├── config.json                       # koşunun tam konfigürasyonu
├── log.txt                           # cihaz, bölme tarihleri, replika bazında val loss, süre
├── checkpoints/
│   ├── bootstrap_model_<b>.pt        # küresel kol: her replikanın ağırlıkları
│   ├── scaler.joblib                 # küresel kol (ve per_city_scaler=False) ölçekleyicisi
│   ├── bootstrap_model_<il>_<b>.pt   # il bazlı kol: (il × replika) ağırlıkları
│   └── scaler_<il>.joblib            # il bazlı kol: il başına ölçekleyici
├── metrics/
│   ├── results_summary.csv           # alt küme × (Aggregate + Aggregate_excl_Rize + iller)
│   ├── results_by_horizon.csv        # alt küme × 1–24 saat ufuk adımları
│   └── test_predictions.npz          # öngörü dağılımının özeti: mean/lower/upper + y_true,
│                                     #   city_id, daylight, window_start
└── figures/
    ├── forecast_ci_<il>.png          # temsilî 24 saatlik tahmin + %95 CI
    ├── rmse_vs_horizon.png           # sonek yok = all_hours
    ├── rmse_vs_horizon_daylight.png  # _daylight = manşet alt küme
    ├── cp_vs_horizon.png
    └── cp_vs_horizon_daylight.png

outputs/experiments_ledger.csv        # KOŞU BAŞINA BİR SATIR — makale tablolarının kaynağı
```

`checkpoints/` altındaki iki dosya adı deseninden yalnızca biri bulunur; hangisi olduğu
`training_scope`'a bağlıdır. `test_predictions.npz` tam örneklemi değil dağılımın özetini
saklar (tam doğrulukta $(S, N, 24)$ dizisi ≈3,4 GB olurdu); eşli anlamlılık testleri bunu
okur, dolayısıyla böyle bir test deneyin koştuğu makinede koşulmalıdır. `.pt` ve `.npz`
dosyaları sürüm kontrolüne alınmaz, tohumlanmış konfigürasyondan yeniden üretilir.

`experiments_ledger.csv` satırının şeması `experiment.py::LEDGER_COLUMNS` ile sabitlenmiştir;
`assert_ledger_schema_ok()` her koşunun **başında** diskteki başlıkla karşılaştırır, böylece
şema uyuşmazlığı saatler süren bir eğitimin sonunda değil milisaniyeler içinde düşer. Satır
üç bloktan oluşur:

- **Kimlik ve eksenler:** `experiment_id`, `model_family`, `training_scope`,
  `excluded_cities` (sıralı, `|` ile ayrılmış dize; hiçbiri dışlanmamışsa boş),
  `lookback_hours`, `horizon_hours`, `window_stride`, `n_features`, `hidden_sizes`,
  `dropout_rate`, `city_embedding_dim`, `train_ratio`, `val_ratio`, `n_bootstrap`,
  `mc_dropout_passes`, `max_epochs`, `early_stop_patience`, `loss_function`, `huber_delta`,
  `loss_daylight_only`, `per_city_scaler`, `clamp_night_to_zero`, `seed`.
- **Metrikler:** tüm-saat toplulaştırması (`RMSE`, `MAE`, `R2`, `CP`, `PINW`, `MPIW`,
  `Reliability`, `CWC`, `CRPS`, `n_samples`, `n_elements`) ve gündüz özeti (`RMSE_daylight`,
  `MAE_daylight`, `R2_daylight`, `CP_daylight`, `n_elements_daylight`).
- **Koşu bilgisi:** `hit_max_epochs`, `n_models_trained`, `training_time_sec`.
  `hit_max_epochs` sıfırdan büyükse eğitimi erken durdurma değil epok tavanı bitirmiştir; iki
  kol farklı miktarda eğitim almışsa karşılaştırılamazlar, dolayısıyla bu sütun her
  kol-karşılaştırmasından önce okunmalıdır.

Makaledeki karşılaştırma tabloları doğrudan bu dosyadan üretilir; kaydedilmeyen bir alan
değiştirilmişse iki satır tabloda ayırt edilemez (§13.4).

### 13.3 Tekrarlanabilirlik

- Tüm rastgelelik kaynakları tohumlanır: `random`, `numpy`, `torch` (`set_seed`).
- **Küresel kolda** her bootstrap replikası için tohum kaydırılır ($\text{seed} + b + 1$);
  böylece replikalar birbirinden farklı ama koşudan koşuya aynıdır. MBB yeniden örneklemesi
  tek bir `numpy.random.default_rng(\text{seed})` üreticisiyle yapılır.
- **İl bazlı kolda** $5B$ model eğitildiği için şema genişletilir: $c$ ilinin $b$ replikası
  $\text{seed} + 1 + c \cdot B + b$ tohumunu alır. Bu eşleme çakışmasızdır ($b < B$
  olduğundan iki (il, replika) çifti aynı tohuma düşemez); çakışma olsaydı iki ilin ağırlık
  ilklendirmesi ve blok çekilişleri birbiriyle ilintili hâle gelirdi. MBB üreticisi ise il
  başına `numpy.random.default_rng([\text{seed}, c])` ile ayrılır.
- **Tekrarlanabilirlik cihaz başınadır.** `set_seed` CPU, CUDA ve MPS üreticilerinin üçünü
  de tohumlar, ama farklı arka uçlar (MPS / CUDA / CPU) bit düzeyinde aynı sonucu vermez;
  bir sonucun yeniden üretilmesi aynı cihaz sınıfını gerektirir ve kullanılan cihaz her
  koşunun `log.txt` dosyasına yazılır.
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

### 13.5 Deney taraması

`configs/experiment_grid.py` taramayı **adlandırılmış gruplar** hâlinde tutar
(`EXPERIMENT_GROUPS`) ve `build_experiment_grid(gruplar)` seçilenleri birleştirip yinelenen
`experiment_id` varsa hata verir. Gruplandırmanın nedeni maliyettir: bütün grupları birden
koşmak günler sürer, dolayısıyla koşumlar `run_all_experiments.py --group ...` ile tek tek
seçilir (grup verilmezse **hepsi** seçilir).

| Grup               | Kol | Doğruluk (fidelity)                  | Ne için                                                                     |
| ------------------ | --- | ------------------------------------ | --------------------------------------------------------------------------- |
| `smoke`            | 2   | $B=1$, $T=10$, 5 epok                | Pahalı hiçbir şeyden önce her iki `training_scope` kolunu uçtan uca koşmak   |
| `main`             | 10  | Varsayılan ($B=8$, $T=100$)          | Hiperparametre taraması (aşağıdaki eksen tablosu)                            |
| `ablation`         | 8   | $B=8$, $T=100$, 200 epok             | `global` ↔ `per_city`: kaynak makalenin iller-arası transfer iddiasının sınanması |
| `rize_curve`       | 12  | $B=8$, $T=100$, 200 epok             | Kayıp seçimi (3 kol) + Rize transfer eğrisi (9 kol)                          |
| `rize_curve_b1`    | 12  | $B=1$, $T=100$, 100 epok (`ABLATION_B1`) | Aynı çalışmanın eldeki hesap kaynağına sığan indirgenmiş kopyası         |
| `rize_curve_smoke` | 2   | $B=1$, $T=10$, 5 epok                | Yalnızca dışlama kod yollarının sınanması                                    |

**`main` grubunun eksenleri (hiperparametre taraması):**

| Eksen                   | Değerler                          | Kaynak                                    |
| ----------------------- | --------------------------------- | ----------------------------------------- |
| Gizli katman yapısı     | [32,16], [64,32], [128,64]        | Kaynak makale Tablo 6                     |
| Dropout oranı           | 0,1 / 0,2 / 0,3                   | Kaynak makale Tablo 6                     |
| Geçmiş pencere uzunluğu | 12 / 24 / 48 saat                 | Bu çalışmaya özgü (PCNN'de karşılığı yok) |
| Bölme oranı             | 0,74/0,11/0,15 vs. 0,64/0,16/0,20 | Bizim tasarımımız vs. kaynak makale       |

**Ablasyon gruplarının eksenleri (`smoke`, `ablation`, `rize_curve*`):**

| Eksen             | Değerler                                                                     | Neyi ayırır                                                                                                   |
| ----------------- | ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| `training_scope`  | `global` / `per_city`                                                        | Havuzlamanın kendisi. Her çift tek bir sözlükten kurulur, böylece kollar kanıtlanabilir biçimde yalnız bu alanda ayrılır |
| `excluded_cities` | Rize tek başına → Rize+Ankara / Rize+Antalya → 4 il → 5 il                    | Transferin **yönü**: her kol Rize'nin kendi test pencerelerinde puanlanır. İkili kollar aynı sayıda pencereyle eğitilir, yalnız hangi ilin eklendiği değişir — "daha çok veri" ile "daha çeşitli veri"yi ayıran kontrol budur |
| `loss_function`   | `mse` / `mae` / `huber`                                                      | Eğitim ölçütü, beş ilde sabit havuzlamayla. Hedefin artık dağılımı sağa çarpık olduğundan L1'in MAE'yi iyileştirip RMSE'yi kötüleştirmesi beklenir; bulgu bu ödünleşimdir |
| `seed`            | 42 / 43 / 44 (`ABLATION_SEEDS`)                                              | Değişkenlik. Tohum hem ağırlık ilklendirmesini hem bootstrap çekilişini değiştirdiği için doğru değişkenlik birimidir; kollar arası fark tohumlar arası yayılımdan küçükse dürüst sonuç "fark saptanamadı"dır |

> **Uyarı (tasarım sınırı, kodda da not düşülmüştür).** `rize_curve` iki aşamalıdır: 1. aşama
> kaybı seçer, 2. aşama havuzlamayı değiştirir. Ancak 2. aşama kaybı `ExperimentConfig`
> varsayılanından (`"mse"`) alır, 1. aşamanın kazananından değil. 1. aşama `mae` ya da `huber`
> seçerse eğri bunu kullanmaz; o hâlde 2. aşama `loss_function` açıkça verilerek yeniden
> tanımlanmalıdır. Aksi hâlde iki aşama, yalnızca aynı doğruluğu paylaşan iki bağımsız
> tek-eksenli karşılaştırmadır.

---

## 14. Hesaplama ortamı

- **Çatı:** PyTorch (≥2.2), scikit-learn (ölçekleme), pandas/numpy, matplotlib.
- **Cihaz seçimi otomatiktir:** MPS (Apple Silicon) → CUDA (Nvidia) → CPU sırasıyla denenir
  (`get_device()`); kullanılan cihaz her koşunun `log.txt` dosyasına yazılır.
- **Süre (ölçülmemiştir, tasarım hedefidir):** Varsayılan konfigürasyonun tam koşusu
  (8 replika × 100 MC geçiş) bu ana dek **hiç tamamlanmamıştır**, dolayısıyla süre iddiası
  doğrulanmış değildir. Eldeki tek ölçüm: CPU'da hızlı doğrulama konfigürasyonu
  (`n_bootstrap=1`, `max_epochs=5`, `mc_dropout_passes=10`) ≈160 saniye. GPU (MPS/CUDA)
  üzerinde tam koşunun saatler mertebesinde olması beklenir; kesin değer ilk tam koşu
  bittiğinde bu bölüme yazılacaktır.
- **Bağımlılık yönetimi:** `uv` + `uv.lock` ile sürümler sabitlenmiştir (tekrarlanabilirlik).

---

## 15. Makale "Yöntem" bölümü için taslak paragraf

> Bu çalışmada, Türkiye'nin farklı iklim kuşaklarında yer alan beş ili için saatlik küresel
> yatay güneş ışınımının 24 saat ileriye dönük tahmini amacıyla, belirsizlik tahmini yeteneğine
> sahip bir derin öğrenme çerçevesi önerilmiştir. NASA POWER veri servisinden elde edilen
> 2019–2026 dönemine ait saatlik meteorolojik veriler (il başına 59.184 saat) kullanılmıştır.
> Saat, yılın günü ve rüzgâr yönü değişkenleri, döngüsel yapılarının korunması amacıyla
> sinüs–kosinüs çiftlerine dönüştürülmüş; toplam 17 sayısal öznitelik elde edilmiştir. Veri,
> zamansal sızıntıyı önlemek amacıyla kronolojik olarak %74 eğitim, %11 doğrulama ve %15 test
> olarak bölünmüş; bu oranlar test kümesinin tam bir mevsimsel yılı kapsayacak biçimde
> seçilmiştir. Standartlaştırma parametreleri yalnızca eğitim dönemi üzerinden hesaplanmıştır.
> Tahmin modeli, il kimliğini 4 boyutlu öğrenilebilir bir gömme vektörü olarak alan iki
> katmanlı bir LSTM ağıdır (gizli boyut 64) ve 24 saatlik girdi penceresinden 24 saatlik
> tahmini tek bir ileri geçişte üretmektedir. Model, ortalama kare hata ve ışınımın negatif
> olamayacağı fiziksel kısıtını yansıtan yumuşak bir düzenlileştirme teriminden oluşan bileşik
> bir kayıp fonksiyonu ile eğitilmiştir. Belirsizlik tahmini için Bootstrap Ensemble ve Monte
> Carlo Dropout yöntemleri hibrit biçimde kullanılmıştır: zamansal otokorelasyonun korunması
> amacıyla hareketli blok bootstrap (blok uzunluğu 168 ardışık pencere; saatlik kaydırma ile
> ≈1 haftalık dilim) ile oluşturulan sekiz farklı
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

1. **Gece saatleri metrikleri şişirir — nicelenmiş ve ele alınmıştır.** Hedef değerlerinin
   **%48,76'sı tam olarak 0'dır** ve bu saatler tüm bölmelerde yer alır. Tahmin edilmeleri
   önemsiz derecede kolay olduğundan MAE/RMSE'yi olduğundan iyi gösterirler: aynı iklimsel
   ortalama arama tablosu gündüz RMSE 106,9 W/m² verirken tüm saatlerde 76,7 W/m² ve
   R² $= 0{,}923$ vermektedir. Gece kırpması açıkken CP de aynı yönde şişer (§11.5).
   Bu nedenle `metrics.py` her metriği **iki alt küme** için raporlar (`all_hours`,
   `daylight`; gündüz göstergesi $\text{CLRSKY} > 0$, §4.2) ve **makalenin manşet sayıları
   gündüz alt kümesinden alınmalıdır**. Tüm-saat R²'si üç metrik içinde en yanıltıcı olanıdır.
2. **Negatiflik cezası ölçeklenmiş uzayda uygulanmaktadır** (§10.1 uyarısı).
3. **Tohum çeşitliliği tasarımda vardır, tam doğrulukta henüz yoktur.** Çoklu tohum
   planlanmıştır: `configs/experiment_grid.py::ABLATION_SEEDS = (42, 43, 44)` ve kol-kol
   karşılaştırma taşıyan kollar (ablasyon çifti, eğrinin iki uç noktası) üç tohumla
   tanımlanmıştır. Ancak **tam doğrulukta ($B=8$, $T=100$) hiçbir çoklu-tohum sonucu
   üretilmemiştir**; eldeki çoklu-tohum kolları indirgenmiş doğruluktadır (`ABLATION_B1`,
   $B=1$) ve §13.4 gereği bunların aralık metrikleri $B=8$ satırlarıyla karşılaştırılamaz.
   Makaleye ortalama ± standart sapma yazılabilmesi için manşet konfigürasyonun üç tohumda
   tam doğrulukta koşulması gerekir.
4. **Dış (exogenous) girdiler gerçek gözlemdir.** Model, tahmin ufkunda değil yalnızca geçmiş
   pencerede meteorolojik değişken kullanmaktadır; operasyonel bir sistemde bu değişkenlerin
   sayısal hava tahmini (NWP) çıktısı olarak gelmesi gerekir.
5. **Aralıklar ölçülen biçimde alt-kapsamalıdır ve bunun yapısal bir nedeni vardır.**
   "CP hedeften saparsa" biçiminde koşullu yazılamaz: eldeki tüm koşularda gündüz CP
   $\approx 0{,}62$–$0{,}67$ ölçülmüştür (hedef $0{,}95$) ve CWC buna karşılık gelen
   büyüklüktedir — §12.4'ün kendi ölçütüne göre "dar ama güvenilmez aralık" tanısı.
   Nedeni §11.5'te açıklanmıştır: havuzlanan dağılım aleatorik terim içermez. Kalibrasyon
   sonrası düzeltme (rezidüel-varyans eklentisi ya da conformal katman) bu nedenle isteğe
   bağlı bir iyileştirme değil, %95 kapsama iddiasının **ön koşuludur**. Koşuların tamamı
   smoke kalitesinde olduğundan sayılar nihai değildir, ama yön tüm koşularda aynıdır.

**Açık işler (bkz. `TODOs.md`):**

- `CLRSKY_SFC_SW_DWN` **öznitelik kümesinden çıkarılmıştır** (bkz. §4.2, §5.2) ama gündüz
  maskesi olarak çerçevede tutulmaktadır. Bu karardan önce üretilmiş ledger satırları
  ($F = 18$) yeni satırlarla karşılaştırılamaz; tarama yeni kimliklerle yeniden koşulmalıdır.
- **R² metriği uygulanmıştır** (`metrics.py::r2`); özet, ufuk bazlı ve ledger çıktılarının
  üçünde de MAE/RMSE ile birlikte, her iki alt küme için raporlanır.
- Karşılaştırma modelleri (SVM, Prophet, GRU; Prophet uygulanabilir değilse Random Forest veya
  MLP) — §13.4 kurallarına uygun biçimde eklenmelidir.
- Makale için betimleyici şekiller **harita dışında tamamlanmıştır**
  (`scripts/02_descriptive_analysis.py` → `outputs/eda/figures/`, her biri PNG + vektör PDF):
  değişken–ışınım saçılım grafikleri, korelasyon matrisleri, il bazında aylık kutu grafikleri,
  ay × yıl × ışınım 3B yüzeyi (ve 2B anomali eşlikçisi) ve iki mevsimsel görünüm. **Açık
  kalan:** beş ili gösteren harita ve illerin iklim/coğrafya farklarını anlatan paragraf;
  ikisi de dış geoveri gerektirdiği için bu depodan üretilememektedir.

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
| §8 Torch veri yükleyici   | `src/merve_solar/datasets.py`   | `WindowDataset`, `make_dataloader`                         |
| §11.4, §12 Metrikler      | `src/merve_solar/metrics.py`    | `summarize_predictive_distribution`, `compute_metric_subsets` |
| §12 Naif referans zemini  | `src/merve_solar/baselines.py`  | `add_baseline_columns`, `build_baseline_predictions`       |
| §13 Orkestrasyon          | `src/merve_solar/experiment.py` | `run_experiment`, `LEDGER_COLUMNS`, `SCOPE_RUNNERS`        |
| §13.5 Tarama              | `configs/experiment_grid.py`    | `build_experiment_grid`, `EXPERIMENT_GROUPS`               |
| §13.2 Şekiller            | `src/merve_solar/utils.py`      | `plot_forecast_with_ci`, `plot_metric_vs_horizon`          |
| §3 Betimleyici analiz     | `src/merve_solar/eda.py`        | `descriptive_table`, `correlation_tables`, `persistence_baseline_table` |
| Makale şekil stili        | `src/merve_solar/paper_style.py`| `PAPER_RC`, `save_figure`                                  |

Betikler (hepsi `src/`'ı `sys.path`'e ekler; `PROJECT_ROOT` dışında yol argümanı almazlar):

| Betik                              | Ne yapar                                                              |
| ---------------------------------- | --------------------------------------------------------------------- |
| `scripts/01_prepare_base_data.py`  | §3–5 taban öznitelik parquet'ini bir kez üretir                        |
| `scripts/02_descriptive_analysis.py` | `outputs/eda/{tables,figures}` — betimleyici tablolar ve makale şekilleri |
| `scripts/03_run_naive_baselines.py`| Naif referansları aynı pencere/bölme/metrik yolundan ledger'a yazar    |
| `scripts/run_experiment.py`        | Tek `ExperimentConfig` koşusu (§13.1)                                  |
| `scripts/run_all_experiments.py`   | Seçilen tarama grupları (§13.5)                                        |

Sınama (`uv run python -m pytest tests/ -q`) — her dosyanın koruduğu değişmez:

| Dosya                        | Neyi korur                                                                    |
| ---------------------------- | ------------------------------------------------------------------------------ |
| `tests/test_data.py`         | §4 veri bütünlüğü: kuyruk kesme satır sayısı, kalan −999 yok, NaN yok           |
| `tests/test_windows.py`      | §8 pencereler il ve bölme sınırını aşmaz; gündüz dizisi ufka doğru hizalanır    |
| `tests/test_metrics.py`      | §12 metrik tanımları; CRPS'in parça boyutundan bağımsızlığı ve nokta tahminde MAE'ye indirgenmesi |
| `tests/test_ledger.py`       | §13.2 ledger şeması; uyuşmazlıkta dosyanın bayt-bayt korunması                  |
| `tests/test_scope.py`        | §13.5 iki `training_scope` kolunun aynı gerçek değerle puanlanması, il-blok hizası |
| `tests/test_excluded_cities.py` | Dışlamanın il kimliklerini yeniden numaralandırmaması ve bölme tarihlerini kaydırmaması |
| `tests/test_loss_function.py`| §10.1 kayıp seçiminin gerçekten ölçütü değiştirmesi, `huber_delta`'nın geçmesi   |
| `tests/test_loss_masking.py` | `loss_daylight_only` maskesi ve gündüzsüz yığının atlanması                      |
| `tests/test_baselines.py`    | Naif referansların model hedefleriyle aynı pencerelerde ve aynı gece kırpmasıyla puanlanması |
| `tests/test_cli_overrides.py`| Eksen geçersiz kılmalarının `--experiment-id` olmadan reddi                     |
| `tests/test_grid.py`         | §13.5 gruplarında yinelenen `experiment_id` olmaması; ablasyon çiftlerinin tek eksende ayrılması |
| `tests/test_eda.py`          | §3 betimleyici katman: gündüz maskesinin geometrik olması, ACF/PACF doğruluğu    |

**Çalıştırma:**

```bash
uv run python scripts/01_prepare_base_data.py                                    # bir kez
uv run python scripts/02_descriptive_analysis.py                                 # EDA tablo + şekilleri
uv run python scripts/03_run_naive_baselines.py                                  # naif referans zemini
uv run python scripts/run_experiment.py --config configs/config_000_smoke.json   # tek deney

# Kayıtlı bir konfigürasyonu tek bir kol için yeniden kullanma. Herhangi bir geçersiz kılma
# --experiment-id ister: aksi hâlde koşu o kimliğin çıktı klasörünü ezer ve ledger'da artık
# yanlış tarif eden bir satır bırakır (§13.4).
uv run python scripts/run_experiment.py --config configs/config_000_smoke.json \
    --exclude-city Rize --loss mae --experiment-id smoke_excl_rize_mae

uv run python scripts/run_all_experiments.py --list                              # ne koşulacak
uv run python scripts/run_all_experiments.py --group ablation --skip-existing --continue-on-error
```

`run_all_experiments.py` grup verilmediğinde **bütün** grupları seçer (günler); önce `--list`.
