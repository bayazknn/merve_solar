# Keşifsel veri analizi — bulgular ve yorumu

**Veri sürümü:** `SolarData_Merve(140926_V2).xlsx` (14 Eylül 2026, V2) — deponun tek veri dosyası.
**Bu belgenin tarihi:** 14 Eylül 2026. Önceki tüm sürümler geçersizdir.

Bu belge `outputs/eda/` altındaki tablo ve figürlerin **ne söylediğini** anlatır. Hedef kitle
makalenin ortak yazarlarıdır: her bölüm, oradaki sayıyı makaleye taşımak için bilmeniz
gereken her şeyi içerir. Analizlerin nasıl üretildiği (kod, filtreler, kapsam kuralları) yan
taraftaki `README.md`'dedir.

Okuma kılavuzu:

- Her sayı `outputs/eda/tables/` altındaki bir dosyadan gelir. Hangi iddianın hangi dosyaya
  dayandığı **§11**'dedir. Metinde bir sayı ile dosya çelişirse **dosya esastır**.
- **Uyarı** ile başlayan cümleler, o sayıyı makaleye taşırken birlikte taşınması gereken
  kısıtlardır.
- **Öneri** ile başlayan cümleler veriden çıkan modelleme yorumlarıdır; henüz sınanmış
  sonuçlar değildir.
- **Figür ve tablolarda değişkenler NASA POWER'ın kendi sütun adlarıyla anılır**
  (`ALLSKY_SFC_SW_DWN`, `T2M`, `RH2M`, …), Türkçe karşılıklarıyla değil: okuyucunun bir eksen
  etiketini veri seti dokümantasyonuyla ve yöntem bölümündeki öznitelik listesiyle
  eşleştirebilmesi gerekiyor. Birim parantez içinde kalır. Başlıklar, açıklamalar, mevsim
  adları ve tablo sütun başlıkları Türkçedir.

---

## 0. Önce okunması gereken: veri seti ve tanımlar değişti

Yeni dosya eskisinin güncellenmiş hâli değil, **farklı ayarlarla alınmış yeni bir dışa
aktarım**. Aynı NASA POWER kaydı, ama birimler, parametre listesi ve kayıt uzunluğu farklı.
Üstelik eksilen parametrelerden biri projenin en çok kullandığı araçtı, o yüzden bazı
**tanımlar** da değişti. Bunları bilmeden aşağıdaki hiçbir sayı eskisiyle kıyaslanamaz.

### 0.1 Birimler değişti

| Değişken | Eski dosya | Yeni dosya | Ne yaptık |
|---|---|---|---|
| `ALLSKY_SFC_SW_DWN` (hedef) | W/m² | **MJ/m²/saat** | Okurken W/m²'ye çevriliyor (×277.78) |
| `PRECTOTCORR` (yağış) | mm/gün | **mm/saat** | Olduğu gibi bırakıldı |

Çevrim tam ve doğrusaldır; iki dosya ortak 59.184 saatte birleştirilerek doğrulanmıştı:
meteorolojik sütunlar bit düzeyinde aynıydı, çevrilmiş ışınım eski değerleri en fazla
1.39 W/m² sapmayla yeniden üretiyordu.

Hedefi W/m²'ye çeviriyoruz çünkü makalenin, kaynak makalenin ve literatürün tamamı W/m²
kullanıyor.

**Uyarı — bir bedeli var.** Yeni dosya MJ cinsinden **2 ondalık** saklıyor. W/m²'ye
çevrildiğinde hedef **2.78 W/m² adımlarla ayrıklaşıyor**: tüm kayıtta yalnız 387 farklı hedef
değeri var. Ayrıklaştırma gürültüsünün standart sapması 2.78/√12 = 0.80 W/m², yani en iyi
referans zeminin RMSE'sinin %1'inin altında — hiçbir metriği maddi olarak etkilemez. Ama
gündüz tanımını doğrudan ilgilendiren bir sonucu var (§3.2).

Yağışta bedel daha ağır: çözünürlük 0.01 mm/gün'den 0.24 mm/gün'e düştü, eskiden yağışlı
görünen saatlerin %38.7'si artık tam sıfır okunuyor. Toplam yağış korunuyor; kaybedilen şey
çiseleme ayrıntısı.

### 0.2 `CLRSKY_SFC_SW_DWN` sütunu artık yok — yerine güneş geometrisi geldi

Berrak gökyüzü ışınımı bu projede hiçbir zaman bir öznitelik olmadı, ama dört yerde taşıyıcıydı:
gündüz alt kümesinin tanımı, gece sabitlemesinin aracı, berraklık indeksinin paydası, ve akıllı
kalıcılık referansının çarpanı.

Yeni dışa aktarımda bu sütun yok. **Eski dosyadan geri çağırmak yerine, gereken şeyi
hesaplıyoruz** (`src/merve_solar/solar.py`). Böylece proje tek bir excele bağlı kalıyor ve
hiçbir ara üründe eski veriye bağımlılık kalmıyor.

**Gündüz artık hesaplanmış güneş yüksekliğiyle tanımlı.** İl koordinatları ve zaman
damgasından, NREL algoritmasıyla (pvlib), her saatin **orta noktasındaki** görünür güneş
yüksekliği hesaplanıyor; `güneş yüksekliği > 0` gündüz demek. Kayıttan doğrulanan iki
konvansiyon:

- Zaman damgaları ilin kendi yerel güneş saatinde, tam olarak `UTC + yuvarla(boylam/15)`.
  Ölçülen tepe saatleri bu kuralla 0.11 saat içinde örtüşüyor (§2.1).
- Saat etiketi aralık **başlangıcı**, güneşin konumu aralık **ortasında** değerlendiriliyor.

