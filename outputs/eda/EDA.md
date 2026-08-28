# Keşifsel veri analizinin yorumu

Bu belge `outputs/eda/` altındaki tablo ve figürlerin **ne anlama geldiğini** tartışır. Analizlerin
nasıl yapıldığı — tanımlar, filtreler, kapsam kuralları, tuzaklar — aynı klasördeki `README.md`
belgesindedir ve burada tekrarlanmaz; gerektiğinde `bkz. README §…` biçiminde atıf yapılır.

Hedef kitle makalenin yazarlarıdır. Paragraflar doğrudan alıntılanabilecek biçimde yazılmıştır.
Her sayı `outputs/eda/tables/` altındaki bir dosyadan doğrulanmıştır; hangi iddianın hangi dosyaya
dayandığı §10'daki eşleme tablosundadır. Metin boyunca **Uyarı** ile işaretlenen cümleler makaleye
sayı taşınırken birlikte taşınması gereken kısıtlardır; **Öneri** ile işaretlenenler veriden çıkan
modelleme yorumlarıdır, henüz sınanmış sonuçlar değildir.

Ayrıca §9.1'de, `README.md` metni ile CSV dosyaları arasında bu tur doğrulamada bulunan
tutarsızlıklar listelenmiştir. Çakışma hâlinde **CSV esastır**.

---

## 1. Kısa özet — makaleye mutlaka girmesi gereken bulgular

**(1) Beş il, iklim çeşitliliği iddiasını taşıyor ama simetrik biçimde değil.** Günlük toplam
ışınım ortalaması Van 4.98, Antalya 4.95, Konya 4.87, Ankara 4.66 kWh/m²/gün ile %6'lık bir bant
içindedir; Rize 3.69 kWh/m²/gün ile bu bandın %21–26 altındadır. Fark seviyede değil
öngörülebilirliktedir: Rize'nin günlük berraklık indeksi ortalaması 0.697 (diğerleri 0.806–0.840),
kapalı gün payı %8.0 (diğerleri %0.97–2.80), günler arası değişim katsayısı 0.569 (diğerleri
0.440–0.493). Makalenin "cross-city transfer" iddiasının gerçek sınavı Rize'dir.

**(2) Ham korelasyonların önemli bir kısmı güneş geometrisidir; öznitelik seçimi kısmi korelasyona
göre yapılmalıdır.** Havuzlanmış gündüz verisinde sıcaklığın hedefle ham korelasyonu +0.520,
(il, ay, saat) hücresi içindeki kısmi korelasyonu +0.300'dür. Basınç −0.037'den +0.263'e, özgül nem
+0.033'ten −0.272'ye işaret değiştirir. Daha da önemlisi: **ham korelasyonda üç değişkenin işareti
iller arasında tutarsızken, geometri sabitlendikten sonra dokuz değişkenin hepsi beş ilde aynı
işarete sahiptir.** Bu tek cümle, kısmi korelasyon tablosunun makaleye girmesi için yeterli
gerekçedir.

**(3) Gece satırları her metriği bedavaya iyileştirir ve rakamları literatürle
kıyaslanamaz kılar.** Satırların %48.8'i geometrik olarak gecedir ve tamamı tam sıfırdır.
Aynı klimatoloji referansı 24 saat üzerinden RMSE 76.7 W/m² / R² 0.923, gündüz saatleri üzerinden
RMSE 106.8 / R² 0.856 verir. Yani gece satırları RMSE'yi %28 düşürür ve R²'yi 0.067 şişirir.
Literatürle kıyaslanabilir olan gündüz rakamıdır.

**(4) Modelin aşması gereken zemin kalıcılık değil klimatolojidir.** Gündüz saatlerinde,
modelin kendi kronolojik test penceresinde: kalıcılık RMSE 116.4 / MAE 68.2 / R² 0.830, akıllı
kalıcılık 109.3 / 60.4 / 0.850, klimatoloji **106.8 / 73.4 / 0.856**. RMSE'de klimatoloji,
MAE'de akıllı kalıcılık kazanır; ikisi birden raporlanmazsa şampiyon değişir. 24 saat ilerisi bir
tahmin için kalıcılığı geçmek bir sonuç değildir — 24 saatlik kalıcılık günlük döngüyle zaten
hizalıdır.

**(5) Zaman ekseninde bilgi 24 saatlik pencerede tükenmektedir.** Berraklık indeksi kt saatlik
ölçekte neredeyse bir AR(1)'dir (PACF gecikme 1: 0.934–0.966; gecikme 2: −0.153…+0.134). 24 saat
ilerisi tahmin için belirleyici olan günlük ölçekte ise kısmi otokorelasyon 1. günde 0.405–0.563,
2. günde 0.006–0.121'e düşer. `lookback_hours` 24'ten 48'e çıkarıldığında eklenen şey kısmi
korelasyonu ~0.1 olan ikinci gündür.

**(6) Öznitelik setinde iki sütun fiilen gereksizdir ve biri bir formülle yeniden üretilebilir.**
`WS10M`–`WS50M` r = 0.965; `QV2M`–`T2MDEW` r = 0.962. Dahası, çiy noktası sıcaklık ve bağıl nemden
Magnus bağıntısıyla **r = 0.9992 ve 0.31 °C RMSE ile** yeniden üretilebilir (bu belge için doğrudan
`base_features.parquet` üzerinde hesaplandı) — yani `T2MDEW` bir ölçüm değil, mevcut iki sütunun
determinist bir dönüşümüdür.

---

## 2. Veri seti ve kapsam

Veri NASA POWER saatlik ürünüdür; beş il için 2019-06-30 00:00 – 2026-03-30 23:00 arası, il başına
**59 184 kesintisiz saatlik satır / 2 466 tam gün**, havuzlanmış **295 920 satır**
(`temporal_coverage_by_city.csv`). Kayıp saat, kayıp gün veya iller arası kapsam farkı yoktur; beş
il birebir aynı zaman ızgarasını paylaşır. Bu, panel yapısının dengeli olduğu ve iller arası
karşılaştırmaların örneklem farkından etkilenmediği anlamına gelir — makalede bir cümleyle
belirtilmeye değer, çünkü çok-istasyonlu çalışmaların çoğunda bu sağlanmaz.

Gündüz tanımı `CLRSKY_SFC_SW_DWN > 0`'dır (geometrik, zaman damgası başına; bkz. README §1 ve
*Düzeltme kaydı*). Havuzlanmış gündüz alt kümesi **151 643 satır, %51.2**'dir. Gündüz payı iller
arasında pratikte sabittir (0.509–0.514) ve ortalama günlük gündüz süresi 12.22–12.35 saattir.
Bu önemli bir nokta: **iller arası ışınım farkı gün uzunluğundan değil, yoğunluktan gelir.**
Enlem aralığı beş il için dar olduğundan (yaklaşık 36.9°–41.0° K) gün uzunluğu ayrımı yıllık
ortalamada kaybolur.

Modelin kronolojik bölmesi (`train_ratio=0.74 / val_ratio=0.11`) altında test penceresi il başına
**8 878 saattir**; bunun **4 544–4 593'ü** geometrik gündüzdür (`persistence_baseline.csv`).

**Uyarı — zaman ekseni ortak bir saat dilimi değildir.** Saat etiketi NASA POWER'ın il-bazlı yerel
güneş saatidir ve ilgili saat aralığının başlangıcını gösterir. `HR = 11` Rize'de ve Ankara'da
farklı fiziksel andır; saatler iller arasında doğrudan karşılaştırılamaz (bkz. README §3). Bu,
`data.py`'deki `hour_sin`/`hour_cos` kodlaması için bir dezavantaj değil avantajdır — her il kendi
güneş saatinde kodlanmış olur — ama yöntem bölümünde açıkça yazılmalıdır.

**Uyarı — ay bazlı tablolarda son ay eksiktir.** Kaynak veri 2026-03-30 23:00'da bittiği için
2026-03 ayı 30 günlüktür. `monthly_target_stats.csv`'de bu satır `n = 30` ile görünür; Mart ışınımı
hızla yükseldiğinden (Şubat→Nisan tırmanışı ~0.044 kWh/m²/gün/gün) atlanan 31 Mart ortalamanın
üstünde bir gündür ve raporlanan Mart ortalaması yaklaşık **%0.4–0.5 (0.018–0.022 kWh/m²/gün)
düşük** kalır. Büyüklük ihmal edilebilir ama tabloya bir dipnot düşülmelidir. 3B yüzey ve anomali
figürleri yalnız tam takvim yıllarını (2020–2025) kullanır.

---

## 3. Değişkenlerin betimsel yapısı

### 3.1 Hedef değişken: dağılım şekli ve ölçekleme

`descriptive_stats_by_city_daylight.csv` ve `descriptive_stats_by_city_24h.csv` aynı 14 sütunlu
yapıyı iki farklı filtre altında verir; ikisini birlikte okumak modelin gördüğü dağılımı anlamanın
en doğrudan yoludur.

| | 24 saat | Gündüz |
|---|---|---|
| n (havuzlanmış) | 295 920 | 151 643 |
| Ortalama (W/m²) | 192.83 | 376.30 |
| Standart sapma | 274.77 | 279.81 |
| Çarpıklık | +1.288 | +0.442 |
| Fazlalık basıklık | +0.420 | −0.933 |

Bu iki sütun arasındaki fark, bu veri setiyle ilgili en pratik gözlemdir: **gece satırlarını
eklemek ortalamayı yarıya indirirken standart sapmayı neredeyse hiç değiştirmez** (274.8 vs 279.8)
ve dağılımın şeklini tersine çevirir. 24 saatlik seri, %48.8'i yapısal sıfır olan sıfır-şişkin bir
karışımdır; medyanı 6.78 W/m², birinci çeyreği tam 0'dır. Gündüzle sınırlandırıldığında dağılım
hafif sağa çarpık ama **basık** hale gelir (fazlalık basıklık −0.933).

