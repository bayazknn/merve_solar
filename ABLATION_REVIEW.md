# Ablasyon incelemesi — mimari hükmü ve alıntılanabilir bulgular

Bu belge `ABLATION.md`'nin bir eki değil, onun üzerine yazılmış bir **incelemedir**. İki soruyu
yanıtlar:

1. **Mimari nereye yakınsamalı** ve `arch_sweep_x` koşulmadan önce nesi değişmeli (§1–§5).
2. **Makalede hangi bulgu alıntılanabilir**, hangisi fazla iddia, hangisi savunulamayacağı için
   dışarıda bırakılmalı (§6–§8).

Mimari yarısı önce gelir çünkü karar bekleyen kısım odur.

`ABLATION.md` düzenlenmemiştir; bu belgenin hiçbir hükmü oradaki §1–§3'ün metnini geçersiz
kılmaz. §1'de bildirilen tek çelişki, `ABLATION.md`'de değil, mimari taramasının **henüz
yazılmamış** özet tablosundadır.

---

## 0. Doğrulama yöntemi ve kapsam

Aşağıdaki her sayı `outputs/experiments/<experiment_id>/metrics/results_summary.csv` ve
`results_by_horizon.csv` dosyalarından **yeniden hesaplanmıştır**; `outputs/experiments_ledger.csv`
yalnızca konfigürasyon eksenleri, `best_val_loss`, `training_time_sec` ve `device` için okunmuştur.
`best_epoch` değerleri kolların `log.txt` dosyalarından çıkarılmıştır. Hiçbir koşu çalıştırılmamış,
`outputs/` altında hiçbir dosya değiştirilmemiştir.

Bu incelemenin mimari yarısı **21 mimari kolu + 3 mevcut taban kolunu** kapsar:

| grup | kollar | doğruluk |
| --- | --- | --- |
| `arch_sweep` | `abl_arch_{h32x16, h128x64, h64x64x32, lookback48, lookback72, dropout02, dropout04}_s{42,43,44}` | `ABLATION_B1`, L1, MPS |
| taban (mevcut) | `abl_rize_all5_s{42,43,44}_l1` | aynı |
| tam doğruluk referansı | `abl_rize_all5_s{42,43,44}_full` | `ABLATION_FULL` ($B=8$), L1, MPS |

**Taban kollarının karşılaştırılabilirliği doğrulandı.** `abl_rize_all5_s*_l1` satırları
`hidden_sizes=[64,32]`, `lookback_hours=24`, `dropout_rate=0.3`, `n_bootstrap=1`,
`mc_dropout_passes=100`, `max_epochs=100`, `early_stop_patience=15`, `loss_function=mae`,
`device=mps`, `training_scope=global`, beş il — yani mimari taramasının kollarıyla **`best_val_loss`
sütunu dışında birebir aynı ayarlardadır.** `per_city_scaler=True` her iki tarafta da yazılıdır ama
`global` kapsamda hiç okunmaz (`experiment.py::_run_per_city_scope`, satır 357), dolayısıyla tüm
kollar aynı havuz ölçekleyicisini kullanır. **Sonuç: taban kolunun test metrikleri zaten
karşılaştırılabilir; `abl_arch_base_s*` yalnızca eksik `best_val_loss` değerini üretmek için
gereklidir, tabloyu geçerli kılmak için değil.**

Tek yapısal farklılık `lookback` kollarındadır: uzayan geriye bakış daha çok pencereyi bölme
sınırına takar, dolayısıyla gündüz eleman sayısı 546.130 (24 s) → 544.642 (48 s) → 543.154 (72 s)
olur. Fark %0,55'tir ve karşılaştırma **eleman-eleman aynı küme üzerinde değildir**; diğer beş eksen
için birebir aynıdır.

---

## 1. Önce düzeltme — mimari özet tablosu iki farklı istatistiği yan yana koyuyor

Bana verilen tabloda `best_val_loss` sütunu **üç tohumun ortalaması ± s.s.**, `test daylight RMSE`
ve `test daylight CP` sütunları ise **yalnızca tohum 42'nin** değeridir. Doğrulama: `[128,64]` için
0,12630 ± 0,00056 üç tohumun ortalamasıdır (0,126541 / 0,126703 / 0,125662 → 0,126302 ± 0,000557,
birebir), ama 89,25 tek başına `abl_arch_h128x64_s42` satırıdır; üç tohumun ortalaması **90,29**'dur.
Aynı karışım yedi kolun hepsinde vardır.

Üç tohumla yeniden hesaplanmış tablo (gündüz alt kümesi, `Aggregate` satırı — beş kol da aynı beş
ilde skorlandığı için K-1 burada bağlayıcı değil):

