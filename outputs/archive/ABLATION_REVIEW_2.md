# Ablasyon incelemesi II — §4–§7'nin bağımsız doğrulaması ve görülmemiş katkılar

Bu belge `ABLATION.md`'nin **§4 (mimari merdiveni), §5 (uç nokta ablasyonu), §6 (hedef
dönüşümü) ve §7 (transferin formülasyona dayanıklılığı)** bölümlerinin bağımsız
doğrulamasıdır. `ABLATION_REVIEW.md` (birinci inceleme, §1–§3'ü kapsıyordu) okunmuş, tekrar
edilmemiş, ve yeni kanıtın onu geçtiği yerler açıkça işaretlenmiştir.

Belge iki iş yapar. Birincisi doğrulama; ikincisi — ve asıl uzun olanı — **veride hâlihazırda
duran ama hiçbir yazıya girmemiş bulguların** çıkarılmasıdır (§4).

---

## 1. Kapsam ve yöntem

**Okunanlar.** `ABLATION.md` (1649 satır, tamamı), `ABLATION_REVIEW.md`, `CLAUDE.md`,
`outputs/eda/EDA.md` + `README.md` + `outputs/eda/tables/` (33 dosya), `main_methodology.md`
§5.4/§12.3.1, `src/merve_solar/{config,experiment}.py`, `configs/experiment_grid.py`,
`outputs/experiments_ledger.csv` (126 satır × 51 sütun), 126 koşunun tamamının
`metrics/results_summary.csv` ve `metrics/results_by_horizon.csv` dosyaları,
`outputs/processed/base_features.parquet`.

**Yöntem.** Her yük taşıyan sayı pandas/scipy ile CSV'den yeniden hesaplandı; `ABLATION.md`
metnindeki değere hiçbir yerde güvenilmedi. Eşleştirilmiş testler `scipy.stats.ttest_rel`,
kümelenmiş testler tohum düzeyinde `ttest_1samp`, $n = 5$ il korelasyonları **tam permütasyon**
$p$ ile (asimptotik Spearman $p$ $n = 5$'te yanıltıcıdır — aşağıda bir örneği var).
Kolların tek eksenli olup olmadığı hem `config.json` alan-alan karşılaştırmasıyla hem ledger'ın
konfigürasyon sütunlarıyla denetlendi.

**Kısıt.** `outputs/**/metrics/*.npz` ve `outputs/**/checkpoints/*.pt` bu makinede **yok**
(gitignore). Dolayısıyla eleman düzeyinde hiçbir şey (eşleştirilmiş Diebold–Mariano, saat-içi
kırılım, mevsim kırılımı, koşullu kapsama) burada hesaplanamaz. Böyle bir analiz gerektiğinde
belirtilmiştir; tahmin edilmemiştir. Hiçbir deney koşulmadı, `outputs/` altında hiçbir şey
değiştirilmedi.

---

## 2. Doğrulama

### 2.1 Birebir doğrulanan iddialar (kısa geçiyorum)

Aşağıdakiler CSV'lerden yeniden hesaplandı ve **son basamağına kadar tuttu**:

| iddia | yer | doğrulama |
| --- | --- | --- |
| `kt` beş ilde de `raw`'ı yeniyor, $p \le 0{,}008$ | §6.3 | ✔ RMSE $p$ = 0,0020/0,0004/0,0007/0,0022/**0,0076**; MAE 0,0008–0,0022; Aggregate ΔRMSE −8,50 (−%9,2), ΔMAE −8,79 (−%12,9), tohum başına −8,50/−8,69/−8,31 |
| `kt` ↔ `raw` çifti **yalnızca** `target_transform`'da ayrılıyor | §6.2 | ✔ İki yoldan: `configs/experiment_grid.py:612-616`'daki `assert differing == {"target_transform"}` ve ledger'ın 30 konfigürasyon sütununun farkı (tek fark). *Küçük uyarı: 2.3'e* |
| §7.6 kümelenmiş test: `raw` −%1,446, $t = -8{,}19$, $p = 0{,}0146$; `kt` −%0,471, $t = -1{,}77$, $p = 0{,}2184$ | §7.6 | ✔ birebir; her ilin $p$'si de (Ankara 0,0354, Antalya 0,3181, Konya 0,9015, Van 0,1923, Rize 0,3482; MAE Antalya **0,0432**) |
| §7.7 kalibrasyon net sıfır, $p = 0{,}995$ | §7.7 | ✔ kümelenmiş ortalama ΔRel = **+0,000008**, $t = -0{,}008$, $p = 0{,}9946$; Rize −0,0307 $p$ = **0,0001**, Konya +0,0160 $p$ = 0,0066, Van +0,0065 $p$ = 0,0131, Ankara +0,0082 $p$ = 0,0601 |
| §5.4 nokta doğruluğu tablosu ve kümelenmiş $p = 0{,}0146$ | §5.4 | ✔ tüm $p$'ler (0,0186/0,0158/0,0518/0,1129/0,1523), 15/15 işaret |
| §3.6 taban çizgisi tablosu; LSTM gündüz MAE'yi **dört ilde** akıllı kalıcılığa kaybediyor | §3.6 | ✔ Ankara +10,12 · Antalya +15,14 · Konya +13,67 · Van +7,88 kaybediyor, Rize −10,20 kazanıyor; altı tohum Aggregate RMSE 91,985 ± 0,624 |
| §6.4 `kt` ile MAE eşiği toplulaştırılmışta ve iki ilde geçiliyor | §6.4 | ✔ Aggregate 59,16 < 60,19; Van 56,70 < 58,08; Rize 69,67 < 85,23 |
| §4.8 B-6 (`[128,64]` → `[256,128]`) ve B-9 (iki eksenli kol) | §4.8 | ✔ tüm $p$'ler: bvl 0,0337 · MAE 0,0208 · CRPS 0,0448 · CP 0,0048 · RMSE 0,3709; B-9 RMSE +1,42 $p$ = 0,0467, CRPS +2,41 $p$ = 0,0095, CP +0,0310 $p$ = 0,0073 |
| §4.8'in cephe regresyonları | §4.8 | ✔ CP ~ log(MPIW) on tek-eksenli kolda **$R^2 = 0{,}9486$**, `[256,128]` **$z = -2{,}19$**; RMSE ~ log(MPIW) öngörü **80,50** vs gözlenen 88,58, **$z = +2{,}31$**; iki eksenli kol $z = -1{,}07$ |
| §6.5'in ufuk kırılımı | §6.5 | ✔ h=1 raw 6,40/0,9948 · kt 6,70/0,9357; h=8 4,74/0,9785 · 4,78/0,9351; h=24 4,13/0,9530 · 4,38/0,9258 |
| §3.2'nin altı tohumlu H1'i | §3.2 | ✔ −2,6998, $t = -3{,}838$, $p = 0{,}0122$, Wilcoxon 0,0312, MAE $p$ = 0,0050 |
| §4.4'ün Spearman'ı | §4.4 | ✔ $\rho = 0{,}8424$, $p = 0{,}00222$ — **on tek-eksenli kol** üzerinde (12 kolun tamamında 0,909; iki `lookback` kolu çıkarılınca 0,939) |

**Karşılaştırılabilirlik denetimi.** §4'ün on iki kolunun **hepsi** referanstan tam bir ledger
sütununda ayrılıyor (tek bilinçli istisna `h128x64_do04`, belgede zaten kayıtlı). §5/§7'nin
`solo` ↔ `all5` kontrastları `training_scope` + `excluded_cities` çiftinde ayrılıyor; bu iki
sütun tek bir kavramsal ekseni kodladığı için kural ihlali değildir. §6 tek eksenlidir.
İki gerçek karıştırıcı var, ikisi de belgede kayıtlı ama biri eksik yazılmış:

- $B{=}1 \to B{=}8$ geçişi aynı zamanda `max_epochs` 100 → 200 değiştiriyor. Her satırda
  `hit_max_epochs = 0` olduğu için bağlayıcı değil — ama §3'ün girişi "yalnızca
  `{n_bootstrap, max_epochs}`" derken bunu doğru yazıyor, §3.2'nin tablosu ise "B=1 → B=8"
  başlığıyla sunuyor. Küçük.
- §1 → §2 geçişi `loss_function` **ve** `device`'ı birlikte değiştiriyor (cpu/mse → mps/mae).
  T-12 bunu kaydediyor. Ama §2.2'nin "kriter değişimi kolları eşit etkilemedi" mekanizma
  açıklaması bu karıştırıcının içindedir ve MSE tarafında **tek tohum** vardır: cihaz
  bileşeni ayrılamaz. Aşağıdaki 2.6'daki tekrarlanabilirlik ölçümü bunu daha da ağırlaştırıyor.

`experiments_ledger.csv`'de mükerrer `experiment_id` **yok** (126/126 tekil); 126 ledger satırı
ile 126 çıktı dizini birebir eşleşiyor.

---

### 2.2 §4.8 B-8 — "tekdüze düşüyor" ve "istisnasız" ifadelerinin ikisi de yanlış

Bu, incelemenin bulduğu en açık olgusal hata ve en kolay hakem hedefi. Tabloyu yeniden
hesapladım; **belgedeki sayıların hepsi doğru, onlardan çıkarılan iki cümle yanlış.**

Kalite sırasına (gündüz Aggregate RMSE azalan) göre oran dizisi:

```
4,591 → 4,800 → 4,263 → 4,316 → 4,277 → 4,291 → 4,346 → 4,084 → 3,535 → 3,419 → 3,433 → 2,734
```

**(a) Tekdüze değil.** On bir adımın **dördü** ters işaretlidir: `[32,16]`→`dropout 0,4`
(+0,209), `[64,64,32]`→`lookback 48` (+0,054), `[64,32]` referans→`lookback 72` (+0,055),
`[128,64] lr3e-4`→`[128,64]` (+0,014). Sıra korelasyonu Spearman $\rho = 0{,}846$
($p = 0{,}00052$) — güçlü, ama "tekdüze" değil ve "CP tam olarak onu izliyor" da değil.

**(b) 3,92 eşiği istisnasız değil: on iki kolun üçü ihlal ediyor.**

| kol | oran | gündüz CP | eşik ne diyor | gerçek |
| --- | ---: | ---: | --- | --- |
| `lookback 48` | 4,316 | 0,9495 | fazla kapsar | **eksik** |
| `lookback 72` | 4,346 | 0,9475 | fazla kapsar | **eksik** |
| `[128,64] × do 0,4` | 4,084 | 0,9260 | fazla kapsar | **eksik (0,024 ile, sınırda değil)** |

İki `lookback` kolu 0,95'e çok yakın (rundama savunulabilir); `[128,64] × do 0,4` savunulamaz —
oran eşiğin 0,16 üstünde, kapsama nominalin 0,024 altında.

**(c) Gauss gerekçesi tutarlı ama bir yasa değil, ve eşiğin kendisi yanlış yerde.** Türetme
şudur: aralık $\pm 1{,}96\,\sigma_{\text{epi}}$ ise ve artık $\mathcal{N}(0, \text{RMSE}^2)$
ise, kapsama $2\Phi(\text{oran}/2) - 1$'dir. Bunu her kol için hesapladım:

| | ortalama $|CP - CP_{\text{Gauss}}|$ | işareti negatif olan kol |
| --- | ---: | ---: |
| on iki kol | **0,0148** | **10/12** |

Yani Gauss haritası CP'yi **sistematik olarak fazla** öngörüyor (gözlenen kapsama daha düşük) —
artıklar Gauss değil (ağır kuyruklu) ve oran eleman düzeyinde heterojen, ikisi de kapsamayı
aşağı çeker. Doğru eşik ölçülebilir: 36 koşu üzerinde $CP = 0{,}6761 + 0{,}0641 \times
\text{oran}$ ($R^2 = 0{,}942$) ve **$CP = 0{,}95$ için gereken oran 4,275**'tir, 3,92 değil.
(Kol düzeyinde $n = 12$ ile 4,270 — aynı yere çıkıyor.)

Yeni eşik de istisnasız değil (9/12, farklı bir üçlü). **Doğru ifade:** "Oran, CP'nin güçlü bir
tek değişkenli öngörücüsüdür ($R^2 = 0{,}94$), ama nominal-%95 kırılma noktası bu tasarımda
Gauss'un 3,92'si değil, ölçülmüş 4,27'dir; aradaki %9'luk fark artık dağılımının Gauss'tan
sapmasının bir ölçüsüdür." Bu hâliyle cümle hem doğru hem daha ilginç: bir varsayım yerine bir
**ölçüm** raporluyor.

**(d) Yanılan iki kolun kimliği bir bonus.** İstisnaların ikisi `lookback` kollarıdır — yani
modeli değil **veriyi** (pencere sayısını, girdi uzunluğunu) değiştiren iki koldur. Bu, §6.5'in
kendi hükmünü ("oran yasası kol ailesi içinde geçerli, formülasyon değişince değil") §4.8'in
**kendi tablosundan** bağımsız olarak doğrular. §4.8, §6.5'in sınırlamasını kendi verisinde
zaten taşıyormuş ve fark edilmemiş.

**Cephe regresyonları etkilenmiyor** — `[256,128]`'in $z = -2{,}19$ / $z = +2{,}31$ değerleri
ve $R^2 = 0{,}95$ birebir doğrulandı. §4.8'in mekanizma paragrafı ("aralık, hatanın
düştüğünden daha hızlı daralıyor") **ayakta**; düşen yalnızca "tekdüze" ve "istisnasız"
kelimeleri ile 3,92 sayısıdır.

---

### 2.3 §4.8 B-7 / §4.5 B-5 — hüküm doğru, kanıt yanlış testten geliyor

Soru: Rize gerçekten kapasiteye duyarsız mı, yoksa üç tohumla sadece güçsüz mü?

Belgenin kanıtı bir **reddedememedir** ($p = 0{,}462$). Bunun ne kadar zayıf olduğunu görmek
için Rize'nin etkisine güven aralığı koydum:

| kontrast | Rize Δ | %95 GA | dört ilin nokta kestirimleri |
| --- | ---: | --- | --- |
| `[64,32]` → `[128,64]` | −0,56 | **[−11,47, +10,35]** | −3,68 … −6,45 (**hepsi GA içinde**) |
| `[64,32]` → `[256,128]` | −1,28 | **[−7,38, +4,82]** | −5,25 … −9,18 (**hepsi GA içinde**) |

Yani belgedeki hâliyle veri, "Rize duyarsız" ile "Rize tam olarak Van gibi davranıyor"u
**ayırt edemiyor**. B-5 tek başına hiçbir şeyin kanıtı değil.

**Ama doğru test var ve iddiayı destekliyor.** Sorulması gereken şey Rize'nin etkisinin sıfır
olup olmadığı değil, diğer dördünden **farklı** olup olmadığıdır; bu bir etkileşim testidir ve
tohum gürültüsü paylaşıldığı için çok daha güçlüdür. Tohum başına
(Rize Δ) − (dört ilin ortalama Δ'sı):

| kontrast | Rize | dört il | etkileşim | tohum başına | $p$ | göreli etkileşim | $p$ |
| --- | ---: | ---: | ---: | --- | ---: | ---: | ---: |
| 64 → 128 | −0,56 | −5,44 | **+4,88** | +5,52/+6,66/+2,46 | 0,060 | +5,51 pp | **0,032** |
| 64 → 256 | −1,28 | −7,48 | **+6,20** | +5,35/+8,97/+4,28 | **0,049** | +7,07 pp | **0,033** |
| 128 → 256 | −0,72 | −2,04 | +1,32 | −0,17/+2,31/+1,82 | 0,223 | +1,68 pp | 0,236 |

**Hüküm: kısmen doğrulandı.** "Rize kapasiteden diğer dört ilden anlamlı biçimde daha az
yararlanıyor" cümlesi **kurulabilir** — kümülatif merdivenin tamamı için ($p = 0{,}033$–0,049,
3/3 tohum). Kurulamayan iki şey: (i) "Rize'de kapasitenin etkisi yok" (bu bir reddedemedir),
(ii) "merdivenin **ikinci** basamağında da sürüyor" (128→256 tek başına $p = 0{,}22$).
§4.8'in B-7 başlığı ikinci basamağı ayrı bir doğrulama gibi sunuyor; değil.

**Yapılacak iş kanıt eklemek değil, testi değiştirmektir.** Bu ücretsizdir.

---

### 2.4 §6.5 — ölçüm doğru, mekanizma **gösterilmiş değil** ve bu dosyalardan gösterilemez

§6.5'in ölçümü tam doğru (2.1'deki tablo). Sorun şu cümlededir:

> `kt` kolunda aralık genişliği inşa gereği $\text{CLRSKY}(t{+}h) \times$ (…), yani güneş
> geometrisiyle tam orantılıdır — **öğle geniş, alacakaranlık dar**. `raw` kolunun aralığı ise
> **gün boyunca** çok daha düzdür (`raw` MPIW ufuk boyunca ×1,001).

Bu iki cümle iki farklı eksenden konuşuyor ve ikincisi birincisini desteklemiyor:

1. "Öğle geniş, alacakaranlık dar" bir **günün saati** iddiasıdır.
2. "MPIW ufuk boyunca ×1,001" bir **ufuk adımı** ölçümüdür.

`window_stride = 1` olduğu için sabit bir $h$ için hedef saat 24 saatlik saate **düzgün
dağılmıştır** — bunu ampirik olarak doğruladım: gündüz `n_elements` $h = 1 \ldots 24$ boyunca
en fazla **5 eleman** (~22.755 içinde) oynuyor. Yani `results_by_horizon.csv`'deki her MPIW
değeri **zaten tam bir günlük çevrim üzerinden ortalanmıştır**; herhangi bir gün-içi
orantılılık CSV'ye ulaşmadan integre edilip yok olur.

Bu dosyaların taşıdığı tek gün-içi bilgi ikili gündüz/gece ayrımıdır, ve o da dejenere:
126 koşunun **hepsinde** $\text{MPIW}(\text{all\_hours}) / \text{MPIW}(\text{daylight}) =
0{,}51535$, beş ondalık basamağa kadar gündüz eleman payına eşit — yani gece aralıkları tam
olarak sıfır genişliktedir. İki kutu, öğleyi alacakaranlıktan ayıramaz.

**Hüküm: kısmen. Ölçüm doğrulandı, mekanizma iddia edilmiş ama sınanmamıştır ve mevcut
çıktılardan sınanamaz.** Gereken şey MPIW'in saat-of-day veya CLRSKY-desil kırılımıdır; o da
`test_predictions.npz`'yi gerektirir, ki bu makinede yok (uzak makinede var). §6.5'in 1. ve 2.
sonuçları (skaler katsayı yetmez; düzeltmenin yönü kola bağlı) **bu mekanizmaya dayanıyor**,
dolayısıyla şu an sınanmamış bir varsayım üzerinde duruyorlar. 2. sonuç (`raw` her ufukta
nominalin üstünde, `kt` altında) ufuk tablosundan doğrudan okunabilir ve **ayakta**; 1. sonuç
değil.

Yan not: `raw` MPIW'in "ufuk boyunca ×1,001" olması bir **uç nokta oranıdır**. Eğri düz değil,
sığ bir ters-U'dur: iç maksimum $h = 9$–22 arasındadır ve maks/min = **1,043**. On sekiz kol
ailesinin **hepsinde** aynı şekil var. `ABLATION_REVIEW.md` §3.3 aynı büyüklüğü "×1,04" diye
verirken $h_{12}/h_1$'i, `ABLATION.md` §6.5 "×1,001" derken $h_{24}/h_1$'i kullanıyor — iki
farklı sözleşme, aynı eğri. Tek bir sözleşme seçilmeli. (Ayrıca `ABLATION_REVIEW.md` §3.3'ün
"`[128,64]` MPIW ×1,05" rakamı hiçbir sözleşmede çıkmıyor: uç nokta oranı **1,0107**, maks/min
1,046.)

---

### 2.5 §5.5 — "hiçbiri anlamlı değil" cümlesi yanlış

§5.5 şöyle diyor: aralık her ilde daralıyor, "**kapsamayı bozmadan** (|ΔCP| ≤ 0,0031, hiçbiri
anlamlı değil)". Eşleştirilmiş testi çalıştırdım:

| il | solo CP | `all5` CP | ΔCP | $p$ |
| --- | ---: | ---: | ---: | ---: |
| **Ankara** | 0,9811 | 0,9842 | **+0,0032** | **0,0243** |
| **Antalya** | 0,9854 | 0,9837 | −0,0017 | **0,0047** |
| Konya | 0,9816 | 0,9813 | −0,0002 | 0,7823 |
| Van | 0,9839 | 0,9829 | −0,0010 | 0,3817 |
| Rize | 0,9529 | 0,9521 | −0,0008 | 0,8396 |

Beşin ikisi $\alpha = 0{,}05$'te anlamlıdır (ve Ankara'nın ΔCP'si 0,0032, "≤ 0,0031"
sınırının da dışında). Etkiler pratikte önemsiz — 0,003'lük bir CP kayması zaten 0,98'de
duran bir kolda hiçbir şey ifade etmez — ama **cümle yanlıştır** ve bir hakem doğrulayabilir.

Daha önemlisi: bu iki anlamlı etkinin işaretleri (Ankara kötüleşiyor, Antalya iyileşiyor)
§7.7'nin `kt` altında "yeniden dağıtım" diye adlandırdığı örüntünün **aynısıdır**, sadece 5–7
kat küçüktür. §7.7'nin "`raw` altında gerçekleşmemişti" ifadesi bu nedenle fazla keskin;
doğrusu "`raw` altında ölçülebilir eşiğin hemen üstünde ama ihmal edilebilir büyüklükte
gerçekleşiyor, `kt` altında büyüklüğü bir mertebe artıyor"dur. Bu, §7'nin iddiasını
**zayıflatmaz, güçlendirir** — yeniden dağıtım bir `kt` tuhaflığı değil, tasarımın genel
özelliğidir (bkz. 4.6).