**Basıklığın negatif olması makale için önemlidir, ama nedeni sıkça yanlış anlatılır.**
`target_histogram` figürü — bu bilgiyi veren tek kaynak, çünkü tablolarda yalnız momentler vardır —
havuzlanmış gündüz dağılımının **iki ayrı tepesi olmadığını** gösterir. Şekil şudur: en düşük
kutuda (0–24 W/m²) çok keskin bir yığılma (12 928 saat, toplamın %8.5'i), ardından yavaş ve
neredeyse doğrusal azalan geniş bir plato, ve ~980–1050 W/m²'de sert bir kesim. Negatif basıklığı
üreten şey bu **geniş plato ve üstteki fiziksel tavan**dır, iki modun karışımı değil.
Alçak uçtaki yığılma da bulutlu saatler değil, gün doğumu/batımı kenar saatleridir — bu veride
gündüz saatlerinin hiçbirinde ışınım tam 0 değildir (minimum 0.80 W/m²).

**Öneri (UQ).** Sonuç yine de aynı yöne çıkar: dağılım Gauss değildir, üstelik **üstten fiziksel
olarak sınırlıdır** (açık-hava zarfı). Bu, `main_methodology.md`'nin öngördüğü **ampirik persentil
tabanlı güven aralığını** (havuzlanmış örneğin 2.5/97.5 yüzdelikleri) simetrik ortalama ± 1.96·σ
yaklaşımına tercih etmek için doğrudan bir gerekçedir; simetrik bir aralık açık-hava tavanının
üstüne taşacak ve üst kuyrukta boşa genişlik harcayacaktır. Aynı gözlem `seasonal_dayofyear`
figüründe de görünür: nokta bulutunun **üst zarfı keskin, alt kuyruğu uzun ve dağınıktır** — ışınım
açık-hava değerinden yalnızca aşağı sapabilir. Öngörü dağılımının sola çarpık ve üstten sınırlı
olması beklenmelidir.

Aynı asimetri berraklık indeksinde daha da nettir: saatlik kt'nin medyanı 0.904–0.921 iken ortalaması
0.691–0.835'tir (`clearness_index_by_city.csv`), yani dağılım açık-hava değerinde bir tepe ve uzun
bir sol kuyruktan oluşur.

**İl bazında hedef (gündüz):** Ankara 377.11 ± 279.72, Antalya 404.63 ± 285.33,
Konya 395.20 ± 285.56, **Rize 300.38 ± 246.50**, Van 404.07 ± 285.99 W/m². Rize hem en düşük
ortalamaya hem de en düşük standart sapmaya sahiptir — ama bu **daha az belirsizlik demek
değildir**; §6'da görüleceği gibi göreli değişkenliği en yüksek olan ildir. Mutlak saçılımın
düşüklüğü, tavanın alçak olmasının sonucudur.

Havuzlanmış satırdaki standart sapma iller-içi ve iller-arası varyansın karışımıdır; ayrıştırma
`between_city_sd` sütunundadır ve hedef için **43.86 W/m²**'dir (gündüz). 24 saatlik veride bu
değer **22.57**'ye düşer — gece sıfırları her ilde aynı olduğundan, 24 saat üzerinde eğitmek şehir
gömülemesinin öğrenebileceği iller-arası sinyali fiilen yarıya indirir. Bu, gündüz-maskeli bir
kayıp fonksiyonu lehine ikinci ve bağımsız bir argümandır.

### 3.2 Meteorolojik yordayıcılar

Havuzlanmış gündüz momentleri (`descriptive_stats_by_city_daylight.csv`, tam liste kaynakta):

| Değişken | Ort. | SS | Çarpıklık | Faz. basıklık | `between_city_sd` |
|---|---|---|---|---|---|
| Sıcaklık, 2 m (°C) | 15.57 | 10.40 | −0.081 | −0.616 | 3.82 |
| Bağıl nem, 2 m (%) | 53.65 | 23.80 | +0.063 | −1.087 | 11.24 |
| Özgül nem, 2 m (g/kg) | 6.44 | 2.93 | +0.742 | +0.231 | 1.58 |
| Çiy noktası, 2 m (°C) | 4.23 | 7.10 | −0.208 | −0.297 | 4.46 |
| Yüzey basıncı (kPa) | 88.28 | 6.03 | −0.647 | −0.505 | **6.72** |
| Rüzgâr hızı, 10 m (m/s) | 3.52 | 2.01 | +1.065 | +1.856 | 0.49 |
| Rüzgâr hızı, 50 m (m/s) | 4.22 | 2.45 | +1.136 | +2.253 | 0.62 |
| Yağış (mm/gün, bkz. §3.4) | 1.69 | 6.26 | **+8.220** | **+101.287** | 1.19 |

Üç yapısal gözlem:

**Yüzey basıncı bir hava değişkeni değil, fiilen bir il kimliğidir.** İller arası standart sapma
6.72 kPa iken il içi standart sapma 0.40–0.52 kPa'dır — oran yaklaşık 15. İl ortalamaları
Antalya 96.00, Rize 91.18, Ankara 88.78, Konya 87.84, **Van 77.69** kPa'dır ve doğrudan rakımı
kodlar. Havuzlanmış bir modelde `PS`, `city_embedding`'in taşıdığı bilginin gereksiz bir tekrarıdır;
gerçek yordayıcı bilgi il içi sapmalarda, yani sinoptik salınımdadır. Bu, §5.4'te ele alınan
Simpson tersinmelerinin de kaynağıdır.

**Uyarı — Rize'nin basıncı sahil şehri değerlerine uymaz.** 91.18 kPa yaklaşık 850–900 m rakıma
karşılık gelir, deniz seviyesine değil. NASA POWER ızgara hücresi Rize il merkezini değil, dik
eğimli iç kesimi de kapsayan bir alan ortalamasını temsil ediyor olmalıdır. Bu bir hata değildir
ama makalede "Rize (sahil, Karadeniz)" biçiminde tanıtılan noktanın aslında bir hücre ortalaması
olduğu belirtilmelidir; aynı gerekçe Rize'nin ölçülen yağışının gerçek sahil normallerinin altında
kalmasını da açıklar (§3.4).

**Rüzgâr hızı iller arası ayrım taşımaz.** `between_city_sd` 0.49 / 0.62 m/s, il içi standart sapma
1.54–2.71 m/s'dir; yani rüzgâr, illeri birbirinden ayırt eden bir değişken değildir.

**10 m ve 50 m rüzgârı istatistiksel olarak eş, fiziksel olarak tam eş değildir.** Ham korelasyonu
0.965 olmasına rağmen, gündüz ile 24 saatlik ortalamaları karşılaştırıldığında ayrışırlar:
`WS10M` gündüzden 24 saate 0.08–0.65 m/s düşerken (Van −0.652), `WS50M` üç ilde **yükselir**
(+0.15). Bu, gece sınır tabakasının ayrışmasıdır (nocturnal decoupling). Yani çiftin fazlalığı
gündüz verisinde tamdır, 24 saatlik veride kısmidir.

**Nem üç ayrı zaman ölçeğinde çalışır.** Gündüz–24 saat ortalama farkı bağıl nemde +12.0…+12.7
puan (Rize'de yalnız +5.0), sıcaklıkta −2.4…−4.4 °C, buna karşılık özgül nemde |Δ| ≤ 0.56 g/kg ve
basınçta |Δ| ≤ 0.05 kPa'dır. Yani **bağıl nem günlük ölçekte, özgül nem ve çiy noktası sinoptik
ölçekte değişen değişkenlerdir.** Bu ayrım, §5.1'deki kısmi korelasyon sonuçlarının fiziksel
karşılığıdır: geometri sabitlendiğinde bağıl nemin gücünün bir kısmı gider (günlük döngüyle
örtüşen kısım), özgül nemin işareti ise ortaya çıkar (sinoptik nem = bulut).

**Öneri (ölçekleme).** `StandardScaler` sekiz değişkende sorunsuzdur; sorun tek bir sütundadır
(§3.4). Rüzgâr hızlarının basıklığı (1.86 / 2.25; Rize `WS50M` 6.85) sınırdadır ama müdahale
gerektirmez.

### 3.3 Rüzgâr yönü: yalnız Van'da bilgi taşıyor

`wind_direction_circular_stats.csv` ana betimsel tablodan bilinçli olarak ayrılmıştır, çünkü
dairesel bir değişkenin aritmetik ortalaması ve standart sapması tanımsızdır (bkz. README).
Tablo hız-ağırlıklı dairesel ortalamayı, bileşke uzunluk *R*'yi ve dairesel standart sapmayı
verir; `WS10M ≤ 1 m/s` sakin saatler dışlanır.

| İl (WD10M) | Ort. yön | *R* | Dairesel SS | Dışlanan sakin saat |
|---|---|---|---|---|
| Ankara | 337.1° (KKB) | 0.125 | 116.8° | 2 919 (%4.9) |
| Antalya | 31.6° (KKD) | 0.191 | 104.2° | 5 212 (%8.8) |
| Konya | 335.8° (KKB) | 0.219 | 99.9° | 2 712 (%4.6) |
| Rize | 256.3° (BGB) | 0.202 | 102.5° | 6 998 (%11.8) |
| **Van** | **209.6° (GGB)** | **0.458** | **71.6°** | 3 153 (%5.3) |
| Havuzlanmış | 275.8° | **0.091** | 125.3° | 20 994 (%7.1) |

Sonuç açıktır ve olumsuz bir sonucu dürüstçe raporlamak burada daha değerlidir: **beş ilden yalnız
Van yönlü olarak örgütlüdür.** *R* = 0.458, yön vektörlerinin yarıya yakınının aynı yöne baktığı
anlamına gelir; kalan dört ilde *R* = 0.125–0.219, yani vektörlerin %78–88'i birbirini götürür.
Ankara'da 337°'lik "hâkim yön", 116.8°'lik bir dairesel saçılımla birlikte istatistiksel olarak
neredeyse anlamsızdır. Van'ın örgütlülüğü Van Gölü havzasının kanalize ettiği kararlı GGB akışıyla
tutarlıdır. 50 m yönü her ilde 10 m'den daha örgütlüdür (yüzey pürüzlülüğünün üstünde), ama sıralama
değişmez.

**Havuzlanmış *R*'nin 0.091 olması tek global model için asıl uyarıdır.** İl ortalamaları
(337°, 32°, 336°, 256°, 210°) pusulanın tamamına yayıldığı için havuzlandıklarında yönsel tutarlılık
tamamen yok olur. `WD10M_sin`/`WD10M_cos` ve 50 m karşılıkları, **yalnızca şehir kimliğiyle
etkileşim hâlinde** bilgi taşıyabilir; şehir gömülemesi bunu prensipte sağlayabilir, ama bu dört
sütunun katkısının Van dışında sıfıra yakın olması beklenmelidir.

**Uyarı — sakin saatlerin kodlanması kontrol edilmelidir.** Bu tablo `WS10M ≤ 1 m/s` saatleri
dışlar, ama bu satırlar veri setinde durmaktadır ve `WD10M_sin`/`WD10M_cos` sütunlarında bir değere
sahiptir. Sakin bir saatte yönün 0° olarak kaydedilmesi, satırların %4.6–11.8'ine sahte bir "kuzey"
enjekte eder. Modelleme öncesinde bu kodlamanın doğrulanması gerekir.

### 3.4 Yağış: bir birim sorunu ve neredeyse ikili bir yapı

Yağış (`PRECTOTCORR`) betimsel tablodaki tek problemli sütundur ve iki ayrı sorunu vardır.

**Birinci sorun: birim etiketi büyük olasılıkla yanlıştır.** Sütun tablolarda ve figür eksenlerinde
"mm/saat" olarak etiketlenmiştir. Bu okumayla il başına yıllık toplam yağış Ankara 8 458 mm,
Konya 8 257 mm, Van 8 441 mm, Antalya 17 292 mm, Rize 33 602 mm çıkar — hiçbiri fiziksel olarak
mümkün değildir. Saatlik değeri **mm/gün cinsinden bir hız** olarak okuyup yıllık toplamı 24'e
bölmek ise şu sonucu verir: Ankara **352**, Konya **344**, Van **352**, Antalya **721**,
Rize **1 400** mm/yıl. Bu rakamlar, Ankara (~390 mm), Konya (~320 mm) ve Van (~380 mm) için
bilinen iklim normalleriyle %10 içinde örtüşür; Antalya ve Rize için normalin altındadır, ki bu da
§3.2'de belirtilen ızgara hücresi/iç kesim etkisiyle tutarlıdır.

Modelleme açısından bu bir sorun değildir — monoton bir yeniden ölçekleme ölçekleyici tarafından
soğurulur ve hiçbir korelasyonu, hiçbir metriği değiştirmez. **Ama makalede bir eksen etiketi veya
bir tablo başlığı olarak "mm/saat" yazılması hakem tarafından yakalanabilecek bir hatadır.**
`scatter_vs_target_<il>` figürlerinin ekseni ve betimsel tablonun `variable_tr` alanı buna göre
düzeltilmelidir.

**İkinci sorun: dağılım ölçekleyiciyi işlevsiz bırakır.** Havuzlanmış gündüz çarpıklığı **8.220**,
fazlalık basıklığı **101.287**'dir; il bazında daha da kötüdür (Van 11.66 / 241.81,
Ankara 10.95 / 220.01). Gündüz satırlarının **%53.4'ü tam sıfırdır** (Rize'de %34.6, diğer dört
ilde %57.3–59.4). Medyan dört ilde tam 0'dır. `StandardScaler` bu sütunda ortalamayı ve standart
sapmayı birkaç uç değere göre belirler; sonuçta kütlenin yarısından fazlası tek bir noktaya
sıkışır ve nadir uçlar 25–30σ'ya gider. LSTM giriş gradyanları açısından bu sağlıklı değildir.

**Bu sütunu atmak yanlış olur, çünkü gerçekten bilgi taşıyor.** Kısmi korelasyonu −0.279…−0.380 ile
bağıl nemden sonra en güçlü ikinci değişkendir (§5.1). Ayrıca `scatter_vs_target_Ankara` figürü —
tabloların göstermediği bir şey — bilginin **nerede** olduğunu gösterir: binlenmiş medyan ışınım
sıfır yağışta ~410 W/m² iken ilk sıfırdan farklı kutuda ~230'a düşer ve 40 mm/gün'e kadar
düz kalır. Yani **bilgi yağış miktarında değil, yağışın olup olmadığındadır.**

Bunu doğrudan sayısallaştırdık (`base_features.parquet`, gündüz satırları): ikili bir "yağış var"
göstergesinin hedefle korelasyonu, ham miktarın korelasyonundan **beş ilin dördünde daha
güçlüdür** — Ankara −0.189 vs −0.097, Konya −0.217 vs −0.109, Antalya −0.215 vs −0.173,
Van −0.169 vs −0.137; tek istisna Rize'dir (−0.200 vs −0.215). Yağışsız ve yağışlı gündüz
saatlerinin ortalama ışınımı arasındaki fark 97.7 (Van) ile 125.8 (Konya) W/m² arasındadır.

