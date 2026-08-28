# Betimsel istatistik çıktıları (EDA)

Tümü `scripts/02_descriptive_analysis.py` tarafından üretilir; girdi
`outputs/processed/base_features.parquet` (5 il, 2019-06-30 00:00 → 2026-03-30 23:00, il
başına 59 184 kesintisiz saatlik satır). `DROPPED_COLUMNS` (`ALLSKY_KT`,
`CLRSKY_SFC_SW_DWN`) okuma anında düşürüldüğü için bu çıktılarda hiç yer almaz.

Yeniden üretmek için:

```bash
uv run python scripts/02_descriptive_analysis.py
```

## Makaleye yazarken dikkat edilecek beş nokta

**1. "Gündüz" klimatolojik olarak tanımlıdır, ölçülen değere göre değil.**
Bir satır, kendi (il, ay, saat) hücresinin ortalaması > 0 ise gündüzdür. Yaygın olan
`ışınım > 0` filtresi bağımlı değişkene koşullama yapıyor: klimatolojik olarak gündüz olup
ölçümü tam 0 olan 5 266 satırı (en bulutlu saatler) siliyor, üstelik iller arasında
dengesiz (Antalya 760, Rize 1 253). Bu, gündüz ortalamasını yapay olarak 9.9–14.4 W/m²
yukarı kaydırır ve tam da raporlanan nem/yağış korelasyonlarını zayıflatır.
Havuzlanmış gündüz payı: **%53.0**.

**2. Aylık kutu grafiği saatlik değil, günlük toplam üzerindendir.**
Gündüz *saatlik* değerlerle çizilen bir kutunun genişliğinin ~%91'i gün içi güneş
geometrisidir ve kışın kutu daralır — okuyucu "kış daha stabil" sonucuna varır. Gerçek
tersidir: Ankara 2025'te gündüz-saatlik IQR Ocak 276 < Temmuz 588 W/m², ama günlük
toplamlarla Ocak 1.33 kWh/m² (CV 0.34) > Temmuz 0.72 kWh/m² (CV 0.08). Günlük toplam ayrıca
gündüz filtresinden bağımsızdır (gece 0 katar).

**3. Saat ekseni NASA POWER'ın il-bazlı yerel güneş saatidir (LST), ortak bir saat dilimi
değil.** Ortalama ışınımın zirve saati Konya 11.25, Ankara 11.26, Antalya 11.41, Van 11.56,
Rize 11.89. Ortak saatte doğudaki iller *erken* zirve yapmalıydı; sıralama tersi.
Boylamdan hesaplanan LST beklentileri (Ankara 11.81, Konya 11.83, Antalya 11.95, Van 12.11,
Rize 12.30) gözlemle 0.1 saat içinde örtüşüyor. Sonuçları:
- `HR=11` Rize'de ve Ankara'da farklı fiziksel andır; **saatler iller arasında
  karşılaştırılmaz**, her il kendi paneline bakılır.
- Saat etiketi ilgili saat aralığının **başlangıcıdır**; figürlerde aralık ortasına
  (`HR + 0.5`) çizilir.
- Bu, `data.py`'deki `hour_sin`/`hour_cos` kodlaması için aslında avantajdır: her il kendi
  güneş saatinde kodlanmış olur. Makalenin yöntem bölümünde bir cümleyle belirtilmeli.

**4. p-değeri ve anlamlılık yıldızı bilinçli olarak yoktur.** n ≈ 157 000 otokorelasyonlu
saatlik satırda her |r| > 0.01 "p < 0.001" çıkar; etkin örneklem büyüklüğü bunun kat kat
altındadır. Anlamlılık yerine etki büyüklüğü ve `partial_r_within_hour` raporlanır.

