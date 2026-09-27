# `main_methodology.md` Denetim Raporu

**Tarih:** 2026-08-28
**Denetlenen belge:** `main_methodology.md` (831 satır)
**Karşılaştırma temeli:** git `main @ 7106709`; `src/merve_solar/*.py`, `configs/experiment_grid.py`,
`scripts/*.py`, `tests/*.py`; `outputs/processed/base_features.parquet` (295.920 satır);
`SolarData_Merve_All(16July).xlsx` (Ankara sayfası ham doğrulama); `outputs/experiments_ledger.csv`
(5 satır). Tüm sayısal iddialar gerçek veri/kod üzerinde çalıştırılan hesaplarla kontrol edilmiştir.

---

## Özet — en kritik bulgular

1. **§9 mimari şeması hâlâ F=18 dönemine ait:** LSTM girdi boyutu belgede 22, gerçekte **21** (17+4).
2. **Parametre sayısı yanlış:** belge 58.700 diyor; gerçek **58.444**. 58.700, tam olarak F=18
   konfigürasyonunun sayısıdır (ampirik olarak doğrulandı).
3. **Belge, mevcut tüm koşularda CP ≈ 0,67 (hedef 0,95) olduğunu hiçbir yerde söylemiyor**;
   §16.5 bunu "CP hedeften saparsa" diye varsayımsal anlatıyor — ledger'daki dört tamamlanmış
   koşunun dördü de 0,667–0,677 aralığında.
4. **"Test kümesi tam olarak 369 gün" iddiası yanlış:** test dilimi 8.878 saat =
   **369 gün 22 saat (≈370 gün)**.
5. **§15 taslak paragrafta blok uzunluğu birimi yanlış** ("168 saat"); kodda blok uzunluğu
   168 **penceredir** ve §11.2 ile çelişiyor.
6. **Tam-doğruluklu (B=8, T=100) hiçbir koşu tamamlanmamıştır** (`config_002_default_full` boş);
   belgenin süre iddiası ve sonuç imaları doğrulanmamış durumda.

---

## KRİTİK — makaleye girerse hata olur

### K1. LSTM girdi boyutu 22 değil 21 (satır 348, 350)

**Belgede:**
> `├─ concat([X, e_c]) ──► (batch, 24, 22)`
> `├─ LSTM(input=22, hidden=64, num_layers=2, dropout=0.3, batch_first=True)`

**Gerçek:** F=17 öznitelik + 4 boyutlu il gömmesi = **21**. `model.py:18`:
`input_size=num_numeric_features + config.city_embedding_dim`. Ampirik doğrulama:
`lstm.weight_ih_l0` şekli `(256, 21)`. Belge aynı şemanın 344. satırında `F=17` yazdığı için
**kendi içinde de çelişkilidir** (17+4≠22). 22, `CLRSKY_SFC_SW_DWN` düşürülmeden önceki F=18
döneminin kalıntısıdır.

**Düzeltme:** Şemada `(batch, 24, 21)` ve `LSTM(input=21, ...)`.

### K2. Toplam parametre sayısı 58.700 değil 58.444 (satır 369)

**Belgede:** "Toplam öğrenilebilir parametre: **58.700**."

**Gerçek:** Varsayılan konfigürasyonla model kuruldu ve sayıldı: **58.444** (gömme 20 +
LSTM katman-1 22.272 + LSTM katman-2 33.280 + başlık 2.080+792). Aynı model F=18 ile
kurulduğunda **tam olarak 58.700** çıkıyor — yani belgedeki sayı, öznitelik düşürme
düzenlemesinde güncellenmemiş eski değerdir.

**Düzeltme:** "Toplam öğrenilebilir parametre: **58.444**."

### K3. Belge, ölçülen kalibrasyon başarısızlığı (CP ≈ 0,67) konusunda sessiz (satır 52, 790–791)

