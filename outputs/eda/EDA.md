# Keşifsel veri analizi — bulgular ve yorumu

**Veri sürümü:** `SolarData_Merve(140926).xlsx` (14 Eylül 2026 dışa aktarımı)
**Bu belgenin tarihi:** 14 Eylül 2026 — önceki sürüm (16 Temmuz dosyası) tamamen geçersizdir.

Bu belge `outputs/eda/` altındaki tablo ve figürlerin **ne söylediğini** anlatır. Hedef kitle
makalenin ortak yazarlarıdır: her bölüm, o bölümdeki sayıyı makaleye taşımak için bilmeniz
gereken her şeyi içerir, ayrı bir teknik belgeye gitmeniz gerekmez. Analizlerin nasıl
üretildiği (kod, filtreler, kapsam kuralları) yan taraftaki `README.md`'dedir.

Okuma kılavuzu:

- Her sayı `outputs/eda/tables/` altındaki bir dosyadan gelir. Hangi iddianın hangi dosyaya
  dayandığı **§11**'dedir. Metinde bir sayı ile dosya çelişirse **dosya esastır**.
- **Uyarı** ile başlayan cümleler, o sayıyı makaleye taşırken birlikte taşınması gereken
  kısıtlardır. Tek başına alıntılanan bir sayı yanıltıcı olur.
- **Öneri** ile başlayan cümleler veriden çıkan modelleme yorumlarıdır; henüz sınanmış
  sonuçlar değildir.

---

## 0. Önce okunması gereken: veri seti değişti

Yeni dosya eskisinin güncellenmiş hâli değil, **farklı ayarlarla alınmış yeni bir dışa
aktarım**. Aynı NASA POWER kaydı, ama üç şey değişti. Bunları bilmeden aşağıdaki hiçbir sayı
eskisiyle kıyaslanamaz.

### 0.1 Birimler değişti

| Değişken | Eski dosya | Yeni dosya | Ne yaptık |
|---|---|---|---|
| `ALLSKY_SFC_SW_DWN` (hedef) | W/m² | **MJ/m²/saat** | Okurken W/m²'ye çevriliyor (×277.78) |
| `PRECTOTCORR` (yağış) | mm/gün | **mm/saat** | Olduğu gibi bırakıldı |

Çevrim tam ve doğrusaldır; iki dosyayı ortak 59.184 saatte birleştirip doğruladık:
meteorolojik sütunlar bit düzeyinde aynı, çevrilmiş ışınım eski değerleri **en fazla
1.39 W/m² sapmayla** yeniden üretiyor.

Hedefi W/m²'ye çevirmeyi tercih ettik çünkü makalenin, kaynak makalenin ve literatürün
tamamı W/m² kullanıyor; birim değiştirmek hiçbir kazanç sağlamadan mevcut tüm tabloları
okunamaz hâle getirirdi.

**Uyarı — bir bedeli var.** Yeni dosya MJ cinsinden **2 ondalık** saklıyor. Bu, W/m²'ye
çevrildiğinde hedefin **2.78 W/m² adımlarla ayrıklaştığı** anlamına gelir: tüm kayıtta yalnız
387 farklı hedef değeri var. Ayrıklaştırma gürültüsünün standart sapması 2.78/√12 = 0.80 W/m²,
yani en iyi referans zeminin RMSE'sinin %1'inin altında — hiçbir metriği maddi olarak
etkilemez. Ama iki somut sonucu var ve ikisi de aşağıda yeniden karşımıza çıkacak (§3.1, §6.3).