§5.5'in MPIW ve CRPS için verdiği yüzdelerin hepsi doğrudur; anlamlılıkları da ekliyorum,
çünkü tablo makaleye girecekse gerekecek: MPIW $p$ = 0,0084/0,0222/0,0071/0,0513/0,0283,
CRPS $p$ = 0,0006/0,0320/0,0038/0,0259/0,0649 (Ankara/Antalya/Konya/Van/Rize).

---

### 2.6 Tekrarlanabilirlik — **MPS'te aynı tohum aynı sonucu vermiyor**, ve bu §7'nin etki büyüklüklerinin altında

Bu, incelemenin en sonuçlu bulgusudur ve `ABLATION_REVIEW.md` §6 B-8'i **geçersiz kılar.**

Ledger'ın 30 konfigürasyon sütununu anahtar yapıp mükerrer konfigürasyon aradım. **Beş çift**
var: biri CPU'da, dördü MPS'te.

| çift | cihaz | gündüz Aggregate RMSE farkı | MAE | MPIW |
| --- | --- | ---: | ---: | ---: |
| `abl_loss_mse_s42_b1` ↔ `abl_rize_all5_s42_b1` | **cpu** | **0,0000** | 0,0000 | 0,0000 |
| `abl_rize_all5_s42_l1` ↔ `abl_arch_base_s42` | mps | +0,486 (%0,51) | +0,557 | −1,29 |
| `abl_rize_all5_s43_l1` ↔ `abl_arch_base_s43` | mps | +0,401 (%0,43) | +0,470 | −1,21 |
| `abl_rize_all5_s44_l1` ↔ `abl_arch_base_s44` | mps | +0,570 (%0,60) | +0,438 | **−4,83 (%1,19)** |
| `abl_parity_mps_s42` ↔ `abl_rize_solo_s42_l1` | mps | **+1,637 (%1,47)** | +1,230 | +3,55 |

`abl_arch_base_*` ile `abl_rize_all5_*_l1` **konfigürasyon olarak birebir aynıdır** (§4.2 bunu
zaten yazıyor ve `best_val_loss` için yeniden koşulduğunu açıklıyor). Aradaki commit'leri
denetledim: `2e3c209`, `268eb66`, `75ba063` yalnızca ledger/raporlama değiştiriyor;
`train.py`/`mc_dropout.py`/`bootstrap.py`/`windows.py`/`scaling.py`'ye dokunmuyorlar. Yani
fark **kod farkı değil, arka uç determinizmsizliğidir.**

**Sonuçlar, sırayla:**

1. **§1.10'un "determinizm doğrulandı" bulgusu yalnızca CPU için geçerlidir.** Bu iyi bir
   ölçümdür ve makalede kalmalıdır, ama şu anda yazıldığı gibi genel bir iddia gibi
   okunuyor. Ledger'ın 126 satırının **107'si MPS'tedir** — tam doğruluklu koşuların hepsi
   dâhil. Tekrarlanabilirlik iddiası şu anda makaleye yazılamaz hâlde.

2. **§1.11'in cihaz eşdeğerliği hükmü çürütüldü.** §1.11 tek bir CPU çekilişi ile tek bir MPS
   çekilişini karşılaştırıp nokta metriklerinde %0,25 fark buluyor ve "nokta metrikleri arka
   uçlar arasında okunabilir" pratik kuralını çıkarıyor. Ama **aynı konfigürasyonun aynı arka
   uçtaki iki çekilişi** %1,47 farklıdır — iddia edilen arka uç etkisinin **6 katı.** Üçlüyü
   yan yana koyalım (Rize solo, tohum 42, aynı konfigürasyon):

   | | RMSE | MAE | CP | MPIW |
   | --- | ---: | ---: | ---: | ---: |
   | CPU | 110,557 | 77,559 | 0,8674 | **318,38** |
   | MPS-a (`abl_parity_mps_s42`) | 110,832 | 77,920 | 0,8894 | 332,66 |
   | MPS-b (`abl_rize_solo_s42_l1`) | 112,469 | 79,149 | 0,8843 | 329,12 |

   CPU, MPS ikilisinin nokta metriği aralığının **içindedir**. §1.11'in "Sonuç 1"i (nokta
   metrikleri %0,25 kayıyor) ölçüm değil gürültüdür. **"Sonuç 2" (aralık metrikleri kayıyor)
   ise ayakta:** CPU'nun MPIW'i her iki MPS çekilişinin de 10,7–14,3 W/m² altındadır, MPS
   ikilisinin kendi arası ise 3,5'tur. Ama $n = 1$ ile bu da zayıftır.

3. **Etki büyüklüklerinin bir tabanı var ve §7'nin etkileri onun altında.** Havuzlanmış
   Aggregate için koşu-içi s.s. ≈ $0{,}486/\sqrt2 = 0{,}34$ W/m²; tohumlar arası s.s. 0,90.
   İl düzeyinde ise (üç çiftten):

   | il | MPS koşu s.s. | tohum s.s. | §5 (`raw`) etkisi | §7 (`kt`) etkisi |
   | --- | ---: | ---: | ---: | ---: |
   | Ankara | **1,05** | 1,87 | −2,07 | −0,72 |
   | Konya | 0,62 | 1,31 | −1,31 | −0,06 |
   | Antalya | 0,21 | 0,73 | −1,02 | +0,39 |
   | Van | 0,22 | 1,52 | −0,43 | −0,95 |
   | Rize | 0,15 | 2,50 | −2,05 | −0,79 |

   Eşleştirilmiş $t$-testi bu gürültüyü **doğru** ele alıyor (kendi s.h.'sinin içine
   soğuruyor), dolayısıyla $p$'ler dürüst. Bozulan şey **işaret sayımıdır**: §5'in "15/15
   tohum-kol" ve §7'nin "3/3 · 2/3" ifadeleri, etkinin koşu gürültüsüyle aynı mertebede olduğu
   yerlerde replikasyon değil, kısmen yazı-tura sayımıdır. §7'nin Van (−0,95) ve Konya
   (−0,06) etkileri koşu gürültüsünün içindedir.

4. **Bu bir kusur değil, bir katkıdır.** Aşağıda K-2'de.

**Not.** MPS farkları her üç çiftte de **aynı yönlü** (base kolu üç tohumda da daha kötü,
MPIW üçünde de daha dar). Saf sayısal gürültüden beklenen simetri bu değil; muhtemel açıklama
T-4.5'in kaydettiği çekişmedir (`arch_sweep_x` ve `percity_endpoints` eşzamanlı koştu) ya da
ölçülmemiş bir ortam farkıdır. Bu ayrım ölçülmemiştir ve ölçülmelidir (bkz. §5, Ö-2).

---

### 2.7 §7.4'ün kaydettiği hata biçimi başka nerede var — dört yer, en ağırı §3.5

§7.4 "Rize tuzağı"nı kayda geçiriyor ve "beş il kolu koşulmadan hiçbir *transfer şu biçimde
çalışıyor* cümlesi yazılmamalıdır" diyor. Belgeyi bu ölçütle taradım. **Dördü yakalanmamış.**

**(a) §3.5 — en ağırı, ve hüküm tersine dönüyor.** §3.5 $B{=}1 \to B{=}8$ geçişini kalibrasyon
zaferi olarak sunuyor: "Bootstrap bileşeni **tam da eksik kapsanan ili** düzeltti… projedeki en
büyük tek metrik iyileşmesi (CWC −%87)" ve buradan "`METHODOLOGY_REVIEW.md` K3 **yanlıştı**:
sorun eksik aleatorik terim değil, eksik doğruluktu" sonucunu çıkarıyor. Bu, Rize satırından
okunmuş. Beş il:

| il | $B{=}1$ Rel. | $B{=}8$ Rel. | Δ | işaret | $p$ |
| --- | ---: | ---: | ---: | :-: | ---: |
| **Rize** | 0,0366 | **0,0021** | **−0,0345** | 3/3 | **0,0123** |
| Ankara | 0,0127 | 0,0342 | **+0,0215** | 0/3 | **0,0158** |
| Antalya | 0,0190 | 0,0337 | **+0,0147** | 0/3 | **0,0023** |
| Konya | 0,0108 | 0,0313 | **+0,0205** | 0/3 | **0,0003** |
| Van | 0,0174 | 0,0329 | **+0,0156** | 0/3 | **0,0004** |
| **kümelenmiş** | | | **+0,0076** | | **0,0054** |

Yani $B{=}8$'e geçmek **dört ilde kalibrasyonu anlamlı biçimde bozuyor**, birinde
düzeltiyor, ve **net etki anlamlı biçimde kötüdür** ($p = 0{,}0054$). §3.5'in okuduğu tek
satır beşin en iyisiydi. §3.5'in CRPS savunması ("CRPS her ilde iyileşiyor") **doğrudur**
(kümelenmiş −%1,91, $p = 0{,}032$) ama kalibrasyon iddiasını kurtarmaz: keskinleşen bir
ortalama + fazla geniş bir aralık tam olarak bunu üretir.

`ABLATION_REVIEW.md` O-3 bu bölümü "nitelendirilsin" diye işaretlemişti. **Yeni kanıt daha
sert:** nitelendirilmesi değil, **net etkinin işaretinin ters yazıldığının** düzeltilmesi
gerekiyor. Ve §3.5'in "K3 yanlıştı" cümlesi, §4.8 ve §6.5'in daha sonra ulaştığı hükümle
("aralıklar hiçbir zaman inşa gereği kalibre değildi") **doğrudan çelişiyor** ve geri
alınmamış durumda.