**Öneri.** `scaling.py`'de `PRECTOTCORR` için `log1p` dönüşümü (eğitim sınırı içinde kalarak)
uygulanmalıdır; ek olarak bir ikili "yağışlı saat" göstergesi eklemek, tablo ve figürdeki kanıta
göre neredeyse bedava bir kazançtır. Bu ablasyon ayrı bir `experiment_id` ile koşulmalıdır.

**Uyarı.** 24 saatlik veride yağışın maksimumu 347.72 (gündüzde 177.24) birimdir. Bu gece değeri
ölçekleyiciye girmeden önce ayrıca incelenmelidir.

---

## 4. Zamansal yapı

### 4.1 Günün saati: baskın ama büyük ölçüde önemsiz

`time_feature_explained_variance.csv`, saat ve yılın günü faktörleri için η² (tek yönlü ANOVA'da
açıklanan varyans oranı) ve ilk harmonik çiftinin R²'sini verir. Sin/cos sütunlarına karşı düz
Pearson *r* raporlanmaz, çünkü determinist bir saat fonksiyonuna karşı korelasyon yorumlanamaz.

| | saat, 24 s | yıl günü, 24 s | saat, gündüz | yıl günü, gündüz |
|---|---|---|---|---|
| Ankara | 0.730 | 0.100 | 0.500 | 0.179 |
| Antalya | **0.778** | 0.087 | **0.566** | 0.170 |
| Konya | 0.756 | 0.089 | 0.536 | 0.162 |
| **Rize** | **0.664** | 0.094 | **0.431** | 0.141 |
| Van | 0.768 | 0.090 | 0.551 | 0.159 |
| Havuzlanmış | 0.729 | 0.088 | 0.499 | 0.147 |

Üç okuma:

**(a) Saatin baskınlığı büyük ölçüde gece–gündüz karşıtlığıdır.** 24 saatlik veride saat, yılın
gününü 7.3–9.0 kat geride bırakır (havuzlanmış 0.729 vs 0.088). Gündüzle sınırlandırıldığında oran
2.8–3.5 kata düşer (0.499 vs 0.147) ve yılın gününün payı neredeyse iki katına çıkar. Yani
"modelin öğrendiğinin %73'ü günlük döngüdür" cümlesi 24 saatlik veri için doğru ama yanıltıcıdır;
gündüz saatlerinde tablo çok daha dengelidir. Makalede hangi kapsam kullanıldığı yazılmalıdır.

**(b) Sin/cos kodlaması saat için bilgi kaybetmez, yılın günü için biraz kaybeder.** Saat
faktöründe η² ile harmonik R² arasındaki fark her hücrede ≤ 0.004 (bağıl kayıp ≤ %0.5, gündüzde
≤ %0.24) kalır: tek bir harmonik çift, 24 kategorili ANOVA'nın açıkladığı varyansı neredeyse
tamamen yeniden üretir. Saat için one-hot kodlama veya ayrı bir gömüleme aramaya gerek yoktur.
Buna karşılık **yılın gününde kayıp gündüz saatlerinde yoğunlaşır**: Rize 0.141 → 0.117
(**bağıl %17.1 kayıp**), Van %9.9, Konya %8.3, Ankara %7.6. Mutlak olarak konu edilen varyans
küçüktür (~0.02), ama takvim özniteliğinden daha fazlasını almak istenirse doğru müdahale ikinci
bir yılın-günü harmoniği eklemektir.

**(c) Rize'de saatin açıklayıcılığı her iki kapsamda da en düşüktür** (0.664 / 0.431). Aynı bulgu
bu belgede en az beş farklı ölçüden gelmektedir; §6'da toplanmıştır.

**Günlük profilin şekli.** `target_by_hour_by_city.csv`, (il, mevsim, LST saati) hücrelerinde
ortalama, medyan ve çeyrekleri verir. Zirve saat dört ilde `HR = 11`, Rize'de `HR = 12`'dir; enerji
ağırlık merkezi Ankara 11.255, Konya 11.254, Antalya 11.411, Van 11.561, **Rize 11.891**'dir.
Saat etiketi aralığın başlangıcı olduğundan bu değerlere +0.5 eklenerek boylamdan hesaplanan
LST beklentileriyle (Ankara 11.81, Konya 11.83, Antalya 11.95, Van 12.11, Rize 12.30)
karşılaştırıldığında, dört il beklenen güneş öğlesinden **0.05–0.08 saat erken**, Rize ise
**0.09 saat geç** kalır. Yani zaman ekseni tutarlıdır; kalan küçük asimetri meteorolojiktir:
Anadolu illerinde öğleden sonra konvektif bulut günün enerjisini sabaha kaydırır, Rize'de ise
sabah bulut örtüsü öğleden sonra açılır. Yaz mevsiminde günlük enerjinin `HR ≤ 11`'de kalan payı
Ankara ve Konya'da 0.531, Antalya'da 0.508, Van'da 0.494, **Rize'de 0.432**'dir.

Profilin *biçimi* ise iller arasında şaşırtıcı ölçüde ortaktır. Zirveye normalize edilmiş eğriler
Ankara ile Konya arasında pratikte özdeştir (maksimum mutlak fark 0.008). Ankara–Rize farkı ham
hâlde 0.178 iken, eğriler ağırlık merkezine hizalandığında **0.052**'ye düşer: **iller arası eğri
farkının yaklaşık %70'i bir zamanlama kaymasıdır, bir biçim farkı değil.** Bu, tek global model +
şehir gömülemesi tasarımını destekleyen somut bir argümandır — gömülemenin taşıması gereken şey
esas olarak bir seviye ve küçük bir faz kaymasıdır.

Gündüz penceresinin genişliği kışın beş ilde de 11 saat (07–17), yazın 14–15 saattir; yarı-maksimum
genişlik kışın 6, yazın 8 saat (Rize 9) olarak her ilde aynıdır.

### 4.2 Mevsimsellik: ışınım ile öngörülebilirlik ters yönde hareket eder

`seasonal_target_stats.csv`, günlük toplam (kWh/m²/gün) ve günler arası değişim katsayısı:

| | Kış | İlkbahar | Yaz | Sonbahar | Yaz/Kış |
|---|---|---|---|---|---|
| Ankara | 2.22 (CV 0.43) | 5.26 (0.34) | 7.29 (**0.14**) | 3.98 (0.37) | 3.28× |
| Antalya | 2.58 (0.38) | 5.66 (0.28) | 7.45 (**0.10**) | 4.21 (0.32) | 2.89× |
| Konya | 2.50 (0.40) | 5.39 (0.33) | 7.45 (**0.13**) | 4.26 (0.35) | 2.97× |
| Rize | 1.78 (**0.50**) | 4.35 (0.45) | 5.71 (0.28) | 3.01 (0.46) | 3.21× |
| Van | 2.71 (0.33) | 5.41 (0.32) | 7.64 (**0.12**) | 4.27 (0.37) | 2.82× |

Yaz günleri kıştan 2.8–3.3 kat fazla enerji taşır **ve** belirgin biçimde daha az değişkendir.
Kışın günler hem kısa hem de bulut rejimi kararsızdır; yazın Anadolu'da neredeyse determinist bir
açık-hava rejimi vardır (Antalya'da CV 0.10).

**Uyarı — "yazın 3–4 kat daha az değişken" ifadesi beş il için doğru değildir.** Kış/Yaz CV oranı
Ankara 3.04, Antalya 3.82, Konya 3.06, Van 2.72, **Rize 1.81**'dir. Doğru ifade "**1.8–3.8 kat**"
veya "Anadolu illerinde 3–4 kat, Rize'de yalnızca 1.8 kat"tır (bkz. §9.1, madde 6).

**Mevsimsel farkın ayrıştırılması makale için temiz bir cümle verir.** Günlük toplam, tanım gereği
gündüz süresi ile ortalama gündüz yoğunluğunun çarpımıdır; `temporal_coverage_by_city.csv` ikisini
de verir. Ankara'da kıştan yaza gündüz **süresi** 10.28 → 14.45 saat (1.41×), ortalama gündüz
**yoğunluğu** 216.1 → 504.3 W/m² (2.33×), çarpımları 3.28× — gözlenen oranın tam kendisi.
Beş ilde de bu çarpım gözlenen oranı 10⁻³ hassasiyetle verir. **Uyarı:** bu bir doğrulama değil,
bir özdeşliktir; makalede "ayrıştırma" olarak sunulmalıdır. Anlamlı olan payların büyüklüğüdür:
mevsimselliğin logaritmik ölçekte **%29–36'sı gün uzunluğundan, %64–71'i güneş yüksekliği ve
atmosferik geçirgenlikten** gelir. Van'ın mevsimselliği en zayıftır (2.82×) çünkü kış yoğunluğu
zaten en yüksektir (262.4 W/m²); Ankara'nınki en güçlüdür (3.28×).

**Aylık dağılımın şekli — tablolarda olmayan bilgi.** `monthly_boxplot_all_years` figürü hiçbir
CSV'nin karşılamadığı bir soruyu cevaplar: mutlak saçılım hangi ayda en büyüktür? Cevap kış değil,
**geçiş aylarıdır**. Ankara'da Mayıs kutusunun çeyrekler açıklığı yaklaşık 5.3–7.9 kWh/m² ile
yılın en genişidir; Temmuz kutusu 7.6–8.3 ile en darlarındandır; Ocak kutusu mutlak olarak dardır
ama medyanı (2.1) küçük olduğu için göreli olarak en geniştir. Ayrıca aykırı değerler
(kutu dışı noktalar) neredeyse yalnızca yaz aylarında ve **aşağı yönde** birikir — nadir bulutlu
yaz günleri. Bu, mevsimsel ortalamaların anlatmadığı bir yapıdır ve model hatasının ilkbaharda
neden yüksek olacağını önceden açıklar.

**Uyarı (bkz. README §2).** Aylık kutu grafiği **günlük toplamlar** üzerindendir. Gündüz *saatlik*
değerlerle çizilen bir kutunun genişliğinin büyük kısmı gün içi güneş geometrisidir ve kışın kutu
daralır; okuyucu "kış daha stabil" gibi tersine bir sonuca varır.

**Öneri (metrik).** Düz RMSE bu tabloyla birlikte yanıltıcıdır: yaz hatası mutlak olarak büyük
olacaktır (sinyal büyük) ama görece kolaydır; kış hatası küçük olacaktır ama görece zordur.
`metrics.py`'ye mevsim kırılımı veya dilim ortalamasına normalize edilmiş hata (nRMSE) eklenmelidir.

### 4.3 Yıllar arası değişkenlik: yok denecek kadar az, ama sıfır değil

`monthly_target_stats.csv` yalnız son 12 ayı (2025-04 → 2026-03, il başına 364 gün) kapsar ve
`monthly_boxplot_last12m_*` figürlerinin verisidir. Kapsamı sınırlı olan tek tablodur; bu nedenle
tek başına iklimsel bir ifadeye kaynak gösterilemez, ama **model performansının okunacağı test
dönemine denk düştüğü için** ayrı bir değeri vardır.

Son 12 ay yıllık ortalamada anormal değildir: tüm-yıllar ortalamasına göre Ankara +%2.4,
Konya +%2.3, Antalya −%0.2, Van −%0.1, Rize −%0.9. **Ama mevsimsel dağılımı anormaldir: kış
belirgin biçimde karanlıktır** — Van −%11.9 (2.39 vs 2.71 kWh/m²/gün), Rize −%11.6, Ankara −%7.7,
Konya −%4.2, Antalya −%3.9; bu, Ankara'da +%4.5 ve Konya'da +%3.0'lık parlak bir yazla dengelenmiştir.
Test kümesinin kış dilimindeki hata rakamları okunurken bu göz önünde bulundurulmalıdır.

Aynı tabloda beş ilin **en parlak ayı istisnasız Haziran 2025**'tir (Ankara 8.05, Van 8.16,
Konya 8.05, Antalya 7.92, Rize 6.37 kWh/m²/gün) — Temmuz değil. En karanlık ay Ankara ve
Antalya'da Ocak 2026, Konya, Rize ve Van'da Aralık 2025'tir. Aylık değişim katsayıları mevsimsel
tablodan daha keskindir: Antalya Ağustos 2025'te **0.046**, Ankara Ağustos 2025'te 0.062
(fiilen determinist bir açık-hava rejimi) iken Rize Şubat 2026'da **0.567**, Ocak 2026'da 0.503'tür.
**Rize'nin en iyi ayı (Temmuz 2025, CV 0.269) diğer illerin kış aylarından daha değişkendir.**