Eşik bilerek **ayarlanmamıştır**. Eşiği tarayarak gerçekleşen hedefe daha iyi uyan bir değer
bulmak mümkün (−2.0° uyumsuzluğu 3.034'ten 587 satıra düşürüyor), ama geometrik bir maskeyi
hedefe göre ayarlamak, maskenin var olma nedenini ortadan kaldırır. Ayarlanmamış seçimin bedeli
ölçüldü: klimatoloji zemininin gündüz RMSE'si 108.78 → 109.86 W/m², R²'si 0.8514 → 0.8456.

**Berraklık indeksi artık literatürün standart tanımıyla.** Eskiden `kt = ALLSKY / CLRSKY`
("berrak gökyüzü indeksi") kullanılıyordu; şimdi

> **kt = GHI / (I₀ · cos θz)**

yani payda **atmosfer üstü** yatay ışınım. Bu bir geri adım değil, ilerlemedir:

| | Eski (berrak gökyüzü paydası) | Yeni (atmosfer üstü paydası) |
|---|---|---|
| Kaynak | Sağlayıcının ürünü | Saf astronomi, hiçbir şey uydurulmuyor |
| Literatürle kıyas | Sağlayıcıya özgü | Standart tanım, doğrudan kıyaslanabilir |
| kt > 1 payı | %2.91 | **%0.001** (150.746 saatte 2 satır) |
| p99 | 1.003 | **0.801** |

**Uyarı — ölçek değişti, eski sayılarla karıştırılamaz.** Bulutsuz bir saat bu ölçekte
kt ≈ 0.75–0.80 okur (atmosferik geçirgenlik), eski ölçekte ≈ 1.0 okuyordu. Gökyüzü durumu
eşikleri de buna göre literatürün standart bantlarına alındı: **berrak kt > 0.65**, **kapalı
kt < 0.35**.

### 0.3 İki analiz kaldırıldı

Berrak gökyüzü **büyüklüğüne** ihtiyaç duyan iki şey, güneşin konumu bilinse bile geri
getirilemedi ve ölçülerek kaldırıldı:

- **Akıllı kalıcılık referansı** (`ŷ(T) = kt(T−24s) × CLRSKY(T)`). Atmosfer üstü paydasıyla
  yeniden kurulduğunda **düz kalıcılıkla aynı şeye dönüşüyor**: gündüz RMSE 121.93 / MAE 72.42,
  düz kalıcılık 121.85 / 72.38. Sebebi basit — ardışık günlerde atmosfer üstü ışınım neredeyse
  aynıdır, oysa berrak gökyüzü sütunu sadeleşmeyen bir hava kütlesi terimi taşıyordu. Hiçbir
  şey eklemeyen bir referans, referans olmamasından kötüdür.
- **`clearsky_index` hedef dönüşümü** (ağın kt'yi regresyonu). Aynı büyüklük sorunu. Eksen,
  dört ızgara grubu ve ledger sütunu kaldırıldı. `ABLATION.md` §6–§7 bu eksenin ürettiği
  bulgulardır; **eski veri seti hakkında** doğru sonuçlar olarak dururlar, yeniden
  ölçülemezler.

**Öneri.** Bu iki analiz istenirse tek hamleyle geri gelir: NASA POWER'dan
`CLRSKY_SFC_SW_DWN` parametresini de içeren bir dışa aktarım, aynı istekte tek kutucuk.

### 0.4 Öznitelik seti: 17 → 13

İki adımda daraldı. 16 Temmuz dosyasından 14 Eylül'e geçerken `QV2M` ve 50 m rüzgâr çıktı, 2 m
rüzgâr girdi; V2 sürümünde 10 m rüzgâr da çıkarıldı.

| Kalan (13) | Çıkan |
|---|---|
| `ALLSKY_SFC_SW_DWN` (kendi gecikmesi), `T2M`, `RH2M`, `T2MDEW`, `PS`, `WS2M`, `PRECTOTCORR` | `QV2M` — `T2MDEW` ile r = 0.962 |
| `WD2M_sin`, `WD2M_cos` | `WS50M`, `WD50M` — 50 m rüzgâr |
| `hour_sin`, `hour_cos`, `doy_sin`, `doy_cos` | `WS10M`, `WD10M` — 10 m rüzgâr |
| | `ALLSKY_KT`, `CLRSKY_SFC_SW_DWN` |

**10 m rüzgârın çıkarılması EDA'nın zaten savunduğu şeydi, bir kayıp değil.** Aynı kaydın V1
sürümünde ölçülmüştü: `WS2M`–`WS10M` korelasyonu 0.987, `WD2M` ile `WD10M` arasındaki açı
farkının medyanı 0.30° ve sin/cos korelasyonları 0.996. Yani 10 m çifti, 2 m çiftinin
taşımadığı neredeyse hiçbir şey taşımıyordu.

Somut sonucu §6.3'te görünür: **artık |r| > 0.9 olan hiçbir öznitelik çifti kalmadı**
(`collinear_pairs.csv` boş). Geriye tek bir gizli fazlalık kalıyor ve o ikili korelasyonla
görünmüyor — `T2MDEW`, `T2M` ve `RH2M`'den türetilebilir (§6.3).

### 0.5 Kayıt uzadı

`-999` kuyruğu 2.208 saatten **744 saate** düştü ve yalnızca hedefi etkiliyor. Sonuç: il başına
**1.464 saat (61 gün) daha fazla veri**.

---

## 1. Kısa özet — makaleye mutlaka girmesi gereken yedi bulgu

**(1) Beş il iklim çeşitliliği iddiasını taşıyor, ama simetrik biçimde değil.** Günlük toplam
ışınım Van 5.00, Antalya 4.97, Konya 4.89, Ankara 4.68 kWh/m²/gün ile %7'lik dar bir bantta;
Rize 3.71 ile bandın %21–26 altında. Asıl fark seviyede değil **öngörülebilirlikte**: Rize'nin
günlük berraklık indeksi 0.463 (diğerleri 0.574–0.609), kapalı gün payı **%28.9** (diğerleri
%6.4–11.3), berrak gün payı %13.8 (diğerleri %43.7–50.0), günler arası değişim katsayısı 0.566
(diğerleri 0.436–0.489). Makalenin "iller arası aktarım" iddiasının gerçek sınavı Rize'dir.

**(2) Gece satırları her metriği bedavaya iyileştirir.** Satırların %49.6'sı geometrik olarak
gecedir ve tamamı tam sıfırdır. Aynı klimatoloji referansı 24 saat üzerinden RMSE 78.3 W/m² /
R² 0.920, gündüz saatleri üzerinden RMSE 109.9 / R² 0.846 veriyor. Gece satırları RMSE'yi %29
düşürüyor ve R²'yi 0.074 şişiriyor. **Literatürle kıyaslanabilir olan gündüz rakamıdır.**

**(3) Modelin aşması gereken zemin klimatolojidir — ve şampiyon metriğe göre değişir.**
Gündüz saatlerinde, modelin kendi kronolojik test penceresinde, boru hattının içinden geçirilmiş
hâliyle: klimatoloji RMSE **109.86** / MAE 75.72 / R² **0.8456**; kalıcılık 121.56 / MAE
**72.15** / R² 0.8110. RMSE ve R²'de klimatoloji, MAE'de kalıcılık kazanıyor. LSTM'in bir sonuç
sayılabilmesi için **her üçünü birden** geçmesi gerekir.

**(4) Ham korelasyonların önemli kısmı güneş geometrisidir.** Havuzlanmış gündüz verisinde
sıcaklığın hedefle ham korelasyonu +0.515, (il, ay, saat) hücresi içindeki kısmi korelasyonu
+0.307. Basınç −0.038'den **+0.268**'e, çiy noktası +0.042'den **−0.272**'ye işaret
değiştiriyor. Daha güçlü ifade: **ham korelasyonda üç değişkenin işareti iller arasında
tutarsızken, geometri sabitlendikten sonra yedi değişkenin yedisi de beş ilde aynı işarete
sahip.**

**(5) Zaman ekseninde bilgi 24 saatlik pencerede tükeniyor.** 24 saat ilerisi tahmin için
belirleyici olan günlük ölçekte berraklık indeksinin kısmi otokorelasyonu 1. günde 0.417–0.561,
2. günde **−0.002…0.098**'e düşüyor. `lookback_hours`'ı 48'e çıkarmak, kısmi korelasyonu
sıfıra yakın bir ikinci gün eklemek demektir.

**(6) Öznitelik seti artık büyük ölçüde temiz, ama bir gizli fazlalık kaldı.** V2 sürümünde
10 m rüzgârın çıkarılmasıyla |r| > 0.9 olan çift kalmadı. Buna karşılık `T2MDEW`, `T2M` ve
`RH2M`'den Magnus bağıntısıyla **r = 0.99919 ve 0.30 °C RMSE** ile yeniden üretilebiliyor —
yani bir ölçüm değil, mevcut iki sütunun determinist bir dönüşümü. İkili korelasyon bunu
göremez (iki değişkenli bir fonksiyondur); 13 öznitelikten 12'si bağımsızdır.

**(7) Test penceresi dört mevsimi kapsıyor; doğrulama penceresi kapsamıyor.** Test 9.097 saat =
**379 gün** (2025-05-16 → 2026-05-30), mevsim yanlılığı yok. Doğrulama penceresi
(2024-08-12 → 2025-05-16) ise **Haziran ve Temmuz'u içermiyor** — yılın en parlak ve en kararlı
iki ayı. Konformal katmanın kalibrasyon kümesi budur; ayrıntı §9.4.

---

## 2. Veri seti ve kapsam

| | |
|---|---|
| Kaynak | NASA POWER saatlik, `SolarData_Merve(140926).xlsx`, il başına bir sayfa |
| İller | Ankara, Antalya, Konya, Rize, Van |
| Kayıt aralığı | 2019-06-30 00:00 → 2026-05-30 23:00 |
| İl başına saat | 60.648 (2.527 gün ≈ 6.92 yıl) |
| Toplam satır | 303.240 |
| Gündüz satırı | 152.893 (**%50.42**) |
| Eksik değer | yok |
| Öznitelik | 16 |
| Hedef | `ALLSKY_SFC_SW_DWN`, W/m² |

Kapsam tamamen dengeli: beş il de aynı 60.648 saati paylaşıyor. Ortalama günlük gündüz süresi
12.07–12.14 saat arasında; iller arası fark enlem farkının beklenen sonucudur.

Kronolojik bölme (train 0.74 / val 0.11 / test 0.15) beş il için **aynı tarihlerde**:

| Bölüm | Aralık | Saat | Gün |
|---|---|---|---|
| Eğitim | 2019-06-30 → 2024-08-11 | 44.879 | 1.870 |
| Doğrulama | 2024-08-12 → 2025-05-16 | 6.671 | 278 |
| **Test** | **2025-05-16 → 2026-05-30** | **9.097** | **379** |

Test penceresi 13 takvim ayını ve dört mevsimin tamamını kapsıyor (İlkbahar 12.725, Yaz 11.040,
Sonbahar 10.920, Kış 10.800 saat).

**Uyarı.** `train_ratio`/`val_ratio` test penceresinin bir tam yılı aşması için ayarlanmıştır.
Oranları değiştirmek dört mevsim özelliğini bozar ve skoru mevsim yanlı hâle getirir.

### 2.1 Saat dilimi: paylaşılan bir saat değil, yerel güneş saati

Saat sütunu ortak bir saat dilimi değildir; her il kendi yerel güneş saatinde kayıtlıdır.
Ortalama ışınımın ağırlık merkezi olarak tepe saati

> Konya 11.24 ≈ Ankara 11.24 < Antalya 11.41 < Van 11.58 < Rize 11.91

sırasını veriyor — ortak bir saat dilimi olsaydı ortaya çıkacak sıranın **tam tersi**, ve
`UTC + yuvarla(boylam/15)` beklentisiyle 0.11 saat içinde örtüşüyor. Bu artık yalnız bir
gözlem değil, **gündüz maskesinin dayandığı konvansiyon**: güneşin konumu bu offsetle
hesaplanıyor.

İki sonucu var:

- **Saatler iller arasında karşılaştırılmaz.** Rize'de saat 11, Ankara'da saat 11 ile aynı
  fiziksel an değildir. Eksenler "yerel saat (LST)" olarak etiketlenmiştir; saat etiketleri
  aralık başlangıcıdır.
- **`hour_sin`/`hour_cos` göründüğünden iyi bir kodlamadır**, çünkü her il kendi güneş
  saatinde kodlanmış olur. Makalenin yöntem bölümünde bir cümleyi hak ediyor.

---

## 3. Hedef değişken

### 3.1 Dağılım

Havuzlanmış, gündüz saatleri: ortalama **384.2 W/m²**, medyan 341.7, standart sapma 277.7,
maksimum 1216.7 (Van). Çarpıklık +0.425, fazlalık basıklığı −0.944. İller arası standart sapma
44.7.

24 saat üzerinden: ortalama 193.7, medyan 8.3, çarpıklık +1.279.

Bu iki satır arasındaki fark §1(2)'nin özüdür. 24 saatlik dağılım iki kütlenin karışımıdır: tam
sıfırdan oluşan gece yığını ve gündüz dağılımı. Gündüz dağılımı **negatif basıklıklıdır** —
tek tepeli değil, geniş ve yayvan; geometrinin gün içinde 0'dan ~1000'e süpürmesinin doğrudan
sonucu.

**Uyarı — ölçekleme.** Hedef normal dağılımlı değildir ve öyle varsayan hiçbir dönüşüm
uygulanmamıştır. `StandardScaler` yalnızca eğitim satırlarına uydurulur.

### 3.2 Gündüz nasıl tanımlanıyor ve neden

**Gündüz = hesaplanmış güneş yüksekliği > 0**, saatin orta noktasında (§0.2).

Denenmiş ve reddedilmiş iki alternatif:

**`hedef > 0`.** Görünüşte en basiti ve bu veride 303.240 satırın 303.204'ünde aynı sonucu
veriyor. Yine de kabul edilemez, iki nedenle ve ikincisi belirleyici:

1. *Ölçüt kümesini sonuca göre seçer.* Gündüz alt kümesi başlık metriklerinin paydasıdır.
   Üyeliği gerçekleşen hedefin fonksiyonu yaparsanız, çok bulutlu bir alacakaranlık saati sıfır
   okur ve metrikten sessizce düşer — yani modelin en kötü olduğu saatler elenir. Bu veride
   ayrıklaştırma yüzünden 36 satır böyledir; küçük, ama mekanizma sınırsız.
2. *Tahmin anında kullanılamaz.* `clamp_night_to_zero` 24 saat sonrası için "güneş batmış mı"
   kararını vermek zorundadır ve o an `y` elde yoktur. Hedefe dayalı bir kural, operasyonel
   olarak elde edilemeyecek bir beceriyi raporlamak olur. Geometriye zaten mecburuz; elimizde
   geometri varken metrik için başka bir tanım kullanmak tutarsızlık olur.

**Klimatolojik (il, ay, saat) hücre ortalaması.** İlk EDA turunda kullanıldı, fazla kaba: bir ay
içinde gün doğumu 30–60 dakika kayar, hücre ortalaması kenar saatin karanlık yarısını da gündüz
sayar. 5.266 gerçek gece satırını gündüz kümesine sokuyordu.

**Yeni tanımın veriyle uyumu.** Geometrik maske ile `hedef > 0`:

- Gündüz dediğimiz ama ışınımı tam sıfır okuyan saat: **1** (303.240 satırda).
- Gece dediğimiz ama ışınım taşıyan saat: 2.968. Bunlar güneşin aralık içinde doğduğu
  alacakaranlık saatleridir; toplam gündüz enerjisinin **%0.03'ünden azını** (ölçülen %0.024)
  taşırlar ve gündüz
  alt kümesinden düşmeleri alt kümeyi *zorlaştırır*, kolaylaştırmaz. Bu, güvenli yöndür.

### 3.3 Gün içi ve mevsimsel yapı

Saat, 24 saatlik varyansın **%73.1'ini** tek başına açıklıyor (havuzlanmış η²); gündüz alt
kümesinde %48.8'e düşüyor. Yılın günü sırasıyla %8.6 ve %14.8.

- 24 saatlik bir skorun dörtte üçü gün/gece döngüsünü bilmekten gelir — modelden değil;
- gündüz alt kümesinde saat hâlâ baskındır ama mevsimin payı neredeyse iki katına çıkar.

Harmonik (sin/cos) uyarlaması η²'nin neredeyse tamamını yakalıyor (24 saat: 0.7313'e karşı
0.7285). **Öneri:** mevcut sin/cos kodlaması kategorik saat kuklalarına kıyasla bilgi
kaybetmiyor; korunmalı.

### 3.4 Mevsimsellik: ışınım ile öngörülebilirlik ters yönde hareket eder

Günlük toplamın mevsimsel değişim katsayısı (CV):

| İl | Kış | Yaz | Kış/Yaz |
|---|---|---|---|
| Ankara | 0.432 | 0.142 | 3.04× |
| Antalya | 0.383 | 0.100 | 3.82× |
| Konya | 0.397 | 0.130 | 3.05× |
| Van | 0.326 | 0.120 | 2.72× |
| Rize | 0.504 | 0.279 | **1.81×** |

Yaz günleri yalnız daha parlak değil, **1.8–3.8 kat daha az değişken**. Hata metrikleri mevsime
göre çok farklı davranacaktır; mutlak hatanın kışın küçük çıkması modelin kışın iyi olduğu
anlamına gelmez — kışın tahmin edilecek şey daha azdır.

**Uyarı.** Rize bandın dışındadır: yazın bile diğer illerin kışına yakın bir değişkenlik taşır.
Rize'yi içeren bir cümle **1.8–3.8** aralığını vermelidir, "3–4 kat" dememelidir.

### 3.5 Yıllar arası değişkenlik: küçük ama sıfır değil

Tam takvim yılları (2020–2025), ortalama günlük toplam kWh/m²/gün:

| İl | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | En iyi/en kötü |
|---|---|---|---|---|---|---|---|
| Ankara | 4.83 | 4.73 | 4.64 | 4.56 | 4.72 | 4.90 | %7.2 |
| Antalya | 5.06 | 5.13 | 5.04 | 4.86 | 4.99 | 5.04 | %5.6 |
| Konya | 5.01 | 4.98 | 4.87 | 4.84 | 4.90 | 5.09 | %5.1 |
| Rize | 3.91 | 3.75 | 3.54 | 3.68 | 3.82 | 3.74 | **%10.3** |
| Van | 4.95 | 5.26 | 5.16 | 4.87 | 4.95 | 5.05 | %8.0 |

Yıllar arası bağıl standart sapma %1.8–3.3. Eğitim ve test yıllarının farklı olması başlı başına
büyük bir kayma yaratmıyor — ama **Rize'de %10'luk bir yıl etkisi** var ve bu, Rize'nin test
skorundaki oynaklığın bir kısmının modelden değil o yılın kendisinden geldiği anlamına gelir.

---

## 4. Meteorolojik değişkenler

Havuzlanmış gündüz değerleriyle:

| Sütun | Ortalama | SS | Aralık | İller arası SS | Not |
|---|---|---|---|---|---|
| `T2M` (°C) | 15.60 | 10.32 | −23.6 … 42.3 | 3.83 | |
| `RH2M` (%) | 53.60 | 23.63 | 3.4 … 100 | **11.19** | En ayrıştırıcı; tek gerçek yordayıcı |
| `T2MDEW` (°C) | 4.27 | 7.05 | −27.5 … 22.9 | 4.43 | Türetilebilir (§6.3) |
| `PS` (kPa) | 88.28 | 6.03 | 75.8 … 97.7 | **6.72** | Varyansın tamamı rakım |
| `WS2M` (m/s) | 2.61 | 1.54 | 0.01 … 13.7 | 0.51 | |
| `PRECTOTCORR` (mm/saat) | 0.072 | 0.263 | 0 … 7.4 | 0.049 | Çarpıklık +8.1 |

**Basınç bir meteorolojik değişken gibi davranmıyor.** Havuzlanmış standart sapması 6.03 kPa ama
iller arası standart sapması 6.72 — varyansın tamamı iller arasıdır (Van 77.7, Konya 87.9,
Ankara 88.8, Rize 91.2, Antalya 96.0 kPa). Havuzlanmış bir modelde `PS` fiilen bir **rakım/il
kimliği göstergesi** olarak çalışır ve şehir gömmesiyle bilgi tekrarı yapar. İl içi değişimi
(SS ≈ 0.4–0.5 kPa) gerçek sinoptik sinyaldir ve §6.1'de kısmi korelasyonun neden işaret
değiştirdiğini açıklar.

### 4.1 Yağış: neredeyse ikili bir değişken

Gündüz saatlerinin **%66.7'si tam sıfır**; sıfır olmayan kuyruk çok çarpık (çarpıklık +8.1).
Hedefle korelasyon, üç kodlama için:

| İl | İkili (yağış var/yok) | Ham miktar | `log1p(miktar)` |
|---|---|---|---|
| Ankara | **−0.168** | −0.101 | −0.115 |
| Antalya | −0.215 | −0.178 | −0.206 |
| Konya | **−0.192** | −0.116 | −0.138 |
| Rize | −0.222 | −0.219 | **−0.250** |
| Van | **−0.188** | −0.139 | −0.162 |

Üç ilde basit bir "yağış var mı" göstergesi ham miktardan daha bilgili; Rize'de `log1p` öne
geçiyor.

**Öneri.** Yağışı tek bir ham sütun yerine **`log1p(PRECTOTCORR)` + ikili yağış göstergesi**
çifti olarak vermek hem Rize'yi hem kuru illeri karşılıyor. Yeni bir deney kimliği gerektirir.

**Birim doğrulaması.** Yeni sütun mm/saat okunup yıllık toplandığında (2020–2025 ortalaması)
Ankara 340, Konya 326, Van 343, Antalya 664, Rize 1399 mm/yıl çıkıyor. Sıralama ve mertebe
Türkiye iklim normalleriyle uyumlu (NASA POWER uydu ürünü olarak Rize ve Antalya'yı düşük
tahmin ediyor; bilinen bir davranış). Bu, mm/saat yorumunun bağımsız teyididir.

### 4.2 Rüzgâr yönü: yalnız Van'da bilgi taşıyor

Hıza göre ağırlıklı dairesel istatistikler, 1 m/s altındaki durgun saatler dışarıda:

| İl | `WD2M` ortalama yön | Bileşke uzunluk *R* | Dairesel SS |
|---|---|---|---|
| Van | 215° | **0.468** | 71° |
| Rize | 270° | 0.244 | 96° |
| Konya | 337° | 0.227 | 99° |
| Antalya | 43° | 0.188 | 105° |
| Ankara | 332° | 0.124 | 117° |

Bileşke uzunluk 0 (tamamen dağınık) ile 1 (tek yön) arasındadır. **Yalnızca Van'da baskın bir
yön var**; diğer dört ilde rüzgâr yönü pratik olarak düzgün dağılmış ve öngörücü olarak
neredeyse boş.

**Uyarı.** Durgun saat payı iller arasında çok farklı (`WS2M ≤ 1 m/s`: Rize 16.175 saat,
Konya 8.606) ve o saatlerde yönün kendisi gürültüdür; yön öznitelikleri tartışılacaksa bu filtre
belirtilmelidir. Eşik 10 m yerine 2 m rüzgârına uygulandığı için dışlanan saat sayısı V1'e göre
belirgin biçimde artmıştır — 2 m'de rüzgâr daha yavaştır, fiziksel bir değişim değildir.

---

## 5. Zamansal yapı ve `lookback_hours` kararı

Otokorelasyon **berraklık indeksi kt üzerinde** hesaplanır, ham ışınım üzerinde değil: ham
ışınımın otokorelasyonu neredeyse tamamen günlük döngüdür ve hiçbir şey öğretmez; kt geometriyi
böldüğü için geriye kalan **atmosferin belleğidir**.

### 5.1 Saatlik ölçek

| | Ankara | Antalya | Konya | Rize | Van |
|---|---|---|---|---|---|
| PACF gecikme 1 | 0.905 | 0.866 | 0.900 | 0.920 | 0.867 |
| PACF gecikme 2 | −0.295 | −0.373 | −0.270 | −0.345 | −0.215 |
| PACF gecikme 3 | −0.013 | +0.087 | −0.016 | −0.006 | −0.006 |
| ACF gecikme 24 | 0.630 | 0.724 | 0.653 | 0.531 | 0.678 |

Birinci gecikme her ilde 0.87'nin üzerinde; ikinci gecikme belirgin biçimde negatif; üçüncü
gecikme sıfırda. Yani saatlik kt bir **AR(2)** gibi davranıyor.

**Uyarı — bu, eski veri sürümünden farklıdır.** Berrak gökyüzü paydasıyla ikinci gecikme sıfır
civarında salınıyordu ("neredeyse AR(1)"); atmosfer üstü paydasıyla net bir ikinci terim
görünüyor. Eski belgelerdeki "saatlik kt bir AR(1)'dir" cümlesi bu veriye taşınmamalıdır.

**Teknik not.** PACF iller arasında 10.–12. gecikmede kesiliyor; sebebi gece saatlerinde kt'nin
tanımsız olması ve serinin günlük bloklara ayrılmasıdır. Ötesi raporlanmaz.

### 5.2 Günlük ölçek: 24 saat ilerisi tahmin için belirleyici olan budur

| | Ankara | Antalya | Konya | Rize | Van |
|---|---|---|---|---|---|
| PACF gün 1 | 0.541 | 0.545 | 0.557 | **0.417** | 0.561 |
| PACF gün 2 | 0.098 | 0.094 | 0.076 | **−0.002** | 0.069 |
| PACF gün 3 | 0.112 | 0.122 | 0.082 | 0.066 | 0.110 |
| ACF gün 30 | 0.177 | 0.229 | 0.164 | **0.083** | 0.165 |

Birinci günden ikinci güne düşüş beş ilâ altı kat. **`lookback_hours = 24` kararının kanıtı
budur:** 48 saate çıkmak, kısmi korelasyonu −0.002 (Rize) ile 0.098 (Ankara) arasında olan bir
ikinci gün eklemek demektir. Bu sonuç, payda değişmesine rağmen eski sürümdekiyle aynıdır —
yani karara dayanak olan bulgu veri tanımına duyarlı değil.

30. gündeki artık otokorelasyon (0.08–0.23) mevsimsel eğilimdir, bellek değil; `doy_sin`/
`doy_cos` bu bilgiyi zaten taşır.

**Uyarı.** Rize her satırda bandın dışındadır ve her seferinde daha az belleğe sahiptir.

### 5.3 Rampalar

Ardışık gündüz saatleri arasındaki mutlak değişim:

| İl | Medyan \|Δ\| | p90 | p99 | >200 W/m² payı | \|Δkt\| p99 |
|---|---|---|---|---|---|
| Ankara | 105.6 | 188.9 | 211.1 | %3.4 | 0.222 |
| Antalya | 116.7 | 191.7 | 219.4 | %6.0 | 0.218 |
| Konya | 111.1 | 194.4 | 216.7 | %6.1 | 0.222 |
| Rize | 83.3 | 166.7 | 213.9 | %1.7 | 0.206 |
| Van | 116.7 | 194.4 | 216.7 | %6.7 | 0.224 |

Ham ışınımdaki rampanın çoğu geometridir. Δkt sütununda iller şaşırtıcı biçimde **birbirine
yakındır** (0.206–0.224): Rize'nin ham rampası küçük görünür çünkü güneşi zaten zayıftır, ama
atmosferik değişkenliği diğerlerinden geri kalmaz.

### 5.4 Gündüz blokları

Gündüz saatleri kesintisiz bloklar hâlinde gelir: il başına 2.527 blok (günde bir), medyan
uzunluk 12 saat, en kısa 9, en uzun 14 (Antalya) / 15 (diğerleri). Hiçbir blok 24 saati
aşmıyor.

**Uyarı.** Bu, 24 saatlik tahmin ufkunun **her zaman en az bir gece içerdiği** anlamına gelir.
Bir tahmin penceresi asla tamamen gündüz olamaz; `clamp_night_to_zero` her pencerenin yaklaşık
yarısını doğrudan etkiler.

---

## 6. Değişkenler arası ilişkiler ve öznitelik seçimi

### 6.1 Ham korelasyon güneş geometrisiyle karışıktır

`target_correlation_by_city.csv` hem ham Pearson korelasyonunu hem de **(il, ay, saat) hücresi
içindeki kısmi korelasyonu** verir. İkincisi, güneş geometrisi ve mevsim sabitken değişkenin
hedefle ilişkisini ölçer. Havuzlanmış gündüz verisi:

| Sütun | Ham r | Kısmi r | Yorum |
|---|---|---|---|
| `RH2M` | −0.628 | **−0.530** | Tek gerçek yordayıcı; her iki ölçümde de güçlü |
| `T2M` | +0.515 | +0.307 | Yarısı geometri |
| `PRECTOTCORR` | −0.168 | **−0.328** | Geometri sabitlenince **iki katına çıkıyor** |
| `T2MDEW` | +0.042 | **−0.272** | **İşaret değiştiriyor** |
| `PS` | −0.038 | **+0.268** | **İşaret değiştiriyor** |
| `WS2M` | +0.143 | −0.150 | **İşaret değiştiriyor** |

Üç değişken işaret değiştiriyor, yağış iki katına çıkıyor. Mekanizma basit: sıcak, rüzgârlı,
yüksek çiy noktalı saatler aynı zamanda **yazın öğlen saatleridir** — ışınımın geometrik olarak
zaten yüksek olduğu saatler. Geometri sabitlendiğinde bu sahte ilişki kaybolur ve fiziksel
ilişki (nem ve bulut → daha az ışınım) ortaya çıkar.

**En güçlü tek argüman:** ham korelasyonda `PS` ve `WS2M`'in işareti beş il arasında
**tutarsız**; kısmi korelasyonda **altı değişkenin altısı da** beş ilde aynı işarete sahip.
Geometri ayıklandığında iller fizik konusunda hemfikir hâle geliyor.

**Öneri.** Makalede yordayıcı önemi tartışılacaksa **kısmi korelasyon tablosu kullanılmalıdır**;
ham matris ancak "neden yanıltıcı olduğu" gösterilmek üzere verilmelidir.

### 6.2 Doğrusallık: Spearman ile Pearson örtüşüyor

Havuzlanmış gündüz verisinde en büyük fark yağışta **−0.059**, ardından `WS2M`'de +0.047.
Hiçbir değişkende fark 0.06'yı aşmıyor (`T2M` −0.017, `T2MDEW` −0.009, `PS` −0.008,
`RH2M` +0.001). Monotonik olmayan bir ilişki yok. Farkın yağış ve
rüzgârda yoğunlaşması beklenen yöndedir (ikisi de çok çarpık) ve **Spearman'ın mutlak değerce
daha büyük olması** §4.1'deki öneriyi güçlendirir: yağışın ilişkisi doğrusaldan çok sıralamaya
dayalıdır.