**(b) §2.6 — "kalibrasyon büyük ölçüde çözüldü", ikinci tür Aggregate tuzağı.** §2.6, `all5`
kolunun **Aggregate** gündüz CP'sinin 0,9535/0,9570/0,9534 olmasından "hedefte" sonucunu
çıkarıyor. İl kırılımı ($B{=}1$, L1, `all5`, üç tohum):

| Ankara | Antalya | Konya | Van | **Rize** | Aggregate |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0,9627 | 0,9690 | 0,9608 | 0,9674 | **0,9134** | 0,9547 |

Aggregate 0,955, dört fazla-kapsayan il ile bir eksik-kapsayan ilin ortalamasıdır. §0'ın K-1
kuralı bunu il kümesi farkı için yasaklıyor; burada il kümesi aynı ama **karşıt işaretli
hataların ortalaması** aynı sonucu doğuruyor. §3.5'in T-15'i bunu $B{=}8$ için fark ediyor,
ama §2.6'ya geri uygulanmamış. §2.6'nın "rezidüel-varyans eklentisi artık bir **ön koşul
değil**" hükmü hâlâ ayakta ve §6.5'in "conformal katman ertelenebilir bir iyileştirme değil"
hükmüyle çelişiyor.

**(c) §3.2 — "havuzlama ve topluluk kısmen birbirinin yerine geçer".** `ABLATION_REVIEW.md`
bunu "taramanın en yayımlanabilir yeni sonucu" (B-2) diye işaretledi; ben de tabloyu
doğruladım (kazanç eğitim hacmiyle tekdüze ters: −4,07 / −2,65 / −2,30 / −1,11 / −1,00). Ama
tablonun **beş satırının hepsi Rize satırıdır**. Hacim ekseni diğer dört ilde hiç
ölçülmemiştir, çünkü onların $B{=}1$ solo kolu ledger'da yok. §7.4'ün kuralı bu iddiaya da
uygulanmalıdır: şu an "Rize'de ölçüldü" diye sunulmuyor, genel bir mekanizma iddiası olarak
sunuluyor. Kolayca düzeltilir (bir cümle) ama düzeltilmeli.

**(d) §4.6 — Rize'nin duyarsızlığını §5'i doğrulamak için genelliyor, ve kendi T-5.3'üyle
çelişiyor.** §4.6 şunu yazıyor: "§1–§3 ve §5'in tamamı `[64,32]` altında geçerliliğini
koruyor, çünkü B-5 ve B-7 **en büyük etkinin ölçüldüğü ilde (Rize)** kapasitenin merdivenin
iki basamağı boyunca etkisiz olduğunu gösteriyor." Ama T-5.3 aynı belgede tam tersini söylüyor
("dört kolay il kapasiteye duyarlı: bir solo `[128,64]` kolu farkı kapatabilir"). Sayılar
T-5.3'ü destekliyor:

| il | kapasite 64→128 | kapasite 64→256 | §5 havuzlama kazancı | kapasite / havuzlama |
| --- | ---: | ---: | ---: | ---: |
| Ankara | −5,45 | −7,48 | −2,07 | 2,6× |
| Konya | −6,45 | −9,18 | −1,31 | 4,9× |
| Antalya | −6,19 | −8,03 | −1,02 | 6,1× |
| Van | −3,68 | −5,25 | −0,43 | 8,7× |
| Rize | −0,56 | −1,28 | −2,05 | 0,3× |

Dört ilde kapasite kazancı havuzlama kazancının **2,6–8,7 katıdır.** §5'in solo kolları
havuzlanmış rejim için ayarlanmış `[64,32]`'yi kullanıyor. Solo kollar kapasiteye
havuzlanmış kol kadar duyarlıysa, `[128,64]` solo kolu dört ilde §5'in işaretini
**tersine çevirebilir**. Bu, §5'in hükmüne ("havuzlama beş ilin hepsinde iyileştiriyor")
yönelik en ciddi açık tehdittir ve §4.6 onu Rize üzerinden kapattığını sanıyor. Kapatmıyor.