> **ÇÖZÜLDÜ — ve teşhisin ikinci yarısı yanlıştı (2026-08-29).** Belgenin sessizliğine dair
> tespit doğruydu ve düzeltildi. Ancak bu bulgunun "alt-kapsama yapısaldır, çünkü aleatorik
> terim eklenmiyor; rezidüel-varyans eklentisi bir ön koşuldur" biçimindeki açıklaması
> **ölçümle çürütülmüştür.** CP ≈ 0,67 değerleri $B = 1$ doğruluğunun eseriydi: havuzun
> bootstrap yarısı hiç üretilmiyordu. Tam doğrulukta ($B = 8$, L1) Rize gündüz CP'si
> 0,9521 ± 0,0009, Reliability 0,001'dir; diğer dört il ise hedefi *aşmaktadır* (0,981–0,984).
> Önerilen rezidüel-varyans eklentisi o dört ilde durumu kötüleştirirdi. Ayrıntı:
> `ABLATION.md` §3 ve `main_methodology.md` §11.5.

Aşağıdaki özgün denetim metni, kayıt olarak değiştirilmeden bırakılmıştır.

**Belgede (satır 790–791):**
> "Kalibrasyon sonrası düzeltme yapılmamıştır (örn. conformal prediction); CP hedeften
> **saparsa** bu bir sonraki iyileştirme adayıdır."

**Gerçek:** `outputs/experiments_ledger.csv`'deki tamamlanmış dört koşunun tamamında CP hedeften
çok uzaktadır: 0,6668 / 0,6701 / 0,6766 / 0,6751 (sonuncusu F=17 ile, `config_003_smoke_f17`).
CWC değerleri 143.000–254.000 mertebesindedir — belgenin kendi §12.4 kriterine göre "dar ama
güvenilmez aralık" tanısının ta kendisi. Koşuların hepsi smoke kalitesindedir (B=1, T=10, 5 epok),
dolayısıyla nihai hüküm değildir; ama eldeki *tüm* kanıt aynı yöndeyken "saparsa" dili
yanıltıcıdır.

Ayrıca yapısal bir neden vardır: havuzlanan B×T dağılımı yalnızca model/örneklem belirsizliğini
içerir; **aleatorik (gözlem gürültüsü) terimi hiçbir yerde eklenmemektedir**
(`metrics.py::summarize_predictive_distribution` doğrudan geçişlerin yüzdeliklerini alır).
Rezidüel varyans eklenmeden %95 kapsamaya ilkesel olarak ulaşılamayabilir — hakemin ilk
saldıracağı nokta budur.

**Düzeltme:** §16.5'i "Mevcut ön koşularda CP ≈ 0,67 ölçülmüştür; havuzlanan dağılım aleatorik
bileşeni içermediği için alt-kapsama yapısaldır; rezidüel-varyans eklentisi veya conformal
kalibrasyon planlanmaktadır" biçiminde açık yazın. Satır 52'deki "belirsizlik doğrudan
gözlemlenebilir (bkz. `cp_vs_horizon.png`)" göndermesi de yalnızca smoke koşusu figürüne işaret
ediyor; tam koşu tamamlanana dek bu tür sonuç imalarını koşullu yazın.

### K4. Hiçbir tam-doğruluklu koşu yok; belge varsayılan konfigürasyonun çıktısı varmış gibi okunabiliyor

**Gerçek:** `outputs/experiments/config_002_default_full/` içinde `log.txt` yok, `metrics/` boş,
`config_002_default_full_stdout.log` 0 bayt — koşu tamamlanmamıştır. Ledger'daki tüm satırlar
`n_bootstrap=1`, `mc_dropout_passes=10` smoke koşularıdır; F=17 ile yalnızca tek bir smoke koşusu
vardır. §11'deki "B×T = 800 örnek", "(800, 44155, 24)" tensörü ve §14'teki süre tahmini tasarım
değerleridir, ölçülmüş değildir. Belge başlığındaki "Sayısal değerler ... doğrulanmıştır" cümlesi
bu bölümler için geçerli değildir.

**Düzeltme:** §11 ve §14'e "varsayılan konfigürasyonun tam koşusu henüz tamamlanmamıştır;
buradaki B×T ve süre değerleri tasarım hedefidir" notu ekleyin; makale taslağına smoke
metriklerinin asla girmemesi gerektiğini belirtin.

---

## DÜZELTİLMELİ — tutarsızlık / yanlış ifade

### D1. "Test kümesi tam olarak bir mevsimsel yıl (369 gün)" (satır 258–259)