### 6.3 Eşdoğrusallık: aşikâr fazlalık bitti, bir gizli fazlalık kaldı

**`collinear_pairs.csv` artık boş**: |r| > 0.9 olan hiçbir öznitelik çifti yok. V1 sürümünde tek
böyle çift `WS2M`–`WS10M` (r = 0.987) idi ve 10 m rüzgâr V2'de çıkarıldı. Boş bir tablo burada
bir hata değil, bir sonuçtur.

Havuzlanmış gündüz verisinde |r| > 0.5 olan çiftler — hepsi fiziksel, hiçbiri kaldırılacak
düzeyde değil:

| Çift | Pearson | Spearman |
|---|---|---|
| `T2M` – `RH2M` | −0.673 | −0.676 |
| `T2M` – `T2MDEW` | +0.609 | +0.594 |
| `T2MDEW` – `PS` | +0.521 | +0.482 |

**Uyarı — ikili korelasyonun göremediği bir fazlalık var.** `T2MDEW` bir ölçüm değil, bir
formül: Magnus bağıntısıyla `T2M` ve `RH2M`'den yeniden üretildiğinde r = **0.99919**,
RMSE = **0.30 °C** (24 saat); gündüzde r = 0.99957, RMSE = 0.23 °C. Ölçüm gürültüsü düzeyinde.
İkili korelasyon bunu yakalayamaz çünkü iki değişkenli bir fonksiyondur — `T2M`–`T2MDEW`
korelasyonu yalnız 0.609'dur. Eşdoğrusallık tablosu fazlalık için bir **alt sınırdır**, asla
üst sınır değil.