**Aggregate tuzağı denetimi (birinci tür).** Farklı il kümelerinde eğitilmiş kolların
`Aggregate` satırıyla karşılaştırıldığı **hiçbir yer bulamadım**; §4/§6 kolları hep `all5`,
§5/§7 hep il satırı. Bu kural belgede tutarlı biçimde uygulanmış. **Ama bir tuzak kapısı
açık:** `results_by_horizon.csv`'de **il sütunu yoktur** (126 dosyanın hepsi yalnızca
`horizon_step × subset`). Bir solo kolun ufuk eğrisi o ilin tamamıdır, `all5`'inki beş ilin
havuzudur; ikisi ufuk düzeyinde karşılaştırılırsa doğrudan Aggregate tuzağına düşülür
(bu incelemede bir kez neredeyse düşüldü: `raw` solo−`all5` ufuk farkı 13,5–19,0 W/m²
görünüyor, oysa Rize satırındaki gerçek fark 2,05'tir). §0'a bir kural eklenmeli.

---

### 2.8 Küçük düzeltmeler

- **§5.6'nın iki $k_t$ değeri yanlış.** Belge "Konya 0,832" ve "Van 0,821" diyor.
  `outputs/eda/tables/clearness_index_by_city.csv` (`season == Tümü`, `kt_daily_mean`):
  Ankara 0,8065 · Antalya 0,8396 · **Konya 0,8158** · Rize 0,6974 · **Van 0,8267**. Belgedeki
  0,832 ve 0,821 hiçbir EDA tablosunda yok. Sıralama da değişiyor: Van, Konya'nın **üstünde**.
  (`ABLATION_REVIEW.md` §6 B-6 doğru değerleri kullanıyor — iki belge çelişiyor.)
- **§4.5'in "(§2.5 il profili, günlük $k_t$ 0,697)" atfı yanlış bölüme gidiyor.**
  `ABLATION.md` §2.5 "Ölçekleyici karıştırıcısı elendi" bölümüdür; il profili orada yok.
  Aynı yanlış atıf §4.5'te bir, §1.2'de örtük olarak bir kez daha geçiyor.
- **§4.4'ün başlığı "10 kol × 3 tohum" diyor, tablo 12 satır.** Spearman gerçekten on kol
  üzerinden hesaplanmış (doğrulandı, $\rho = 0{,}8424$); başlık ile tablo uyuşmuyor.
- **§6.2'nin "aynı dict, tek alan farkı" iddiası konfigürasyon düzeyinde doğru, kod düzeyinde
  eksik.** `abl_rize_all5_s*_full` 2026-08-29'da koştu; `target_transform` ekseni
  (`d16fd2b`) 2026-08-30'da geldi ve o commit `experiment.py`'nin layout geçişine
  `extra_target_columns=(CLRSKY,)` ekledi. Ham kolların `config.json`'ında
  `target_transform` **alanı hiç yok** (varsayılandan çıkarılıyor). Diff'i denetledim:
  eğitim yolunda hiçbir değişiklik yok, dolayısıyla risk düşük — ama "alan alan aynı" cümlesi
  "aynı kod sürümünde koştular" anlamına gelmiyor ve 2.6'daki tekrarlanabilirlik bulgusundan
  sonra bu ayrım bedava değil.
- **`ABLATION_REVIEW.md` §2.2'nin ufuk eğrisi yanlış referans kola dayanıyor.**
  Rakamları yalnızca `[64,32]` = `abl_rize_all5_s*_l1` alındığında çıkıyor; oysa §4.2
  referansı açıkça `abl_arch_base_s*` olarak tanımlıyor ve ikisinin farkı 0,49 W/m²'dir
  (2.6). Doğru referansla U'nun dibi $h = 15$'te değil **$h = 20$**'de ve −0,57 değil −1,79.

---

## 3. Fazla iddialar ve düzeltilmesi gerekenler

Hakeme ulaşırsa vereceği zarara göre sıralı.

**F-1 — §3.5'in kalibrasyon hükmü. İŞARETİ TERS. (en yüksek zarar)**
"Bootstrap bileşeni kalibrasyonu çözdü / K3 yanlıştı" cümlesi beş ilin dördünde yanlış ve net
etki anlamlı biçimde kötüdür ($+0{,}0076$, $p = 0{,}0054$). Bu cümle makaleye girerse ve bir
hakem il tablosunu isterse savunulamaz. Doğru ifade: "*bootstrap bileşeni eksik-kapsanan ili
nominale getirir ve fazla-kapsayan dördünü daha da fazla kapsatır; net kalibrasyon etkisi
negatiftir, kazanç keskinlikte ve CRPS'tedir.*" Bu ifade aynı zamanda §7.7'nin yeniden
dağıtım çerçevesiyle **tutarlıdır** ve onu güçlendirir (bkz. K-4).

**F-2 — §4.6'nın "§5 geçerliliğini koruyor" cümlesi. GEREKÇESİ ÇÜRÜK.**
Rize'nin kapasite duyarsızlığından dört ilin sonucuna geçilemez; dört ilde kapasite kazancı
havuzlama kazancının 2,6–8,7 katıdır. §5'in hükmü **kapasiteye koşulludur** ve bu, T-5.3'ün
zaten yazdığı ama §4.6'nın sildiği bir kayıttır. Bir hakem "solo modelinizi en iyi hâlinde
koşmadınız" diyecektir ve bugün yanıtı yoktur.

**F-3 — §4.8'in "tekdüze" ve "istisnasız" ifadeleri. OLGUSAL OLARAK YANLIŞ.**
Dört ters adım, üç eşik ihlali. Kolay düzeltilir, ve düzeltilmiş hâli (ölçülmüş kırılma
noktası 4,27, Gauss'un 3,92'sine karşı) daha güçlü bir cümledir.

**F-4 — §2.6'nın "kalibrasyon çözüldü / eklenti ön koşul değil" hükmü. GERİ ALINMALI.**
$B{=}1$ aralık metriğinden kurulmuş (K-4 ihlali), Aggregate ortalamasından okunmuş, ve §4.8 ile
§6.5 tarafından zaten çürütülmüş. Belgede geri alınmamış tek büyük hüküm budur.

**F-5 — §5.5'in "hiçbiri anlamlı değil"i.** İki il anlamlı. Pratikte önemsiz, cümle olarak
yanlış.

**F-6 — §6.5'in mekanizma paragrafı. "GÖSTERİLDİ" DEĞİL, "ÖNERİLDİ" OLMALI.**
Ve ondan türeyen "skaler katsayı yetmez" sonucu buna dayandığı için aynı nitelemeyi
taşımalıdır. Mekanizmayı sınamak `test_predictions.npz` gerektirir ve **uzak makinede
koşulmalıdır.**

**F-7 — §1.11'in "nokta metrikleri arka uçlar arasında okunabilir" pratik kuralı.
KANITSIZ.** MPS'in kendi içindeki çekiliş farkı iddia edilen arka uç farkının 6 katı. Kural
tesadüfen doğru olabilir; kanıtı yok. Aralık metriği tarafı (Sonuç 2) ayakta ama $n = 1$.

**F-8 — §1.10'un determinizm iddiası. "CPU'DA" NİTELEMESİ EKLENMELİ.**
Makalenin tekrarlanabilirlik cümlesi bugünkü hâliyle koşuların %85'i için yanlıştır.

**F-9 — §5.6'nın iki yanlış $k_t$ değeri ve §4.5/§4.4'ün atıf/başlık hataları.** Kozmetik ama
`CLAUDE.md`'nin "sayı CSV'ye izlenebilir olmalı" kuralını ihlal ediyor.

**F-10 — `ABLATION_REVIEW.md` §6 B-8'in tamamı.** Bu incelemenin 2.6'sı onu geçmiştir; eski
hâliyle makaleye taşınmamalıdır.

---

## 4. Görülmemiş katkılar

Sıralama: kanıt gücü × yenilik × makalenin argümanına katkı. Hepsi **yeni koşu gerektirmez**
(aksi belirtilmedikçe); hepsinin kanıtı diskte.

---

### K-1. `clearsky_index`, modeli **her iklim kuşağında eşit derecede becerikli** hâle getiriyor — `raw` yapmıyor

**Ne.** İklimsel ortalama tabanına karşı gündüz RMSE beceri skoru (skill), il bazında:

| | Ankara | Antalya | Konya | **Rize** | Van | yayılım/ort |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `raw` `all5` | %11,0 | %10,9 | %10,0 | **%18,7** | %13,4 | **%67,7** |
| **`kt` `all5`** | **%20,3** | **%20,9** | **%19,3** | **%23,1** | **%22,5** | **%17,8** |

`kt` altında model her ilde iklimsel ortalamayı **%19,3–23,1** ile geçiyor; iller arası yayılım
`raw`'a göre **3,8 kat** daralıyor.

**Neden güçlü.** Bu, §6'nın hiç kurmadığı ikinci ve bağımsız bir `kt` argümanıdır. §6 "kt
mutlak doğrulukta %9–13 daha iyi" diyor — bir hakem "beş ilde de mi, yoksa kolay illerde mi?"
diye sorar. Yanıt burada: `kt` en çok **zor** ili değil, herkesi eşitliyor. Makalenin
"beş farklı iklim kuşağı" seçimi ancak böyle bir cümleyle kazanca dönüşür; şu anda beş kuşak
seçilmiş ama sonuçta yalnızca "Rize kötü" deniyor.

**Ek analiz.** Yok — `results_summary.csv` ve `baseline_climatology` yeter. MAE ve CRPS için
aynı tablo üretilmeli. Altı tohuma çıkarılırsa (`target_kt_full`) ölçümün s.h.'si de verilir.

**Güç: yüksek.** Tek zayıflık: `kt` kolları üç tohum.

---

### K-2. Ölçülmüş bir **tekrarlanabilirlik tabanı**: CPU bit düzeyinde deterministik, MPS değil

**Ne.** 2.6'daki beş mükerrer konfigürasyon çifti. CPU çifti altı ondalık basamağa kadar
aynı; dört MPS çifti gündüz Aggregate RMSE'de %0,43–0,60, tek il düzeyinde **%1,47** farklı.
Bu, kimsenin kurmadığı bir deney değil — **ledger'da zaten duran, kazara üretilmiş dört
tekrardır.**

**Neden güçlü.**
1. **Metodolojik katkı.** Derin öğrenmeli güneş tahmini yazınında "tohum sabitlendi" cümlesi
   rutin olarak tekrarlanabilirlik iddiası olarak yazılır. Bu çalışma, aynı tohum + aynı
   konfigürasyon + farklı arka uç kombinasyonunda o iddianın **ne kadar tuttuğunu ölçebilen**
   nadir çalışmalardan biridir, çünkü ledger'ı mükerrer konfigürasyonu tespit edecek kadar
   eksiksizdir. Ölçülmüş taban: **nokta metriklerinde %0,5, il düzeyinde %1,5, aralık
   metriklerinde %1,2.**
2. **Yorumlama aracı.** Bu taban, hangi etkilerin okunabileceğini belirler. §7'nin `kt`
   etkilerinin çoğu (Van −0,95, Konya −0,06, Antalya +0,39) bu tabanın **içindedir** — yani
   §7'nin "net kazanç yok" hükmü yalnızca istatistiksel güç eksikliği değil, **ölçüm çözünürlüğü
   eksikliğidir** de. Bu, T-7.1'i ("bu bir yokluk sonucu değildir") güçlendirir.
3. **Tasarım sonucu.** Aralık metriklerinin çok-tohumlu ortalaması tek arka uçtan gelmelidir —
   `device` sütunu tam da bunun için var ve şimdi kullanılacak bir sayıya sahip.

**Ek analiz.** Yönün sistematik mi rastgele mi olduğu ayrılmalı: üç MPS çiftinin farkı da aynı
yönlü. En ucuzu iki-üç ek `abl_arch_base` tekrarıdır (~%5 ek maliyet) — bu tek istisnayı
**koşu önermek** olarak işaretliyorum, çünkü karşılığı doğrudan makalenin yöntem bölümüdür.

**Güç: yüksek.** Yeri: Yöntem, tekrarlanabilirlik; ve her ablasyon bölümünün eşik cümlesi.

---

### K-3. `kt`'nin taban çizgisi zaferi **$h \le 9$ tarafından taşınıyor**; gün-öncesi ufukta baz çizgisi hâlâ kaybediliyor

**Ne.** `baselines.py`'nin üç kuralı da 24 saatlik gecikme kuralıdır, dolayısıyla ufuk boyunca
**sabittir** (iklimsel ortalama gündüz RMSE 106,85–106,88; akıllı kalıcılık 108,89–109,19).
Modelin marjı ise ufukla çöküyor. Gündüz MAE'de modelin kaybetmeye başladığı ufuk:

| | iklimsel ortalamaya karşı | kalıcılığa karşı | **akıllı kalıcılığa karşı** |
| --- | ---: | ---: | ---: |
| `raw` $B{=}8$ | $h = 23$ | $h = 8$ | **$h = 4$** |
| `kt` $B{=}8$ | hiç | hiç | **$h = 10$** |

İklimsel ortalamaya karşı RMSE beceri skoru: `raw` $h{=}1$ 0,376 → $h{=}24$ **0,033**;
`kt` 0,465 → **0,149**.

**Neden güçlü — ve neden acil.** §6.4'ün manşeti ("`kt` ile MAE eşiği toplulaştırılmışta
geçiliyor: 59,16 < 60,19") **doğrudur ama yalnızca 24 ufkun ortalamasında doğrudur.**
$h = 10$'dan itibaren `kt` de akıllı kalıcılığa MAE'de her adımda kaybediyor (+0,84'ten
+3,17'ye). Makale kendisini "24 saat ilerisi tahmin" diye tanımlıyor; bir hakem $h = 24$
satırını hesaplayacak ve tabanın geçilmediğini görecek. `ABLATION_REVIEW.md` O-6 çerçeveyi
"1–24 saatlik profil tahmini" olarak yeniden adlandırmayı zaten öneriyordu; **bu, o önerinin
sayısal gerekçesidir ve ondan çok daha keskindir.**

Bunu gizlemek yerine kurmak gerekir, ve kurulacak cümle güçlüdür: *24 saatlik gecikmeye
dayanan naif kurallar ufuktan bağımsızdır; öğrenilmiş model kısa ufuklarda onları büyük farkla
geçer ve marjı ufukla azalır — çünkü $h$ büyüdükçe her iki taraf da aynı son gözleme
dayanır.* $h = 24$'te iki tarafın aynı bilgiye sahip olması, karşılaştırmanın **tek adil**
olduğu noktadır ve orada `kt` iklimsel ortalamayı hâlâ %14,9 geçiyor.

**Ek analiz.** `results_by_horizon.csv` + üç taban çizgisi dosyası; hepsi mevcut. İl kırılımı
için `metrics.py`'ye il × ufuk çıktısı gerekir (K-9).

**Güç: yüksek.** Yeri: Sonuçlar, taban tablosunun altında bir şekil (ufka göre beceri skoru).

---

### K-4. **Yeniden dağıtım** bir `kt` tuhaflığı değil, bu tasarımdaki her varyans azaltmanın imzasıdır

**Ne.** §7.7 havuzlamanın `kt` altında kalibrasyonu Rize lehine, üç il aleyhine yeniden
dağıttığını gösteriyor ($p_{\text{net}} = 0{,}995$). Aynı örüntü **iki eksende daha** var ve
ikisi de fark edilmemiş:

| eksen | Rize | diğer dört il | net | $p_{\text{net}}$ |
| --- | ---: | ---: | ---: | ---: |
| havuzlama, `kt` (§7.7, bilinen) | −0,0307 | +0,0002 … +0,0160 | +0,00001 | 0,995 |
| **havuzlama, `raw`** (2.5) | −0,0030 | −0,0017 … +0,0032 | −0,00054 | **0,0254** |
| **$B{=}1 \to B{=}8$** (2.7a) | **−0,0345** | **+0,0147 … +0,0215** | **+0,0076** | **0,0054** |

Üç ayrı müdahale — daha çok veri, daha çok model, daha iyi hedef parametrelemesi — **aynı
şeyi** yapıyor: en kötü kalibre edilmiş ili nominale çekiyor, iyi kalibre edilmişleri fazla
kapsamaya itiyor.

**Neden güçlü.** §7.8 yeniden dağıtımı "makale için en güçlü çerçeve" ilan ediyor ama tek bir
eksende ölçülmüş olarak sunuyor, dolayısıyla bir hakem "kt'ye özgü bir tuhaflık" diyebilir.
Üç eksende gösterildiğinde iddia **tasarımın yapısal bir özelliği** hâline gelir ve
mekanizmayla birleşir: aralık epistemik yayılıma göre boyutlanıyor, epistemik yayılım da
sinyal düzeyiyle ölçekleniyor (K-5), dolayısıyla varyansı azaltan her şey aralığı **her yerde
aynı oranda** daraltıyor — oysa daralması gereken yer ile miktar ile ayrışıyor. Bu, §3.5,
§4.8, §6.5'in üç ayrı teşhisini **tek bir mekanizmada birleştirir.**

**Ek analiz.** Yok. Üç satırlık bir tablo yeter.

**Güç: yüksek.** Yeri: Tartışma, kendi başına bir alt bölüm; conformal katmanın gerekçesi.

---

### K-5. Aralık genişliği **ilin iklimsel ışınım düzeyine** kilitli, zorluğuna değil — ve bu, conformal ızgaranın ölçülmüş hedefidir

**Ne.** İl bazında, `raw` `all5`, gündüz:

| | Ankara | Antalya | Konya | **Rize** | Van | yayılım/ort |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| MPIW / ort. gündüz ışınım | 1,168 | 1,136 | 1,158 | 1,237 | 1,146 | **%8,7** |
| MPIW / RMSE | 4,93 | 5,43 | 5,06 | **3,50** | 5,14 | **%40,2** |
| gündüz CP | 0,9842 | 0,9837 | 0,9813 | **0,9521** | 0,9829 | |

MPIW ile ilin ortalama gündüz ışınımı arasındaki Pearson $r = \mathbf{+0{,}998}$, ve
**bu ilişki Rize'ye dayanmıyor** (leave-one-out aralığı +0,973…+1,000) — bu projedeki tüm il
düzeyi korelasyonlar arasında outlier'a dayanmayan tek ilişkidir.

**Neden güçlü.** Aralığın sabit tutması **gereken** oran (MPIW/RMSE) %40 oynuyor; sabit
tuttuğu şey ise iklimsel düzey (%8,7). Bu, §4.8'in mekanizma iddiasının doğrudan, il bazında,
ölçülmüş kanıtıdır — §4.8 onu yalnızca mimari ekseni üzerinden dolaylı olarak gösteriyordu.
Ayrıca §4.8'in oran yasasının **üçüncü** kırıldığı yerdir: Rize 3,50 oranla CP 0,952
veriyor (yasa "eksik kapsama" diyor), `kt` altında 3,44 oranla 0,911.

Ve pratik: bu, il × ufuk conformal ızgarasının **ne kadar oynaması gerektiğini** verir.
Ölçülmüş düzeltme faktörleri (nominal 0,95'e getirmek için gereken çarpan tahmini) bu
tablodan doğrudan türetilebilir.

**Ek analiz.** Yok, `results_summary.csv` + `descriptive_stats_by_city_daylight.csv` yeter.

**Güç: yüksek.**

---

### K-6. §6'nın a priori gerekçesi EDA'da **zaten vardı** — `kt` post hoc bir keşif olmak zorunda değil

**Ne.** `base_features.parquet` üzerinde, gündüz satırları ($n = 151.643$):

| | ALLSKY (ham) | $k_t$ |
| --- | ---: | ---: |
| (il, ay, saat) hücresinin açıkladığı gündüz varyansı | **%85,6** | **%25,2** |
| $\eta^2$(günün saati), havuzlanmış | 0,499 | **0,012** |
| değişim katsayısı (gündüz) | 0,744 | 0,269 |
| gündüz-çifti ACF, gecikme 6 / 12 | **−0,343 / −0,506** | +0,741 / +0,407 |

Günün saatinin açıkladığı varyans `kt`'ye geçişte **41 kat** çöküyor. Ve %85,6 rakamı,
`outputs/eda/tables/persistence_baseline.csv`'de raporlanan iklimsel ortalama gündüz
$R^2 = 0{,}8564$ ile **aynı sayıdır** — yani EDA "gündüz hedefinin %85,6'sı deterministik bir
geometrik arama tablosudur" cümlesini zaten kurmuştu, sadece "öyleyse astronomiyi bölerek
atın" adımını atmamıştı.

**Neden güçlü.** §6 şu anda §3.6'nın MAE açığından doğmuş bir *post hoc* düzeltme gibi
okunuyor. EDA kanıtıyla birlikte sunulduğunda **öngörülmüş bir sonuç** olur: "veri
çözümlemesi hedefin %86'sının astronomi olduğunu gösterdi; onu ayırdık; hata %9–13 düştü."
Bu, aynı ölçümlerle çok daha güçlü bir anlatıdır. Ek olarak `raw`'ın gündüz ACF'sinin 6–12
gecikmede **negatife** düşmesi (LSTM'in 24 saatlik geriye bakışının önemli bir kısmının
anti-korelasyonlu geometri olduğu anlamına gelir) `lookback` ablasyonunun (B-2) fiziksel
açıklamasını verir — §4'ün B-2'si şu anda yalnızca "ölçtük, fark yok" diyor.

**İki nitelendirme, ikisi de yeni:**
- `kt` **günlük** durağandır, **mevsimsel** değil: $\eta^2$(ay) 0,139 → 0,150'ye *çıkıyor*
  (Antalya 0,159 → 0,284). Kalan mevsimsellik bulut mevsimselliğidir, yani modellenmesi
  gereken şeyin ta kendisi.
- Hedefin **şekli tersine dönüyor**: `raw` gündüz çarpıklık +0,44 / fazla basıklık −0,93;
  `kt` çarpıklık **−1,13** / fazla basıklık **+0,49**. EDA §8'in yüzdelik-CI gerekçesi ham
  dağılımın şekline dayanıyordu ve manşet kol `kt` olursa o gerekçe yeniden yazılmalıdır.
  Bu asimetri ayrıca §6.5'in CP düşüşünün (0,977 → 0,928) doğrudan mekanik açıklamasıdır.

**Ek analiz.** `time_feature_explained_variance.csv`'ye bir `kt` sütunu eklemek (`eda.py`'de
birkaç satır). Koşu yok.

**Güç: yüksek.**

---

### K-7. Havuzlama kazancı, ilin bulutluluk **düzeyini** değil **değişkenliğini** takip ediyor — §5.6 var olan bir ilişkiye null raporluyor

**Ne.** §5.6 kazancın "ne $k_t$ ile ne solo hata düzeyiyle tekdüze bir ilişki göstermediğini"
söylüyor ve mekanizma önermeyi reddediyor. İki öngörücüye baktığı için. Üçüncüsü çalışıyor:

| öngörücü | $\rho$ (`raw` havuzlama kazancı, %RMSE) | **tam permütasyon $p$** | Rize atıldığında Pearson |
| --- | ---: | ---: | ---: |
| **günlük $k_t$ s.s.** | **+0,900** | 0,083 | +0,725 → **+0,870** |
| **kapalı gün payı** | **+0,900** | 0,083 | +0,569 → **+0,949** |
| kış günlük toplam CV | +0,900 | 0,083 | — |
| günlük $k_t$ ortalaması | −0,800 | 0,133 | — |
| solo RMSE düzeyi | +0,600 | 0,350 | — |

Kazanç sırası Van < Antalya < Konya < Rize < Ankara; $k_t$ s.s. sırası Van < Antalya < Konya <
Ankara < Rize — **yalnızca Ankara ile Rize yer değiştiriyor.**

**Neden değerli.** İki nedenle. Birincisi §5.6'nın hükmünü null'dan mekanizmaya çeviriyor:
*havuzlama, ilin bulut rejimi ne kadar **değişkense** o kadar yardımcı oluyor* — çünkü yerel
sinyal gürültülüyken ödünç alınacak paylaşılan hava yapısı daha çoktur. Bu, §5.5'in
"havuzlama aralığı her ilde daraltıyor" bulgusuyla tutarlıdır. İkincisi ve daha önemlisi,
bu projedeki **tek** il düzeyi ilişki ki Rize atıldığında **güçleniyor** (+0,725 → +0,870);
diğer her korelasyon tek bir aykırı değerin artefaktıdır.

**Dürüst uyarı — ve bu da bir katkı.** $n = 5$ ile Spearman yalnızca 21 farklı değer alabilir
ve **elde edilebilecek en küçük iki yanlı tam $p$, $2/120 = 0{,}0167$'dir**, o da yalnızca
$\rho = \pm 1$'de. `scipy`'nin asimptotik $p$'si aynı veri için 0,037 verir — yani
$n = 5$'te asimptotik $p$ **yanıltıcıdır** ve bu belgede tam permütasyon kullanılmıştır. Bu
bir yöntem notu olarak makaleye girmeye değer: beş illik bir çalışmada il düzeyi korelasyonlar
**hiçbir zaman** anlamlı olamaz, dolayısıyla betimleyici olarak sunulmalıdır.

**Ek analiz.** Yok.

**Güç: orta–yüksek** ($\rho$ güçlü ve outlier'a dayanmıyor; $n = 5$ nedeniyle iddia
betimleyici olarak kurulmalı).

---

### K-8. Kapasite kazancı **kısa ufukta**, havuzlama kazancı **uzun ufukta** — ve gün-öncesi tahmin uzun ufuktur

**Ne (kapasite tarafı, doğrulanmış ve sıkılaştırılmış).** `[64,32]` → `[128,64]`, gündüz
RMSE, `abl_arch_base` referansıyla, eşleştirilmiş üç tohum:

| $h$ | 1 | 2 | 3 | 4 | 6–20 | 22 | 23 | 24 |
| --- | ---: | ---: | ---: | ---: | :-: | ---: | ---: | ---: |
| kazanç (W/m²) | 15,90 | 12,98 | 10,29 | 5,74 | 1,79–6,11 | 2,78 | 4,96 | 6,22 |
| $p$ | 0,0001 | 0,0018 | 0,0001 | 0,045 | **hepsi a.d.** | 0,023 | 0,012 | 0,024 |

Yani doğru ifade `ABLATION_REVIEW.md` §2.2'nin "kazanç uçlarda toplanıyor"undan daha
keskindir: **$h = 6 \ldots 20$ aralığında `[128,64]`'ün `[64,32]`'ye üstünlüğü sıfırdan
ayırt edilemez.** `[128,64]` → `[256,128]` için de aynı: $h \le 6$'da anlamlı, $h \ge 9$'dan
itibaren düz (0,17–2,04 W/m², $p$ = 0,35–0,95).

U şekli her **kapasite artıran** müdahalede var (`dropout 0,2` dâhil: 121× derinlik), hiçbir
kapasite azaltan müdahalede yok — yani bu bir "genişlik" özelliği değil, kapasitenin genel
özelliğidir.

**İki uyarı, ikisi de yeni.** (i) U'nun uzak ucu, `raw` kollarına özgü bir **kuyruk
hızlanmasıyla** karışıyor: $h = 22$–24'te `abl_arch_base` 100,57 → 106,23 tırmanırken
`h128x64` 97,79 → 100,02'de kalıyor. Yani "$h = 24$'te kapasite PACF tepesini sömürüyor"
açıklaması ile "küçük model kuyrukta daha hızlı bozuluyor" açıklaması ayrılmamıştır; §2.2
birincisini tek açıklama gibi sunuyor. (ii) Kuyruk hızlanması **on beş `raw` kolunun
hepsinde** var (RMSE($h{=}24$)/ort. RMSE($h{=}16..20$) = 1,010–1,075) ve **hiçbir `kt` kolunda
yok** (1,005–1,021) — yani bir formülasyon artefaktıdır, veri özelliği değil.

**Ne (havuzlama tarafı — ve burada bir düzeltme).** "Havuzlama kazancı ufukla büyüyor"
sonucunu `results_by_horizon.csv`'den okumak **caziptir ve yanlıştır**: o dosyalarda il sütunu
yoktur, dolayısıyla solo kolun eğrisi bir il, `all5`'inki beş ildir; aradaki 13–19 W/m²'lik
"kazanç" Aggregate tuzağıdır. **Geçerli olan yol solo kollardır** — her solo kolun Aggregate'i
zaten o ilin kendisidir. Oradan çıkan tablo (aşağıda K-9) bu ayrımı yapıyor ve gerçek bir
per-il ufuk yapısı veriyor.

**Ek analiz.** Kapasite tarafı için yok. Havuzlama tarafı için `metrics.py`'ye il × ufuk
çıktısı (K-9) gerekir.

**Güç: yüksek** (kapasite tarafı); havuzlama tarafı **koşullu**.

---

### K-9. İl × ufuk yapısı: **Rize ufukla diğerlerinden iki kat hızlı bozuluyor**, ve `kt` bunu daha da kötüleştiriyor

**Ne.** Solo kollardan (her birinin Aggregate'i tek il olduğu için geçerli), $B = 8$, üç tohum:

| formülasyon | il | RMSE $h_1 \to h_{24}$ | oran | CP $h_1 \to h_{24}$ |
| --- | --- | --- | ---: | --- |
| `raw` | Ankara | 74,9 → 96,4 | ×1,287 | 0,9932 → 0,9737 (−0,020) |
| `raw` | Antalya | 72,5 → 90,7 | ×1,250 | 0,9904 → 0,9791 (−0,011) |
| `raw` | Konya | 75,1 → 99,0 | ×1,318 | 0,9946 → 0,9676 (−0,027) |
| `raw` | Van | 76,1 → 98,6 | ×1,295 | 0,9917 → 0,9736 (−0,018) |
| **`raw`** | **Rize** | **80,2 → 120,7** | **×1,506** | **0,9845 → 0,9126 (−0,072)** |
| `kt` | Ankara | 63,3 → 84,8 | ×1,339 | 0,9338 → **0,9400 (+0,006)** |
| `kt` | Antalya | 61,4 → 78,5 | ×1,280 | 0,9307 → **0,9473 (+0,017)** |
| `kt` | Konya | 64,3 → 86,5 | ×1,345 | 0,9396 → 0,9278 (−0,012) |
| `kt` | Van | 68,0 → 86,3 | ×1,268 | 0,9429 → 0,9361 (−0,007) |
| **`kt`** | **Rize** | **68,2 → 111,7** | **×1,638** | **0,9130 → 0,8600 (−0,053)** |

Ve `kt`'nin ufuk boyunca sağladığı iyileşme (aynı ilin solo kollarında):

| il | $h{=}1$ | $h{=}9$ | $h{=}18$ | $h{=}24$ |
| --- | ---: | ---: | ---: | ---: |
| Ankara | −%15,5 | −%10,2 | −%10,5 | −%12,1 |
| Antalya | −%15,4 | −%11,1 | −%12,1 | −%13,4 |
| Konya | −%14,5 | −%9,8 | −%10,5 | −%12,7 |
| Van | −%10,6 | −%9,3 | −%8,3 | −%12,5 |
| **Rize** | −%14,9 | **−%5,2** | **−%6,0** | −%7,5 |

**Üç yeni cümle, hepsi ölçülmüş.**
1. **Ufka göre bozulma il-özgüdür ve iklimle açıklanır.** Dört il ×1,25–1,35 ile bir bantta;
   Rize ×1,51. Yani Rize'nin "yüksek hatası" bir düzey kayması değil, **ufukla farklı bir
   eğimdir** — bulut alanlarının kalıcılık ufku diğer illerden kısadır. Bu, §2.5'in il
   profilinin şu ana kadar hiç yapılmamış dinamik versiyonudur.
2. **Kapsamanın ufukla çöküşü bir `raw` özelliğidir.** `kt` altında Ankara ve Antalya'nın
   CP'si ufukla **yükseliyor**. `ABLATION_REVIEW.md` §3.3'ün "uzun ufukta eksik kapsama"
   uyarısı manşet `kt` olursa büyük ölçüde ortadan kalkar — Rize hariç.
3. **`kt`'nin kazancı en çok berrak illerde.** Zarfı bedava vermek, gökyüzünün gerçekten
   berrak olduğu yerde en çok işe yarıyor (−%8…−%13), Rize'de en az (−%5…−%7,5). Bu, §7'nin
   mekanizma açıklamasının ("havuzlamanın satın aldığı şey paylaşılan zarftı") bağımsız bir
   doğrulamasıdır: zarfın değeri il başına ölçülebiliyor ve bulutlulukla ters orantılı.

**Ek analiz.** Bu tablo mevcut CSV'lerden çıkıyor. **Ama havuzlanmış kolun il × ufuk
kırılımı yok** — `metrics.py`'ye `results_by_city_horizon.csv` eklemek ve bitmiş koşuları
`test_predictions.npz`'den yeniden skorlamak gerekir (`fee7fc0` commit'i bunun tam olarak
nasıl yapıldığının kalıbıdır: yeniden eğitim olmadan). **Bu, npz'lerin bulunduğu uzak makinede
koşulmalıdır.**

**Güç: yüksek** (solo kollar için hazır), havuzlanmış kol için bir yeniden skorlama gerekir.

---

### K-10. Gece aralıklarının **tam olarak sıfır** genişlikte olduğunun 126 koşuluk doğrulaması

**Ne.** 126 koşunun **hepsinde**
$\text{MPIW}(\text{all\_hours}) = 0{,}51535 \times \text{MPIW}(\text{daylight})$, beş ondalık
basamağa kadar, ve 0,51535 tam olarak gündüz eleman payıdır. Ek olarak `Reliability` ≡
$|CP - 0{,}95|$ (maks. mutlak hata $2{,}1 \times 10^{-16}$) ve `CWC` ≡ `PINW` her yerde
$CP \ge 0{,}95$.

**Neden değerli.** `CLAUDE.md` "all-hours CP inşa gereği şişkindir" diyor ve bunu niteliksel
olarak açıklıyor. Bu, o cümlenin **tam mekanik ispatıdır** ve bir satıra sığıyor: gece
elemanlarının aralığı dejenere $[0,0]$ ve gerçek değeri 0 olduğundan, karışımın %48,8'i model
katkısı olmadan 1,0'dır. Bir hakemin "neden gündüz alt kümesini raporluyorsunuz" sorusuna
verilecek en kısa yanıt budur. Ayrıca `clamp_night_to_zero`'nun beyan ettiği şeyi gerçekten
yaptığının 126 koşuluk denetimidir.

**Yan not — `CWC` yayımlanamaz.** 18 deneyde 333 satırda CWC > 100, maksimum
$1{,}02 \times 10^8$. Üstel ceza nedeniyle CWC farkları kollar arası ölçeklenebilir değildir;
bir bayrak olarak raporlanmalı, basamaklı bir tablo sütunu olarak değil.

**Güç: orta** (küçük ama tamamen sağlam ve bedava).

---

### K-11. Test penceresinin kışı **anormal derecede karanlık** — hiçbir tehdit listesinde yok

**Ne.** `outputs/eda/tables/monthly_target_stats.csv`: test penceresinin kış ayları, tüm
yılların ortalamasına göre Van −%11,9, Rize −%11,6, Ankara −%7,7 daha düşük ışınıma sahip.

**Neden değerli.** `ABLATION.md`'nin **her** manşet sayısı bu pencere üzerinde skorlanmıştır.
Kronolojik bölme doğru seçimdir ve dört mevsim özelliği korunmuştur — ama "test kümesi dört
mevsimi kapsıyor" cümlesi "test kümesi tipik bir yılı temsil ediyor" anlamına gelmiyor.
Bir hakem bunu sorabilir; §0'ın okuma kurallarına ve tehdit listelerine ait bir maddedir ve
şu anda hiçbirinde yok. Ölçülmüş ve dosyada.

**Güç: orta** (tehdit olarak yüksek değer, bulgu olarak düşük).

---

### K-12. Doğrulama kaybıyla seçim disiplininin **ölçülmüş** maliyeti sıfır

**Ne.** On tek-eksenli kol üzerinde `best_val_loss` ↔ gündüz test RMSE Spearman
$\rho = 0{,}842$ ($p = 0{,}0022$); on iki kolun tamamında 0,909; iki `lookback` kolu (pencere
sayısını değiştiren, dolayısıyla kriteri sınırda kılan iki kol) çıkarılınca **0,939**.

**Neden değerli.** `ABLATION_REVIEW.md` B-9 bunu zaten işaretledi ama 21 koşu üzerinden ve
kolların hangileri olduğunu ayırmadan. Yeni olan, **kriterin nerede bozulduğunun ölçülmüş
olmasıdır**: kriterin geçerli olmadığı tek kol ailesi (`lookback`, çünkü ölçekleyici ve
pencere sayısı değişiyor) çıkarıldığında korelasyon 0,84'ten 0,94'e çıkıyor. Yani §4.3'ün
"bu iki kol sınırda" uyarısı **ölçülmüştür**, sadece iddia edilmemiştir. Test kümesinin model
seçimine karışmadığını ve bunun bir maliyeti olmadığını gösteren cümle böyle kurulur.

**Güç: orta.**

---

### K-13. Kullanılmayan EDA ve ondan doğan ucuz makale cümleleri

`ABLATION.md` 18 EDA tablosunun **3'üne**, `main_methodology.md` ve `CLAUDE.md` **sıfırına**
atıf yapıyor; hiçbir EDA şekli aşağı akışta referanslanmıyor. Doğrudan makale cümlesine
dönüşebilecekler:

- **İller arası günlük eğri farkının ~%70'i bir *zamanlama kayması*dır, şekil farkı
  değil** (EDA §4.1). Bu, tek-küresel-model + il gömmesi tasarımının en doğrudan ampirik
  gerekçesidir ve hiçbir belgede yok. `CLAUDE.md`'nin "saat, yerel güneş saatidir"
  değişmezinin de tamamlayıcısıdır.
- **Rüzgâr yönü öznitelikleri muhtemelen bilgisiz** ($R = 0{,}091$ havuzlanmış); 17
  özniteliğin **4'ü**, girdi vektörünün %24'ü. Hiç ablasyon edilmemiş. Bu bir koşu
  gerektirir ama tek koldur ve makaleye "öznitelik seçimi yapıldı" cümlesini kazandırır.
- **Ramp (|Δ$k_t$| > p90) kırılımlı CP/PINW**, EDA §8'in açıkça önerdiği ve `metrics.py`'de
  bulunmayan alt küme. §6.5'in teşhis ettiği kusuru (aralık zorlukla koşullanmıyor) **tam
  olarak** hedefliyor. Uygulanması `metrics.py`'ye bir alt küme eklemek ve npz'lerden yeniden
  skorlamaktır — yeniden eğitim yok.
- **Sakin saat rüzgâr yönü kodlaması açık tehdidi kapatılabilir ve yanlış alarmdır:**
  `WD10M == 0,0` 295.920 satırın **265'inde** (%0,09), bunların yalnızca 66'sı sakin;
  sentinel değer yok. Bir satır maliyetiyle kapanan bir tehdit.
- **Van 1215,88 W/m² artefaktı** (`kt = 3{,}28`) `clearsky_index` altında p99'u 1,000 olan bir
  dağılımda 3,28'lik bir hedeftir. L1 altında etkisi sınırlıdır ama §6.7'de bir cümle hak
  ediyor.

**Güç: orta**, ama toplam maliyeti neredeyse sıfır.

---

### K-14. Bir **negatif sonuç** olarak: normalize edilmiş hata illeri eşitlemiyor — ve bunu bilmek zaman kazandırır

**Ne.** "İklim için normalize edince model her yerde eşit iyidir" cazip bir cümledir ve
**ölçülmüş olarak yanlıştır**:

| istatistik | min | maks | menzil/ort |
| --- | ---: | ---: | ---: |
| gündüz RMSE (W/m²) | 84,65 | 106,27 | %23,5 |
| RMSE / ort. gündüz ışınım | %20,9 | %35,4 | **%57,8** |
| RMSE / gündüz ışınım s.s. | 0,297 | 0,431 | %40,0 |

Rize hem en düşük ortalama ışınıma hem en yüksek RMSE'ye sahip olduğu için oran birleşiyor ve
yayılım **artıyor**. Aynı biçimde, $n = 5$'te il düzeyi korelasyonların hepsi tek bir aykırı
değerin kaldıracıdır (RMSE ~ $k_t$ ortalaması $r = -0{,}981$ → Rize atılınca **−0,732**;
RMSE ~ kapalı gün payı +0,949 → **+0,295**). **Tek istisna K-7'dir.**

**Neden değerli.** İki nedenle: (i) K-1'in *işleyen* normalizasyonunu (taban çizgisine karşı
beceri skoru) bir alternatifler kümesi içinde konumlandırır, dolayısıyla K-1 keyfi bir seçim
gibi görünmez; (ii) bu incelemenin yapmadığı ama makalede kolayca yapılabilecek bir hatayı
kapatır. Negatif sonuç olarak yayımlanmasa da, K-1 ve K-7'yi kurarken arka planda durması
gerekir.

**Güç: orta** (negatif sonuç; asıl işlevi K-1/K-7'yi savunmak).

---

## 5. Öneriler

Sırayla, gerekçesiyle.

**Ö-1 — Önce yazıyı düzelt, koşu yok (yarım gün).** F-1'den F-9'a kadarki maddeler. En kritik
üçü: §3.5'in kalibrasyon hükmünün işaretini düzeltmek, §4.6'nın "§5 geçerliliğini koruyor"
gerekçesini T-5.3'e geri döndürmek, §4.8'in "tekdüze/istisnasız"ını ölçülmüş 4,27 eşiğiyle
değiştirmek. Bunlar makaleye taşınmadan önce yapılmalı, çünkü hepsi **hakemin
doğrulayabileceği** olgusal ifadelerdir ve düzeltilmiş hâlleri orijinallerinden daha güçlüdür.
Aynı geçişte §5.6'nın iki yanlış $k_t$ değeri ve §4.5'in yanlış atfı da düzelsin.

**Ö-2 — Tekrarlanabilirlik tabanını sağlamlaştır (≈%5 ek maliyet, tek koşu önerisi).**
`abl_arch_base` konfigürasyonunun iki-üç tekrarı, aynı arka uçta, art arda (eşzamanlı iş
olmadan). Amaç: MPS farkının sistematik mi (ortam/çekişme) yoksa rastgele mi olduğunu ayırmak.
Bu, K-2'yi bir gözlemden ölçüme çevirir ve **makalenin yöntem bölümünün doğruluğunu**
belirler; ayrıca §7'nin her etki büyüklüğünün okunabilirlik eşiğini verir. Bu inceleme boyunca
önerilen tek koşu budur ve en ucuzu.

**Ö-3 — `metrics.py`'ye il × ufuk çıktısı ekle ve bitmiş koşuları yeniden skorla (eğitim
yok).** `fee7fc0` bunun kalıbıdır. Bu tek değişiklik dört katkının kilidini açıyor: K-3'ün il
kırılımı, K-8'in havuzlama tarafı, K-9'un havuzlanmış kolu, ve §6.5'in mekanizma testi için
gereken CLRSKY-desil kırılımı. **`test_predictions.npz` gerektirdiği için uzak makinede
koşulmalıdır** ve çıktıları git'e girmelidir. Aynı geçişte EDA §8'in ramp alt kümesi de
eklenebilir (K-13).

**Ö-4 — `kt` manşetini K-1 + K-9 ile kur, ve §6.4'ün ufuk kırılımını (K-3) önden yaz.**
§7.8 zaten `kt` manşetini öneriyor; eksik olan iki şey onu savunulabilir kılıyor: her ilde
eşit beceri (K-1) ve `kt`'nin ufuk boyunca ne yaptığı (K-9). Ve K-3'ün açığı ($h \ge 10$'da
akıllı kalıcılığa MAE kaybı) makalede **hakemden önce** yazılmalıdır — `ABLATION_REVIEW.md`
O-6'nın "1–24 saatlik profil tahmini" yeniden adlandırması bu yüzden benimsenmelidir.

**Ö-5 — Rize'nin kapasite duyarsızlığını etkileşim testiyle yeniden yaz (2.3).** Hüküm doğru,
kanıt yanlış testten geliyor; doğru test ücretsiz ve $p = 0{,}033$–0,049 veriyor. Aynı anda
"merdivenin ikinci basamağında da sürüyor" cümlesi çıkarılmalı ($p = 0{,}22$).

**Ö-6 — §5'in açık tehdidini (F-2) kapatmak için tek gerçek pahalı koşu: `[128,64]` solo
kolları.** Dört il × üç tohum, ölçülmüş solo maliyeti ~547 s → ≈1,8 sa. Bu, "havuzlama beş
ilin hepsinde iyileştiriyor" hükmünün kapasiteye koşulsuz olup olmadığını sınayan tek
deneydir ve §4'ün ölçtüğü kapasite kazançları (dört ilde havuzlama kazancının 2,6–8,7 katı)
sonucun tersine dönmesini **fiziksel olarak makul** kılıyor. Her iki sonuç da yayımlanabilir;
tersine dönerse §7.8'in "yeniden dağıtım" çerçevesi `raw` altında da geçerli olur ve K-4 üç
eksen yerine dört eksen kazanır. **Bunu §4'ün merdivenini $B{=}8$'e taşımaktan önce
koşmayı öneririm** — merdiven ikinci ondalık basamağı hedefliyor, bu manşet iddianın dış
geçerliliğini hedefliyor.

**Ö-7 — EDA'yı modelleme anlatısına bağla (koşu yok).** K-6 (§6'nın a priori gerekçesi),
K-13'ün zamanlama-kayması cümlesi, K-11'in karanlık kış tehdidi. Bunların hiçbiri yeni ölçüm
gerektirmiyor ve üçü birlikte "veriye baktık, ne yapacağımıza karar verdik, ölçtük" anlatısını
kuruyor — şu anda EDA ile modelleme birbirine değmiyor.