**Uyarı — bu tablonun mevsim etiketleri temiz değildir.** Son 12 aylık pencerede "İlkbahar"
Nisan+Mayıs 2025 ile Mart 2026'dan oluşur: iki farklı ilkbahardan üç ay. Mevsimsel yorum için
`seasonal_target_stats.csv` kullanılmalıdır.

**Uzun dönemli yıllar arası sinyal için doğru figür 3B yüzey değil, anomali haritasıdır.**
`month_year_surface_panel` figürü aylık ortalama günlük toplamı (ay × yıl × ışınım, 2020–2025)
gösterir ve gösterdiği şey tam olarak beklenendir: yıl eksenine **paralel, kabartması sabit bir
sırt**. Aylık ortalamalardaki mevsimsel aralık 193–247 W/m², aynı ayın yıllar arası standart sapması
ise medyan 8–16 W/m²'dir; yani yüzeyin kabartmasının yaklaşık %95'i mevsim eğrisinin altı kez
tekrarıdır. Figür, ortak yazarların istediği görselleştirmedir ve "iklimsel rejim istikrarlı,
mevsimsel yapı yıldan yıla tekrar ediyor" mesajını taşır — bir model için iyi haberdir, çünkü
öğrenilen mevsimsel yapının test yılına genellenmesi beklenir. **Uyarı:** üç boyutlu perspektif
uzak yılların kış çukurunu sırtın arkasına gizler ve renk ölçeği için bir çubuk yoktur; yayın
öncesinde ya bir renk çubuğu eklenmeli ya da figür yalnızca anomali paneliyle birlikte
kullanılmalıdır. Yüzeyden **trend iddiası çıkarılmamalıdır**: altı yıl trend için kısadır ve sinyal
mevsimsel genliğin ~%5'idir.

`month_year_anomaly_panel` figürü aynı verinin iki boyutlu anomali görünümüdür ve yıllar arası
sinyalin gerçekten bulunduğu yerdir. Bu grid hiçbir tabloya yazılmamıştır, dolayısıyla aşağıdaki
gözlemler yalnız figürden okunabilir:

- Anomaliler **3.–7. aylarda yoğunlaşır**; kasım–şubat hücreleri neredeyse renksizdir. Bunun
  nedeni kısmen ölçek birimidir: anomali mutlak kWh cinsindendir ve kış ortalaması küçüktür,
  dolayısıyla göreli olarak büyük bir kış anomalisi bile soluk görünür. Makalede kullanılacaksa
  normalize (yüzde) bir sürüm daha dürüst olur.
- **2023, dört ilde en düşük yıldır ve bu bir yıl boyu süren bir eksiklik değil, ilkbahar–erken
  yaz odaklı bir olaydır**: Ankara'da 3.–6. aylar üst üste negatif, Konya'da 5.–6. aylar, Antalya'da
  5. ay belirgin negatiftir. Rize aynı yılda 3. ayda güçlü negatif ama 7. ayda pozitiftir, yani
  **Rize bölgesel anomaliden ayrışır**.