**Öneri — `T2MDEW` çıkarılarak tek eksenli bir arma koşulmalı.** 13 → 12. Beklenen etki
küçüktür ama ölçülmemiştir, ve LSTM'in girdi katmanı öznitelik sayısıyla ölçeklendiği için
gerçek bir parametre azalmasıdır.

---

## 7. İller arası farklılaşma: Rize ve Van, iki uç

### 7.1 Rize: ayrı bir iklim rejimi

Rize dört ilden farklı bir yerde değil, **farklı bir dağılımda** duruyor.

| Ölçüm | Rize | Diğer dördü |
|---|---|---|
| Günlük toplam ışınım | 3.71 kWh/m²/gün | 4.68 – 5.00 |
| Günlük berraklık indeksi kt | **0.463** | 0.574 – 0.609 |
| Saatlik kt medyanı | **0.422** | 0.565 – 0.600 |
| Berrak gün payı (kt > 0.65) | **%13.8** | %43.7 – 50.0 |
| Kapalı gün payı (kt < 0.35) | **%28.9** | %6.4 – 11.3 |
| Günler arası CV | **0.566** | 0.436 – 0.489 |
| Günlük PACF gün 1 | **0.417** | 0.541 – 0.561 |
| Günlük ACF gün 30 | **0.083** | 0.164 – 0.229 |
| Klimatoloji gündüz RMSE | **133.8 W/m²** | 97.2 – 108.2 |
| Klimatoloji gündüz R² | **0.710** | 0.853 – 0.883 |