**Ö-8 — Ertelenmeli: §4'ün merdivenini $B{=}8$'e taşımak, ve mimari kararını conformal
katmanla birlikte vermek.** §4.6 bunu "sıradaki tek karar noktası" ilan ediyor. Katılmıyorum:
`kt` manşet olacaksa (§7.8) merdiven **`kt` altında yeniden koşulmalıdır** (T-7.5 bunu zaten
söylüyor) ve `raw` altındaki $B{=}8$ ölçümü o durumda çöpe gider. Sıra: Ö-3 (bedava, dört
katkıyı açıyor) → Ö-6 (manşetin dış geçerliliği) → `kt` altında merdiven → conformal.

---

## Kaynaklar

| Ne | Nerede |
| --- | --- |
| Ledger, 126 satır × 51 sütun | `outputs/experiments_ledger.csv` |
| İl bazlı metrikler | `outputs/experiments/<id>/metrics/results_summary.csv` (`subset == "daylight"`) |
| Ufuk bazlı metrikler (il sütunu **yok**) | `outputs/experiments/<id>/metrics/results_by_horizon.csv` |
| Tek eksen ispatı | `configs/experiment_grid.py:612-616` (`assert differing == {"target_transform"}`) |
| Mükerrer konfigürasyon çiftleri | `abl_arch_base_s{42,43,44}` ↔ `abl_rize_all5_s{42,43,44}_l1`; `abl_parity_mps_s42` ↔ `abl_rize_solo_s42_l1`; `abl_loss_mse_s42_b1` ↔ `abl_rize_all5_s42_b1` |
| Kod farkı denetimi | `git show 2e3c209 268eb66 75ba063 d16fd2b` — eğitim yolunda değişiklik yok |
| İl iklimolojisi | `outputs/eda/tables/{clearness_index_by_city,daily_clearness_by_city,descriptive_stats_by_city_daylight,monthly_target_stats,persistence_baseline,time_feature_explained_variance,wind_direction_circular_stats}.csv` |
| $k_t$ / ham ACF ve $\eta^2$ hesapları | `outputs/processed/base_features.parquet` üzerinde yeniden hesaplandı |
| Taban çizgileri | `outputs/experiments/baseline_{climatology,persistence,smart_persistence}/` |
| Önceki inceleme | `ABLATION_REVIEW.md` (§1–§3); bu belge onun §6 B-8'ini geçersiz kılar ve §2.2'nin referans kolunu düzeltir |