| konfigürasyon | `best_val_loss` ort ± s.s. | RMSE ort ± s.s. | (brief'teki s42) | MAE | R² | CP ort | MPIW | CRPS |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `[128,64]` | **0,12630 ± 0,00056** | **90,29 ± 2,21** | *(89,25)* | **61,13** | **0,8975** | 0,8949 | **309,9** | **46,47** |
| `dropout 0,2` | 0,12951 ± 0,00113 | 91,21 ± 3,10 | *(90,48)* | 62,92 | 0,8954 | 0,9120 | 322,4 | 46,73 |
| `[64,32]` (taban) | *(kayıtlı değil)* | **94,09 ± 0,85** | *(94,89)* | 68,75 | 0,8887 | 0,9547 | 408,3 | 50,48 |
| `lookback 72` | 0,14007 ± 0,00139 | 94,42 ± 2,57 | *(96,97)* | 68,36 | 0,8881 | 0,9475 | 410,3 | 50,98 |
| `lookback 48` | 0,13894 ± 0,00338 | 94,87 ± 1,11 | *(94,01)* | 67,74 | 0,8870 | 0,9495 | 409,5 | 50,86 |
| `[64,64,32]` | 0,14165 ± 0,00215 | 97,85 ± 1,81 | *(97,22)* | 72,06 | 0,8796 | 0,9640 | 417,1 | 51,90 |
| `dropout 0,4` | 0,15785 ± 0,00158 | 101,69 ± 0,39 | *(102,11)* | 77,32 | 0,8700 | 0,9744 | 488,1 | 56,49 |
| `[32,16]` | 0,17933 ± 0,00420 | 112,43 ± 1,60 | *(114,26)* | 87,65 | 0,8411 | 0,9791 | 516,2 | 61,18 |
| *referans:* `[64,32]` $B{=}8$ | 0,14470 | *92,45 ± 0,45* | — | *67,96* | *0,8930* | *0,9769* | *438,6* | *49,51* |
| *taban: iklimsel ortalama* | — | *106,86* | — | *73,38* | *0,8565* | — | — | — |

**Neyi değiştirir, neyi değiştirmez.**

- **Sıralama bir yerde değişiyor:** tek tohumla `lookback 48` (94,01) `lookback 72`'den (96,97)
  belirgin biçimde iyi görünüyordu; üç tohumla sıra terse dönüyor (94,87 vs 94,42). İki kolun
  farkı üç tohumda 0,45 W/m² ve kendi saçılımlarının (1,11 ve 2,57) çok altındadır. **"48, 72'den
  iyidir" cümlesi yazılamaz; yazılabilecek olan "geriye bakış uzatmanın ölçülebilir bir etkisi
  yoktur"tur** — ki §2.4'te gösterildiği gibi EDA da tam bunu öngörüyor.
- **Taban ile aradaki mesafe küçülüyor.** Tek tohumla taban 94,89, `lookback 48` 94,01 idi — yani
  geriye bakış uzatmak *iyileştiriyor* gibi görünüyordu. Üç tohumla taban 94,09, iki lookback kolu
  94,42 ve 94,87: her ikisi de tabandan **kötü**, ama fark yine saçılımın içinde.
- **Hükmün kendisi değişmiyor:** `[128,64]` en iyi, `[32,16]` en kötü, `[64,64,32]` iki katmanlı
  tabandan kötü, `dropout 0,4` kötü. Genişlik–derinlik–dropout okumaları ayakta.
- **Seçim kriteri sağlamlandı.** Yirmi bir mimari koşuda `best_val_loss` ile gündüz test RMSE'si
  arasındaki Spearman korelasyonu **0,935** ($p = 5{,}3\times10^{-10}$), Pearson 0,975. Konfigürasyon
  içinde, tohum düzeyinde bile ilişki pozitiftir (yedi konfigürasyonun dördünde $\rho = 1{,}0$,
  üçünde 0,5). **Doğrulama kaybı üzerinden seçim bu problemde işleyen bir seçicidir** ve bu, kendi
  başına raporlanmaya değer bir metodolojik doğrulamadır (§6, B-6).

**Öneri:** tabloyu `ABLATION.md`'ye taşırken tek tohum sütunu hiç yazılmasın; her hücre üç tohumun
ortalaması ± s.s. olsun ve tohum değerleri §2/§3'teki gibi ayrı bir sütunda verilsin.

---

## 2. Kapasite gerçekte ne satın alıyor — iki kırılım hükmü değiştiriyor

Toplulaştırılmış −3,80 W/m²'lik kazanç (`[64,32]` → `[128,64]`) tek başına yanıltıcıdır. İki
kırılım onu tanınmaz hâle getiriyor ve ikisi de fiziksel olarak yorumlanabilir.

### 2.1 Kapasite Rize'ye hiçbir şey vermiyor

Eşleştirilmiş il bazlı fark, gündüz RMSE, taban `[64,32]`'ye karşı, $n=3$ tohum:

| konfigürasyon | Rize | Ankara | Konya | Van | Antalya | `Aggregate` |
| --- | --- | --- | --- | --- | --- | --- |
| `[128,64]` | **−0,40** (p = 0,88; 2/3) | −4,08 (3/3) | −5,58 (3/3) | −3,49 (3/3) | −6,34 (p = 0,048; 3/3) | −3,80 (3/3) |
| `dropout 0,2` | **−0,97** (p = 0,25; 2/3) | −2,43 (2/3) | −2,63 (2/3) | −3,60 (3/3) | −5,37 (p = 0,022; 3/3) | −2,87 (2/3) |
| `lookback 72` | +0,69 (2/3) | +1,02 | +0,75 | +0,81 | −1,85 | +0,33 |
| `lookback 48` | +5,55 (p = 0,061) | +0,54 | +0,36 | −1,27 | −2,39 | +0,78 |
| `[64,64,32]` | +3,45 (p = 0,025) | +3,43 | +4,73 | +4,13 | +3,13 | +3,76 |
| `dropout 0,4` | +4,29 | +8,08 | +9,69 | +7,55 | +8,99 | +7,61 |
| `[32,16]` | +6,67 | +20,36 | +22,57 | +22,82 | +20,39 | +18,35 |

Kapasiteyi iki katına çıkarmak **dört Anadolu ilinde 3,5–6,3 W/m² kazandırıyor, Rize'de 0,40
W/m² — yani hiç.** Aynı asimetri `dropout 0,2`'de de vardır (Rize −0,97, Antalya −5,37) ve
CRPS'te de görünür: `[128,64]` CRPS'i Ankara'da 49,16 → 44,94, Antalya'da 48,24 → 42,12 çekerken
Rize'de 54,44 → 54,24, yani ölçülemez.

**Bunun neden böyle olduğu EDA'da yazılı.** İklimsel ortalama tabanı Rize'nin gündüz varyansının
yalnızca %71,8'ini açıklar; diğer dört ilde %86,8–89,6'sını (`outputs/eda/tables/persistence_baseline.csv`).
Yani Rize'de öğrenilecek hava artığı toplam varyansın ~%28'i, diğerlerinde ~%12'sidir — ama Rize'nin
günlük $k_t$ kısmi otokorelasyonu (PACF gecikme 1 gün) **0,405**, diğerlerinde 0,534–0,563
(`autocorrelation_clearness.csv`). Rize'de artık *büyük* ama *öngörülemez*. Model kapasitesi
yalnızca öngörülebilir sinyali sömürebilir.

**Makale için sonucu:** kapasite tavanı ile veri tavanı ayrı şeylerdir ve bu veri kümesinde
il-özgüdür. Bu, aynı zamanda **başlık bulgusunu koruyan** bir gözlemdir: Rize'deki havuzlama kazancı
(−2,70 W/m², 6/6 tohum) mimari büyütülerek elde edilemez, dolayısıyla o kazanç bir kapasite
artefaktı değildir. `ABLATION.md` §3.2'nin yanına yazılmaya değer.

Ters yöndeki uyarı da aynı ölçümdedir: **`[256,128]`'in Rize'yi iyileştirmesi beklenmemelidir.**
`[64,32]` → `[128,64]` geçişi Rize'de 0,40 W/m² verdiyse, bir sonraki basamağın daha fazlasını
vermesi için bir mekanizma yoktur.

### 2.2 Kazanç ufkun iki ucunda toplanıyor — ve tam da EDA'nın işaret ettiği iki gecikmede

`[128,64]` eksi `[64,32]`, gündüz RMSE, ufuk adımı başına (üç tohum ortalaması):

| ufuk adımı | 1 | 2 | 3 | 6 | 9 | 12 | 15 | 18 | 21 | 23 | 24 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fark (W/m²) | **−15,07** | −11,51 | −9,10 | −5,81 | −3,71 | −2,32 | **−0,57** | −1,83 | −2,27 | −4,51 | **−6,39** |

Eğri U biçimlidir: kazanç $h=1$'de 15,07 W/m², $h=15$'te 0,57 W/m², $h=24$'te yeniden 6,39 W/m².

Bu, EDA'nın otokorelasyon tablosuyla birebir örtüşüyor. `autocorrelation_clearness.csv`'de
öngörülebilir sinyal **iki** gecikmede toplanmıştır: saatlik PACF gecikme 1 ≈ 0,93–0,97 ve günlük
PACF gecikme 1 ≈ 0,41–0,56 (yani saatlik gecikme 24). Aradaki gecikmelerin kısmi katkısı 0,10'un
altına düşer. Ek kapasite tam olarak bu iki tepeyi sömürüyor ve aradaki düz bölgede hiçbir şey
yapmıyor.

**Bu, taramanın en yorumlanabilir sonucudur ve makalede bir paragrafı hak eder** (§6, B-3). Ayrıca
bir uyarı taşır: toplulaştırılmış RMSE'nin %40'a yakını $h \le 3$ adımlarından gelir ve orası
"gün-öncesi" tahmin değil, 1–3 saat ilerisidir. Makale `horizon_hours=24`'ü "24 saat ileri tahmin"
diye tanıttığı sürece bir hakem $h=1$ adımını sorar; doğru tanım **"1–24 saatlik profil
tahmini"**dir ve $h=24$ satırı ayrıca raporlanmalıdır ($B{=}8$ tabanında 103,36 W/m²,
`Aggregate` 92,45'e karşı).

### 2.3 Derinlik kolu temiz bir tek-eksen değişimi değil

`model.py`'de `hidden_sizes` üç şeyi birden yönetir. `[64,64,32]`, `[64,32]`'ye göre:

- LSTM katman sayısını 2 → **3** çıkarır,
- başlıktaki gizli Linear katmanı sayısını 1 → **2** çıkarır,
- **stokastik katman sayısını 3 → 5 çıkarır**: `nn.LSTM` dropout'u son katman dışında her katman
  çıkışına uygular, yani katman-arası uygulama 1 → 2 olur; buna `head_dropout` ve başlıktaki her
  gizli katmanın kendi `nn.Dropout`'u eklenir (1 → 2).

Yani "derinlik yardımcı olmuyor" hükmü, derinlik ile **MC-Dropout gürültü kaynağı sayısını**
karıştırmaktadır. `[64,64,32]`'nin daha geniş aralıkları (MPIW 417,1 vs 408,3) ve daha yüksek CP'si
(0,9640 vs 0,9547) bu ikinci etkinin doğrudan izidir. `[32,16]`, `[64,32]`, `[128,64]` üçlüsü ise
aynı sayıda dropout uygulamasına sahiptir; **genişlik kolu temiz, derinlik kolu değil.**

Makalede "derinlik yardımcı olmadı" yazılacaksa bunun bir dipnotu olmalıdır. Temiz bir derinlik
testi `hidden_sizes` yorumunu değiştirmeyi gerektirir (mevcut ledger'ın tamamını yetim bırakır,
CLAUDE.md) — bu yüzden **önerim testi yapmamak, iddiayı zayıflatmaktır**: "iki katmanlı LSTM
yeterlidir; üç katmanlı bir varyant iyileştirme sağlamamıştır" denir ve overloading dipnotta
açıklanır.

### 2.4 Geriye bakış: hüküm doğru, gerekçesi EDA'dan gelmeli

Üç tohumla `lookback 48` ve `72` tabandan sırasıyla +0,78 ve +0,33 W/m² kötüdür — yani **fark
yoktur** ($p = 0{,}56$ ve $0{,}77$). `best_val_loss` sıralaması ise nettir: 0,13894 ve 0,14007'ye
karşı taban... kayıtlı değil, ama `[128,64]`'ün 0,12630'u ile `[64,64,32]`'nin 0,14165'i arasında
kalması beklenir.

Asıl gerekçe EDA'dadır ve **ölçümden daha güçlüdür**: günlük $k_t$ üzerinde AR($p$) uyumunun
örneklem-içi R²'si 24 s → 48 s geçişinde yalnızca **+0,007…+0,010**, 24 s → 72 s geçişinde
+0,016…+0,019 artar; Rize'de 1 günden 7 güne toplam kazanç **+0,006**'dır
(`autocorrelation_clearness.csv` üzerinden türetilmiştir). İkinci günün kısmi korelasyonu
0,006–0,12 bandındadır. **`lookback_hours=24` savunulabilir ve savunması otokorelasyon tablosuyla
yapılmalıdır, taramayla değil** — tarama yalnızca "beklendiği gibi fark çıkmadı" der ve o, tek
başına, negatif sonuç olarak zayıftır.

Uyarı: bu türetim (`AR(p)` R² tablosu) `outputs/eda/tables/` altında **yoktur**; alıntılanacaksa
önce `scripts/02_descriptive_analysis.py`'ye eklenip üretilmelidir (izlenebilirlik kuralı).

### 2.5 `best_epoch` taramanın ne ölçtüğünü değiştiriyor

Bana verilen "erken durdurma en iyi epoğu 3–9'da seçiyor, koşu 19–25 sürüyor" ifadesi
**`ABLATION.md` T-14'ten, yani $B=8$ tam doğruluk koşusundan** gelmektedir. Mimari taramasında
dağılım çok daha geniştir (`log.txt`'lerden okundu):

| konfigürasyon | `best_epoch` (s42/s43/s44) | koşulan epok |
| --- | --- | --- |
| `[128,64]` | **3 / 7 / 3** | 19 / 23 / 19 |
| `[64,64,32]` | 10 / 4 / 25 | 26 / 20 / 41 |
| `dropout 0,2` | 8 / 4 / 19 | 24 / 20 / 35 |
| `dropout 0,4` | 7 / 19 / 17 | 23 / 35 / 33 |
| `[32,16]` | 12 / 7 / 5 | 28 / 23 / 21 |
| `lookback 48` | **15 / 15 / 14** | 31 / 31 / 30 |
| `lookback 72` | 16 / 4 / 3 | 32 / 20 / 19 |

Üç okuma çıkıyor ve üçü de kapasite hükmünü nitelendiriyor:

1. **Kollar eşit yakınsamamıştır.** `[128,64]` optimumuna ortalama 4,3 epokta ulaşıyor,
   `lookback 48` 14,7 epokta. Tarama "hangi mimari en iyidir"i değil, **"lr = $10^{-3}$, toplu
   boyut 128 altında hangi mimari en hızlı iyi bir çözüme varıyor"u** ölçmektedir.
2. **Öğrenme oranı çizelgesi hiçbir zaman devreye girmiyor.** `lr_reduce_patience=7` olduğuna
   göre ilk LR düşüşü `best_epoch + 7`'de, yani `[128,64]` için 10. epokta gerçekleşir — model
   çoktan tepe noktasını geçmiştir. **Hiçbir kol düşük öğrenme oranında bir iyileştirme evresi
   görmemiştir.** 218.745 pencere / 128 = epok başına 1.709 adım; `[128,64]` optimumuna ~5.100
   adımda varıp orada bırakılıyor.
3. **Epok gürültüsü çok yüksek.** `dropout 0,2` için 8/4/19, `[64,64,32]` için 10/4/25. Doğrulama
   eğrisi bu kadar gürültülüyse öğrenme oranı toplu boyuta göre yüksektir.

**Kapasite sonucunu nasıl okumalı:** genişliğin yardım ettiği doğru, ama ölçülen etkinin bir
bölümü "büyük model az adımda daha iyi bir noktaya varır"dır. Bu, makalede sorun değildir —
eğitim protokolü sabittir ve öyle beyan edilir. Sorun **ileriye dönüktür**: `[256,128]` bu
protokolde muhtemelen 1–2. epokta tepe yapacak ve fiilen eğitilmemiş bir model olarak
skorlanacaktır. **Kapasite basamağı öğrenme oranı ekseniyle birlikte çıkılmalıdır, tek başına
değil** (§5).

---

## 3. Doğruluk–kapsama gerilimi: ölçülmüş, ve sanıldığından daha katı

### 3.1 Bu tasarımda kapsama, aralık genişliğinin saf bir fonksiyonudur

Sekiz $B=1$ konfigürasyonunun her biri için il bazlı (MPIW, CP) çiftleri alınıp
$\mathrm{CP} = a + b\ln(\mathrm{MPIW})$ uyumlandığında:

| il | uyum R² | eğim $b$ | en büyük artık |
| --- | --- | --- | --- |
| Rize | **0,963** | 0,254 | +0,0139 (`[64,64,32]`) |
| Ankara | 0,941 | 0,163 | +0,0125 |
| Konya | 0,931 | 0,148 | +0,0143 |
| Van | 0,927 | 0,136 | +0,0090 |
| Antalya | 0,936 | 0,109 | +0,0072 |

Yedi farklı mimari müdahale — genişlik, derinlik, geriye bakış, dropout — **tek bir eğri üzerine
düşüyor**, artıklar 0,014'ü aşmıyor. Yani:

> **Bu tasarımda kapsama yalnızca genişlikle satın alınabilir ve hiçbir mimari seçim
> kapsama–genişlik sınırını kaydırmaz.**

Bu, "dropout iki iş birden yapıyor" sezgisinin ölçülmüş ve **daha güçlü** bir versiyonudur: iki
işi yapan yalnızca dropout değildir, taranan **her** eksen aynı tek gizli değişkeni (etkin
düzenlileştirme gücü) oynatmaktadır. Nokta doğruluğunu iyileştiren her müdahale aralığı daraltır.

**Ama nokta doğruluğu genişliğin saf fonksiyonu değildir.** Aynı sekiz nokta için
$\mathrm{RMSE} = a + b\ln(\mathrm{MPIW})$ uyumu yalnızca R² = 0,75 verir ve `[128,64]` hem
**en düşük RMSE'ye hem de en dar aralığa** sahiptir (90,29 / 309,9) — yani $B=1$ kollarının
tamamını (RMSE, MPIW) düzleminde **Pareto-domine eder**. Sınırı hareket ettiren tek ölçülmüş
mekanizma bu tarama içinde yoktur; **§3.4'te.**

### 3.2 Yapısal kusur I — aralık genişliği ille eşleşmiyor

Gauss varsayımı altında %95'lik bir aralığın genişliği ≈ 3,92 σ olmalıdır, yani MPIW/RMSE oranı
her ilde ~3,9 civarında olmalıdır. Ölçülen (gündüz, üç tohum):

| konfigürasyon | Rize | Ankara | Konya | Van | Antalya |
| --- | --- | --- | --- | --- | --- |
| `[128,64]` | **2,39** | 3,59 | 3,79 | 3,70 | 4,08 |
| `dropout 0,2` | **2,54** | 3,67 | 3,77 | 3,84 | 4,17 |
| `[64,32]` $B{=}1$ | **3,18** | 4,52 | 4,65 | 4,71 | 4,94 |
| `[64,32]` $B{=}8$ | **3,50** | 4,93 | 5,06 | 5,14 | 5,43 |
| `[32,16]` | **3,77** | 4,69 | 4,72 | 4,72 | 5,09 |

Sekiz konfigürasyonun **hepsinde** Rize'nin oranı diğer dördünkinden 1,2–1,4 puan düşüktür. Bu bir
mimari etkisi değil, **sabit bir yapısal yanlılıktır**: MC-Dropout yayılımı modelin çıktı
büyüklüğüyle ölçekleniyor ve Rize beş ilin en düşük ortalamalı ilidir (gündüz hedef ortalaması
300,4 W/m², diğerleri 377–405; `descriptive_stats_by_city_daylight.csv`) — ama en yüksek hataya
sahip olandır (106–113 W/m², diğerleri 81–92). **En dar aralığı, en geniş aralığa ihtiyaç duyan il
alıyor.**

Bu, `ABLATION.md` §3.5'in "bootstrap bileşeni tam da eksik kapsanan ili düzeltti" cümlesini
nitelendiriyor: $B{=}8$ Rize'yi 0,910 → 0,9521'e taşıdı ama oranı 3,18 → 3,50 yaptı, hâlâ 3,92'nin
altında; aynı hamle diğer dördünü 4,5–4,9 → 4,9–5,4'e, yani hedefin **daha da uzağına** itti.
$B{=}8$ kalibrasyonu çözmedi; **ortalamada doğru görünen bir noktaya denk getirdi.**

### 3.3 Yapısal kusur II — aralık genişliği ufukla ölçeklenmiyor *(en güçlü ve en giderilebilir bulgu)*

`[64,32]` $B{=}8$, gündüz, ufuk adımı başına (üç tohum ortalaması):

| ufuk adımı | 1 | 3 | 6 | 12 | 18 | 24 | oran |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MPIW | 426,4 | 429,2 | 436,1 | 444,3 | 444,7 | 426,8 | **×1,04** |
| RMSE | 66,6 | 74,8 | 89,3 | 95,1 | 97,3 | 103,4 | **×1,55** |
| MPIW/RMSE | 6,40 | 5,74 | 4,89 | 4,67 | 4,57 | **4,13** | — |
| CP | 0,9948 | 0,9870 | 0,9792 | 0,9771 | 0,9751 | **0,9530** | — |

`[128,64]` $B{=}1$'de aynı yapı daha da keskindir: MPIW ×1,05, RMSE ×1,78, CP 0,9569 → 0,8719.

**Yirmi dört saatlik ufuk boyunca gerçek hata %55–78 büyürken öngörü aralığı %4–5 büyüyor.**
Doğrusal bir tahmin başlığından ($h$ boyutlu tek bir `nn.Linear`) beklenmesi gereken davranış budur:
MC-Dropout gürültüsü başlığın 24 çıkışına neredeyse aynı ölçekte yansır, çünkü gecikmeye göre
ölçeklenmesini sağlayacak hiçbir mekanizma yoktur.

Sonuç: aralıklar kısa gecikmede ağır biçimde fazla kapsıyor (CP 0,995), uzun gecikmede yetersiz
kapsıyor (0,953 — ve `[128,64]`'te 0,872). `ABLATION.md`'nin `Aggregate` CP 0,977 rakamı **üç ayrı
karşıt hatanın** ortalamasıdır: il (§3.2), ufuk (§3.3) ve mevsim (EDA §8, göreli yayılım
il × mevsim × saat ızgarasında ~8,5 kat değişiyor).

Bu bulgu `ABLATION.md`'de **hiç yoktur** ve bence taramadan çıkan en değerli tek şeydir; §6'da B-1.

### 3.4 `[128,64]`'ün $B{=}8$'de nereye düşeceği — konjektür kısmen doğru, sonucu ters

Konjektürü ölçülmüş büyüklüklerle test ettim. Taban kolunun $B{=}1 \to B{=}8$ geçişinde MPIW
çarpanı il başına 1,066–1,091'dir. §3.1'in il başına eğimi bu çarpana uygulanıp, taban kolunun
kendi gözlenen CP sıçramasıyla kalibre edilerek (bootstrap, saf genişlik etkisinin ötesinde
Rize'de +0,017, diğerlerinde +0,007…+0,010 ek kapsama getiriyor — dağılımın *şeklini* de
düzelttiğinin ölçüsü):

| il | `[128,64]` $B{=}1$ CP | öngörülen $B{=}8$ CP |
| --- | --- | --- |
| **Rize** | 0,8204 | **≈ 0,86** |
| Ankara | 0,9017 | ≈ 0,92 |
| Konya | 0,9092 | ≈ 0,93 |
| Van | 0,9141 | ≈ 0,93 |
| Antalya | 0,9293 | ≈ 0,94 |
| `Aggregate` | 0,8949 | ≈ 0,92 |

**"`Aggregate` 0,92 civarına düşer" öngörüsü doğru. "Bu, kalibrasyonu iyileştirir" sonucu yanlış.**
Bugün il bazlı sapma 0,9521–0,9842 (genişlik 0,032, tamamı hedefin üstünde); `[128,64]` altında
0,86–0,94 (genişlik 0,08, tamamı hedefin altında) olur. Hafif ve tek yönlü bir fazla kapsama,
**ağır ve heterojen bir yetersiz kapsamaya** dönüşür — üstelik en kötü nokta, makalenin başlık
iddiasının skorlandığı il olan Rize'dir. Hakem karşısında savunulacak sayı 0,86 değildir.

*Sınır:* bu bir dışdeğerlemedir. Yedi konfigürasyonun (MPIW, CP) eğrisi il başına R² ≥ 0,93 ile
uyuyor ve kalibrasyon taban kolunun kendi ölçülmüş sıçramasıyla yapıldı, ama `[128,64]` $B{=}8$'de
hiç koşulmadı. §5'te bunun ölçülmesi öneriliyor.

### 3.5 İki işi ayırmanın ilkeli yolu — ve tasarımda zaten var olan ikinci düğme

Soru "dropout iki iş mi yapıyor" biçiminde soruldu. Ölçüm daha ağır bir yanıt veriyor: **taranan
tüm eksenler tek bir işi yapıyor** (§3.1). Ama havuzlanan dağılım $\mathcal{P} = B \cdot T$ iki
bileşenden oluşur ve bunlardan **biri nokta modelinden bağımsızdır**:

| bileşen | genişliği belirleyen | nokta doğruluğuna bağlı mı |
| --- | --- | --- |
| MC-Dropout ($T$) | `dropout_rate` | **evet** — düzenlileştirmenin kendisi |
| Bootstrap ($B$) | `n_bootstrap`, `bootstrap_block_length` | **hayır** — her replika aynı biçimde eğitilir |

Ve bootstrap bileşeninin ölçülmüş etkisi **bedava genişliktir**: $B{=}1 \to B{=}8$ geçişi MPIW'i
%7,4 artırırken RMSE'yi 94,09 → 92,45 **düşürdü** ve CRPS'i 50,48 → 49,51 iyileştirdi. (RMSE ~
ln MPIW uyumunda taban $B{=}8$ noktası artığı −7,5 W/m²'dir; sekiz konfigürasyonun en büyük sapması,
ve tek olumlu yönde olanı.) Yani projede ölçülmüş tek gerçek **sınır kaydırıcı** budur.

**Öneri sırası, ucuzdan pahalıya:**

1. **`bootstrap_block_length`'i bir eksen olarak tara.** Bu, mevcut kodda dropout'tan bağımsız
   çalışan tek genişlik düğmesidir ve hiç dokunulmamıştır (168 s). Blok kısaldıkça replikalar
   çeşitlenir → bootstrap bileşeni genişler; blok uzadıkça daralır. **Kod değişikliği sıfır**,
   ledger'da zaten sütun var. Bu, "iki işi ayırma"nın sıfır maliyetli versiyonudur.
2. **Doğrulama kümesi üzerinde bölünmüş-conformal ölçekleme, (il × ufuk adımı) hücresi başına.**
   §3.2 ve §3.3'ün ikisini birden kapatan tek müdahale. Her hücre için doğrulama artıklarından bir
   $\lambda_{c,h}$ ölçek katsayısı kestirilir, test aralığı $\lambda$ ile çarpılır. Bu, nominal
   %95'i tanım gereği tutturur ve **fazla geniş olan hücreleri daraltır**: §3.1'in toplulaştırılmış
   eğimiyle (~0,15) hesaplandığında, `[64,32]` $B{=}8$'in 0,977'den 0,950'ye inmesi MPIW'i
   438,6 → **≈ 366**, yani **%16 daraltır** — PINW/CWC tablosunda büyük bir kazanç, ve CP hedefte.
   *Maliyeti:* doğrulama kümesi üzerinde de MC-Dropout geçişi gerekir (`experiment.py` bugün
   yalnızca `splits["test"]` üzerinde tahmin üretiyor, satır 257). Ölçek katsayısı bir skalerdir,
   yüzdelik CI değil; doğrulamada $T = 20$ yeter. Ek maliyet tam doğrulukta koşu başına **%5'in
   altında.**
3. **Heteroskedastik başlık (σ kestiren ikinci çıkış ya da kuantil başlıklar).** Fiziksel gerekçesi
   EDA'da güçlüdür: koşullu yayılım bağıl nemden doğrudan öngörülebilir (RH > %80'de gözlenen
   ışınım ~600 W/m² ile sınırlanıyor, RH < %40'ta 0–1000 aralığının tamamı doluyor; `EDA.md` §5.2a)
   ve il × mevsim × saat ızgarasında ~8,5 kat değişiyor. Bu, aleatorik terimi de ekler.
   *Maliyeti:* `model.py`, `train.py`, `metrics.py`'de gerçek bir değişiklik; kayıp fonksiyonu
   değişir, dolayısıyla **L1 seçimi yeniden sınanmalıdır** ve tüm ledger satırları yetim kalır.
   Bu makale için değil, bir sonraki için.

**Hükmüm:** (1) ve (2) yapılmalı, (3) yapılmamalı. (2), `METHODOLOGY_REVIEW.md` K3'ün "conformal
katman" önerisini — orada "genişletme" olarak düşünülüyordu — **daraltma** olarak geri getirir ve
§3.5'in "kalan iş daraltmadır" cümlesiyle tam uyumludur.

---

## 4. Taranmamış eksenler — hangisi gerçekten önemli

Verilen aday listesi için, ölçümden ve EDA'dan gerekçelendirilmiş sıralama:

**1. `learning_rate` (ve LR çizelgesi) — açık ara birinci.**
Gerekçe folklor değil, günlüklerdedir (§2.5): kazanan konfigürasyon optimumuna **3. epokta**
varıyor, `lr_reduce_patience=7` ilk LR düşüşünü ancak 10. epokta tetikliyor, yani **hiçbir kol
düşük öğrenme oranında bir iyileştirme evresi görmedi.** `best_epoch`'un tohumlar arası saçılımı
(4 ile 25 arası) doğrulama eğrisinin gürültülü olduğunu, yani lr'nin toplu boyuta göre yüksek
olduğunu söylüyor. Bu, hem nokta doğruluğunda en büyük kullanılmamış marjdır hem de kapasite
basamağının önkoşuludur: `[256,128]` mevcut protokolde 1–2. epokta durur.

**2. `bootstrap_block_length` — ikinci, çünkü aradığınız ayrımı yapan tek mevcut eksen o.**
§3.5. Ayrıca bir yan sorusu vardır ki makale için önemlidir: 168 saat (bir hafta) seçimi
gerekçelendirilmemiştir, oysa EDA'nın kısmi otokorelasyonu 2 günde 0,10'a düşüyor
(`autocorrelation_clearness.csv`). Blok, korelasyon ölçeğinin ~7 katı seçilmiş durumda; bu
replikaları gereğinden fazla birbirine benzetiyor olabilir, yani bootstrap bileşeni **olduğundan
dar** olabilir. Bedava genişlik burada duruyor olabilir.

**3. Başlığın yapısı — üçüncü, ama tek başına bir "iyileştirme" olarak değil.**
Tek bir `nn.Linear(h → 24)` başlığı §3.3'ün doğrudan nedenidir. Ufka duyarlı bir genişlik ancak
başlık değişirse **mimariden** gelebilir (ufuk başına ayrı dropout, ya da bir çözücü). Ancak
conformal ölçekleme (§3.5-2) aynı sonucu kodun onda biriyle verir; başlığı değiştirmeyi
**önermiyorum**, yalnızca §3.3'ün nedenini makalede doğru adlandırmayı öneriyorum.

**4. `city_embedding_dim` — dördüncü; makul ama beklenen etkisi küçük.**
EDA lehte ve aleyhte kanıt veriyor. Lehte: iller **hava anomalisinde** üç kümeye ayrılıyor
(günlük $k_t$ anomali korelasyonu Ankara–Konya 0,670, Rize–Van 0,339, Antalya–Rize **−0,056**) ve
gömme ayrıca yükseklik kodu (`PS` iller arası s.s. 6,72 kPa, il içi 0,40–0,52 kPa) ile ile özgü bir
rüzgâr yönü döndürmesi taşımak zorunda — bu, 4 boyutu sınırın tam üstüne koyuyor. Aleyhte: iller
**neyin ışınımı yordadığı konusunda hemfikirdir** (hedef–yordayıcı korelasyonlarının iller arası
aralığı bağıl nemde yalnızca 0,029) ve günlük profil şekli hizalandığında neredeyse ortaktır
(Ankara–Rize farkı 0,178 → enerji ağırlık merkezine hizalandığında **0,052**); yani gömmenin
taşıması gereken şey büyük ölçüde bir seviye ve bir faz kaymasıdır. Dahası §2.1 gösteriyor ki iller
arası başarım farkı kimlik kodlamasından değil **öngörülebilirlikten** geliyor. Bir 2/4/8 taraması
yapılabilir ama önce **`experiment.py::LEDGER_COLUMNS`'a eklenmelidir** (bugün ledger'da yok, kollar
ayırt edilemez).

**5. `batch_size` — beşinci; lr ekseninin bir kopyası.**
128'de epok başına 1.709 adım var. Toplu boyutu değiştirmek, sabit epok sayısında etkin lr'yi
değiştirmekten ibarettir; ayrı bir eksen olarak taranması ölçüm bütçesinin israfıdır. lr taranırsa
bu eksen kapanır.

**6. `nonneg_penalty_weight` — sonuncu, ve muhtemelen ölçülemez.**
`clamp_night_to_zero=True` gece saatlerini zaten kesin sıfırlıyor; ceza yalnızca gündüz negatif
tahminlerini etkiler, onlar da nadirdir. Taramaya değmez. (Tek ilginç yan soru: ceza L1 kaybıyla
birlikte MC-Dropout yayılımını alttan kırpıyor olabilir, bu da §3.2'nin Rize yanlılığına katkı
yapabilir — ama bu bir hipotezdir, ölçülmemiştir.)

---

## 5. Somut öneri — `arch_sweep_x` koşulmadan önce

### 5.1 Beyan edilmiş iki koşu hakkında

- **`abl_arch_base_s{42,43,44}` — KOŞULSUN, ama gerekçesi düzeltilsin.** `abl_rize_all5_s*_l1`
  satırları test metriklerinde **zaten karşılaştırılabilirdir** (§0'da doğrulandı: on üç
  konfigürasyon alanının hepsi aynı). Bu koşunun tek çıktısı eksik `best_val_loss`'tur — ve
  §1'de gösterildiği gibi seçici olarak `best_val_loss` çalışıyor, dolayısıyla değeri gerçektir.
  Ayrıca bedava bir determinizm kontrolüdür. **Maliyet ≈ 17 dk. Değişiklik gerekmiyor.**
- **`abl_arch_h256x128_s{42,43,44}` — KOŞULSUN, ama tek başına değil.** Basamak henüz dönmedi,
  bu doğru. Ama üç ölçüm bu basamağın düz çıkacağını söylüyor: (a) `[128,64]` zaten 219.244
  parametre taşıyor ve EDA'nın bağımsız gün-bloğu sayısı havuzda ~9.100'dür (stride = 1 nedeniyle
  218.745 pencere bağımsız değildir), (b) `[128,64]` optimumuna 3. epokta varıyor, yani
  optimizasyon zaten bağlayıcı, (c) `[256,128]` 848.044 parametredir — bağımsız blok başına 93
  parametre. **Öneri: aynı grupta bir de `abl_arch_h256x128_lr3e4_s{42,43,44}` koşulsun**
  (`learning_rate=3e-4`), yoksa basamağın düz çıkması durumunda "kapasite bitti mi, optimizasyon mu
  yetmedi" ayrımı yapılamaz.

### 5.2 Gruba eklenmesini önerdiğim üç kol (öncelik sırasıyla)

| # | id öneri | değişen | neden | maliyet (3 tohum) |
| --- | --- | --- | --- | --- |
| **A** | `abl_arch_h128x64_drop04_s{42,43,44}` | `hidden_sizes=[128,64]` **ve** `dropout_rate=0.4` | Bilinçli tek istisna: iki eksen birlikte. §3.1 sınırın tek boyutlu olduğunu (MPIW, CP) düzleminde gösterdi ama (RMSE, MPIW) düzleminde göstermedi. Bu kol, "kapasiteyi büyütüp düzenlileştirmeyi artırarak aynı genişlikte daha doğru bir model" elde edilip edilemeyeceğini doğrudan sorar — yani sınırın kaydırılıp kaydırılamayacağını. **Sonuç ne çıkarsa çıksın alıntılanabilir.** | ≈ 25 dk |
| **B** | `abl_arch_lr3e4_s{42,43,44}` | `learning_rate=3e-4`, taban mimarisinde | §2.5 ve §4-1. Tek eksen, taban mimarisinde, dolayısıyla ledger'da temiz. `best_epoch`'un 3'ten uzaklaşması beklenir; uzaklaşmazsa lr hipotezi ölür ve bu da bir sonuçtur. **`learning_rate` ledger'da zaten yok — önce `LEDGER_COLUMNS`'a eklenmeli** (`ABLATION.md` §A-2). | ≈ 20 dk |
| **C** | `abl_arch_h128x64_full_s{42,43,44}` | kazanan mimari, $B=8$ | §3.4'ün dışdeğerlemesini ölçüme çevirir. Mimari kararı, makalenin sayılarının üretildiği doğrulukta verilmelidir; $B=1$'de seçip $B=8$'de raporlamak §3.2–§3.4'ün gösterdiği gibi güvenli değildir. | ≈ 2,0 sa |

Ölçülmüş birim maliyetler (MPS, `training_time_sec` ortalaması, 5 il, $B=1$): taban 337 s,
`[128,64]` 466 s, `[32,16]` 227 s, `lookback 72` 701 s. `[256,128]` için LSTM maliyeti gizli boyutun
karesiyle büyüdüğünden ≈ 800–900 s/koşu, üç tohum ≈ 45 dk beklenir. $B=8$ tam doğruluk kolu
2.337 s'dir (ölçülmüş).

**Toplam önerilen ek iş: A + B + `h256x128` + `h256x128_lr3e4` ≈ 2,3 saat; C ile birlikte ≈ 4,3
saat.** `arch_sweep_x`'in beyan edilmiş hâli tek başına ≈ 1,0 saattir.

### 5.3 Yakınsanması önerilen konfigürasyon

Bugünkü kanıtla, **A ve B koşulmadan** verilecek karar:

```
hidden_sizes      = [128, 64]      # genişlik; temiz eksen, 3/3 tohumda kazanıyor
lookback_hours    = 24             # değiştirilmesin; gerekçe EDA'nın PACF'i, tarama değil
dropout_rate      = 0.3            # DÜŞÜRÜLMESİN — §5.4
loss_function     = "mae"          # yerleşik
n_bootstrap       = 8              # tek ölçülmüş sınır kaydırıcı; pazarlık konusu değil
+ (il × ufuk) conformal ölçekleme  # §3.5-2; aralık iddiası ancak bununla yayımlanabilir
```

Bu, `[64,32]`+$B{=}8$'e göre toplulaştırılmış gündüz RMSE'de ~2–3 W/m² kazanç ve — conformal
katman olmadan — Rize'de 0,86 civarında bir CP demektir. **Conformal katman olmadan `[128,64]`'e
geçilmemelidir.** İkisi tek bir karardır, iki ayrı karar değil.

### 5.4 Ne koşulmamalı

- **`dropout_rate` daha da düşürülmemeli.** `dropout 0,2`, `[128,64]`'ten daha kötü nokta doğruluğu
  (91,21 vs 90,29) ve daha kötü CRPS (46,73 vs 46,47) verirken kapsamayı da bozuyor — yani
  dominant değil, sadece daha az kalibre. Dahası dropout MC-Dropout'un **tek** gürültü kaynağıdır
  (proje değişmezi); 0,2'ye inmek elinizdeki tek belirsizlik düğmesini küçültür.
- **Çapraz çarpım taraması yapılmamalı.** `experiment_grid.py`'nin gerekçesi doğrudur; §5.2-A tek
  bilinçli istisnadır ve neden istisna olduğu (sınırın kaydırılabilirliği) yazılıdır.
- **`hidden_sizes` yorumu değiştirilmemeli.** Temiz bir derinlik testi için cazip ama tüm ledger'ı
  yetim bırakır (CLAUDE.md); §2.3'teki dipnot çözümü yeterlidir.
- **`early_stop_patience` bu tarama bitene kadar 15'te kalmalı.** `experiment_grid.py`'nin bu
  gerekçesi doğrudur ve §2.5 onu güçlendirir: sabır düşürülürse kollar farklı sayıda LR rejimi
  görür ve karşılaştırma bozulur. Kazanan seçildikten *sonra* kendi tek-eksen değişimi olarak
  düşürülmeli — duvar saatinin ~%60'ını geri verir.