- Rize'nin paneli genel olarak daha benekli ve mevsime bağlı olmayan bir dağılım gösterir
  (2020–2021'de sonbahar aylarında güçlü anomaliler) — bulut kaynaklı değişkenliğin yıl içine
  yayıldığı, ilkbahara toplanmadığı anlamına gelir.

**Sonuç ve bölme stratejisi.** Yıllık ortalama günlük toplamın altı yıl boyunca oynama aralığı il
başına 0.25–0.39 kWh/m²/gün, yani ortalamanın %5–8'idir. Kronolojik bölme bu nedenle güvenlidir:
test kümesi son bir tam mevsimsel yıla denk gelir ve o yıl anormal değildir. **Ama tek yıllık test
setinin içsel bir belirsizlik tabanı vardır**: yıllar arası %5–8'lik oynama tek bir test yılıyla
temsil edilmektedir; raporlanan RMSE'nin bu mertebede bir "yıl seçimi" belirsizliği taşıdığı
makalede bir cümleyle belirtilmelidir.

### 4.4 Otokorelasyon ve `lookback_hours` kararı

`autocorrelation_clearness.csv`, ACF ve PACF'i **berraklık indeksi kt üzerinde** verir; ham ışınım
üzerinde ACF almak anlamsız olurdu, çünkü yalnızca 24 saatlik güneş döngüsünü yeniden türetirdi.

**Saatlik ölçekte kt neredeyse bir AR(1)'dir.** PACF gecikme 1: Ankara 0.963, Antalya 0.960,
Konya 0.963, Rize 0.966, Van 0.934. Gecikme 2: −0.056 / −0.153 / −0.026 / −0.149 / +0.134.
Gecikme 3: −0.100 / −0.057 / −0.084 / −0.096 / −0.034. Bir saat öncesi neredeyse her şeyi taşır;
2. ve sonraki gecikmeler bağımsız bilgi katmaz.

**24 saat ilerisi tahmin için belirleyici olan günlük ölçektir**, çünkü en son gözlem hedefin
24 saat öncesindedir.

| Gecikme | Ankara | Antalya | Konya | Rize | Van |
|---|---|---|---|---|---|
| ACF 1 gün | 0.538 | 0.534 | 0.563 | **0.405** | 0.560 |
| ACF 2 gün | 0.371 | 0.371 | 0.385 | **0.169** | 0.393 |
| PACF 1 gün | 0.538 | 0.534 | 0.563 | **0.405** | 0.560 |
| PACF 2 gün | 0.115 | 0.121 | 0.100 | **0.006** | 0.116 |
| PACF 3 gün | 0.116 | 0.144 | 0.085 | 0.053 | 0.122 |

Bilgi neredeyse tamamen birinci gecikmededir: PACF 1. günde 0.405–0.563, 2. günde 0.006–0.121.
**`lookback_hours`'u 24'ten 48'e çıkarmak, kısmi korelasyonu ~0.1 olan ikinci günü eklemek
demektir** — sıfır değil ama küçük. Bu, `TODOs.md`'deki "zaman penceresi gecikmesi (24 saat)?"
sorusunun veriye dayalı cevabıdır ve ucuz bir tek-konfigürasyon testiyle
(`lookback_hours=48`, yeni `experiment_id`) kapatılabilir.

Saatlik ACF de aynı hikâyeyi il bazında ayrıştırır: gecikme 24'te Ankara 0.489, Antalya 0.535,
Konya 0.524, Van 0.518, **Rize 0.389**; gecikme 48'de 0.340 / 0.400 / 0.366 / 0.380 / **0.178**.
Rize'nin bir ve iki günlük hafızası diğer illerden %20–50 zayıftır.

**Uyarı — ACF'nin kuyruğuna aldanılmamalıdır.** Günlük ACF 30. gecikmede Ankara 0.200,
Antalya 0.252, Konya 0.184, Van 0.219 görünür; bu gerçek bir hafıza değil, kt'nin kendi mevsimsel
döngüsünün artığıdır (kış kt'si düşük, yaz kt'si yüksek — §6). Rize'nin aynı gecikmedeki değeri
**0.070**'tir ve bu, argümanı zayıflatmak yerine güçlendirir: Rize'nin mevsimsel kt döngüsü en
sığ olan ildir (§6), dolayısıyla mevsimsel artığı da en küçüktür. Doğru okuma PACF'tir. Aynı
nedenle saatlik PACF yalnız 12. gecikmeye kadar raporlanır: gece maskesi ACF'yi çift yönlü eksik
gözlemle tahmin ettirir ve Durbin–Levinson özyinelemesi uzun gecikmelerde sahte sivrilikler üretir.

---

## 5. Değişkenler arası ilişkiler ve öznitelik seçimi

Bu bölümün tabloları — `correlation_pearson_<il>.csv`, `correlation_spearman_<il>.csv`, her ikisinin
`_pooled` sürümleri, `target_correlation_by_city.csv` ve `collinear_pairs.csv` — hepsi **gündüz
satırları** üzerinde hesaplanmıştır. `correlation_heatmap_<il>` ve `target_correlation_panel`
figürleri bu tabloların görselleştirmesidir ve ek bilgi taşımaz; makalede tablo yerine figür
kullanılacaksa hangisinin seçildiği bir tercih meselesidir.

**Uyarı — p-değeri ve anlamlılık yıldızı bilinçli olarak yoktur.** n ≈ 150 000 otokorelasyonlu
saatlik satırda her |r| > 0.01 "p < 0.001" çıkar; etkin örneklem büyüklüğü bunun kat kat altındadır.
Anlamlılık yerine etki büyüklüğü ve kısmi korelasyon raporlanır (bkz. README §4).

### 5.1 Ham korelasyon güneş geometrisiyle karışıktır; kısmi korelasyon dürüst sütundur

`target_correlation_by_city.csv`, hedefle ham Pearson korelasyonunun yanında
`partial_r_within_hour` sütununu taşır: (il, ay, saat) hücre ortalaması çıkarıldıktan sonra kalan
korelasyon. Bu, güneş geometrisi sabitlendiğinde geriye kalan hava sinyalidir.

| Değişken | Ham *r* (havuz.) | Ham *r* (il aralığı) | Kısmi *r* (havuz.) | Kısmi *r* (il aralığı) | Ne oluyor |
|---|---|---|---|---|---|
| Bağıl nem | **−0.631** | −0.660 … −0.631 | **−0.524** | −0.566 … −0.481 | Ayakta kalıyor, en güçlüsü |
| Sıcaklık | **+0.520** | +0.461 … +0.559 | **+0.300** | +0.243 … +0.360 | Gücü yarıya iniyor |
| Yağış | **−0.163** | −0.215 … −0.097 | **−0.324** | −0.380 … −0.279 | **İki katına çıkıyor** |
| Yüzey basıncı | **−0.037** | −0.158 … +0.113 | **+0.263** | +0.185 … +0.335 | **İşaret değiştiriyor** |
| Özgül nem | **+0.033** | +0.008 … +0.212 | **−0.272** | −0.369 … −0.162 | **İşaret değiştiriyor** |
| Çiy noktası | **+0.043** | +0.013 … +0.227 | **−0.274** | −0.385 … −0.150 | **İşaret değiştiriyor** |
| Rüzgâr hızı, 10 m | **+0.078** | −0.091 … +0.187 | **−0.156** | −0.218 … −0.107 | Tutarsızdan tutarlıya |
| Rüzgâr hızı, 50 m | **−0.064** | −0.244 … +0.044 | **−0.162** | −0.190 … −0.117 | Tutarsızdan tutarlıya |

Bu tablo makaleye girmelidir, çünkü ham korelasyona bakarak varılacak üç sonuç da yanlış olurdu:

**"Sıcaklık en önemli öznitelik" demek hatalı olurdu.** Sıcaklığın ham +0.520'sinin yarısı,
sıcaklığın da güneş yüksekliğini takip etmesinden kaynaklanır — sıcaklık büyük ölçüde ışınımın
*sonucudur*, nedeni değil. Geometri sabitlenince +0.300'e düşer.

**"Korelasyonu düşük diye özniteliği at" refleksi burada üç değişkeni birden kaybettirirdi.**
Basınç, özgül nem ve çiy noktası ham korelasyonda sıfıra yakındır (|r| ≤ 0.043) ama kısmi
korelasyonda 0.26–0.27 büyüklüğüne çıkar ve işaret değiştirir. Fizik nettir ve klasiktir: yüksek
basınç = antisiklonik, açık hava; yüksek sinoptik nem = bulut. Ham korelasyonda ikisi de görünmez,
çünkü her ikisi de mevsimsel/günlük döngüyle örtüşür.

**En güçlü tek argüman ise tutarlılık argümanıdır.** Ham korelasyonda üç değişkenin — basınç,
`WS10M`, `WS50M` — işareti iller arasında değişir (örneğin `WS50M` Antalya'da −0.244, Van'da
+0.044). **Kısmi korelasyona geçildiğinde dokuz değişkenin hepsi beş ilde aynı işarete sahiptir.**
Yani geometri sabitlendiğinde iller "aynı fiziği" gösterir; ham korelasyonlardaki tutarsızlık
gerçek bir bölgesel farklılık değil, geometrik karışmanın artığıdır. Bu cümle, kısmi korelasyon
tablosunun neden makalenin öznitelik seçimi bölümünde yer alması gerektiğini tek başına
gerekçelendirir.

**Uyarı — geometri sabitlendikten sonra hiçbir tek değişkenin |r|'si 0.566'yı geçmez**
(en güçlüsü bağıl nem, Antalya −0.566). Yani tek değişkenli veya doğrusal bir baseline yapısal
olarak zayıf kalacaktır; çok değişkenli ve otoregresif bir yapı gerekir. Bu, LSTM tercihini
destekleyen bir argümandır — ama aynı gerekçe planlanan SVM/RF/MLP baseline'larının **haksız
biçimde zayıf çıkmaması için** yeterince esnek seçilmesi gerektiği anlamına da gelir (§5.2).

**Rize kısmi korelasyonlarda da ayrışır ve yönü ilginçtir.** Rize'nin **ham** nem korelasyonları
beş ilin en güçlüsüdür (`QV2M` +0.212, `T2MDEW` +0.227; diğer illerde +0.008…+0.099) ama **kısmi**
korelasyonları en zayıfıdır (−0.162 / −0.150; Antalya'da −0.369 / −0.385). Yani Rize'de nem ile
ışınım arasındaki ham bağ neredeyse tamamen mevsimseldir; hava ölçeğinde nem, ışınım hakkında
diğer illerdekinden daha az şey söyler. Buna karşılık Rize yağışta hem ham (−0.215) hem kısmi
(−0.380) olarak en güçlü ildir — Rize'de bulut sinyalini taşıyan değişken nem değil, yağıştır.

### 5.2 Doğrusallık: bir istisna dışında Spearman ile Pearson örtüşüyor

Hedefle olan korelasyonlarda Spearman ile Pearson farkı yağış dışında hiçbir değişkende 0.04'ü
geçmez (`correlation_spearman_pooled.csv`; `WS10M` +0.033, `T2M` −0.017, `RH2M` +0.002).
**Yağışta ise fark havuzlanmışta −0.072'dir** (−0.163 → −0.235) ve il bazında Konya'da −0.104'e
(−0.109 → −0.212), Ankara'da −0.086'ya çıkar. Yordayıcılar arasında en büyük fark
`RH2M`–`PRECTOTCORR` çiftindedir: havuzlanmış 0.292 → **0.497** (+0.206), Rize'de 0.401 → 0.643.

Yorum: **gizli, monotonik olmayan bir ilişki yoktur** — hiçbir çiftte Pearson ile Spearman işaret
uyuşmazlığı görülmez. Var olan şey, yağışın sıfır-şişkin ve ağır kuyruklu dağılımının Pearson'u
aşağı çekmesidir; ilişki monotoniktir ama doğrusal değildir. Bu, §3.4'teki "bilgi miktarda değil
varlıktadır" bulgusunun korelasyon dilindeki karşılığıdır ve yağışın ham Pearson tablosunda
göründüğünden **yaklaşık %45 daha fazla** bilgi taşıdığı anlamına gelir.

**Doğrusallığın gerçek sınırı katsayılarda değil, saçılım figürlerinde görünür.**
`scatter_vs_target_<il>` figürleri her değişkenin hedefe karşı saçılımını binlenmiş medyan eğrisiyle
birlikte verir ve hiçbir korelasyon katsayısının taşıyamayacağı üç şey gösterir:

**(a) Bağıl nem bir tavan değişkenidir, bir eğim değişkeni değil.** Ankara'da binlenmiş medyan
%18'in altında doyar (667 → 681 W/m², artık fark yok), %20–90 arasında neredeyse doğrusal iner
(667 → 73 W/m²), %94'ün üstünde çöker (14 W/m²). Ama asıl bilgi noktalarda: **nem yükseldikçe
gözlenen maksimum ışınımın kendisi düşer.** Nem %80'in üstündeyken bulut ~600 W/m² ile sınırlıdır;
nem %40'ın altındayken 0–1000 aralığının tamamı doludur. Yani koşullu varyans nem ile birlikte
değişir. Bu, §8'de ele alınan heteroskedastik aralık argümanının doğrudan kanıtıdır.

**(b) Özgül nem ve çiy noktası ters-U biçimlidir ve iki panel neredeyse aynıdır.** Ankara'da özgül
nemin binlenmiş medyanı 2 g/kg'da ~290 W/m², 8 g/kg'da ~450 (tepe), 12 g/kg'da ~200 W/m²'dir.
Bu, ham korelasyonun neden sıfıra yakın (+0.033) ve kısmi korelasyonun neden negatif (−0.272)
olduğunun görsel açıklamasıdır: yükselen kol mevsimseldir (yaz = nemli **ve** ışınımlı), inen kol
meteorolojiktir (nem = bulut). Çiy noktası paneli aynı biçimi tekrar eder — iki sütunun fazlalığı
(§5.3) figürde de görünür.

**(c) Aynı ilişki illerde farklı biçimlere sahiptir.** `scatter_vs_target_Rize` ile
karşılaştırıldığında: Rize'de özgül nem **tek yönlü artan**dır (medyan 140 → 350 W/m²), ters-U
yoktur — çünkü Rize'de nem esas olarak mevsimi kodlar ve bastırıcı kol baskın gelmez. Sıcaklık
Rize'de bir eğim değil bir **eşik**tir: 0–18 °C arasında medyan 100–200 W/m² civarında düz seyreder,
sonra 28 °C'ye kadar ~630'a fırlar. Rüzgâr hızı Rize'de **tek tepeli**dir: medyan 4 m/s'de ~420
W/m² ile zirve yapar, 11 m/s'de ~120'ye iner — kara/deniz meltemi rejimi ile fırtına rejiminin
ayrımı. Ankara'da aynı panel düzdür. Yani "rüzgâr hızı bilgi taşımıyor" ifadesi havuzlanmış veride
doğru, Rize'de yanlıştır.

Ayrıca değişkenlerin **destek aralıkları** iller arasında farklıdır: Ankara'da bağıl nem %10–100
arasında gözlenirken Rize'de %35'in altına hiç inmez. Tek bir global ölçekleyici altında Rize,
havuzlanmış nem dağılımının üst kısmında yaşar; bu kaymanın taşınması şehir gömülemesinin
işlerinden biridir.

**Öneri.** Planlanan SVM/RF/MLP karşılaştırmasında çekirdek/derinlik seçimi bu doygunluk, eşik ve
ters-U davranışlarını temsil edebilmelidir. Doğrusal çekirdekli bir SVM veya tek katmanlı bir MLP
haksız biçimde zayıf çıkar ve karşılaştırma yayınlanabilir olmaz.

### 5.3 Eşdoğrusallık: iki sütun gereksiz, biri fiilen türetilmiş

`collinear_pairs.csv` iki satırdan oluşur (eşik |r| > 0.9, havuzlanmış gündüz Pearson):

```
WS10M,WS50M,0.9652
QV2M,T2MDEW,0.9623
```

Her ikisi de fiziksel olarak beklenendir: özgül nem ve çiy noktası aynı büyüklüğün iki ifadesidir;
10 m ve 50 m rüzgârı aynı sınır tabakasındandır. İl bazında bu çiftler daha da güçlüdür —
`QV2M`–`T2MDEW` her ilde 0.977–0.981'dir (havuzlanmış değerin 0.962 olması, iller arası karışımın
korelasyonu hafifçe seyreltmesindendir).

**Bu belge için yapılan ek bir kontrol, çiy noktası için durumu "yüksek korelasyon"dan
"determinist tekrar"a taşımaktadır.** Çiy noktası, sıcaklık ve bağıl nemden standart Magnus
bağıntısıyla yeniden üretildiğinde 295 920 satırın tamamında **r = 0.99919** ve **RMSE = 0.31 °C**
elde edilir (gündüz alt kümesinde r = 0.99956, RMSE = 0.23 °C). Yani `T2MDEW` bağımsız bir ölçüm
değil, veri setinde zaten bulunan iki sütunun kapalı formlu bir fonksiyonudur; taşıdığı ek bilgi
0.3 °C mertebesinde bir yuvarlama artığından ibarettir. (Doğrusal bir regresyon aynı işi yalnız
r = 0.962 ile yapar; ilişki doğrusal değil, üstel-logaritmiktir — bu yüzden düz korelasyon tablosu
fazlalığın derecesini olduğundan küçük gösterir.)

**Öneri.** `T2MDEW` ve `WS50M` çıkarılmış 15 öznitelikli bir ablasyon konfigürasyonu, yeni bir
`experiment_id` ile koşulmalıdır. LSTM için eşdoğrusallık zararsızdır, ama (a) parametre ve gürültü
azalır, (b) planlanan SVM/RF/MLP baseline'ları için — özellikle doğrusal ve mesafe tabanlı olanlar
için — önemlidir, (c) "öznitelik seçimi yapıldı" cümlesi makalede gerekçelendirilmiş olur.
`n_features` ledger'da zaten bir sütun olduğu için karşılaştırma izlenebilir kalır.
**Uyarı:** `WS50M` fazlalığı gündüz verisinde tamdır ama 24 saatlik veride kısmidir (§3.2, gece
sınır tabakası ayrışması); model 24 saatlik seri üzerinde eğitildiği sürece bu ablasyonun küçük
bir kayıp getirmesi mümkündür ve ölçülmelidir.

### 5.4 Yordayıcılar arası yapı: iller hedef konusunda hemfikir, birbirleri konusunda değil

Havuzlanmış gündüz matrisinde |r| > 0.6 olan yordayıcı çiftleri yalnız üçtür:
`WS10M`–`WS50M` +0.965, `QV2M`–`T2MDEW` +0.962, `T2M`–`RH2M` −0.673, ve sınırda
`T2M`–`T2MDEW` +0.611. 0.5–0.6 bandında `T2M`–`QV2M` +0.568 ve `T2MDEW`–`PS` +0.519 bulunur.
Yani öznitelik uzayı, iki bilinen fazlalık çifti dışında makul ölçüde iyi koşullanmıştır.

**Ama havuzlanmış basınç korelasyonları fizik olarak alıntılanmamalıdır.** `PS`'i içeren her çift
havuzlandığında işaret değiştirir, çünkü havuzlanmış korelasyon il içi hava değil, iller arası
rakım farkı tarafından sürüklenir (§3.2) — ders kitabı bir Simpson tersinmesi:

| Çift | Havuzlanmış | Ankara | Antalya | Konya | Rize | Van |
|---|---|---|---|---|---|---|
| `T2M`–`PS` | **+0.251** | −0.166 | −0.515 | −0.163 | −0.270 | +0.272 |
| `T2MDEW`–`PS` | **+0.519** | −0.217 | −0.493 | −0.229 | −0.302 | +0.068 |
| `QV2M`–`PS` | **+0.397** | −0.211 | −0.498 | −0.221 | −0.306 | +0.062 |
| `RH2M`–`PS` | **+0.145** | +0.004 | +0.194 | +0.001 | +0.017 | −0.340 |

Havuzlanmış `T2MDEW`–`PS` = +0.519 hiçbir ilde gözlenen bir ilişki değildir; beş ilin dördünde
negatiftir. **Makalede havuzlanmış korelasyon ısı haritası kullanılacaksa, basınç satırı için bu
uyarı verilmelidir**; alternatif olarak il bazlı ısı haritaları (`correlation_heatmap_<il>`) tercih
edilebilir.

İller arasındaki gerçek farklılıklar üç tutarlı hikâyeye ayrılır:

- **Van basınç aykırısıdır.** `PS` ile `T2M`/`QV2M`/`T2MDEW` arasındaki korelasyonun pozitif,
  `RH2M` ile negatif olduğu tek ildir. Yüksek, karasal, yarı kurak bir havzada yüksek basınç açık
  ve ılık hava demektir; Antalya'da (deniz seviyesi, Akdeniz) yüksek basınç serin ve kuru
  advection ile birliktedir.
- **Rize nem–sıcaklık aykırısıdır.** `T2M`–`T2MDEW` 0.903 ve `T2M`–`QV2M` 0.876 (diğer illerde
  0.52–0.61); `T2M`–`RH2M` yalnız −0.520 (diğerlerinde −0.73…−0.81). Sürekli doygunluğa yakın bir
  Karadeniz ikliminde çiy noktası sıcaklığı neredeyse birebir takip eder ve bağıl nem sıcaklık
  bilgisinin çok azını taşır.
- **Antalya rüzgâr aykırısıdır.** Her iki yükseklikte de rüzgâr hızının hedefle negatif
  (−0.091 / −0.244), bağıl nem (+0.283) ve yağışla pozitif korele olduğu tek ildir: onshore/meltem
  ve cephesel rüzgâr rejimi bulut getirir; iç kesimde (Van `WS10M` +0.187) rüzgâr açık ve kuru
  havaya eşlik eder.

**Buna karşılık hedef–yordayıcı korelasyonları şaşırtıcı ölçüde homojendir**: bağıl nemin iller
arası aralığı yalnız 0.029, sıcaklığınki 0.098'dir. **İller ışınımı neyin yordadığı konusunda
hemfikirdir; yordayıcıların birbiriyle nasıl ilişkilendiği konusunda ayrışırlar.** Bu, tek global
model + şehir gömülemesi tasarımı için doğrudan bir gerekçedir: paylaşılan ağırlıklar ortak
hedef ilişkisini, gömüleme ise il-özgü ortak değişken yapısını üstlenir.

---

## 6. Bölgesel farklılaşma: Rize ve Van, iki uç

Makalenin "beş farklı iklim bölgesi" iddiası için bu bölümdeki bulgular hem destek hem sınırlama
sağlar. Gerçek çeşitlilik esas olarak tek bir ilden — Rize'den — gelir; Ankara, Antalya, Konya ve
Van birbirine yakın rejimlerdir. Van, karşı uçta, kendi başına ikinci bir özel durumdur.

### 6.1 Rize

Rize'nin farkı bu belgede en az **sekiz bağımsız ölçüden** gelir ve hepsi aynı yönü gösterir:

| Ölçü | Rize | Diğer dört il | Kaynak |
|---|---|---|---|
| Günlük toplam ışınım (kWh/m²/gün) | 3.686 | 4.656 – 4.983 | `daily_clearness_by_city.csv` |
| Fiziksel kt (günlük ort.) | **0.697** | 0.806 – 0.840 | `clearness_index_by_city.csv` |
| kt standart sapması | **0.244** | 0.174 – 0.207 | " |
| Kapalı gün payı (kt < 0.3) | **%8.03** | %0.97 – 2.80 | " |
| Günler arası CV | **0.569** | 0.440 – 0.493 | `daily_clearness_by_city.csv` |
| Saatin η²'si (gündüz) | **0.431** | 0.500 – 0.566 | `time_feature_explained_variance.csv` |
| Günlük PACF, gecikme 1 | **0.405** | 0.534 – 0.563 | `autocorrelation_clearness.csv` |
| En iyi referansın R²'si (gündüz) | **0.718** | 0.868 – 0.896 | `persistence_baseline.csv` |

`rize_comparison` figürü bu argümanı tek panelde toplar ve üç şeyi tablolardan daha iyi gösterir:

**(a) Berraklık dağılımı birinci dereceden ayrışır.** Günlük kt'nin birikimli dağılımında Rize
eğrisi 0.2 ile 0.95 arasındaki **her eşikte** diğer dördünün üstündedir; diğer dört il ise sıkı bir
demet oluşturur. Fark kt ≈ 0.6–0.7 civarında en geniştir (Rize'de birikimli oran ~0.50, diğer
dörtte ~0.25). Yani **her berraklık eşiğinde Rize'nin o eşiğin altında kalma olasılığı yaklaşık iki
katıdır**; bu, tek bir ortalamadan daha güçlü bir ifadedir.

**(b) Rize'nin mevsimsel döngüsü hem sığdır hem de faz kaymıştır.** Aylık ortalama kt'de Rize
Şubat'ta 0.59'dan Ağustos'ta 0.78'e çıkar (genlik 0.19); diğer dört il Ocak/Aralık'ta 0.65–0.75'ten
Temmuz'da 0.94–0.97'ye çıkar (genlik ~0.25). **Rize'nin zirvesi Ağustos'ta, diğer dördününki
Temmuz'dadır; Rize'nin en düşük ayı Şubat, diğerlerininki Aralık/Ocak'tır.** Bu denizel gecikme
Karadeniz rejimi için beklenendir ve figürden başka hiçbir yerde görünmez. Ayrıca dört ilin eğrileri
kışın belirgin biçimde ayrışır (Ocak 0.67–0.75), yazın neredeyse üst üste biner (Temmuz 0.94–0.97):
**iller arası farklar bir kış olgusudur.**

**(c) Rize'nin en iyi mevsimi diğer illerin en kötü mevsimine yakındır.** Mevsimlik CV panelinde
Rize'nin minimumu 0.28 (yaz) iken diğer dördünün yaz CV'si 0.10–0.14, kış CV'si 0.33–0.43'tür.
Yani Rize'nin en öngörülebilir mevsimi, Anadolu illerinin en zor mevsimiyle aynı mertebededir.

Mevsimsel kt yörüngesi bunu tamamlar (`clearness_index_by_city.csv`, Kış → Yaz):
Ankara 0.679 → 0.922, Antalya 0.716 → 0.953, Konya 0.702 → 0.929, Van 0.750 → 0.938,
**Rize 0.626 → 0.772**. Rize'nin en açık mevsimi bile diğer illerin kışına yakındır.

**Uyarı — Rize'nin mutlak rampaları küçüktür, bu onu kolay yapmaz.** `ramp_stats_by_city.csv`,
Rize'de saatlik |ΔIşınım| medyanını 81.77 W/m² ile beş ilin en düşüğü olarak verir ve 200 W/m²'yi
aşan saat payı yalnız %1.63'tür (Van'da %7.09). Aynı zamanda Rize'nin |Δkt| medyanı **0.0300** ile
beş ilin **en yükseğidir** (Konya 0.0137). Sürekli bulut mutlak ışınımı, dolayısıyla mutlak
rampaları da tavanlar; atmosferin kendisi ise en oynak olandır. Mutlak rampa büyüklüğüne bakarak
"Rize sakin" sonucuna varmak hatalı olur.