Rize'nin **en iyi mevsimi** (yaz, kt = 0.522) diğer illerin **kışına** yakın (0.477–0.556).
Yani mevsimsel bir fark değil, rejim farkı.

**Uyarı — havuzlanmış ortalama Rize'yi gömüyor.** Beş ilin havuzlanmış ortalaması, dört ilin
birbirine yakın değerleriyle Rize'yi 4'e 1 bastırır. Metrik tablosunun `Aggregate_excl_Rize`
satırını ayrıca taşımasının nedeni budur; iller arası aktarım iddiasının katkısı o satır
olmadan görünmez.

**Öneri.** Makalede Rize "zor il" olarak değil, **"ikinci rejim"** olarak tanıtılmalıdır. Beş
ilin iklim çeşitliliği iddiası ancak bu çerçevede doğrudur: dört il tek bir rejimin
varyasyonları, Rize tek başına ikinci bir rejim.

### 7.2 Van: en berrak, ama en uçlu

Van en yüksek günlük toplamı (5.00 kWh/m²/gün), en yüksek berraklık indeksini (0.609), en düşük
kapalı gün payını (%6.4) ve en düşük kış CV'sini (0.326) taşıyor — kışı bile öngörülebilir.
Ayrıca rüzgâr yönünde tek baskın yönlü il (§4.2).