**5. 2026-03 ayı 31 değil 30 günlüktür** (kaynak veri 2026-03-30 23:00'da bitiyor) ve 3B
yüzey yalnız tam takvim yıllarını (2020–2025) kullanır; 2019 (30 Haziran'da başlıyor) ve
2026 kısmi olduğu için dışarıdadır.

## Bulguların yorumu

Aşağıdaki her sayı `tables/` altındaki bir dosyaya dayanır; parantez içinde kaynağı yazılıdır.
Modelleme önerileri **Öneri** olarak işaretlenmiştir — bunlar veriden çıkan yorumlardır,
henüz denenmiş sonuçlar değil.

### 1. Beş il aslında iki rejim: Rize ve diğer dördü

Günlük toplam ışınım ortalaması (`daily_clearness_by_city.csv`): Van 4.98, Antalya 4.94,
Konya 4.87, Ankara 4.66, **Rize 3.69 kWh/m²/gün**. Yani dört il %6'lık bir bant içinde,
Rize ise onlardan %21–26 aşağıda.

Ama asıl fark seviyede değil, **öngörülebilirlikte**:

| | Ankara | Antalya | Konya | Rize | Van |
|---|---|---|---|---|---|
| Berraklık oranı (ort.) | 0.81 | 0.85 | 0.82 | **0.73** | 0.85 |
| Açık gün payı (>0.9) | %45 | %56 | %48 | **%37** | %52 |
| Kapalı gün payı (<0.5) | %11 | %8 | %10 | **%24** | %6 |
| Günlük toplamın CV'si | 0.49 | 0.44 | 0.46 | **0.57** | 0.45 |

("Berraklık oranı" = günlük toplam ÷ aynı yılın-günü için gözlenen 95. persentil; mevsimsel
geometriyi böler, geriye bulutluluk kalır — `daily_clearness_by_city.csv`.)

Meteorolojik profil bunu doğruluyor (`descriptive_stats_by_city_daylight.csv`): Rize'nin
gündüz bağıl nemi %73.7, diğer dört ilde %46–53; yağışı 3.74 mm/saat, diğerlerinde 0.9–1.8.
Van ise diğer uçta: en yüksek berraklık, en düşük kapalı gün payı (%6), en düşük bağıl nem
(%46.2) ve en düşük basınç (77.7 kPa — yükseklik göstergesi). Van'ın 1215.9 W/m² olan
maksimumu da beş ilin en yükseği; yükseklik + kuru hava kombinasyonunun beklenen sonucu.

**Bu, makalenin "5 farklı iklim bölgesi" iddiası için hem iyi hem kötü haber.** Kötü tarafı:
gerçek çeşitlilik esasen tek ilde. Ankara/Konya/Van/Antalya birbirine çok yakın rejimler;
şehir gömülemesinin (`SolarLSTM.city_embedding`) öğrenmesi gereken asıl ayrım Rize'dir. İyi
tarafı: tek bir global modelin dört ili birden öğrenmesi kolay olacak, yani cross-city
transfer iddiası muhtemelen tutacak — ama iddianın gücü Rize'deki performansa bağlı.

**Öneri:** agregat skor Rize'yi gizler (dört il onu 4'e 1 bastırır). Sonuç tablolarında
Rize'nin ayrı satırı zaten var (`results_summary.csv`), ama makale metninde "en zor il" olarak
açıkça tartışılmalı; ayrıca "Rize hariç agregat" bir satır olarak eklenirse şehir gömülemesinin
katkısı görünür hale gelir.

### 2. Mevsimsellik: ışınım ile öngörülebilirlik ters yönde hareket ediyor

`seasonal_target_stats.csv`, günlük toplam (kWh/m²/gün) ve günler-arası CV:

| | Kış | İlkbahar | Yaz | Sonbahar | Yaz/Kış |
|---|---|---|---|---|---|
| Ankara | 2.22 (CV 0.43) | 5.26 (0.34) | 7.29 (**0.14**) | 3.98 (0.37) | 3.3× |
| Antalya | 2.58 (0.38) | 5.66 (0.28) | 7.45 (**0.10**) | 4.21 (0.32) | 2.9× |
| Konya | 2.51 (0.40) | 5.39 (0.33) | 7.44 (**0.13**) | 4.26 (0.35) | 3.0× |
| Rize | 1.78 (**0.50**) | 4.35 (0.45) | 5.71 (0.28) | 3.01 (0.46) | 3.2× |
| Van | 2.71 (0.33) | 5.41 (0.32) | 7.64 (**0.12**) | 4.27 (0.37) | 2.8× |

Yaz günleri kıştan 2.8–3.3 kat fazla enerji taşıyor **ve** 3–4 kat daha az değişken.
Kışın günler hem kısa hem de bulut rejimi kararsız; yazın Anadolu'da neredeyse deterministik
bir açık-hava rejimi var (Antalya'da CV 0.10).

Mevsimsel farkın kaynağını ayırmak makalede güzel bir cümle: Ankara'da gündüz **süresi**
kıştan yaza 10.63 → 14.65 saat (1.38×, `temporal_coverage_by_city.csv`), gündüz saatlerinin
ortalama **yoğunluğu** ise 208.9 → 497.4 W/m² (2.38×). Çarpımları 3.28× — tam olarak
gözlenen günlük toplam oranı. Yani mevsimselliğin yaklaşık üçte biri gün uzunluğundan,
üçte ikisi güneş yüksekliği ve atmosferik geçirgenlikten geliyor.

**Öneri (metrik):** düz RMSE bu tabloyla birlikte yanıltıcıdır. Yaz hatası mutlak olarak
büyük olacak (sinyal büyük) ama görece kolay; kış hatası küçük olacak ama görece zor.
`metrics.py`'ye mevsim kırılımı veya normalize hata (nRMSE = RMSE / o dilimin ortalaması)
eklenmeli — aksi halde model "yazı iyi öğrendi" gibi görünürken asıl zorluğu kaçırıyor olur.

### 3. Zaman değişkenleri: saat baskın, yılın günü ikincil, ikisi de harmoniklerle biter

`time_feature_explained_variance.csv`, η² (açıklanan varyans oranı):

| | saat (24 saat) | yılın günü (24 saat) | saat (gündüz) | yılın günü (gündüz) |
|---|---|---|---|---|
| Havuzlanmış | **0.729** | 0.088 | 0.524 | 0.148 |
| Antalya | 0.778 | 0.087 | 0.584 | 0.171 |
| **Rize** | **0.664** | 0.094 | 0.458 | 0.146 |

Üç sonuç:

- **Günün saati tek başına varyansın %73'ünü açıklıyor**, yılın günü ise %9'unu. Yani modelin
  öğrendiği şeyin büyük kısmı günlük döngü. Bu, 24 saatlik lookback'in neden yeterli
  göründüğünü açıklıyor.
- **Harmonik R² ≈ η²** (0.726 vs 0.729): ilişki neredeyse tamamen ilk iki harmonikle
  yakalanıyor. `hour_sin`/`hour_cos` kodlaması bilgi kaybetmiyor; saat için one-hot veya
  gömüleme aramaya gerek yok.
- **Rize'de saatin açıklayıcılığı en düşük** (0.66 vs Antalya 0.78). Aynı bulgu üçüncü kez
  farklı bir ölçüden geliyor: Rize'de deterministik geometri daha az, bulut gürültüsü daha
  çok baskın.

**Öneri:** deterministik günlük döngü zaten 24 saatlik pencerede mevcut olduğuna göre,
lookback'i 48 saate çıkarmanın kazancı muhtemelen sınırlı olacaktır; asıl kazanç bulut
durumunu taşıyan değişkenlerde. `config_fast_lookback_48h` bu hipotezi test etmek için doğru
deney — ama yeni öznitelik setiyle (17 sütun) yeniden koşulması gerekiyor.

### 4. Ham korelasyonların önemli kısmı güneş geometrisi, gerçek sinyal bulutlulukta

`target_correlation_by_city.csv`. Solda ham Pearson, sağda aynı (il, ay, saat) hücresi
içindeki kısmi korelasyon — yani güneş geometrisi sabitlendikten sonra kalan:

| Değişken | Ham *r* (aralık) | Kısmi *r* (aralık) | Ne oluyor |
|---|---|---|---|
| Bağıl nem | −0.63 … −0.67 | −0.47 … −0.56 | **Ayakta kalıyor** — en güçlü gerçek yordayıcı |
| Sıcaklık | +0.47 … +0.57 | +0.24 … +0.35 | Gücü yarıya iniyor |
| Yağış | −0.09 … −0.21 | −0.27 … −0.37 | **Güçleniyor** |
| Yüzey basıncı | −0.16 … +0.10 | +0.18 … +0.33 | **İşaret değiştiriyor** |
| Özgül nem / çiy nokt. | −0.00 … +0.24 | −0.15 … −0.38 | **İşaret değiştiriyor** |
| Rüzgâr hızı (10/50 m) | −0.24 … +0.21 (tutarsız) | −0.11 … −0.21 (tutarlı) | Zayıf ama istikrarlı hale geliyor |

Bu tablo makaleye girmeli, çünkü ham korelasyona bakarak varılacak sonuç yanlış olur:

- **"Sıcaklık en önemli öznitelik" demek hatalı olurdu.** Sıcaklığın ham +0.55'inin yarısı,
  sıcaklığın da güneş yüksekliğini takip etmesinden kaynaklanıyor — büyük ölçüde ışınımın
  *sonucu*, nedeni değil. Geometri sabitlenince +0.30'a düşüyor.
- **Basınç ve özgül nem ham korelasyonda görünmez ama gerçekte bilgi taşıyor.** Yüksek basınç
  = açık hava, yüksek nem = bulut: ikisi de klasik sinoptik göstergeler ve ancak kısmi
  korelasyonda ortaya çıkıyorlar. Bu, "korelasyonu düşük diye özniteliği atma" refleksine
  karşı somut bir gerekçe.
- **Geometri sabitlendikten sonra hiçbir tek değişkenin |r|'si 0.56'yı geçmiyor** (en
  güçlüsü bağıl nem, Antalya −0.56). Yani tek değişkenli veya doğrusal bir baseline zayıf
  kalacak; çok değişkenli + otoregresif yapı gerekiyor. Bu, LSTM tercihini destekleyen bir
  argüman.

**Doğrusallık:** Spearman ile Pearson farkı hiçbir değişkende 0.06'yı geçmiyor
(`correlation_spearman_pooled.csv`; en büyük fark yağışta −0.06). Yani gizli, monotonik
olmayan bir ilişki yok. Ama `scatter_vs_target_<il>` figürleri açık bir **doygunluk +
çöküş** davranışı gösteriyor. Ankara'da bağıl nemin binlenmiş medyan ışınımı: %18'in altında
doyuyor (667 → 681 W/m², artık fark yok), %20–90 arasında neredeyse doğrusal iniyor
(667 → 73 W/m²), %94'ün üstünde ise çöküyor (14 W/m²). İlişki monotonik ama doğrusal değil —
LSTM için sorun değil, **doğrusal baseline için sorun**; planlanan SVM/RF/MLP
karşılaştırmasında çekirdek/derinlik seçimi bunu karşılayabilmeli, yoksa baseline haksız
biçimde zayıf çıkar ve karşılaştırma yayınlanabilir olmaz.

### 5. Öznitelik setinde iki gereksiz sütun var

`collinear_pairs.csv`: **QV2M–T2MDEW r = 0.96** ve **WS10M–WS50M r = 0.96**. Fiziksel
olarak beklenen (özgül nem ve çiy noktası aynı büyüklüğün iki ifadesi; 10 m ve 50 m rüzgârı
aynı sınır tabakası). Yani 17 öznitelikten fiilen ikisi bilgi katmıyor.

**Öneri:** `T2MDEW` ve `WS50M` çıkarılmış 15 öznitelikli bir ablasyon konfigürasyonu, yeni
bir `experiment_id` ile koşulmalı. LSTM için eşdoğrusallık zararsızdır, ama (a) parametre ve
gürültü azalır, (b) planlanan SVM/RF/MLP baseline'ları için önemlidir, (c) "öznitelik seçimi
yapıldı" cümlesi makalede gerekçelendirilmiş olur. Not: `n_features` ledger'da zaten bir
sütun, dolayısıyla karşılaştırma izlenebilir olur.

### 6. Yıllar arası değişkenlik neredeyse yok — bölme stratejisi için iyi haber

Yıllık ortalama günlük toplam, 2020–2025 (`month_year_anomaly_panel` figürünün verisi):
altı yıl boyunca il başına toplam oynama aralığı sadece **0.25–0.39 kWh/m²/gün**, yani
ortalamanın %5–8'i. Aylık anomalilerin mutlak ortalaması 0.19–0.27 kWh, en büyük tekil
anomali ~1.0 kWh. Buna karşılık mevsimsel aralık 4.6–5.9 kWh.

İlginç bir bölgesel ortaklık var: **2023 beş ilin dördünde en düşük yıl** (Ankara 4.56,
Antalya 4.85, Konya 4.84, Van 4.87); Rize'de en düşük yıl 2022. Yani anomaliler gürültü
değil, bölgesel olarak eşlenik — ama genliği küçük.

İki sonuç:

- **Kronolojik bölme güvenli.** Test kümesi son bir tam mevsimsel yıla denk geliyor
  (`train_ratio=0.74 / val_ratio=0.11`) ve o yılın anormal olmadığını bu tablo gösteriyor.
  Test skoru bir "kötü yıl" kazasından etkilenmiyor.
- **Ama tek yıllık test setinin içsel bir belirsizlik tabanı var:** yıllar arası %5–8'lik
  oynama, tek bir test yılıyla temsil ediliyor. Raporlanan RMSE'nin bu mertebede bir yıl
  seçimi belirsizliği taşıdığı makalede bir cümleyle belirtilmeli.
  *(Not: buradaki "tek yıllık test seti" **modelin** kronolojik bölmesine aittir —
  `train_ratio=0.74 / val_ratio=0.11` test kümesini tam bir mevsimsel yıla oturtuyor. Bu
  bölümdeki "6 yıl" ise 3B yüzey/anomali analizinin kullandığı 2020–2025 tam takvim
  yıllarıdır. Yukarıdaki tabloların hiçbiri son yılla sınırlı değildir; tek istisna
  `monthly_target_stats.csv`'dir.)*
- **3B yüzeyden trend iddiası çıkarılmamalı.** 6 yıl trend için zaten kısa, üstelik sinyal
  mevsimsel genliğin ~%5'i. Figürün doğru mesajı "iklimsel rejim istikrarlı, mevsimsel yapı
  yıldan yıla tekrar ediyor" — bu da bir model için iyi haber, çünkü öğrenilen mevsimsel
  yapının test yılına genellenmesi bekleniyor.

### 7. Dağılım şekilleri: bir ölçekleme sorunu var

`descriptive_stats_by_city_daylight.csv`, havuzlanmış çarpıklık / fazlalık basıklık:

- **Hedef: 0.47 / −0.92.** Ağır kuyruklu değil, *basık ve iki tepeli* — açık gün modu ile
  bulutlu gün modunun karışımı. Normal dağılım varsayan hiçbir şey (ör. hata dağılımının
  Gaussyen olduğu varsayımı) doğrudan geçerli değil; bu, ampirik persentil tabanlı CI
  tercihini (`main_methodology.md`'nin 2.5/97.5 yaklaşımı) destekliyor.
- **Yağış: 8.24 / 101.97.** Aşırı çarpık, gündüz satırlarının çoğunda tam sıfır.
  `StandardScaler` bu sütunda fiilen iş görmüyor: ortalama ve standart sapma birkaç uç
  değer tarafından belirleniyor, sonuçta ölçeklenmiş sütunun neredeyse tamamı dar bir
  aralıkta sıkışıp nadir uçlar ±50'ye gidiyor. **Öneri:** `scaling.py`'de `PRECTOTCORR`
  için `log1p` dönüşümü (train sınırı içinde kalarak). Kısmi korelasyonu −0.27…−0.37 olan,
  yani gerçekten bilgi taşıyan bir değişken; ölçekleme yüzünden kaybedilmesi ziyan olur.
- Rüzgâr hızları (çarpıklık ~1.1) ve diğerleri sorun çıkarmıyor.

### 8. Gece saatleri metriklerin yarısını bedavaya veriyor

24 saatlik ortalama 192.8 W/m², gündüz ortalaması 363.7 W/m²
(`descriptive_stats_by_city_24h.csv` vs `..._daylight.csv`); satırların **%47'si gece** ve
neredeyse tamamı tam sıfır. Bir modelin gece 0 tahmin etmesi bedavadır — MAE/RMSE'nin kabaca
yarısı hiçbir öğrenme gerektirmeden kazanılıyor, CP ise şişiyor (sıfır etrafında dar bir
aralık %100 kapsıyor).

CLAUDE.md bu uyarıyı zaten taşıyor; bu tablolar onu sayısallaştırıyor. **Öneri:**
`metrics.py`'ye gündüz-only kırılım eklenmeli ve literatürle karşılaştırma o rakam üzerinden
yapılmalı. Aksi halde raporlanan RMSE, literatürdeki gündüz-only rakamlarla kıyaslandığında
haksız biçimde iyi görünür.

### 9. Modelin aşması gereken zemin: klimatoloji, RMSE 105 W/m² ve R² 0.86

`persistence_baseline.csv` — üçü de aynı kronolojik test penceresinde, hiçbiri test
satırlarına bakmadan, gündüz saatleri üzerinden:

| Referans | RMSE (W/m²) | MAE | R² |
|---|---|---|---|
| Kalıcılık (dün aynı saat) | 114.5 | 66.0 | 0.839 |
| Akıllı kalıcılık (dünün berraklığı × bugünün açık-hava referansı) | 107.5 | **58.4** | 0.858 |
| **Klimatoloji** ((il, ay, saat) eğitim ortalaması) | **105.0** | 71.1 | **0.864** |

Üç sonuç, üçü de makaleye girmeli:

- **LSTM'in anlamlı olması için gündüz RMSE'sinin 105 W/m²'nin, R²'sinin 0.864'ün altına/
  üstüne geçmesi gerekiyor.** Bu rakam olmadan raporlanan bir "RMSE = 90 W/m²" hakem için
  yorumlanamaz. Kaynak: `persistence_baseline.csv`, figür: `persistence_baseline`.
- **Klimatoloji RMSE'de kazanıyor ama MAE'de kaybediyor** (71.1 vs 58.4). Klasik ayrım:
  klimatoloji koşullu ortalama olduğu için kareli hatayı minimize eder; akıllı kalıcılık
  günü takip ettiği için tipik günlerde daha iyi, uç günlerde daha kötüdür. Modelin ikisini
  birden geçmesi gerekir — sadece RMSE raporlamak bunu gizler.
- **24 saatlik ölçüm zemini bedavaya iyileştiriyor.** Aynı klimatoloji referansı 24 saat
  üzerinden RMSE 76.7 / R² 0.923 veriyor, gündüzde 105.0 / 0.864. Yani gece satırları
  RMSE'yi **%27 düşürüyor** ve R²'yi 0.06 şişiriyor — hiçbir öğrenme olmadan. Literatürle
  kıyaslanabilir rakam gündüz olanıdır.

Rize burada da ayrışıyor: en iyi referansı R² 0.733, diğer dört ilde 0.882–0.894.

### 10. Lookback kararı: 24 saatin ötesi az şey katıyor

`autocorrelation_clearness.csv`, berraklık indeksi kt üzerinde (ham ışınım üzerinde ACF
almak anlamsız olurdu — sadece 24 saatlik güneş döngüsünü yeniden türetir).

**Saatlik ölçekte kt neredeyse bir AR(1):** PACF gecikme 1'de 0.93–0.97, gecikme 2'de
−0.15…+0.13, gecikme 3'te ≈ −0.09. Yani bir saat öncesi neredeyse her şeyi taşıyor,
2. ve sonraki gecikmeler bağımsız bilgi katmıyor.

**Günlük ölçekte:**

| Gecikme | Ankara | Antalya | Konya | Rize | Van |
|---|---|---|---|---|---|
| ACF 1 gün | 0.538 | 0.534 | 0.563 | **0.405** | 0.560 |
| ACF 2 gün | 0.371 | 0.371 | 0.385 | **0.169** | 0.393 |
| **PACF 1 gün** | 0.538 | 0.534 | 0.563 | **0.405** | 0.560 |
| **PACF 2 gün** | 0.115 | 0.121 | 0.100 | **0.006** | 0.116 |
| PACF 3 gün | 0.116 | 0.144 | 0.085 | 0.053 | 0.122 |

**24 saat ilerisi tahmin için önemli olan günlük ölçektir**, çünkü en son gözlem hedefin
24 saat öncesindedir. Orada bilgi neredeyse tamamen 1 gecikmede: PACF 1. günde 0.41–0.56,
2. günde 0.006–0.12'ye düşüyor.

→ **`lookback_hours`'u 24'ten 48'e çıkarmanın kazancı sınırlı olmalı**: 48 saat, kısmi
korelasyonu ~0.1 olan ikinci günü ekliyor. Sıfır değil ama küçük. Ucuz test: tek bir
`lookback_hours=48` konfigürasyonu, yeni `experiment_id` ile. Bu, `TODOs.md`'deki
"time window lag (24h)?" sorusunun veriye dayalı cevabıdır.

**Uyarı — ACF'nin kuyruğuna aldanmayın.** Günlük ACF 30. gecikmede hâlâ 0.18–0.25
görünüyor; bu gerçek bir hafıza değil, kt'nin kendi mevsimsel döngüsünün artığı (kış kt'si
düşük, yaz kt'si yüksek — bkz. mevsimsel kt tablosu aşağıda). Kısa gecikmeleri temizleyen
PACF çöktüğü için doğru okuma PACF'tir. Aynı nedenle saatlik PACF yalnız 12. gecikmeye
kadar raporlanır: gece maskesi ACF'yi çift-yönlü eksik gözlemle tahmin ettiriyor, sonuçta
Durbin-Levinson özyinelemesi uzun gecikmelerde sahte sivrilikler üretiyor.

### 11. Berraklık indeksi ve rampalar: UQ katmanının kapsaması gereken şey

**Fiziksel berraklık indeksi** (`clearness_index_by_city.csv`, kt = ALLSKY / CLRSKY) daha
önceki ampirik proxy'yi doğruluyor ve keskinleştiriyor:

| | Ankara | Antalya | Konya | **Rize** | Van |
|---|---|---|---|---|---|
| Günlük kt ortalaması | 0.806 | 0.840 | 0.816 | **0.697** | 0.827 |
| Günlük kt std | 0.207 | 0.178 | 0.202 | **0.244** | 0.174 |
| Açık gün payı (kt > 0.7) | %73 | %82 | %75 | **%55** | %79 |
| Kapalı gün payı (kt < 0.3) | %2.8 | %1.4 | %2.3 | **%8.0** | %1.0 |

Mevsimsel kt (Kış → Yaz): Ankara 0.679 → 0.922, Antalya 0.716 → 0.953, Van 0.750 → 0.938,
Rize 0.626 → **0.772**. Rize'nin en açık mevsimi bile diğer illerin kışına yakın.

**Rampalar** (`ramp_stats_by_city.csv`, gündüz saatlik |Δ|): medyan 79–113 W/m², %90'lık
165–194, %99'luk 210–218, maksimum 424–1114 W/m². Dağılım dar bir gövde + uzun bir kuyruk:
gövde günün deterministik yükseliş/alçalışı, kuyruk bulut geçişleri. `|Δkt|` medyanı ise
sadece 0.014–0.030, %99'luğu 0.19–0.24 — yani hava kaynaklı ani değişim seyrek ama sert.

**UQ için anlamı:** %95 aralığın kapsaması gereken şey bu kuyruktur. Aralık genişliği
(PINW/MPIW) tüm saatlerde sabit tutulursa, gövdede gereksiz geniş, kuyrukta yetersiz olur —
CP ≈ 0.95 tutturulsa bile. **Öneri:** CP/PINW sonuçları rampa büyüklüğüne göre kırılarak da
raporlanmalı (ör. |Δ| > %90'lık dilim olan saatler ayrı). Rize'nin aralıklarının neden
zorunlu olarak geniş olması gerektiği de burada görünür.

**Ölçüm uyarısı:** NASA POWER saatlik verisi saat *ortalamasıdır*, dolayısıyla saat-içi
bulut geçişlerini yumuşatır. Buradaki rampa büyüklükleri gerçek anlık rampaların alt
sınırıdır; makalede bir cümleyle belirtilmeli.

### Modelleme için çıkan iş listesi

Öncelik sırasıyla, hepsi bu tablolardan doğrudan çıkıyor. Ayrıntılı gerekçeler
`TODOs.md`'nin "EDA bulgularından çıkan görevler" bölümünde.

1. **Gündüz-only eğitim, gece satırlarını silerek değil maskeleyerek yapılmalı**
   (`daylight_block_structure.csv`): satırlar silinirse seri il başına 2 466 bloğa
   parçalanıyor, medyan blok 13 saat, ≥48 saatlik blok oranı 0.000 — yani hiç pencere
   üretilemez. TODOs.md A maddesi.
2. `metrics.py`: gündüz-only kırılım + mevsim kırılımı (madde 8 ve 2) **ve referans
   zemininin rapora eklenmesi** (madde 9). Halen raporlanan rakamlar literatürle
   kıyaslanabilir değil.
3. `scaling.py`: `PRECTOTCORR` için `log1p` (madde 7). TODOs.md B maddesi.
4. 15 öznitelikli ablasyon — `T2MDEW` ve `WS50M` `NUMERIC_FEATURE_COLUMNS`'tan çıkarılmış
   (madde 5). TODOs.md C maddesi.
5. Tek bir `lookback_hours=48` konfigürasyonu (madde 10) — beklenti düşük kazanç, ama
   `TODOs.md`'deki açık soruyu kapatır.
6. Sonuçlarda Rize'nin ayrı tartışılması ve "Rize hariç" agregat satırı (madde 1 ve 9).
   TODOs.md D maddesi.
7. Makale metninde: sıcaklığın ham korelasyonunun neden şişkin olduğu ve kısmi korelasyon
   tablosu (madde 4) — bu, öznitelik seçimini gerekçelendiren asıl argüman.

## Tablolar (`tables/`)

**Kapsam kuralı: bir istisna dışında her tablo verinin tamamını kullanır** — 2019-06-30 →
2026-03-30, il başına 59 184 saat / 2 466 gün, havuzlanmış 295 920 satır (gündüz alt kümesi
156 909). Tek istisna `monthly_target_stats.csv`'dir: o, son 12 ayın kutu grafiğinin
verisidir ve bilerek 2025-04 → 2026-03 ile sınırlıdır. Figürlerde iki istisna vardır:
`monthly_boxplot_last12m_*` (son 12 ay) ve `month_year_surface_*` / `month_year_anomaly_panel`
(yalnız tam takvim yılları, 2020–2025).

| Dosya | İçerik | Kapsam |
|---|---|---|
| `descriptive_stats_by_city_daylight.csv/.md/.tex` | **Birincil tablo.** Gündüz saatleri, il bazında + havuzlanmış. | tam veri (gündüz, n=156 909) |
| `descriptive_stats_by_city_24h.csv/.md/.tex` | Aynı tablo 24 saat üzerinden — modelin bugüne kadar eğitildiği dağılım budur. | tam veri (n=295 920) |
| `temporal_coverage_by_city.csv` | Zaman feature'larının tarifi: kapsam, saat/gün sayısı, gündüz payı, mevsime göre ortalama günlük gündüz süresi, hedefin mevsimsel özetleri. | tam veri |
| `target_by_hour_by_city.csv` | Hedefin (il, mevsim, LST saati) dağılımı — günlük profil figürünün verisi. | tam veri |
| `time_feature_explained_variance.csv` | Saat ve yılın günü için η² ve harmonik R². Sin/cos sütunlarına karşı Pearson *r* yerine bu raporlanır: deterministik bir saat fonksiyonuna karşı korelasyon yorumlanamaz. | tam veri (her ikisi: 24 saat ve gündüz) |
| `wind_direction_circular_stats.csv` | Rüzgâr yönü dairesel istatistiği (bkz. aşağıda). | tam veri (24 saat, WS>1 m/s) |
| `correlation_pearson_<il>.csv`, `correlation_spearman_<il>.csv`, `..._pooled.csv` | 9 fiziksel değişkenin korelasyon matrisleri. | tam veri (gündüz) |
| `target_correlation_by_city.csv` | Hedefle korelasyon + `partial_r_within_hour` (bkz. aşağıda). | tam veri (gündüz) |
| `collinear_pairs.csv` | \|r\| > 0.9 çiftler. | tam veri (gündüz) |
| `seasonal_target_stats.csv` | Mevsim bazında saatlik ve günlük toplam özetleri. | tam veri (2 466 gün/il) |
| `daily_clearness_by_city.csv` | Ampirik berraklık oranı (günlük toplam ÷ aynı yılın-günü için gözlenen 95. persentil), açık/kapalı gün payları — illeri enlemden bağımsız olarak bulutluluk üzerinden kıyaslar. | tam veri (2 464 gün/il; 29 Şubat'lar hizalama için düşülür) |
| `monthly_target_stats.csv` | Son 12 ayın günlük toplam özetleri — kutu grafiğinin verisi. | **SADECE 2025-04 → 2026-03** (364 gün/il) |
| `clearness_index_by_city.csv` | **Fiziksel berraklık indeksi** kt = ALLSKY / CLRSKY, saatlik ve günlük, il × mevsim. Kaynak xlsx'teki açık-hava sütunundan; ayrı bir cache'e (`outputs/processed/clearsky_reference.parquet`) yazılır ve **modele asla öznitelik olarak girmez**. | tam veri |
| `autocorrelation_clearness.csv` | kt'nin ACF ve PACF'i, saatlik (gecikme 1–72) ve günlük (1–30), il bazında. `lookback_hours` kararının dayanağı. | tam veri |
| `ramp_stats_by_city.csv` | Saatlik \|ΔIşınım\| ve \|Δkt\| dağılımı, il × mevsim. | tam veri (gündüz) |
| `daylight_block_structure.csv` | Gece satırları silinseydi oluşacak kesintisiz blok uzunlukları. TODOs.md A maddesinin kanıtı. | tam veri (gündüz) |
| `persistence_baseline.csv` | Referans tahmin zemini: kalıcılık, akıllı kalıcılık, klimatoloji için RMSE/MAE/R²/yanlılık. | **modelin test penceresi** (val_end sonrası) |

**Basıklık Fisher (fazlalık) tanımıdır:** normal dağılım için 0, 3 değil. Gündüz verisinde
hedefin çarpıklığı 0.47, fazlalık basıklığı −0.92 — yani ağır kuyruklu değil, basık/iki
tepeli. Spearman bu yüzden değil, **doğrusal olmayan** ilişkiler için raporlanır.

**Havuzlanmış ("Tümü") satırın standart sapması** iller-içi ve iller-arası varyansın
karışımıdır; iller-arası bileşen `between_city_sd` sütununda ayrıca verilir (hedef için
43.6 W/m²).

**Rüzgâr yönü** ana tablodan çıkarılmıştır: dairesel bir değişkenin aritmetik ortalaması
anlamsızdır (havuzlanmış ham hesap "189.5° ± 107°" verir, bu bir istatistik değil bir
artefakttır). Ayrı tabloda hız-ağırlıklı dairesel ortalama, bileşke uzunluk *R* (0 = yönsüz,
1 = tek yön) ve dairesel SD verilir; `WS10M ≤ 1 m/s` sakin saatler dışlanır ve dışlanan
saat sayısı tabloda yazılıdır. Yön klimatolojisi gündüzle sınırlı değildir, 24 saat
üzerinden hesaplanır. Van belirgin şekilde en yönlü ildir (R = 0.46).

**`partial_r_within_hour`**, (il, ay, saat) hücre ortalaması çıkarıldıktan sonraki
korelasyondur; hava sinyalini güneş geometrisinden ayırır. Fark büyüktür ve makaleye
girmelidir: havuzlanmış gündüz verisinde sıcaklık 0.53 → 0.30, özgül nem +0.04 → −0.27,
basınç −0.03 → +0.26 (işaret değiştiriyor), bağıl nem −0.64 → −0.51. Yani ham
korelasyonların önemli bir kısmı, değişkenlerin de güneş yüksekliğini takip etmesinden
kaynaklanıyor; gerçek bulut sinyali bağıl nem ve yağışta.

## Figürler (`figures/`)

Her figür hem `.png` (300 dpi) hem `.pdf` (vektör, Type 42 yazı tipi) olarak yazılır.
Arka plan her yerde beyazdır; mevsimler renk **ve** çizgi tipiyle ayrışır, böylece
siyah-beyaz baskıda ve renk körlüğünde kimlik korunur.

| Dosya | Ne gösterir | Filtre |
|---|---|---|
| `correlation_heatmap_<il>`, `_pooled` | 9 değişkenin korelasyon matrisi | gündüz |
| `target_correlation_panel` | Değişken × il, hedefle korelasyon | gündüz |
| `scatter_vs_target_<il>` | Her değişkenin hedefe karşı saçılımı + binlenmiş medyan eğrisi | gündüz |
| `monthly_boxplot_last12m_<il>`, `_panel` | Son 12 ayın günlük toplamları | 24 saat (toplam) |
| `month_year_surface_<il>`, `_panel` | 3B ay × yıl × ışınım yüzeyi, 2020–2025 | 24 saat (toplam) |
| `month_year_anomaly_panel` | Aynı verinin 2B anomali görünümü | 24 saat (toplam) |
| `seasonal_diurnal_profile` | Mevsimlere göre günlük profil, LST saati | **24 saat** |
| `seasonal_dayofyear` | Yıl içi gün × günlük toplam, mevsim bantlı | 24 saat (toplam) |
| `target_histogram` | Gündüz ışınımının il bazında dağılımı (iki tepeli yapı) | gündüz |
| `monthly_boxplot_all_years` | Ay bazında kutu grafiği, tüm yıllar havuzlanmış (~200 gün/kutu) | 24 saat (toplam) |
| `autocorrelation_hourly`, `autocorrelation_daily` | kt'nin ACF/PACF'i, il bazında | gündüz (kt tanımlı saatler) |
| `ramp_distribution` | \|Saatlik değişim\| birikimli dağılımı, mevsim bazında | gündüz |
| `persistence_baseline` | Modelin aşması gereken RMSE ve R² zemini | gündüz |
| `rize_comparison` | Rize'yi diğer dört ile karşı dört eksende toplayan panel | karışık (alt panellerde yazılı) |

**Günlük profil figüründe gündüz filtresi bilinçli olarak uygulanmaz:** gece sıfırları
fiziksel bilgidir, filtrelenirse eğri sıfırdan yükselip sıfıra dönmez ve kış sabahı gibi az
örnekli saatlerde yapay sıçrama oluşur. IQR bandı yalnız Kış ve Yaz için çizilir (dört bant
üst üste binince okunmaz oluyor) ve **güven aralığı değil, günler arası IQR**'dir.

**3B yüzey tek başına yanıltıcıdır**, `month_year_anomaly_panel` ile birlikte
değerlendirilmelidir: aylık ortalamalarda mevsimsel aralık 193–247 W/m², aynı ayın yıllar
arası standart sapması ise medyan 8–16 W/m². Yani yüzeyin kabartmasının ~%95'i mevsim
eğrisinin 6 kez tekrarıdır; yıllar arası sinyali gerçekten gösteren figür anomali
haritasıdır.

`seasonal_dayofyear`'da **29 Şubat düşürülür** ve artık yıllarda Mart'tan sonraki günler bir
gün geri kaydırılır; aksi halde 2020 ve 2024 diğer yıllara göre bir gün kayar ve
klimatoloji bulanıklaşır. Düzleştirme, per-gün klimatolojik ortalamanın 7 günlük merkezli
hareketli ortalamasıdır ve seri 3× döşenerek hesaplanır, böylece 31 Aralık/1 Ocak dikişinde
kopukluk olmaz.

## Mevsim tanımı

Meteorolojik mevsimler: **Kış** = Aralık, Ocak, Şubat · **İlkbahar** = Mart, Nisan, Mayıs ·
**Yaz** = Haziran, Temmuz, Ağustos · **Sonbahar** = Eylül, Ekim, Kasım.