**Öneri.** Agregat skor Rize'yi gizler (dört il onu 4'e 1 bastırır). `results_summary.csv`'de
Rize'nin ayrı satırı zaten vardır, ama makale metninde açıkça "en zor il" olarak tartışılmalıdır;
ayrıca "Rize hariç agregat" bir satır olarak eklenirse şehir gömülemesinin katkısı görünür hale
gelir.

### 6.2 Van

Van, kaynağın en yüksek olduğu ildir (4.983 kWh/m²/gün) ve bunu **Antalya'yı geçerek** başarır —
yani bu veri setinde rakım enlemi yenmektedir. Van hem en yüksek kış (2.710) hem en yüksek yaz
(7.641) günlük toplamına sahiptir, en düşük basınca (77.69 kPa, ~2 100 m'ye karşılık gelen bir
hücre ortalaması), en düşük bağıl neme (%45.5) ve en düşük kt standart sapmasına (0.174) sahiptir.
Kış kt'si 0.750 ile beş ilin en yükseğidir (diğerleri 0.626–0.716) — yüksek platonun kış
enversiyonunun ve alçak bulut tabakasının üstünde kalmasıyla tutarlıdır. Van ayrıca rüzgâr yönü
bakımından örgütlü tek ildir (§3.3).

**Uyarı — Van'ın 1215.88 W/m²'lik maksimumu fiziksel bir kayıt değil, bir ölçüm artığıdır ve
makalede iklim kanıtı olarak kullanılmamalıdır.** Bu değer 2020-02-17 15:00 LST'de kayıtlıdır;
aynı saatin açık-hava referansı 370.23 W/m²'dir, yani **kt = 3.28** — açık-hava değerinin 3.3 katı,
şubat ayında, saat 15'te, −3.4 °C ve %83 bağıl nem koşullarında. Fiziksel olarak mümkün değildir.
Tüm veri setinde kt > 1.2 olan yalnız **dört satır** vardır (295 920 satırın %0.0014'ü) ve dördü de
Van'da, dördü de Ocak/Şubat aylarındadır — kar örtüsü albedosu kaynaklı bir uydu getirimi
artığıyla uyumlu bir desen. Aynı satır `seasonal_target_stats.csv`'de Van'ın kış maksimumu olarak,
`descriptive_stats_by_city_*.csv`'de Van'ın ve havuzlanmış satırın maksimumu olarak, ve
`ramp_stats_by_city.csv`'de Van'ın 1 113.76 W/m²'lik kış rampa maksimumu olarak (kendi p99.9'unun
3.5 katı) görünür.

Fiziksel olarak savunulabilir maksimumlar il başına şöyledir: Van 1 068.7, Konya 1 054.3,
Antalya 1 043.1, Ankara 1 029.1, Rize 988.1 W/m². Van hâlâ en yüksektir, ama üstünlüğü %15 değil
%1.4'tür. **Makalede "Van'ın maksimumu 1 215.9 W/m² ile en yüksektir; yükseklik ve kuru havanın
beklenen sonucudur" biçiminde bir cümle kullanılmamalıdır.** Doğru ifade, Van'ın kış kt'si ve kış
günlük toplamıdır — ikisi de sağlam ve aynı fiziği anlatır.

kt > 1 olan saatlerin genel payı %0.02–0.15'tir ve kt ≤ 1.11 aralığında kalanlar bulut kenarı
yansımasıyla (cloud enhancement) fiziksel olarak açıklanabilir; sorun yalnız yukarıdaki dört
satırdadır. Bunlar eğitim setine girecekse ayrıca ele alınmaları önerilir, ama sayıları ihmal
edilebilir olduğu için etkileri metriklerde değil, yalnız raporlanan maksimumlarda görülür.

---

## 7. Öngörülebilirlik ve referans zemin

`persistence_baseline.csv`, üç referans tahmin kuralını modelin kendi kronolojik test penceresinde
(`datetime > val_end`, varsayılan 0.74/0.11 ile 2025-03-26 01:00 sonrası) değerlendirir; hiçbiri
test satırlarına bakmaz.

**Havuzlanmış, gündüz saatleri (n = 22 882):**

| Referans | RMSE (W/m²) | MAE | R² | Yanlılık |
|---|---|---|---|---|
| Kalıcılık (dün aynı saat) | 116.39 | 68.23 | 0.8295 | +0.21 |
| Akıllı kalıcılık (dünün berraklığı × bugünün açık-hava referansı) | 109.32 | **60.42** | 0.8496 | −0.99 |
| **Klimatoloji** ((il, ay, saat) eğitim ortalaması) | **106.81** | 73.41 | **0.8564** | +1.89 |

**Havuzlanmış, 24 saat (n = 44 390):** kalıcılık 83.57 / 35.17 / 0.9086; akıllı kalıcılık
78.49 / 31.15 / 0.9194; klimatoloji **76.69 / 37.89 / 0.9230**.

Dört sonuç, dördü de makaleye girmelidir:

**(1) Referans zemin klimatolojidir, kalıcılık değildir.** LSTM'in anlamlı olması için gündüz
RMSE'sinin 106.81 W/m²'nin altına ve R²'sinin 0.856'nın üstüne geçmesi gerekir. 24 saat ilerisi
bir tahminde kalıcılığı geçmek bir sonuç değildir; 24 saatlik kalıcılık günlük döngüyle
tanımı gereği hizalıdır. Yalnız kalıcılık raporlamak, CLAUDE.md'nin uyardığı "haksız baseline"
durumudur.

**(2) RMSE ve MAE farklı şampiyonlar seçer.** Klimatoloji RMSE'de kazanır (106.81) ama MAE'de
kaybeder (73.41 vs 60.42). Klasik ayrımdır: klimatoloji koşullu ortalama olduğu için kareli hatayı
minimize eder, büyük hata yapmaz ama hiçbir zaman keskin değildir; akıllı kalıcılık günü takip
ettiği için tipik günlerde daha iyi, uç günlerde daha kötüdür. **Modelin ikisini birden geçmesi
gerekir**; yalnız RMSE raporlamak bunu gizler.

**(3) Gece satırları zemini bedavaya iyileştirir.** Aynı klimatoloji referansı 24 saat üzerinden
RMSE 76.69 / R² 0.9230, gündüzde 106.81 / 0.8564 verir. Gece satırları RMSE'yi **%28 düşürür** ve
R²'yi **0.067 şişirir** — hiçbir öğrenme olmadan. Literatürle kıyaslanabilir rakam gündüz olanıdır.

**(4) Yanlılıklar ihmal edilebilir** (|yanlılık| ≤ 8.13 W/m², en büyüğü Rize klimatolojisi +8.13);
referanslar arasındaki fark sistematik kayma değil, saf varyanstır.