**Belgede:** "Bu oranlarla test kümesi **tam olarak bir mevsimsel yıla** (369 gün) denk gelir."

**Gerçek:** test satır dilimi = 59.184 − 43.796 − 6.510 = **8.878 saat = 369 gün 22 saat
≈ 369,92 gün** (2025-03-26 02:00 → 2026-03-30 23:00). "Tam olarak 369 gün" hem sayı hem
"tam olarak" ifadesi düzeyinde yanlıştır.

**Düzeltme:** "test kümesi yaklaşık bir tam yılı (≈370 gün; 8.878 saat) kapsar ve dört mevsimi
dengeli içerir."

### D2. Blok uzunluğu birimi: §15 "168 saat" vs §11.2 "168 pencere" (satır 510–511 vs 763)

**Belgede (§15 taslak):** "hareketli blok bootstrap (**blok uzunluğu 168 saat**)".

**Gerçek:** `bootstrap.py::resample_train_split` **pencere dizileri** üzerinde çalışır;
`bootstrap_block_length=168`'in birimi penceredir. Stride=1'de 168 ardışık pencerenin
*başlangıçları* 168 saatlik aralığa yayılır ama her blok 168+47 = 215 saatlik ham veriye dokunur.
§11.2 ("ℓ = 168 pencere") doğrudur; §15 taslağı — makaleye kopyalanacak metin — yanlış birim
taşımaktadır.

**Düzeltme (§15):** "...hareketli blok bootstrap (blok uzunluğu 168 ardışık pencere; saatlik
kaydırma ile ≈1 haftalık dilim)...".

### D3. Epok-bazlı kayıpların günlüğe yazıldığı iddiası (satır 429–430)

**Belgede:** "Eğitim ve doğrulama kayıpları epok bazında kaydedilir (`history`) **ve deney
günlüğüne (`log.txt`) yazılır**."

**Gerçek:** `experiment.py:101` günlüğe yalnızca `replica {b}: final val_loss=... epochs=...`
yazar; epok-bazlı `history` hiçbir dosyaya kaydedilmez (bellekte kalır ve atılır). Doğrulama:
`config_000_smoke/log.txt` içeriği 7 satırdır, epok dökümü yoktur. §13.2'deki tanım ("replika
bazında val loss") doğru olan tanımdır — §10.2 onunla çelişiyor. Eğitim eğrisi figürü istenirse
bu ayrıca bir tekrarlanabilirlik boşluğudur.

**Düzeltme:** ya cümleyi "epok bazında tutulur; günlüğe replika başına son doğrulama kaybı yazılır"
yapın, ya da (tercihen) `history`'yi diske yazacak küçük bir kod değişikliği planlayın ve belgeyi
ona göre bırakın.

### D4. Sınır-kesen pencere kaybı "bölme başına en fazla (L+H−1)" değil (satır 324)

**Belgede:** "Kayıp, bölme başına en fazla $(L+H-1)$ penceredir."

**Gerçek:** kayıp **il × sınır başına** (L+H−1) = 47 penceredir; 2 sınır × 5 il × 47 = **470**
pencere. Doğrulama: il başına toplam pencere 59.137; 5 il = 295.685; atanmış toplam
218.745+32.315+44.155 = 295.215; fark = 470. "İhmal edilebilir" sonucu değişmez ama nicel ifade
yanlış.

**Düzeltme:** "Kayıp, il ve sınır başına en fazla $(L+H-1)$ penceredir (varsayılanda toplam 470
pencere, ≈%0,16)."

### D5. §14 süre iddiası doğrulanmamış (satır 739–741)

**Belgede:** "Tam konfigürasyon ... yaklaşık 30 dakika – birkaç saat sürer."

**Gerçek:** Hiçbir tam koşu bitmemiştir (bkz. K4). Tek veri noktası: CPU'da smoke
(1 replika × 5 epok × 10 geçiş) ≈ 160 s. 8 replika × erken-durdurmalı ~30–60 epok × 100 geçiş
CPU'da bundan çok daha uzun sürecektir; "30 dakika" ancak GPU varsayımıyla savunulabilir.