**Uyarı — Van'ın 1216.7 W/m²'lik maksimumu fiziksel bir bulgu değildir.** Bu satır
(2020-02-17 15:00) kt = 2.24'e karşılık gelir: ölçülen ışınım, o saatte atmosferin üstüne
düşenin (544 W/m²) iki katından fazla. Fiziksel olarak imkânsız, yani bir ölçüm/geri-doldurma
artefaktı. Van'ın yüksek rakım ve kuru hava
kombinasyonu gerçek bir olgudur ama **bu satıra dayandırılmamalıdır**.

### 7.3 Berraklık indeksinin sınırları

Yeni tanımla kt fiziksel olarak kusursuz davranıyor: 150.746 ışıklı saatin yalnız **2'si** 1.0'ı
aşıyor, 99. persentil 0.801. Bu, eski berrak-gökyüzü paydasına göre belirgin bir iyileşmedir
(orada kt > 1 payı %2.9 idi, tamamı ayrıklaştırma artefaktı).

**Uyarı.** kt hiçbir yerde kırpılmamıştır ve kırpılmamalıdır.

---

## 8. Referans zemin: modelin aşması gereken sayılar

İki naif referans, **modelin kendi kronolojik test penceresinde** ve **aynı pencereleme ile**
puanlanıyor:

- **Kalıcılık:** 24 saat önceki değeri tekrar et.
- **Klimatoloji:** (il, ay, saat) hücresinin eğitim satırlarındaki ortalaması.

Boru hattından geçirilmiş, havuzlanmış sonuçlar (`scripts/03_run_naive_baselines.py`):

| Referans | Kapsam | RMSE | MAE | R² |
|---|---|---|---|---|
| Kalıcılık | 24 saat | 86.67 | 36.72 | 0.9021 |
| Klimatoloji | 24 saat | 78.33 | 38.53 | 0.9200 |
| Kalıcılık | **gündüz** | 121.56 | **72.15** | 0.8110 |
| Klimatoloji | **gündüz** | **109.86** | 75.72 | **0.8456** |

İl bazında, gündüz, klimatoloji: Antalya 97.2 / Van 98.8 / Konya 107.1 / Ankara 108.2 /
**Rize 133.8** W/m²; R² 0.883 / 0.876 / 0.861 / 0.853 / **0.710**.

**LSTM'in bir sonuç sayılabilmesi için gündüz saatlerinde RMSE'de 109.86 W/m² ve R²'de 0.8456'yı
(klimatoloji) *ve* MAE'de 72.15 W/m²'yi (kalıcılık) aşması gerekir.** Tek bir metrikte kazanmak
yeterli değildir; şampiyon metriğe göre değişiyor.

**Uyarı — akıllı kalıcılık bu tabloda yok.** Berrak gökyüzü büyüklüğü gerektirdiği ve atmosfer
üstü paydasıyla düz kalıcılıkla aynı şeye dönüştüğü için kaldırıldı (§0.3). Önceki veri
sürümünde MAE şampiyonu oydu; şimdi o rolü düz kalıcılık üstleniyor.

**Uyarı — 24 saatlik R² değerleri makaleye girmemelidir.** Klimatoloji 24 saat üzerinde
R² = 0.920 veriyor. R² alt kümenin kendi varyansına göre normalize olduğu için gün/gece salınımı
bu sayıyı domine eder. **24 saatlik R²'nin 0.9'un üzerinde olması hiçbir şeyin kanıtı değildir.**
Aynı normalizasyon argümanı PINW için de geçerlidir.

**Uyarı — 24 saatlik kalıcılığı geçmek bir sonuç değildir.** 24 saat ilerisi bir tahminde
kalıcılık zaten günlük döngüyle hizalıdır, yani ücretsiz bir geometri bilgisi taşır. Kıyas
klimatolojiye karşı yapılmalıdır.

**Uyarı — aralık metrikleri naif referanslar için tanımsızdır.** Tek bir determinist tahminin
aralık genişliği sıfırdır, dolayısıyla CP bir eşitlik testine dönüşür. CP/PINW/MPIW/CWC naif
satırlarda `NaN`'dır; CRPS korunur çünkü orada tam olarak MAE'ye indirgenir.

---

## 9. Belirsizlik (UQ) katmanı için çıkarımlar

**(1) Hedef heteroskedastiktir ve varyans yapısı mevsimle ters yönde hareket eder.** §3.4: kış
CV'si yaz CV'sinin 1.8–3.8 katı. Sabit genişlikli bir aralık kışın dar, yazın geniş kalır.
Konformal katmanın **mevsim eksenli** olması gerektiğinin veri tarafındaki gerekçesi budur.

**(2) İller arası fark mevsimler arası farktan küçük değildir.** §7: Rize'nin klimatoloji gündüz
RMSE'si 133.8, Antalya'nın 97.2 — %38 fark. Skaler tek bir kalibrasyon katsayısının
yetmeyeceği buradan görülür.

**(3) Gece elemanları aralık metriklerini yapısal olarak şişirir.** `clamp_night_to_zero`
açıkken her gece elemanı gerçek değeri tam 0 olan `[0, 0]` aralığı alır, yani **tanım gereği**
kapsanır. Elemanların %49.6'sı gecedir; 24 saatlik CP karışımının yaklaşık yarısı model hiçbir
şey yapmadan 1.0'dır. **Bir koşu önce gündüz CP ≈ 0.95'e göre yargılanmalıdır**, sonra gündüz
PINW/CWC/CRPS'e göre.

**(4) Kalibrasyon kümesinin kusuru yön değiştirdi.** Konformal katman doğrulama bölümünü
kalibrasyon kümesi olarak kullanıyor ve bu kümenin iki bilinen kusuru var: erken durdurma zaten
onu gördü, ve tüm takvimi kapsamıyor. **Yeni veriyle eksik aylar Nisan–Mayıs'tan
Haziran–Temmuz'a kaydı** (doğrulama penceresi 2024-08-12 → 2025-05-16). Bu daha kötü bir
durumdur: mevsim eksenli bir ızgaranın Yaz hücresi yalnız 12–31 Ağustos'tan, yani doğrulama
penceresinin %7'sinden öğrenilecek. Üstelik yanlılık tehlikeli yönde — Ağustos, görmediği
Haziran–Temmuz'dan daha az değişkendir (beş ilde de günlük kt standart sapması 0.007–0.036 daha
düşük), dolayısıyla oradan öğrenilen katsayı **fazla dar** aralık üretir.

**Öneri.** Mevsim eksenli konformal ızgara yeniden koşulmadan önce bu kaydırma belgelenmelidir.
Çözüm oranları değiştirmekte aranmamalıdır (test penceresinin dört mevsim özelliği daha
değerlidir); kalibrasyon kümesini eğitimin son bir yılından ayrı bir dilim olarak almak
sınanabilir ve saniyeler sürer.

---

## 10. Sınırlılıklar ve makalede mutlaka belirtilmesi gerekenler

1. **Veri uydu kaynaklıdır, yer istasyonu değil.** NASA POWER ışınımı uydu gözlemlerinden
   türetir; yağış toplamları Rize ve Antalya'da bilinen biçimde düşük kalmaktadır.

2. **Hedef 2.78 W/m² adımlarla ayrıklaştırılmıştır** (§0.1). Metrikler üzerindeki etkisi ihmal
   edilebilir (sd 0.80 W/m²), ama gündüz tanımını doğrudan ilgilendirir (§3.2).

3. **Gündüz maskesi hesaplanmıştır, ölçülmemiştir** (§0.2). İl koordinatları, zaman
   konvansiyonu ve eşik seçimi makalenin yöntem bölümünde açıkça yazılmalıdır. Ayarlanmamış
   eşiğin bedeli ölçülmüştür: klimatoloji zemini RMSE 108.78 → 109.86.

4. **Berraklık indeksi ölçek değiştirdi** (§0.2). Eski belgelerdeki kt sayıları (Rize 0.697,
   diğerleri 0.806–0.840 gibi) bu veriye **taşınamaz**.