**İl bazında, gündüz, en iyi referansın R²'si:** Ankara 0.8753 (klimatoloji), Antalya **0.8956**
(akıllı kalıcılık — tek istisna), Konya 0.8798 (klimatoloji), **Rize 0.7184** (klimatoloji),
Van 0.8677 (klimatoloji). Rize her referansa karşı ve her iki kapsamda 0.14–0.17 R² kaybettirir.
Tek global model bir makale iddiası olduğuna göre il kırılımı zorunludur; havuzlanmış bir R²,
beş ilden birinin belirgin biçimde daha zor bir problem olduğunu gizler.

**Uyarı — bu tablo tanımlayıcıdır, makalenin sonuç tablosu değildir.** Burada değerlendirme
**saat başına** yapılır. Aynı referanslar `run_experiment` boru hattından koşulduğunda
değerlendirme **pencere başına** olacaktır: `window_stride=1` ve `horizon_hours=24` ile her test
saati 24'e kadar örtüşen pencerede tekrar sayılır, bölme sınırındaki saatler farklı ağırlık alır
ve etkin n yaklaşık 24 katına çıkar. **Aynı tahmin kuralı iki yöntemde birebir aynı sayıyı
vermez.** Makalede yalnız boru hattından geçen (ledger'a yazılan) sürüm alıntılanmalı; buradaki
rakamlar çapraz kontrol içindir. Sıralamanın (RMSE'de klimatoloji, MAE'de akıllı kalıcılık önde)
iki yöntemde de aynı çıkması beklenir; çıkmıyorsa birinde hata vardır. `persistence_baseline`
figürü aynı tablonun görselleştirmesidir ve ek bilgi taşımaz.

**Uyarı — yaz neredeyse dejenere bir problemdir.** Ankara, Antalya, Konya ve Van'da yaz saatlerinin
%93–98'i açıktır (kt > 0.7) ve kapalı gün payı %0.0'a yaklaşır. Model becerisinin neredeyse tamamı
kış ve ilkbaharda kazanılacaktır; yıllık agregat bir metrik bunu gizler.

**Uyarı — gündüz-only eğitim, satır silerek yapılamaz.** `daylight_block_structure.csv` bunun
kanıtıdır: gece satırları silinseydi seri il başına **2 466 kesintisiz bloğa** parçalanırdı
(günde bir blok), medyan blok uzunluğu **12 saat**, maksimum 15 saat (Antalya 14), minimum 10 saat
(Rize 9) olurdu ve **≥ 24 saatlik blok payı 0.000** olurdu. Boru hattı bir pencere için
`lookback_hours + horizon_hours` kadar kesintisiz satır ister; tek başına 24 saatlik ufuk bile
hiçbir geçerli pencere bırakmaz. Yani gece satırlarını silmek bir ön işleme tercihi değil, boş bir
eğitim kümesi garantisidir. Savunulabilir seçenek, 24 saatlik seriyi korumak ve geceyi **kayıp ve
metrik düzeyinde maskelemektir**.

---

## 8. Belirsizlik (UQ) katmanı için çıkarımlar

Bu bölüm, Bootstrap Ensemble × MC-Dropout katmanının tasarımı ve raporlanması için EDA'dan çıkan
kısıtları toplar.

**(1) Öngörü dağılımı simetrik ve Gauss varsayılmamalıdır.** Gündüz hedefinin fazlalık basıklığı
−0.933, çarpıklığı +0.442'dir; dağılım üstten açık-hava zarfıyla fiziksel olarak sınırlıdır
(§3.1) ve `seasonal_dayofyear` figüründe üst zarfın keskin, alt kuyruğun uzun olduğu açıkça
görülür. Bu, `main_methodology.md`'nin öngördüğü **ampirik persentil tabanlı CI** (havuzlanmış
örneğin 2.5/97.5 yüzdelikleri) tercihini destekler; ortalama ± 1.96·σ aralığı üst uçta açık-hava
tavanının ötesine taşar ve alt uçta negatif ışınım üretir.

**(2) Aralık genişliği koşullu olmalıdır, sabit değil.** Rampa dağılımı bunun neden gerektiğini
gösterir. `ramp_stats_by_city.csv`'de gündüz saatlik |ΔIşınım| medyanı 81.8–115.0, %90'lık
166.6–194.6, %99'luk 210.8–218.5 W/m²'dir. `ramp_distribution` figürü — birikimli dağılımın
tabulanmış persentiller arasındaki biçimini veren tek kaynak — bu sayıların ima ettiğinden farklı
bir şekil gösterir: eğri ~180 W/m²'ye kadar neredeyse **doğrusal** yükselir, ~200–220 W/m²'de
sert bir dirsekle 1.0'a oturur ve bunun ötesinde pratik olarak kütle yoktur. Yani rampa dağılımı
"dar gövde + kalın kuyruk" değil, **geniş ve neredeyse düzgün bir gövde + çok ince bir kuyruktur**;
tabloda görülen 423–1 114 W/m²'lik maksimumlar birkaç tekil noktadır (Van'ınki §6.2'de tartışılan
artıktır). Bu, UQ için iyi haberdir: aralığın kapsaması gereken şey patolojik bir kuyruk değil,
geniş ama sınırlı bir gövdedir.

**(3) Mutlak rampa mevsimselliği aldatıcıdır; kt rampası doğru ölçüdür.** `ramp_distribution`
figüründe mevsim sıralaması beş ilde de aynıdır: **Kış eğrisi en solda, Yaz en sağda.** Yani
mutlak rampalar yazın en büyüktür. Ama bu meteorolojik değil geometriktir — yazın güneş yükseklik
eğrisi diktir, saatler arası determinist değişim büyüktür. `ramp_stats_by_city.csv`'nin |Δkt|
sütunları sıralamayı tersine çevirir: yaz |Δkt| medyanı 0.0037–0.0134 iken kış 0.0236–0.0371'dir.
**Rampa istatistikleri makalede kt cinsinden raporlanmalıdır**, aksi halde problemin ne zaman zor
olduğu konusunda ters bir sonuç çıkar.

**(4) Koşullu varyans bilinen bir değişkenin fonksiyonudur.** `scatter_vs_target_Ankara`
figüründeki bağıl nem paneli (§5.2a), yüksek nemde gözlenen ışınım aralığının kendisinin
daraldığını gösterir. Yani CP ≈ 0.95 tutturulsa bile, tüm saatlerde sabit genişlikte bir aralık
düşük nemde yetersiz, yüksek nemde gereksiz geniş olacaktır.

**Öneri (raporlama).** CP/PINW sonuçları en az iki kırılımla birlikte raporlanmalıdır:
(a) **rampa büyüklüğüne göre** — ör. |Δkt| değeri kendi %90'lık diliminin üstünde olan saatler
ayrı; (b) **mevsime göre**. Ayrıca Rize'nin aralıklarının neden zorunlu olarak diğer illerden geniş
olması gerektiği (kt standart sapması 0.244 vs 0.174–0.207, kapalı gün payı %8.0 vs %1–3) burada
gerekçelendirilebilir; şehir gömülemesinin yalnız seviyeyi değil belirsizliği de ayrıştırıp
ayrıştıramadığı sınanabilir bir hipotezdir.

**Uyarı — ölçüm çözünürlüğü.** NASA POWER saatlik verisi saat **ortalamasıdır**, dolayısıyla
saat-içi bulut geçişlerini yumuşatır. Buradaki rampa büyüklükleri gerçek anlık rampaların
**alt sınırıdır**; makalede bir cümleyle belirtilmelidir. Aynı nedenle, gerçek operasyonel
belirsizlik burada ölçülenden büyüktür.

---

## 9. Sınırlılıklar ve makalede belirtilmesi gereken uyarılar

Aşağıdakiler, bu EDA'dan bir sayı alıntılandığında birlikte taşınması gereken kısıtlardır. Çoğu
yukarıdaki bölümlerde gerekçelendirilmiştir; burada bir kontrol listesi olarak toplanmıştır.

1. **Saatler iller arasında karşılaştırılamaz** (il-bazlı LST; §2). Saat etiketi aralığın
   başlangıcıdır.
2. **p-değeri yoktur ve olmamalıdır**; n ≈ 150 000 otokorelasyonlu satırda anlamlılık ölçüsüzdür
   (§5).
3. **Trend iddiası yoktur.** Altı tam takvim yılı trend için kısadır ve yıllar arası sinyal
   ortalamanın %5–8'idir (§4.3).
4. **Ham korelasyonlar güneş geometrisiyle karışıktır**; öznitelikler `partial_r_within_hour`
   sütununa göre sıralanmalıdır (§5.1).
5. **Havuzlanmış basınç korelasyonları Simpson artığıdır** ve fizik olarak alıntılanmamalıdır
   (§5.4).
6. **Aylık karşılaştırmalar günlük toplamlar üzerindendir**, saatlik değerler üzerinden değil;
   saatlik kutu kışı yapay olarak "stabil" gösterir (§4.2).
7. **Gece satırları her metriği şişirir**; literatürle kıyaslama gündüz rakamı üzerinden
   yapılmalıdır (§7).
8. **3B yüzey tek başına yanıltıcıdır** ve anomali paneliyle birlikte okunmalıdır (§4.3).
9. **`CLRSKY_SFC_SW_DWN` betimsel amaçlıdır ve modele asla öznitelik olarak girmemelidir** — hedefin
   neredeyse determinist bir zarfıdır. Yalnız berraklık indeksinin paydası ve gündüz maskesinin
   (boolean) kaynağı olarak kullanılır.
10. **Rüzgâr yönü dairesel bir değişkendir**; aritmetik ortalaması anlamsızdır, havuzlanmış bileşke
    uzunluğu 0.091'dir (§3.3).
11. **Basıklık Fisher (fazlalık) tanımıdır**: normal dağılım için 0, 3 değil.
12. **Havuzlanmış "Tümü" standart sapması** iller-içi ve iller-arası varyansın karışımıdır;
    ayrıştırma `between_city_sd` sütunundadır (§3.1).
13. **Referans zemin tablosu tanımlayıcıdır**, boru hattı sürümüyle birebir aynı sayıyı vermez
    (§7).
14. **İki öznitelik fazlalıdır** (`WS10M`↔`WS50M`, `QV2M`↔`T2MDEW`) ve çiy noktası sıcaklık ile
    bağıl nemden r = 0.9992 doğrulukla yeniden üretilebilir (§5.3).
15. **Yağış sütununun birim etiketi büyük olasılıkla yanlıştır** ("mm/saat" yerine mm/gün
    mertebesinde bir hız); metriği etkilemez ama etiketler düzeltilmelidir (§3.4).
16. **Van'ın 1 215.88 W/m²'lik maksimumu bir ölçüm artığıdır** (kt = 3.28) ve iklim kanıtı olarak
    kullanılmamalıdır (§6.2).
17. **İki farklı "açık gün" eşiği kullanılmaktadır** — `clearness_index_by_city.csv`'de fiziksel kt
    için 0.7/0.3, `daily_clearness_by_city.csv`'de ampirik berraklık oranı için 0.9/0.5. Aynı il
    için çok farklı paylar üretirler (Ankara %73.2 vs %45.4). Her tabloda hangi tanımın
    kullanıldığı yazılmalıdır. Ayrıca gün sayısı ilk tabloda 2 466, ikincisinde 2 464'tür
    (29 Şubat hizalaması).
18. **Betimsel tabloların `.md` ve `.tex` sürümleri `between_city_sd` sütununu içermez.** Makale
    tablosu `.tex` dosyasından üretilirse bu istatistik sessizce kaybolur.
19. **Sakin saatlerde rüzgâr yönü kodlaması doğrulanmamıştır** (§3.3).
20. **Aylık kutu grafiği (son 12 ay) mevsim analizine uygun değildir**: penceresinin "İlkbahar"ı
    iki farklı ilkbahardan üç ay içerir (§4.3).

### 9.1 `README.md` ile CSV dosyaları arasındaki tutarsızlıklar

Bu tur doğrulamada bulunan farklar. **Her durumda CSV esastır** ve README güncellenmelidir.