**Düzeltme:** "GPU üzerinde ... (henüz ölçülmemiştir)" gibi açık koşullu ifade.

### D6. §16.1 gece oranı nicelenmemiş (satır 779–782)

Belge gece saatlerinin metrikleri şişirdiğini doğru söylüyor ama oranı vermiyor. Ölçülen değer:
hedefin **%48,76'sı tam olarak 0** (parquet üzerinde hesaplandı). Makale tartışması için bu sayının
belgeye eklenmesi gerekir. Ayrıca "CP'yi olduğundan yüksek gösterir" iddiası mevcut koşularla henüz
doğrulanmamıştır (gündüz/gece ayrımlı CP hiçbir çıktıda yok) — bu ayrım `metrics.py`'ye eklenene
kadar iddiayı "beklenir" kipinde yazın.

---

## İYİLEŞTİRME — hakem itirazını önler

1. **Aleatorik belirsizlik eksikliği (K3'ün metodolojik yüzü).** Bootstrap×MC-Dropout havuzunun
   yüzdelikleri "modelin ortalama tahmini üzerindeki" belirsizliği verir; gözlem gürültüsü
   eklenmedikçe %95'lik aralıklar sistematik dar kalır. Literatürdeki standart çare (bootstrap +
   rezidüel varyans, ya da split-conformal katman) belgede "gelecek iş" olarak değil, tasarımın
   bilinen bir sınırı olarak §11'de tartışılmalı. Kaynak makale ile PICP kıyası (0,9472) bu
   düzeltme yapılmadan adil olmayacaktır.
2. **Doğrulama kümesi tüm replikalar için ortaktır** (`experiment.py:94`: her replika
   `splits["val"]` ile erken durdurulur). Replikaların bağımsızlığı varsayımını zayıflatır;
   belgede belirtilmesi hakem sorusunu önler.
3. **Stride=1 örtüşen pencereler:** 44.155 test penceresi bağımsız örnek değildir (ardışık
   pencereler 47 saat paylaşır). `n_samples` sütunu makalede "bağımsız gözlem" gibi okunmamalı;
   anlamlılık testi yapılacaksa blok yapısı hesaba katılmalı.
4. **Ledger hijyeni:** `config_000_smoke` ledger'da **iki kez** vardır ve `experiment_grid.py`
   smoke konfigürasyonunu taramaya dahil ettiği için her `run_all_experiments.py` koşusu yeni bir
   mükerrer satır ekleyecektir — §13.4'ün kendi kuralı fiilen ihlal edilmiş durumda. Ayrıca eski
   F=18 satırları (`n_features=18`) tabloya çekilirken filtrelenmelidir.
5. **Smoke koşularında T=10 ile %2,5/%97,5 yüzdelikleri** 10 örnekten kestirilir — bu koşuların
   aralık metrikleri anlamsızdır; belgeye "smoke metrikleri yalnızca boru hattı doğrulaması
   içindir" notu eklenmeli.
6. **Tek seed** sınırı belgede zaten dürüstçe veriliyor (§16.3) — makalede çoklu-seed planı en
   azından varsayılan konfigürasyon için uygulanmalı.

---

## Doğrulanmış ve sorunsuz bulunan iddialar

Aşağıdakiler kod ve veri üzerinde birebir doğrulandı:

> **Sonradan eklenen uyarı (D7).** Aşağıdaki "§3 betimleyici istatistik tablosunun beş satırı da
> ondalığına kadar doğru" tespiti geçerlidir — tablo veriyle birebir uyuşuyor. Ancak **Van'ın
> 1215,88 W/m² maksimumu bir veri artefaktıdır**: o satırda kt = ALLSKY/CLRSKY = **3,28**, yani
> açık gökyüzü limitinin 3,3 katı, üstelik Şubat ayında −3,4 °C'de. Tüm veri setinde kt > 1,2 olan
> yalnızca **4 satır** vardır; dördü de Van, dördü de Ocak/Şubat (kt 1,21 / 1,25 / 1,42 / 3,28).
> Van'ın savunulabilir maksimumu **1068,72** W/m²'dir. Eğitim için zararsızdır, ama `max` kotalayan
> her tabloda görüneceği için makalede alıntılanmamalıdır. (Paralel EDA oturumunun bulgusu;
> bu denetimde bağımsız olarak doğrulandı.)