5. **Akıllı kalıcılık ve `clearsky_index` armı yoktur** (§0.3). `ABLATION.md` §6–§7 eski veri
   seti hakkında doğru sonuçlar olarak durur ama yeniden ölçülemez.

5b. **Öznitelik seti iki kez daraldı** (17 → 16 → 13) ve üçü de farklı dışa aktarımlardır
   (§0.4). Tek bir sütun değişikliği bile ledger satırlarını kıyaslanamaz kılar; kıyaslanabilir
   olmak isteyen her koşu aynı sürümden gelmelidir.

6. **Yalnızca beş il vardır ve dördü aynı rejimdedir** (§7.1). "İklim çeşitliliği" iddiası bu
   asimetriyle birlikte sunulmalıdır.

7. **Yıllar arası değişkenlik küçük ama sıfır değildir** (§3.5); Rize'de %10.3.

8. **Eski ledger satırlarının tamamı geçersizdir** ve `outputs/archive/` altına alınmıştır.
   Farklı bir öznitelik seti, farklı bir birim, farklı bir gündüz tanımı ve 61 gün daha kısa bir
   kayıt altında üretilmişlerdir. Yeniden koşulmaları ve **yeni kimlikler** almaları gerekir.

9. **Beş ilin haritası ve coğrafi/iklimsel farklarının yazılı paragrafı hâlâ eksiktir.**
   Koordinatlar artık `config.py::PROVINCE_SITES` içinde hazır durmaktadır.

10. **Figür ve tablolardaki değişken adları NASA POWER'ın ham sütun adlarıdır.** Makale metni
    onları ilk geçtikleri yerde Türkçe olarak tanımlamalıdır (ör. "`RH2M`, 2 m bağıl nem");
    figürler bu tanıma dayanır.

---

## 11. Hangi iddia hangi dosyadan geliyor

### Tablolar (`outputs/eda/tables/`)

| Dosya | Kullanıldığı bölüm |
|---|---|
| `temporal_coverage_by_city.csv` | §2, §3.3 |
| `descriptive_stats_by_city_daylight.csv` / `_24h.csv` (+ `.md`, `.tex`) | §3.1, §4 |
| `target_by_hour_by_city.csv` | §2.1, §3.3 |
| `time_feature_explained_variance.csv` | §3.3 |
| `seasonal_target_stats.csv` | §3.4, §7 |
| `monthly_target_stats.csv` | §3.4 |
| `daily_clearness_by_city.csv` | §1(1), §7.1 (ampirik berraklık; kt'den bağımsız) |
| `clearness_index_by_city.csv` | §7.1, §7.2, §7.3 |
| `autocorrelation_clearness.csv` | §5.1, §5.2 |
| `ramp_stats_by_city.csv` | §5.3 |
| `daylight_block_structure.csv` | §5.4 |
| `persistence_baseline.csv` | §8 (betimsel ikiz; ledger sayıları boru hattından gelir) |
| `target_correlation_by_city.csv` | §6.1 |
| `correlation_pearson_*.csv`, `correlation_spearman_*.csv` | §6.2, §6.3 |
| `collinear_pairs.csv` | §6.3 |
| `wind_direction_circular_stats.csv` | §4.2 |

### Figürler (`outputs/eda/figures/`, PNG 300 dpi + vektör PDF)

| Dosya | Ne gösteriyor |
|---|---|
| `target_histogram` | §3.1'deki iki kütleli yapı |
| `seasonal_diurnal_profile` | §2.1, §3.3 — mevsime göre gün içi profil, yerel saat |
| `seasonal_dayofyear` | §3.4 |
| `monthly_boxplot_last12m_*`, `monthly_boxplot_all_years` | §3.4 |
| `month_year_surface_*`, `month_year_anomaly_panel` | §3.5 |
| `autocorrelation_hourly`, `autocorrelation_daily` | §5.1, §5.2 |
| `ramp_distribution` | §5.3 |
| `correlation_heatmap_*`, `target_correlation_panel` | §6.1 – §6.3 |
| `scatter_vs_target_*` | §4, §6.2 |
| `persistence_baseline` | §8 |
| `rize_comparison` | §7.1 |

### Tablolar dışında, bu belge için hesaplananlar

Makaleye girecekse `scripts/02_descriptive_analysis.py`'ye kalıcı birer tablo olarak
eklenmeleri önerilir; aksi hâlde izlenebilirlik kuralı ihlal edilmiş olur.

| Sonuç | Değer | Bölüm |
|---|---|---|
| Birim çevriminin doğrulanması | ortak 59.184 saatte maks. sapma 1.39 W/m², ortalama 0.70 | §0.1 |
| Yağışta çözünürlük kaybı | eskiden yağışlı görünen saatlerin %38.7'si artık tam sıfır | §0.1 |
| Geometrik maskenin bedeli | klimatoloji gündüz RMSE 108.78 → 109.86, R² 0.8514 → 0.8456 | §0.2, §10(3) |
| Eşik taramasının reddi | ayarlanmış −2.0° eşiği 587, ayarlanmamış 0° eşiği 3.034 uyumsuzluk verir | §0.2 |
| Maske ile `hedef > 0` uyumu | gündüz ama sıfır: 1 satır; gece ama pozitif: 2.968 satır, gündüz enerjisinin %0.024'ü | §3.2 |
| Akıllı kalıcılığın dejenerasyonu | TOA paydasıyla gündüz RMSE 121.93 / MAE 72.42; düz kalıcılık 121.85 / 72.38 | §0.3, §8 |
| `WD2M` – `WD10M` fazlalığı (V1'de ölçüldü, V2'de 10 m sütunu artık yok) | açı farkı medyan 0.30°, ort. 1.56°, p95 6.30°; sin/cos r = 0.996 / 0.997; `WS2M`–`WS10M` r = 0.987 | §0.4, §6.3 |
| Çiy noktasının Magnus ile yeniden üretimi | r = 0.99919, RMSE 0.30 °C (24 s); r = 0.99957, RMSE 0.23 °C (gündüz) | §1(6), §6.3 |
| Yağış kodlamalarının hedefle korelasyonu | tablo §4.1'de; gündüz sıfır payı %66.8 | §4.1 |
| Yağışın yıllık toplamı (birim teyidi) | Ankara 340, Konya 326, Van 343, Antalya 664, Rize 1399 mm/yıl | §4.1 |
| Tepe saatleri (yerel güneş saati teyidi) | Konya 11.2406, Ankara 11.2409, Antalya 11.4107, Van 11.5751, Rize 11.9069 | §2.1 |
| Bölme sınırları ve doğrulama penceresinin eksik ayları | test 9.097 saat / 379 gün; doğrulamada Haziran ve Temmuz yok, Yaz hücresi 480 saat | §2, §9(4) |
| Kalibrasyon deliğinin yönü | Ağustos, Haziran–Temmuz'dan 0.007–0.036 daha düşük günlük kt sd'si taşıyor | §9(4) |
| Yıllar arası değişkenlik | tablo §3.5'te | §3.5 |