| # | README ifadesi | CSV'deki gerçek değer | Değerlendirme |
|---|---|---|---|
| 1 | "gündüz alt kümesi 156 909" (*Kapsam kuralı* paragrafı ve tablo listesindeki `descriptive_stats_by_city_daylight` satırı) | **151 643** | **Eski (klimatolojik) gündüz tanımından kalmış sayı.** README'nin kendi *Düzeltme kaydı* bölümü doğru değeri veriyor; bu iki yer güncellenmemiş. |
| 2 | "Gündüz verisinde hedefin çarpıklığı 0.47, fazlalık basıklığı −0.92" (*Tablolar* bölümü) | **0.442 / −0.933** | Aynı şekilde eski gündüz tanımından kalmış. README §7'deki "0.44 / −0.93" doğrudur; çelişen ifade silinmelidir. |
| 3 | "Spearman ile Pearson farkı hiçbir değişkende 0.06'yı geçmiyor; en büyük fark yağışta −0.06" | Havuzlanmış yağış farkı **−0.072** (−0.163 → −0.235); Konya'da **−0.104**, Ankara'da −0.086. Yordayıcılar arası `RH2M`–`PRECTOTCORR` farkı **+0.206** | **Sayısal sınır yanlış.** Nitel sonuç ("monotonik olmayan ilişki yok") doğru kalıyor; düzeltilmiş ifade §5.2'dedir ve yağış lehine argümanı güçlendiriyor. |
| 4 | Hedefin `between_city_sd`'si "43.6 W/m²" | **43.861** | 43.6, 43.861'in doğru yuvarlaması değil (43.9 olmalı). Muhtemelen `DROPPED_COLUMNS` öncesi bir koşudan kalma. |
| 5 | Test penceresinde gündüz saati "4 543–4 574" | **4 544 – 4 593** (Ankara 4 593, Antalya 4 544, Konya 4 586, Rize 4 570, Van 4 589) | Üst sınır beş ilin üçünün altında; her iki uç da düzeltilmeli. |
| 6 | "Yaz günleri … 3–4 kat daha az değişken" | Kış/Yaz CV oranı Ankara 3.04, Antalya 3.82, Konya 3.06, Van 2.72, **Rize 1.81** | Aralık **1.8–3.8×** olmalı; Rize ve Van bandın dışında. |
| 7 | Saatlik "PACF 3. gecikmede ≈ −0.09" | −0.100 / −0.057 / −0.084 / −0.096 / **−0.034** | Doğru aralık **−0.03 … −0.10** (ortalama −0.074). Van ve Antalya iddia edilenin belirgin biçimde dışında. |
| 8 | "Günlük ACF 30. gecikmede hâlâ 0.18–0.25" | 0.200 / 0.252 / 0.184 / **0.070** / 0.219 | Rize (0.070) aralığın çok dışında. Aralık **0.07–0.25** olmalı; README'nin kendi argümanı (mevsimsel artık) bu düzeltmeyle güçleniyor. |
| 9 | "\|Δkt\| … %99'luğu 0.19–0.24" | **0.1847** (Antalya) – 0.2419 (Van) | Alt uç 0.18'e yuvarlanır, 0.19'a değil. |
| 10 | "\|ΔIşınım\| %99'luk 211–219" | 210.838 – 218.506 | Yuvarlama düzeyinde; kesin aralık 210.8–218.5. |
| 11 | "medyan blok 12 saat (min 9, maks 15)" | min 9 **yalnız Rize**'de (diğerlerinde 10); maks 14 **Antalya**'da (diğerlerinde 15) | Yanlış değil ama iller arası zarf olduğu belirtilmeli. |
| 12 | "Van'ın 1215.9 W/m² olan maksimumu … yükseklik + kuru hava kombinasyonunun beklenen sonucudur" | Değer doğru, **yorum yanlış**: bu satırda kt = 3.28 | Ayrıntı §6.2. Fiziksel yorum bu satıra dayandırılmamalı. |
| 13 | Mevsimsel kt tablosunda **Konya eksik** | Konya Kış → Yaz: **0.702 → 0.929** | Eksiklik; tamamlanmalı. |
| 14 | — (README'de yok) | `autocorrelation_clearness.csv`'de **Antalya'nın saatlik PACF'i 12. değil 11. gecikmede kesiliyor** | Zararsız ama 12. gecikme tablolanacaksa bilinmeli. |
| 15 | — (README'de yok) | Yağış sütununun birimi | §3.4; `variable_tr` alanı ve figür eksenleri "mm/saat" diyor. |

Ayrıca üç doğrulama notu: (a) `descriptive_stats_by_city_*.csv` ile `.md` / `.tex` sürümleri
sayısal olarak tutarlıdır (2 ondalığa yuvarlanmış); (b) `seasonal_target_stats.csv`'deki
günlük toplam ve CV değerlerinin tamamı README tablosuyla birebir örtüşür; (c)
`persistence_baseline.csv`'deki dokuz havuzlanmış rakamın tamamı ve il bazında Rize'nin
0.7184'ü README ile örtüşür.

---

## 10. Tablo–bölüm eşlemesi

Her iddianın hangi dosyadan doğrulanabileceği. Tüm yollar `outputs/eda/` altındadır.

### Tablolar

| Dosya | Bu belgede | Ne için alıntılanır |
|---|---|---|
| `tables/descriptive_stats_by_city_daylight.csv` (`.md`, `.tex`) | §3.1, §3.2, §3.4, §6 | Birincil betimsel tablo: gündüz momentleri, il ortalamaları, `between_city_sd`, yağışın çarpıklık/basıklığı |
| `tables/descriptive_stats_by_city_24h.csv` (`.md`, `.tex`) | §3.1, §3.2, §7 | Modelin eğitildiği dağılım; gece payı (%48.755), 24 s vs gündüz şekil değişimi, diürnal modülasyon |
| `tables/temporal_coverage_by_city.csv` | §2, §4.2 | Kapsam ve kesintisizlik, gündüz payı, mevsimsel gündüz süresi, süre × yoğunluk ayrıştırması |
| `tables/target_by_hour_by_city.csv` | §4.1 | Günlük profil, zirve saat, enerji ağırlık merkezi, gündüz penceresi genişliği |
| `tables/time_feature_explained_variance.csv` | §4.1 | η² (saat / yılın günü), harmonik R², sin-cos kodlamasının yeterliliği |
| `tables/seasonal_target_stats.csv` | §4.2, §6 | Mevsimlik günlük toplam ve CV, Yaz/Kış oranları, Kış/Yaz CV oranı |
| `tables/monthly_target_stats.csv` | §4.3 | Son 12 ay (test dönemi) aylık dağılım; kışın karanlık olduğu tespiti — **yalnız 2025-04 → 2026-03** |
| `tables/daily_clearness_by_city.csv` | §1, §6 | Ampirik berraklık oranı, günlük toplam ortalaması ve CV, açık/kapalı gün payları (eşik 0.9/0.5) |
| `tables/clearness_index_by_city.csv` | §3.1, §6 | Fiziksel kt, saatlik ve günlük, il × mevsim; açık/kapalı payları (eşik 0.7/0.3) |
| `tables/autocorrelation_clearness.csv` | §4.4 | kt'nin ACF/PACF'i; `lookback_hours` kararının dayanağı |
| `tables/ramp_stats_by_city.csv` | §6.1, §8 | \|ΔIşınım\| ve \|Δkt\| persentilleri, mevsim kırılımı |
| `tables/correlation_pearson_<il>.csv`, `_pooled.csv` | §5.3, §5.4 | Yordayıcılar arası yapı, Simpson tersinmeleri, il bazlı ayrışma |
| `tables/correlation_spearman_<il>.csv`, `_pooled.csv` | §5.2 | Doğrusallık kontrolü; yağıştaki Pearson–Spearman farkı |
| `tables/target_correlation_by_city.csv` | §1, §5.1 | Ham ve kısmi korelasyon; işaret tutarlılığı argümanı |
| `tables/collinear_pairs.csv` | §1, §5.3 | \|r\| > 0.9 çiftleri (`WS10M`–`WS50M`, `QV2M`–`T2MDEW`) |
| `tables/wind_direction_circular_stats.csv` | §3.3 | Dairesel yön istatistiği; Van'ın örgütlülüğü, havuzlanmış R = 0.091 |
| `tables/daylight_block_structure.csv` | §7 | Gece satırları silinirse pencere üretilemeyeceğinin kanıtı |
| `tables/persistence_baseline.csv` | §1, §7 | Referans zemin: RMSE/MAE/R²/yanlılık, il ve kapsam kırılımlı — **modelin test penceresi** |

### Figürler

Aşağıdakiler, karşılık gelen bir CSV'de bulunmayan bilgi taşır ve bu belgede o nedenle
incelenmiştir:

| Figür | Bu belgede | Yalnız figürden okunabilen |
|---|---|---|
| `figures/target_histogram.png` | §3.1 | Dağılımın gerçek şekli: kenar-saat yığılması + geniş plato + sert tavan; "iki tepeli" nitelemesinin yerine geçen doğru betim |
| `figures/monthly_boxplot_all_years.png` | §4.2 | Mutlak saçılımın kışta değil **geçiş aylarında** en geniş olması; aykırı değerlerin yazda ve aşağı yönde toplanması |
| `figures/month_year_anomaly_panel.png` | §4.3 | Anomali gridi hiçbir tabloda yok: 2023 eksikliğinin ilkbahar–erken yaz odaklı olması, Rize'nin bölgesel anomaliden ayrışması |
| `figures/scatter_vs_target_Ankara.png` | §3.4, §5.2, §8 | Bağıl nemin tavan/heteroskedastik yapısı; özgül nem ve çiy noktasının ters-U'su; yağışın ikili karakteri |
| `figures/scatter_vs_target_Rize.png` | §5.2 | Aynı ilişkilerin ilden ile biçim değiştirmesi: Rize'de tek yönlü nem, eşikli sıcaklık, tek tepeli rüzgâr |
| `figures/seasonal_dayofyear.png` | §3.1, §8 | Nokta bulutunun asimetrisi — keskin üst zarf, uzun alt kuyruk; simetrik CI'ye karşı görsel argüman |
| `figures/month_year_surface_panel.png` | §4.3 | Ortak yazarların istediği 3B görünüm; yıl ekseninin kabartmasız olduğunun doğrudan gösterimi |
| `figures/ramp_distribution.png` | §8 | Birikimli dağılımın persentiller arasındaki biçimi (geniş gövde, ince kuyruk) ve mevsim sıralamasının geometrik kökeni |
| `figures/rize_comparison.png` | §6.1 | Bileşik argüman: kt'de birinci dereceden ayrışma, mevsimsel faz kayması (zirve Ağustos), CV panelindeki karşılaştırma |

Aşağıdaki figürler **bilinçli olarak incelenmemiştir**, çünkü taşıdıkları bilgi bir CSV'den tam
olarak geri elde edilebilir ve ayrı bir yorum gerektirmez:
`correlation_heatmap_<il>` / `_pooled` (= `correlation_pearson_*.csv`),
`target_correlation_panel` (= `target_correlation_by_city.csv`),
`persistence_baseline` (= `persistence_baseline.csv`),
`autocorrelation_hourly` / `autocorrelation_daily` (= `autocorrelation_clearness.csv`),
`seasonal_diurnal_profile` (= `target_by_hour_by_city.csv`),
`monthly_boxplot_last12m_<il>` / `_panel` (= `monthly_target_stats.csv`),
ve panel figürlerinin il-bazlı kopyaları (`month_year_surface_<il>`,
`scatter_vs_target_{Antalya,Konya,Van}`).

### Bu belge için `base_features.parquet` üzerinde yapılan ek hesaplar

Aşağıdaki üç sonuç mevcut tablolarda bulunmadığı için doğrudan
`outputs/processed/base_features.parquet` üzerinden hesaplanmıştır. Makalede kullanılacaklarsa
`scripts/02_descriptive_analysis.py`'ye kalıcı birer tablo olarak eklenmeleri önerilir, aksi halde
izlenebilirlik kuralı ihlal edilmiş olur.

| Sonuç | Değer | Bu belgede |
|---|---|---|
| Çiy noktasının Magnus bağıntısıyla `T2M` + `RH2M`'den yeniden üretimi | r = 0.99919, RMSE = 0.31 °C (24 s); r = 0.99956, RMSE = 0.23 °C (gündüz) | §1, §5.3 |
| İkili "yağış var" göstergesinin hedefle korelasyonu vs ham miktarınki | Ankara −0.189/−0.097, Antalya −0.215/−0.173, Konya −0.217/−0.109, Rize −0.200/−0.215, Van −0.169/−0.137; gündüz sıfır payı %53.4 | §3.4 |
| kt > 1.2 olan satırların sayısı ve dağılımı | 4 satır / 295 920 (%0.0014), tamamı Van, tamamı Ocak–Şubat; en uç değer kt = 3.28 (2020-02-17 15:00) | §6.2 |
| Yağış biriminin iklim normalleriyle tutarlılık kontrolü | mm/gün okumasıyla Ankara 352, Konya 344, Van 352, Antalya 721, Rize 1 400 mm/yıl | §3.4 |