- **Veri:** il başına 59.184 satır, toplam 295.920; ham 61.392/il; kesilen 2.208/il; aralık
  2019-06-30 00:00 – 2026-03-30 23:00; kuyruk boşluğu 2026-03-31 00:00 – 2026-06-30 23:00 ve her
  iki ışınım sütununun bu aralıkta tümüyle −999 olması; `ALLSKY_KT` −999 oranı ≈%50 (ölçülen
  0,504); §3 betimleyici istatistik tablosunun **beş satırı da ondalığına kadar doğru**.
- **Bölme:** train_end = 2024-06-27 19:00, val_end = 2025-03-26 01:00, test başlangıcı
  2025-03-26 02:00; ilk ilin saat sayısı üzerinden hesap (`windows.py:16`).
- **Pencereler:** 218.745 / 32.315 / 44.155; tensör şekilleri (·, 24, 17); 44.155×24 = 1.059.720;
  il ve bölme sınırı kuralları kodla birebir.
- **Öznitelikler:** F=17; §5.2 tablosunun sırası ve numaralandırması `NUMERIC_FEATURE_COLUMNS` ile
  birebir; döngüsel kodlama formülleri (24, 365,25, derece→radyan) `data.py` ile birebir;
  `DROPPED_COLUMNS` anlatımı doğru.
- **Model:** `hidden_sizes` aşırı-yüklü yorumu (`[0]`=LSTM genişliği, uzunluk=katman sayısı,
  `[1:]`=başlık) `model.py` ile birebir; dropout'un üç konumu; BatchNorm yokluğu ve gerekçesi;
  gömme boyutu 4.
- **Eğitim:** kayıp = MSE + 0,1·ReLU(−ŷ)² (ölçeklenmiş uzay uyarısı dahil, doğru); Adam, lr 10⁻³,
  batch 128, ReduceLROnPlateau(0,5/7), erken durdurma 10, en-iyi-val ağırlıklarının geri
  yüklenmesi — tümü `train.py` ile birebir; §13.1 varsayılanlar tablosunun **her hücresi**
  `config.py` ile eşleşiyor.
- **UQ:** MC-Dropout kod parçası (`model.train()` + `no_grad`, çıktı (T,N,H), T=100) birebir; MBB
  algoritması (⌈n/ℓ⌉ blok, U{0, n−ℓ} yerine koyarak, ilk n'e kırpma, il bazında bağımsız)
  `bootstrap.py` ile birebir; seed şeması (seed+b+1, tek `default_rng(seed)`) `experiment.py` ile
  birebir; havuzlamanın ölçekli uzayda yapılıp sonra W/m²'ye çevrilmesi doğru.
- **Metrikler:** CP (≤/≥, kapalı aralık), PINW (alt-küme aralığına bölme), MPIW,
  Reliability=|CP−0,95| (0,9472 örneği aritmetik olarak doğru), CWC (η=50, γ göstergesi) ve
  yüzdelik 2,5/97,5 tanımları `metrics.py` ile birebir; **CRPS hızlı tahmincisi naive O(S²)
  toplamla sayısal olarak eşleştirildi** (fark <10⁻¹⁴); üç raporlama düzeyi ve CSV şekilleri
  (summary 1+5 satır, horizon 24 satır) çıktılarda doğrulandı.
- **Ölçekleme:** train-satırlarında fit, küresel tek scaler, ters dönüşüm formülü — `scaling.py`
  ile birebir.
- **Altyapı:** §13.2 çıktı ağacı, §13.5 tarama eksenleri (`experiment_grid.py` ile birebir;
  `config_split_paper_64_16_20` mevcut), §17 komutları ve dosya haritası, cihaz önceliği
  MPS→CUDA→CPU.

---

**Öncelik önerisi:** K1–K2 beş dakikalık metin düzeltmesidir, hemen yapılmalı. K3–K4 makalenin
anlatı stratejisini etkiler; tam-doğruluklu bir F=17 koşusu (tercihen rezidüel-varyans/conformal
denemesiyle birlikte) tamamlanmadan §15 taslağı makaleye taşınmamalıdır.