Yağışta bedel daha ağır: eski dosya mm/gün cinsinden 2 ondalık saklıyordu (0.01 mm/gün
çözünürlük), yeni dosya mm/saat cinsinden 2 ondalık sakladığı için çözünürlük 0.24 mm/gün'e
düştü. Eskiden yağışlı görünen saatlerin **%38.7'si artık tam sıfır** okunuyor. Toplam yağış
korunuyor (Ankara için 2381 mm'ye karşı 2371 mm), kaybedilen şey çiseleme ayrıntısı.

### 0.2 `CLRSKY_SFC_SW_DWN` sütunu artık yok

Bu, değişikliklerin en ciddisidir. Berrak gökyüzü ışınımı bu projede bir öznitelik değildir ve
hiç olmadı, ama dört yerde taşıyıcı:

1. **Gündüz alt kümesini tanımlar** (`CLRSKY > 0`) — makalenin başlık metriklerinin tamamı bu
   alt küme üzerinde raporlanıyor;
2. gece tahminlerini sıfıra sabitleyen `clamp_night_to_zero` kısıtının aracıdır;
3. berraklık indeksi `kt = ALLSKY / CLRSKY`'nin paydasıdır — hem `clearsky_index` hedef
   dönüşümü hem de bu belgedeki iller arası karşılaştırmaların çoğu buna dayanır;
4. akıllı kalıcılık referansının ileri taşıdığı çarpandır.

Sütunu silmek bir sadeleştirme değil, makalenin başlık sayılarını silmek olurdu. Bu yüzden
**geri inşa ettik** (`src/merve_solar/clearsky.py`):

- Kaydın **%97.6'sı** için değer eski dışa aktarımdan **birebir** alınıyor. İki dosya aynı
  NASA POWER kaydı olduğundan (meteorolojik sütunlar bit düzeyinde aynı) bu bir tahmin değil,
  aynı verinin kendisidir.
- Kalan **%2.4** (31 Mart – 30 Mayıs 2026, il başına 1.464 saat) hiçbir kaynakta yok; aynı
  (il, ay, gün, saat) hücresinin önceki yıllardaki **medyanı** ile dolduruldu.

Doğruluğu ölçtük — her yılın 31 Mart – 30 Mayıs penceresini diğer yıllardan yeniden kurarak,
yani kuyruğun ihtiyaç duyduğu işlemin birebir aynısıyla:

| Ne | Hata |
|---|---|
| Güneş doğdu/battı bayrağı (gündüz alt kümesinin dayandığı şey) | saatlerin **%0.000–0.082**'sinde yanlış |
| Işıklı saatlerde büyüklük | MAE **24–31 W/m²**, yani %6–8 |

Yani **gündüz maskesi fiilen kusursuz**; `kt` ise kaydın son iki ayında birkaç yüzdelik payda
hatası taşıyor.

**Öneri — asıl çözüm bu değil.** Merve'den `CLRSKY_SFC_SW_DWN` parametresini de içeren bir
yeniden dışa aktarım istemek, NASA POWER arayüzünde tek bir kutucuk işaretlemek demek ve bu
bölümün tamamını gereksiz kılar. Yeniden inşa bir köprüdür, bir tasarım değil.

**Uyarı — bir iddiayı zayıflatmak zorundayız.** Depo üç ayrı yerde berrak gökyüzü ışınımının
"hava durumu terimi içermeyen saf güneş geometrisi" olduğunu yazıyor. Bu, NASA POWER'ın
sütunu için ölçülebilir biçimde fazla güçlü bir iddia: **güneşin konumu sabitken bile** (Ankara,
21 Haziran, saat 11:00) değer 2020–2025 arasında 952.5 ile 1008.7 W/m² arasında geziyor, yani
%5.9'luk bir bant. 200 W/m²'nin üzerindeki tüm hücrelerde yıllar arası bağıl standart sapma
medyan %4.1, %90'lık dilimde %7.9. Demek ki CLRSKY geometrinin üstünde yavaş bir aerosol ve su
buharı terimi taşıyor.

Bunun pratik sonucu dardır ama makale açısından önemlidir: **yalnızca işareti** (`> 0`)
saf geometriktir, ve gündüz maskesi ile gece sabitlemesi yalnızca işarete dayandığı için
ikisi de etkilenmez. Etkilenen, `clearsky_index` hedef dönüşümünün gerekçesidir — bu dönüşüm
hâlâ sızıntı değildir (CLRSKY bulutluluğu, yani tahmin edilen şeyi görmez), ama "tamamen
astronomi" diye savunulmamalıdır.

### 0.3 Öznitelik seti değişti: 17 → 16

| Giden | Gelen |
|---|---|
| `QV2M` (özgül nem) | `WS2M` (2 m rüzgâr hızı) |
| `WS50M`, `WD50M` (50 m rüzgâr) | `WD2M` (2 m rüzgâr yönü) |
| `ALLSKY_KT` (zaten atılıyordu) | — |
| `CLRSKY_SFC_SW_DWN` (§0.2) | — |

Değişmeyenler: hedefin kendi gecikmesi, `T2M`, `RH2M`, `T2MDEW`, `PS`, `WS10M`, `WD10M`,
`PRECTOTCORR` ve dört zaman kodlaması (saat sin/cos, yılın günü sin/cos).

**Kayıp önemsiz, hatta lehimize.** `QV2M` zaten gereksiz işaretlenmişti (eski dosyada `T2MDEW`
ile r = 0.962) ve 50 m rüzgâr, EDA'nın zaten silinmek üzere kuyruğa aldığı çiftin üyesiydi.
Yerine gelen 2 m rüzgârı ise daha da gereksiz: `WS2M`–`WS10M` korelasyonu 0.986 (gündüz),
`WD2M` ile `WD10M` arasındaki açı farkının medyanı **0.30°** ve sin/cos kodlamalarının
korelasyonu 0.996. Ayrıntı §6.3'te.

### 0.4 Kayıt uzadı

Eski dosyada NASA POWER'ın gerçek zamanlı işleme gecikmesinden doğan `-999` kuyruğu 2.208
saatti; yenisinde **744 saat** (31 Mayıs – 30 Haziran 2026) ve yalnızca hedef sütununu
etkiliyor — meteorolojik sütunlar son satıra kadar dolu. Sonuç: il başına **1.464 saat
(61 gün) daha fazla kullanılabilir veri**.

---

## 1. Kısa özet — makaleye mutlaka girmesi gereken yedi bulgu

**(1) Beş il iklim çeşitliliği iddiasını taşıyor, ama simetrik biçimde değil.** Günlük toplam
ışınım ortalaması Van 5.00, Antalya 4.97, Konya 4.89, Ankara 4.68 kWh/m²/gün ile %7'lik dar
bir bantta; Rize 3.71 kWh/m²/gün ile bu bandın %21–26 altında. Asıl fark seviyede değil
**öngörülebilirlikte**: Rize'nin günlük berraklık indeksi 0.697 (diğerleri 0.805–0.839),
kapalı gün payı %8.1 (diğerleri %0.95–2.77), günler arası değişim katsayısı 0.566 (diğerleri
0.436–0.489). Makalenin "iller arası aktarım" iddiasının gerçek sınavı Rize'dir.

**(2) Gece satırları her metriği bedavaya iyileştirir.** Satırların %48.6'sı geometrik olarak
gecedir ve tamamı tam sıfırdır. Aynı klimatoloji referansı 24 saat üzerinden RMSE 78.3 W/m² /
R² 0.920, gündüz saatleri üzerinden RMSE 108.8 / R² 0.851 veriyor. Gece satırları RMSE'yi %28
düşürüyor ve R²'yi 0.069 şişiriyor. **Literatürle kıyaslanabilir olan gündüz rakamıdır.**

**(3) Modelin aşması gereken zemin kalıcılık değil klimatolojidir.** Gündüz saatlerinde,
modelin kendi kronolojik test penceresinde: kalıcılık RMSE 120.7 / MAE 71.0 / R² 0.817,
akıllı kalıcılık 116.2 / 65.0 / 0.830, klimatoloji **108.8 / 74.5 / 0.851**. RMSE'de
klimatoloji, MAE'de akıllı kalıcılık kazanıyor; ikisi birden raporlanmazsa şampiyon
değişiyor. 24 saat ilerisi bir tahmin için kalıcılığı geçmek bir sonuç değildir — 24 saatlik
kalıcılık günlük döngüyle zaten hizalıdır.

**(4) Ham korelasyonların önemli kısmı güneş geometrisidir.** Havuzlanmış gündüz verisinde
sıcaklığın hedefle ham korelasyonu +0.516, (il, ay, saat) hücresi içindeki kısmi korelasyonu
+0.305. Basınç −0.035'ten **+0.266**'ya, çiy noktası +0.042'den **−0.269**'a işaret
değiştiriyor. Daha güçlü bir ifade: **ham korelasyonda üç değişkenin işareti iller arasında
tutarsızken, geometri sabitlendikten sonra yedi değişkenin yedisi de beş ilde aynı işarete
sahip.** Bu tek cümle kısmi korelasyon tablosunun makaleye girmesi için yeterli gerekçedir.

**(5) Zaman ekseninde bilgi 24 saatlik pencerede tükeniyor.** Berraklık indeksi saatlik
ölçekte neredeyse bir AR(1) (PACF gecikme 1: 0.933–0.965; gecikme 2: −0.146…+0.140). 24 saat
ilerisi tahmin için belirleyici olan günlük ölçekte kısmi otokorelasyon 1. günde 0.396–0.560,
2. günde 0.003–0.120'ye düşüyor. `lookback_hours`'ı 24'ten 48'e çıkarmak, kısmi korelasyonu
~0.1 olan bir ikinci gün eklemek demektir.

**(6) Öznitelik setinde en az üç sütun fiilen gereksiz.** `WS2M`–`WS10M` r = 0.986;
`WD2M` ile `WD10M` arasındaki açı farkının medyanı 0.30°, sin/cos korelasyonları 0.996;
ve çiy noktası sıcaklık ile bağıl nemden Magnus bağıntısıyla **r = 0.99919 ve 0.30 °C RMSE
ile** yeniden üretilebiliyor — yani `T2MDEW` bir ölçüm değil, mevcut iki sütunun determinist
bir dönüşümü. 16 öznitelikten etkin olarak ~12'si bağımsız bilgi taşıyor.

**(7) Test penceresi dört mevsimi kapsıyor; doğrulama penceresi kapsamıyor.** Yeni kayıtla
kronolojik bölme test setine 9.097 saat = **379 gün** veriyor (2025-05-16 → 2026-05-30), yani
bir tam yılın biraz üzerinde — mevsim yanlılığı yok. Ama doğrulama penceresi (2024-08-12 →
2025-05-16, 6.671 saat) **Haziran ve Temmuz'u içermiyor**. Bu, konformal katmanın kalibrasyon
kümesinin bilinen kusurudur ve yeni veriyle **yön değiştirdi**: eskiden Nisan–Mayıs eksikti,
şimdi yılın en yüksek ışınımlı iki ayı eksik. Ayrıntı §10.3.

---

## 2. Veri seti ve kapsam

| | |
|---|---|
| Kaynak | NASA POWER saatlik, `SolarData_Merve(140926).xlsx`, il başına bir sayfa |
| İller | Ankara, Antalya, Konya, Rize, Van |
| Kayıt aralığı | 2019-06-30 00:00 → 2026-05-30 23:00 |
| İl başına saat | 60.648 (2.527 gün ≈ 6.92 yıl) |
| Toplam satır | 303.240 |
| Gündüz satırı | 155.896 (**%51.41**) |
| Eksik değer | yok (`-999` kuyruğu kırpıldıktan sonra sıfır, NaN sıfır) |
| Öznitelik | 16 (§0.3) |
| Hedef | `ALLSKY_SFC_SW_DWN`, W/m² |

Kapsam tamamen dengeli: beş il de aynı 60.648 saati, aynı takvim aralığında paylaşıyor.
Kronolojik bölme (train 0.74 / val 0.11 / test 0.15) beş il için **aynı tarihlerde** yapılıyor:

| Bölüm | Aralık | Saat | Gün |
|---|---|---|---|
| Eğitim | 2019-06-30 → 2024-08-11 | 44.879 | 1.870 |
| Doğrulama | 2024-08-12 → 2025-05-16 | 6.671 | 278 |
| **Test** | **2025-05-16 → 2026-05-30** | **9.097** | **379** |

Test penceresi 13 takvim ayını ve dört mevsimin tamamını kapsıyor (İlkbahar 12.725, Yaz
11.040, Sonbahar 10.920, Kış 10.800 saat). Gündüz saati sayısı iller arasında 4.680 (Antalya)
ile 4.743 (Ankara) arasında.

**Uyarı.** `train_ratio`/`val_ratio` değerleri test penceresinin bir tam yılı aşması için
ayarlanmıştır. Yeni kayıt uzadığı için pencere 370 günden 379 güne çıktı; oranları
değiştirmek dört mevsim özelliğini bozar ve skoru mevsim yanlı hâle getirir.

### 2.1 Saat dilimi: paylaşılan bir saat değil, yerel güneş saati

Saat sütunu ortak bir saat dilimi değildir; her il kendi **yerel güneş saatinde** kayıtlıdır.
Bunu veriden doğruladık: ortalama ışınımın ağırlık merkezi olarak tepe saati

> Konya 11.24 ≈ Ankara 11.24 < Antalya 11.41 < Van 11.58 < Rize 11.91

sırasını veriyor. Bu, ortak bir saat dilimi olsaydı ortaya çıkacak sıranın **tam tersidir**
(doğudaki Van ve Rize'nin tepesi ortak saatte daha *erken* olurdu) ve `UTC + yuvarla(boylam/15)`
ile 0.1 saat içinde örtüşüyor.

İki sonucu var:

- **Saatler iller arasında karşılaştırılmaz.** Rize'de saat 11, Ankara'da saat 11 ile aynı
  fiziksel an değildir. Figürlerdeki saat eksenleri "yerel saat (LST)" olarak etiketlenmiştir
  ve saat etiketleri aralık *başlangıcıdır*.
- **`hour_sin`/`hour_cos` göründüğünden iyi bir kodlamadır**, çünkü her il kendi güneş
  saatinde kodlanmış olur. Bu, makalenin yöntem bölümünde bir cümleyi hak ediyor.

---

## 3. Hedef değişken

### 3.1 Dağılım

Havuzlanmış, gündüz saatleri: ortalama **376.9 W/m²**, medyan 333.3, standart sapma 279.9,
maksimum 1216.7 (Van). Çarpıklık +0.437, fazlalık basıklığı −0.940.

24 saat üzerinden: ortalama 193.7, medyan 8.3, çarpıklık +1.279.

Bu iki satır arasındaki fark, §1(2)'nin özüdür. 24 saatlik dağılım iki kütlenin karışımıdır:
tam sıfırdan oluşan gece yığını ve gündüz dağılımı. Gündüz dağılımı ise **negatif basıklıklı**,
yani tek tepeli değil, geniş ve yayvandır — geometrinin gün içinde 0'dan ~1000'e süpürmesinin
doğrudan sonucu.

**Uyarı — ölçekleme.** Hedef normal dağılımlı değildir ve öyle davranan hiçbir dönüşüm
uygulanmamıştır. `StandardScaler` yalnızca eğitim satırlarına uydurulur; ölçekleme sonrası
dağılımın şekli değişmez.

**Ayrıklaştırmanın iki somut sonucu** (bkz. §0.1):

1. Gündüzün en küçük sıfır olmayan okuması artık **2.7778 W/m²**, yani tam olarak bir
   ayrıklaştırma adımı. Eski dosyada 3.78 W/m² idi.
2. **36 gündüz saati tam sıfır okuyor.** Eski dosyada bu sayı sıfırdı ve bu, "gündüz =
   hedef > 0" tanımının geometrik tanımla birebir çakışmasını sağlıyordu. Artık çakışmıyor.
   Bu, gündüz tanımının **geometrik olması gerektiğinin** doğrudan kanıtıdır: hedef eşiği
   hem bağımlı değişkene koşullanır, hem de artık yanlış sonuç verir. Ters yönde tek bir hata
   yok — güneş batmışken pozitif okuyan hiçbir saat bulunmuyor.

### 3.2 Gündüz nasıl tanımlanıyor ve neden

**Gündüz = `CLRSKY_SFC_SW_DWN > 0`**, projenin her yerinde. Gerekçe §0.2'de: berrak gökyüzü
ışınımının büyüklüğü hava durumu terimi taşısa da **işareti** saf güneş geometrisidir, yani
"güneş bu il ve bu saatte ufkun üzerinde mi" sorusunun tam cevabıdır ve gerçekleşen hedefi
hiç okumaz.

Denenmiş ve yanlış bulunmuş iki alternatif:

- **`hedef > 0`** bağımlı değişkene koşullanıyor gibi görünür — ve yeni veride artık
  gerçekten ayrışır (36 satır, §3.1).
- **(il, ay, saat) klimatolojik hücre ortalaması** fazla kabadır: bir ay içinde gün doğumu
  30–60 dakika kayar, hücrenin kenar saati ayın bir kısmında aydınlık bir kısmında karanlıktır;
  hücre ortalaması tüm saati gündüz sayar ve gece satırlarını gündüz rakamlarına geri sokar.

### 3.3 Gün içi ve mevsimsel yapı

Saat, 24 saatlik varyansın **%73.1'ini** tek başına açıklıyor (havuzlanmış η²); gündüz alt
kümesinde bu %50.3'e düşüyor. Yılın günü ise sırasıyla %8.6 ve %14.4. Yani:

- 24 saatlik bir skorun dörtte üçü gün/gece döngüsünü bilmekten gelir — modelden değil;
- gündüz alt kümesinde saat hâlâ baskındır ama mevsimin payı neredeyse iki katına çıkar.

Bir harmonik (sin/cos) uyarlaması η²'nin neredeyse tamamını yakalıyor (örn. havuzlanmış 24
saat: η² 0.7313'e karşı harmonik R² 0.7285). **Öneri:** `hour_sin`/`hour_cos` ve
`doy_sin`/`doy_cos` kodlaması, kategorik saat kuklalarına kıyasla bilgi kaybetmiyor; mevcut
kodlama korunmalı.

### 3.4 Mevsimsellik: ışınım ile öngörülebilirlik ters yönde hareket eder

Günlük toplamın mevsimsel değişim katsayısı (CV):

| İl | Kış | Yaz | Kış/Yaz |
|---|---|---|---|
| Ankara | 0.432 | 0.142 | 3.04× |
| Antalya | 0.383 | 0.100 | 3.82× |
| Konya | 0.397 | 0.130 | 3.05× |
| Van | 0.326 | 0.120 | 2.72× |
| Rize | 0.504 | 0.279 | **1.81×** |

Yaz günleri yalnızca daha parlak değil, **1.8–3.8 kat daha az değişken**. Bu, hata
metriklerinin mevsime göre çok farklı davranacağı anlamına gelir ve mutlak hatanın kışın
küçük çıkması modelin kışın iyi olduğu anlamına gelmez — kışın tahmin edilecek şey daha
azdır.

**Uyarı.** Rize bu tabloda bandın dışındadır: yazın bile diğer illerin kışına yakın bir
değişkenlik taşır. Rize'yi içeren bir "mevsimsel değişkenlik" cümlesi 1.8–3.8 aralığını
vermeli, "3–4 kat" dememelidir.

### 3.5 Yıllar arası değişkenlik: küçük ama sıfır değil

Tam takvim yılları (2020–2025) üzerinde ortalama günlük toplam:

| İl | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | En iyi/en kötü |
|---|---|---|---|---|---|---|---|
| Ankara | 4.83 | 4.73 | 4.64 | 4.56 | 4.72 | 4.90 | %7.2 |
| Antalya | 5.06 | 5.13 | 5.04 | 4.86 | 4.99 | 5.04 | %5.6 |
| Konya | 5.01 | 4.98 | 4.87 | 4.84 | 4.90 | 5.09 | %5.1 |
| Rize | 3.91 | 3.75 | 3.54 | 3.68 | 3.82 | 3.74 | **%10.3** |
| Van | 4.95 | 5.26 | 5.16 | 4.87 | 4.95 | 5.05 | %8.0 |

Yıllar arası bağıl standart sapma %1.8–3.3. Yani eğitim ve test yıllarının farklı olması
başlı başına büyük bir kayma yaratmıyor — ama **Rize'de %10'luk bir yıl etkisi** var ve bu,
Rize'nin test skorundaki oynaklığın bir kısmının modelden değil o yılın kendisinden
geldiği anlamına gelir.

**Uyarı.** Bu tablo yalnızca tam takvim yıllarını içerir; 2019 ve 2026 kısmidir ve
karşılaştırmaya girmez.

---

## 4. Meteorolojik değişkenler

Betimsel istatistikler `descriptive_stats_by_city_daylight.csv` ve `..._24h.csv`
dosyalarında, hem il bazında hem havuzlanmış, `.md` ve `.tex` sürümleriyle birlikte.

Havuzlanmış gündüz değerleriyle kısa tanıtım:

| Değişken | Ortalama | SS | Aralık | Not |
|---|---|---|---|---|
| Sıcaklık `T2M` | 15.5 °C | 10.3 | −23.6 … 42.3 | İller arası SS 3.8 |
| Bağıl nem `RH2M` | %54.0 | 23.7 | 3.4 … 100 | İller arası SS 11.1 — en ayrıştırıcı |
| Çiy noktası `T2MDEW` | 4.3 °C | 7.0 | −27.5 … 22.9 | Türetilebilir, §6.3 |
| Basınç `PS` | 88.3 kPa | 6.0 | 75.8 … 97.7 | Varyansın neredeyse tamamı rakım |
| Rüzgâr 2 m `WS2M` | 2.59 m/s | 1.54 | 0.01 … 13.7 | |
| Rüzgâr 10 m `WS10M` | 3.52 m/s | 2.01 | 0.01 … 18.7 | `WS2M` ile r = 0.986 |
| Yağış `PRECTOTCORR` | 0.071 mm/saat | 0.26 | 0 … 7.4 | Çarpıklık +8.1 |

**Basınç bir meteorolojik değişken gibi davranmıyor.** Havuzlanmış standart sapması 6.0 kPa
ama iller arası standart sapması 6.7 — yani varyansın tamamı iller arasıdır, il içi değil
(Van 77.7, Konya 87.8, Ankara 88.8, Rize 91.2, Antalya 96.0 kPa). Havuzlanmış bir modelde
`PS` fiilen bir **rakım/il kimliği göstergesi** olarak çalışır ve şehir gömmesiyle bilgi
tekrarı yapar. İl içi değişimi (SS ≈ 0.4–0.5 kPa) gerçek sinoptik sinyaldir ve §6.1'de kısmi
korelasyonun neden işaret değiştirdiğini açıklar.

### 4.1 Yağış: neredeyse ikili bir değişken

Gündüz saatlerinin **%66.8'i tam sıfır**. Sıfır olmayan kuyruk çok çarpık (çarpıklık +8.1,
fazlalık basıklığı +99).

Hedefle korelasyon, üç kodlama için:

| İl | İkili (yağış var/yok) | Ham miktar | `log1p(miktar)` |
|---|---|---|---|
| Ankara | **−0.156** | −0.097 | −0.109 |
| Antalya | −0.211 | −0.173 | −0.200 |
| Konya | **−0.183** | −0.110 | −0.132 |
| Rize | −0.218 | −0.215 | **−0.245** |
| Van | **−0.182** | −0.134 | −0.156 |

Üç ilde basit bir **"yağış var mı" göstergesi ham miktardan daha bilgili**; Rize'de ise
`log1p` öne geçiyor. Bu, `TODOs.md` §B'de zaten kuyrukta olan öznitelik çalışmasını
doğruluyor.

**Öneri.** Yağışı tek bir ham sütun olarak bırakmak yerine **`log1p(PRECTOTCORR)` + ikili
yağış göstergesi** çifti olarak vermek, hem yağış rejimi farklı olan Rize'yi hem de kuru
illeri aynı anda karşılıyor. Bu bir ledger sütunu ya da yeni bir deney kimliği gerektirir.

**Birim doğrulaması.** Yeni sütunu mm/saat okuyup yıllık toplarsak (2020–2025 ortalaması)
Ankara 340, Konya 326, Van 343, Antalya 664, Rize 1399 mm/yıl çıkıyor. Sıralama ve büyüklük
Türkiye iklim normalleriyle uyumlu (NASA POWER uydu ürünü olarak Rize ve Antalya'yı
olduğundan düşük tahmin ediyor, bu bilinen bir davranıştır). Bu, mm/saat yorumunun doğru
olduğunun bağımsız teyididir.

### 4.2 Rüzgâr yönü: yalnız Van'da bilgi taşıyor

Rüzgâr yönü dairesel bir değişkendir; aritmetik ortalaması anlamsızdır. Hıza göre ağırlıklı
dairesel istatistikler (`wind_direction_circular_stats.csv`), 1 m/s altındaki durgun saatler
dışarıda bırakılarak:

| İl | Ortalama yön (10 m) | Bileşke uzunluk *R* | Dairesel SS |
|---|---|---|---|
| Van | 211° | **0.464** | 71° |
| Konya | 334° | 0.221 | 100° |
| Rize | 257° | 0.203 | 102° |
| Antalya | 31° | 0.191 | 104° |
| Ankara | 335° | 0.128 | 116° |

Bileşke uzunluk 0 (tamamen dağınık) ile 1 (tek yön) arasındadır. **Yalnızca Van'da baskın bir
yön var**; diğer dört ilde rüzgâr yönü pratik olarak düzgün dağılmış ve dolayısıyla
öngörücü olarak neredeyse boş.

**Uyarı.** Durgun saat payı iller arasında çok farklı (Rize'de 10 m için 7.230 saat, Konya'da
2.786) ve bu saatlerde yönün kendisi gürültüdür. Yön öznitelikleri makalede tartışılacaksa bu
filtre belirtilmelidir.

---

## 5. Zamansal yapı ve `lookback_hours` kararı

Otokorelasyon **berraklık indeksi kt üzerinde** hesaplanır, ham ışınım üzerinde değil. Neden:
ham ışınımın otokorelasyonu neredeyse tamamen günlük döngüdür ve hiçbir şey öğretmez;
kt geometriyi böldüğü için geriye kalan **atmosferin belleğidir** — tahmin edilmesi gereken
şeyin ta kendisi.

### 5.1 Saatlik ölçek: neredeyse bir AR(1)

| | Ankara | Antalya | Konya | Rize | Van |
|---|---|---|---|---|---|
| PACF gecikme 1 | 0.963 | 0.959 | 0.962 | 0.965 | 0.933 |
| PACF gecikme 2 | −0.052 | −0.146 | −0.020 | −0.138 | +0.140 |
| PACF gecikme 3 | −0.102 | −0.057 | −0.087 | −0.096 | −0.024 |
| ACF gecikme 24 | 0.479 | 0.528 | 0.519 | 0.378 | 0.514 |

Birinci gecikme her ilde 0.93'ün üzerinde, ikinci gecikme sıfır civarında salınıyor. Yani
saatlik kt bir AR(1) gibi davranıyor: bir saat öncesini bilmek, iki saat öncesini bilmeye
neredeyse hiçbir şey eklemiyor.

**Teknik not.** PACF her ilde 12. gecikmede kesiliyor; bunun nedeni gece saatlerinde kt'nin
tanımsız olması ve serinin günlük bloklara ayrılmasıdır. 12'nin ötesindeki değerler
raporlanmaz.

### 5.2 Günlük ölçek: 24 saat ilerisi tahmin için belirleyici olan budur

| | Ankara | Antalya | Konya | Rize | Van |
|---|---|---|---|---|---|
| PACF gün 1 | 0.530 | 0.529 | 0.560 | **0.396** | 0.558 |
| PACF gün 2 | 0.112 | 0.120 | 0.096 | **0.003** | 0.116 |
| PACF gün 3 | 0.117 | 0.138 | 0.083 | 0.060 | 0.128 |
| ACF gün 30 | 0.197 | 0.250 | 0.187 | **0.070** | 0.223 |

Birinci günden ikinci güne düşüş beş katın üzerinde. **`lookback_hours = 24` kararının
kanıtı budur:** 48 saate çıkmak, kısmi korelasyonu 0.003 (Rize) ile 0.120 (Antalya) arasında
olan bir ikinci gün eklemek demektir.

30. gündeki artık otokorelasyon (0.07–0.25) mevsimsel eğilimdir, bellek değil — `doy_sin`/
`doy_cos` bu bilgiyi zaten taşır.

**Uyarı.** Rize her satırda bandın dışındadır ve her seferinde daha az belleğe sahiptir.
Rize'nin havası daha az kalıcıdır; bu, §7'deki tüm Rize bulgularıyla tutarlıdır.

### 5.3 Rampalar: modelin gerçekte karşılaştığı zorluk

Ardışık gündüz saatleri arasındaki mutlak değişim (`ramp_stats_by_city.csv`):

| İl | Medyan \|Δ\| | p90 | p99 | >200 W/m² payı | \|Δkt\| p99 |
|---|---|---|---|---|---|
| Ankara | 105.6 | 186.1 | 211.1 | %3.3 | 0.217 |
| Antalya | 113.9 | 191.7 | 219.4 | %5.9 | 0.188 |
| Konya | 108.3 | 191.7 | 216.7 | %5.9 | 0.223 |
| Rize | 80.6 | 166.7 | 213.9 | %1.6 | 0.236 |
| Van | 113.9 | 194.4 | 216.7 | %6.5 | 0.243 |

Ham ışınımdaki rampanın çoğu geometridir (güneşin yükselip alçalması). Anlamlı olan **Δkt**
sütunudur: Rize ve Van, ham rampada bandın alt ve üst ucundayken, kt rampasında **ikisi de
üstte** (0.236 ve 0.243). Yani Rize'nin ham değişimi küçük görünmesi, güneşinin zaten zayıf
olmasındandır; atmosferik değişkenliği en yüksek olan illerden biridir.

### 5.4 Gündüz blokları

Gündüz saatleri kesintisiz bloklar hâlinde gelir: il başına 2.527 blok (günde bir), medyan
uzunluk 12 saat (Rize 13), en kısa 9 (Rize) / 10 (diğerleri), en uzun 14 (Antalya) / 15
(diğerleri). Hiçbir blok 24 saati aşmıyor.

**Uyarı.** Bu, 24 saatlik tahmin ufkunun her zaman en az bir gece içerdiği anlamına gelir.
Bir tahmin penceresi asla tamamen gündüz olamaz; `clamp_night_to_zero` bu nedenle her
pencerenin yaklaşık yarısını doğrudan etkiler.

---

## 6. Değişkenler arası ilişkiler ve öznitelik seçimi

### 6.1 Ham korelasyon güneş geometrisiyle karışıktır

`target_correlation_by_city.csv` hem ham Pearson korelasyonunu hem de **(il, ay, saat)
hücresi içindeki kısmi korelasyonu** verir. İkincisi, güneş geometrisi ve mevsim sabitken
değişkenin hedefle ilişkisini ölçer.

Havuzlanmış gündüz verisi:

| Değişken | Ham r | Kısmi r | Yorum |
|---|---|---|---|
| `RH2M` bağıl nem | −0.629 | **−0.524** | Tek gerçek yordayıcı; her iki ölçümde de güçlü |
| `T2M` sıcaklık | +0.516 | +0.305 | Yarısı geometri |
| `PRECTOTCORR` yağış | −0.163 | **−0.326** | Geometri sabitlenince **iki katına çıkıyor** |
| `T2MDEW` çiy noktası | +0.042 | **−0.269** | **İşaret değiştiriyor** |
| `PS` basınç | −0.035 | **+0.266** | **İşaret değiştiriyor** |
| `WS10M` rüzgâr 10 m | +0.080 | −0.154 | **İşaret değiştiriyor** |
| `WS2M` rüzgâr 2 m | +0.155 | −0.149 | **İşaret değiştiriyor** |

Dört değişken işaret değiştiriyor, biri (yağış) iki katına çıkıyor. Mekanizma basit: sıcak,
rüzgârlı, yüksek çiy noktalı saatler aynı zamanda **yazın öğlen saatleridir**, yani ışınımın
geometrik olarak zaten yüksek olduğu saatler. Geometri sabitlendiğinde bu sahte ilişki
kayboluyor ve fiziksel ilişki (nem ve bulut → daha az ışınım) ortaya çıkıyor.

**En güçlü tek argüman:** ham korelasyonda `PS`, `WS2M` ve `WS10M`'in işareti beş il arasında
**tutarsız**; kısmi korelasyonda **yedi değişkenin yedisi de** beş ilde aynı işarete sahip.
Yani geometri ayıklandığında iller fizik konusunda hemfikir hâle geliyor.

**Öneri.** Makalede yordayıcı önemi tartışılacaksa **kısmi korelasyon tablosu
kullanılmalıdır**; ham korelasyon matrisi ancak "neden yanıltıcı olduğu" gösterilmek üzere
verilmelidir.

### 6.2 Doğrusallık: Spearman ile Pearson örtüşüyor

Havuzlanmış gündüz verisinde Spearman ile Pearson arasındaki en büyük fark **yağışta
−0.054**, ardından `WS2M`'de +0.051. İl bazında en büyük fark Ankara `WS2M` +0.070 ve Konya
yağış −0.069. Hiçbir değişkende fark 0.07'yi aşmıyor.

**Sonuç:** monotonik olmayan bir ilişki yok. Farkın yağış ve rüzgârda yoğunlaşması
beklenen yöndedir (ikisi de çok çarpık dağılımlı), ve **Spearman'ın mutlak değerce daha
büyük olması** §6.1'deki öneriyi güçlendiriyor — yağışın ilişkisi doğrusaldan çok sıralamaya
dayalıdır, dolayısıyla ikili gösterge/`log1p` kodlaması yerindedir.

### 6.3 Eşdoğrusallık: üç sütun gereksiz

Havuzlanmış gündüz verisinde |r| > 0.5 olan yordayıcı çiftleri:

| Çift | Pearson | Spearman |
|---|---|---|
| `WS2M` – `WS10M` | **+0.986** | +0.979 |
| `T2M` – `RH2M` | −0.674 | −0.676 |
| `T2M` – `T2MDEW` | +0.610 | +0.596 |
| `T2MDEW` – `PS` | +0.519 | +0.480 |

Buna ek olarak, tabloların doğrudan göstermediği iki sonuç (bu belge için
`base_features.parquet` üzerinde hesaplandı):

1. **`WD2M` ile `WD10M` fiilen aynı sütun.** Aralarındaki açı farkının medyanı **0.30°**,
   ortalaması 1.56°, %95'lik dilimi 6.30°; farkın 10°'yi aştığı saat payı yalnızca %2.5.
   Sin/cos kodlamalarının korelasyonu 0.996 ve 0.997. Yani `WD2M_sin`/`WD2M_cos` öznitelik
   çifti, `WD10M` çiftine neredeyse hiçbir şey eklemiyor.
2. **`T2MDEW` bir ölçüm değil, bir formül.** Magnus bağıntısıyla `T2M` ve `RH2M`'den yeniden
   üretildiğinde r = **0.99919**, RMSE = **0.30 °C** (24 saat); gündüz alt kümesinde
   r = 0.99956, RMSE = 0.23 °C. Bu, ölçüm gürültüsü düzeyindedir.

**Öneri — öznitelik indirgeme arması.** 16 öznitelikten `WD2M_sin`, `WD2M_cos`, `WS2M` ve
`T2MDEW` çıkarılırsa geriye 12 öznitelik kalır ve kaybedilen bilgi ölçüm gürültüsü
düzeyindedir. Bu tek başına bir ablasyon armasını hak ediyor: LSTM'in öznitelik sayısı
girdi katmanının boyutunu belirlediği için 16 → 12 indirgemesi parametre sayısını gerçekten
düşürür.

**Uyarı.** Öznitelik setini değiştirmek mevcut tüm ledger satırlarını geçersiz kılar ve yeni
bir deney kimliği gerektirir. Kıyaslanabilirlik kuralları gereği bu, tek başına bir eksen
olarak koşulmalıdır.

---

## 7. İller arası farklılaşma: Rize ve Van, iki uç

### 7.1 Rize: ayrı bir iklim rejimi

Rize dört ilden farklı bir yerde durmuyor; **farklı bir dağılımda** duruyor.

| Ölçüm | Rize | Diğer dördü |
|---|---|---|
| Günlük toplam ışınım | 3.71 kWh/m²/gün | 4.68 – 5.00 |
| Günlük berraklık indeksi kt | **0.697** | 0.805 – 0.839 |
| Kapalı gün payı (kt < 0.3) | **%8.1** | %0.95 – 2.77 |
| Berrak gün payı | %55.2 | %73.0 – 81.4 |
| Günler arası CV | **0.566** | 0.436 – 0.489 |
| Günlük PACF gün 1 | **0.396** | 0.529 – 0.560 |
| Günlük ACF gün 30 | **0.070** | 0.187 – 0.250 |
| Klimatoloji gündüz RMSE | **132.8 W/m²** | 96.6 – 106.9 |
| Klimatoloji gündüz R² | **0.716** | 0.859 – 0.886 |

Rize'nin **en iyi mevsimi** (yaz, kt = 0.772) diğer illerin **kışına** yakın (0.679–0.750).
Yani mevsimsel bir fark değil, rejim farkı.

**Uyarı — havuzlanmış ortalama Rize'yi gömüyor.** Beş ilin havuzlanmış ortalaması, dört ilin
birbirine yakın değerleriyle Rize'yi 4'e 1 bastırır. Tam olarak bu yüzden metrik tablosu
`Aggregate_excl_Rize` satırını ayrıca taşır ve iller arası aktarım iddiasının katkısı bu satır
olmadan görünmez.

**Öneri.** Makalede Rize "zor il" olarak değil, **"ikinci rejim"** olarak tanıtılmalıdır.
Beş ilin iklim çeşitliliği iddiası ancak bu çerçevede doğrudur: dört il tek bir rejimin
varyasyonları, Rize tek başına bir ikinci rejim.

### 7.2 Van: en berrak, ama en uçlu

Van en yüksek günlük toplamı (5.00 kWh/m²/gün), en düşük kapalı gün payını (%0.95) ve en
düşük kış CV'sini (0.326) taşıyor — kışı bile öngörülebilir. Ayrıca rüzgâr yönünde tek
baskın yönlü il (§4.2).

**Uyarı — Van'ın 1216.7 W/m²'lik maksimumu fiziksel bir bulgu değildir.** Bu satır
(2020-02-17 15:00) kt = 3.29 değerine karşılık geliyor, yani ışınım o saatin berrak gökyüzü
referansının üç katından fazla. Bu bir ölçüm/geri-doldurma artefaktıdır. Van'ın yüksek rakım
ve kuru hava kombinasyonu gerçek bir olgudur ama **bu satıra dayandırılmamalıdır**.

### 7.3 Aşırı kt değerleri ve ayrıklaştırma

`CLRSKY > 20 W/m²` filtresiyle bakıldığında yeni veride gündüz saatlerinin **%2.91'i
kt > 1.0** veriyor. Eski dosyada bu oran %0.017 idi. Bu 170 katlık artış korkutucu görünüyor;
**tamamı ayrıklaştırma artefaktıdır.**

Kanıt doğrudan: eski dosyaya **yalnızca** MJ yuvarlamasını uygulayıp (CLRSKY'yi hiç
değiştirmeden) yeniden hesapladığımızda kt > 1.0 oranı %0.017'den **%2.645**'e çıkıyor — yani
yeni dosyanın %2.906'sını neredeyse birebir açıklıyor.

Aşımın marjinal olduğu da görülüyor: kt > 1.05 yalnızca 219 satır (%0.149) ve kt > 1.2 yalnızca
14 satır (%0.009). Yani kütle 1.0'ın hemen üstünde toplanıyor, yuvarlama eşiğinin bir adım
ötesinde.

**Uyarı.** kt'yi 1.0'da kırpan hiçbir işlem yapılmamıştır ve yapılmamalıdır; kırpma, fiziksel
olmayan bir düzeltme adı altında ayrıklaştırma gürültüsünü tek yöne itmek olurdu. kt tablolarını
okurken 1.0 civarındaki küçük aşımların anlamsız olduğu bilinmelidir.

**Uyarı.** kt > 1.05 veren 219 satırın 197'si, yani %90'ı, CLRSKY'nin yeniden inşa edildiği
son iki aylık pencerededir (§0.2). Bu pencerede kt'ye dayalı hiçbir ince analiz yapılmamalıdır.

---

## 8. Referans zemin: modelin aşması gereken sayılar

`persistence_baseline.csv`, üç naif referansı **modelin kendi kronolojik test penceresinde**
ve **aynı pencereleme ile** puanlar:

- **Kalıcılık:** 24 saat önceki değeri tekrar et.
- **Akıllı kalıcılık:** dünkü berraklığı ileri taşı, bugünün berrak gökyüzü referansıyla çarp:
  `ŷ(T) = kt(T−24s) × CLRSKY(T)`.
- **Klimatoloji:** (il, ay, saat) hücresinin eğitim satırlarındaki ortalaması.

Havuzlanmış sonuçlar:

| Referans | Kapsam | RMSE | MAE | R² |
|---|---|---|---|---|
| Kalıcılık | 24 saat | 86.9 | 36.8 | 0.902 |
| Akıllı kalıcılık | 24 saat | 83.7 | 33.7 | 0.909 |
| Klimatoloji | 24 saat | 78.3 | 38.7 | 0.920 |
| Kalıcılık | **gündüz** | 120.7 | 71.0 | 0.817 |
| Akıllı kalıcılık | **gündüz** | 116.2 | **65.0** | 0.830 |
| Klimatoloji | **gündüz** | **108.8** | 74.5 | **0.851** |

**LSTM'in bir sonuç sayılabilmesi için gündüz saatlerinde RMSE'de 108.8 W/m² ve R²'de 0.851'i
(klimatoloji) *ve* MAE'de 65.0 W/m²'yi (akıllı kalıcılık) aşması gerekir.** Tek bir metrikte
kazanmak yeterli değildir, çünkü şampiyon metriğe göre değişiyor.

**Uyarı — 24 saatlik R² değerleri makaleye girmemelidir.** Klimatoloji 24 saat üzerinde
R² = 0.920 veriyor. R² alt kümenin kendi varyansına göre normalize olduğu için gün/gece
salınımı bu sayıyı domine eder. **24 saatlik R²'nin 0.9'un üzerinde olması hiçbir şeyin
kanıtı değildir.** Aynı normalizasyon argümanı PINW için de geçerlidir.

**Uyarı — 24 saatlik kalıcılığı geçmek bir sonuç değildir.** 24 saat ilerisi bir tahminde
kalıcılık zaten günlük döngüyle hizalıdır, yani ücretsiz bir mevsim/geometri bilgisi taşır.
Kıyas klimatolojiye karşı yapılmalıdır.

**Uyarı — aralık metrikleri naif referanslar için tanımsızdır.** Tek bir determinist tahminin
aralık genişliği sıfırdır, dolayısıyla CP bir eşitlik testine dönüşür. Bu yüzden CP/PINW/MPIW/
CWC naif satırlarda `NaN`'dır; CRPS korunur çünkü orada tam olarak MAE'ye indirgenir.

---

## 9. Belirsizlik (UQ) katmanı için çıkarımlar

**(1) Hedef heteroskedastiktir ve varyans yapısı mevsimle ters yönde hareket eder.** §3.4:
kış CV'si yaz CV'sinin 1.8–3.8 katı. Sabit genişlikli bir tahmin aralığı kışın dar, yazın
geniş kalır. Konformal katmanın **mevsim eksenli** olması gerektiğinin veri tarafındaki
gerekçesi budur.

**(2) İller arası fark mevsimler arası farktan küçük değildir.** §7: Rize'nin klimatoloji
gündüz RMSE'si 132.8, Antalya'nın 96.6 — %37 fark. Skaler tek bir kalibrasyon katsayısının
yetmeyeceği buradan görülür.

**(3) Gece elemanları aralık metriklerini yapısal olarak şişirir.** `clamp_night_to_zero`
açıkken her gece elemanı gerçek değeri tam 0 olan `[0, 0]` aralığı alır, yani **tanım gereği**
kapsanır. Elemanların %48.6'sı gecedir; dolayısıyla 24 saatlik CP karışımının yaklaşık yarısı
model hiçbir şey yapmadan 1.0'dır. **Bir koşu önce gündüz CP ≈ 0.95'e göre yargılanmalıdır**,
sonra gündüz PINW/CWC/CRPS'e göre.

**(4) Kalibrasyon kümesinin kusuru yön değiştirdi.** Konformal katman doğrulama bölümünü
kalibrasyon kümesi olarak kullanıyor ve bu kümenin iki bilinen kusuru var: erken durdurma
zaten onu gördü, ve tüm takvimi kapsamıyor. **Yeni veriyle eksik aylar Nisan–Mayıs'tan
Haziran–Temmuz'a kaydı** (doğrulama penceresi 2024-08-12 → 2025-05-16). Bu daha kötü bir
durumdur: eksik olan iki ay artık yılın en yüksek ışınımlı ve en düşük değişkenlikli
aylarıdır, yani mevsim eksenli bir kalibrasyon ızgarasının en emin olması gereken hücreleri
hiç veri görmüyor.

**Öneri.** Mevsim eksenli konformal ızgara yeniden koşulmadan önce bu kaydırma
belgelenmelidir; `ABLATION.md` §8'in tüm bulguları eski kalibrasyon penceresi altında
ölçülmüştür ve otomatik olarak taşınmaz.

---

## 10. Sınırlılıklar ve makalede mutlaka belirtilmesi gerekenler

1. **Veri uydu kaynaklıdır, yer istasyonu değil.** NASA POWER, ışınımı uydu gözlemlerinden
   türetir. Yağış toplamları (§4.1) Rize ve Antalya'da bilinen biçimde düşük kalmaktadır.

2. **Hedef 2.78 W/m² adımlarla ayrıklaştırılmıştır** (§0.1). Metrikler üzerindeki etkisi
   ihmal edilebilir (sd 0.80 W/m²), ama kt'nin 1.0 civarındaki davranışını görünür biçimde
   bozar (§7.3).

3. **`CLRSKY_SFC_SW_DWN` yeniden inşa edilmiştir** (§0.2). %97.6'sı birebir, %2.4'ü
   klimatolojik. Gündüz maskesi bundan etkilenmez; kt'ye dayalı analizler kaydın son iki
   ayında birkaç yüzdelik payda hatası taşır.

4. **Berrak gökyüzü ışınımı saf geometri değildir** (§0.2). Makalede "hava durumu terimi
   içermez" ifadesi kullanılmamalıdır.

5. **Yalnızca beş il vardır ve dördü aynı rejimdedir** (§7.1). "İklim çeşitliliği" iddiası
   bu asimetriyle birlikte sunulmalıdır.

6. **Yıllar arası değişkenlik küçük ama sıfır değildir** (§3.5); Rize'de %10.3. Tek bir test
   yılından çıkan il bazlı farklar bu bandın içinde değerlendirilmelidir.

7. **Eski ledger satırları geçersizdir.** Farklı bir öznitelik seti (17 vs 16), farklı bir
   birim ve 61 gün daha kısa bir kayıt altında üretilmişlerdir. Yeniden koşulmaları ve **yeni
   kimlikler** almaları gerekir.

8. **Beş ilin haritası ve coğrafi/iklimsel farklarının yazılı paragrafı hâlâ eksiktir**;
   ikisi de dış coğrafi veri gerektiriyor.

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
| `daily_clearness_by_city.csv` | §1(1), §7.1 |
| `clearness_index_by_city.csv` | §7.1, §7.2 |
| `autocorrelation_clearness.csv` | §5.1, §5.2 |
| `ramp_stats_by_city.csv` | §5.3 |
| `daylight_block_structure.csv` | §5.4 |
| `persistence_baseline.csv` | §1(3), §7.1, §8 |
| `target_correlation_by_city.csv` | §6.1 |
| `correlation_pearson_*.csv`, `correlation_spearman_*.csv` | §6.2, §6.3 |
| `collinear_pairs.csv` | §6.3 |
| `wind_direction_circular_stats.csv` | §4.2 |

### Figürler (`outputs/eda/figures/`, PNG 300 dpi + vektör PDF)

| Dosya | Ne gösteriyor |
|---|---|
| `target_histogram` | §3.1'deki iki kütleli yapı |
| `seasonal_diurnal_profile` | §2.1, §3.3 — mevsime göre gün içi profil, yerel saat |
| `seasonal_dayofyear` | §3.4 — yılın günü boyunca günlük toplam |
| `monthly_boxplot_last12m_*`, `monthly_boxplot_all_years` | §3.4 |
| `month_year_surface_*`, `month_year_anomaly_panel` | §3.5 |
| `autocorrelation_hourly`, `autocorrelation_daily` | §5.1, §5.2 |
| `ramp_distribution` | §5.3 |
| `correlation_heatmap_*`, `target_correlation_panel` | §6.1 – §6.3 |
| `scatter_vs_target_*` | §4, §6.2 |
| `persistence_baseline` | §8 |
| `rize_comparison` | §7.1 |

### Bu belge için tablolar dışında hesaplananlar

Aşağıdakiler mevcut tablolarda bulunmadığından doğrudan `base_features.parquet` ve iki xlsx
üzerinden hesaplanmıştır. Makaleye girecekse `scripts/02_descriptive_analysis.py`'ye kalıcı
birer tablo olarak eklenmeleri önerilir; aksi hâlde izlenebilirlik kuralı ihlal edilmiş olur.

| Sonuç | Değer | Bölüm |
|---|---|---|
| Birim çevriminin doğrulanması | ortak 59.184 saatte maks. sapma 1.39 W/m², ortalama 0.70 | §0.1 |
| Yağışta çözünürlük kaybı | eskiden yağışlı görünen saatlerin %38.7'si artık tam sıfır | §0.1 |
| Berrak gökyüzünün hava terimi | Ankara 21 Haz 11:00: 952.5–1008.7 W/m² (2020–2025); >200 W/m² hücrelerde yıllar arası bağıl sd medyan %4.1, p90 %7.9 | §0.2 |
| Yeniden inşa doğruluğu (dışarıda bırakma) | bayrak hatası %0.000–0.082; ışıklı saatlerde MAE 24–31 W/m² (%6–8) | §0.2 |
| `WD2M` – `WD10M` fazlalığı | açı farkı medyan 0.30°, ort. 1.56°, p95 6.30°; sin/cos r = 0.996 / 0.997 | §0.3, §6.3 |
| Çiy noktasının Magnus ile yeniden üretimi | r = 0.99919, RMSE 0.30 °C (24 s); r = 0.99956, RMSE 0.23 °C (gündüz) | §1(6), §6.3 |
| Yağış kodlamalarının hedefle korelasyonu | tablo §4.1'de; gündüz sıfır payı %66.8 | §4.1 |
| Yağışın yıllık toplamı (birim teyidi) | Ankara 340, Konya 326, Van 343, Antalya 664, Rize 1399 mm/yıl | §4.1 |
| kt aşımının kaynağı | eski veriye yalnız yuvarlama uygulanınca kt>1 oranı %0.017 → %2.645 | §7.3 |
| kt uç değerleri | kt>1.05: 219 satır (%0.149), %90'ı yeniden inşa penceresinde; kt>1.2: 14 satır | §7.3 |
| Tepe saatleri (yerel güneş saati teyidi) | Konya 11.2406, Ankara 11.2409, Antalya 11.4107, Van 11.5751, Rize 11.9069 | §2.1 |
| Bölme sınırları ve doğrulama penceresinin eksik ayları | test 9.097 saat / 379 gün; doğrulamada Haziran ve Temmuz yok | §2, §9(4) |
| Yıllar arası değişkenlik | tablo §3.5'te | §3.5 |
