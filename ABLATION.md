# Ablasyon çalışmaları

Bu belge, makalenin modelleme iddialarının **tek eksen değiştirilerek** sınandığı ablasyon
koşularını toplar. Her bölüm kendi içinde bağımsızdır: sınanan iddia, hipotezler, kolların tam
konfigürasyonu, sonuç tabloları, karıştırıcı (*confound*) çözümlemesi, hüküm ve geçerlilik
tehditleri. Yeni bir ablasyon eksenine geçildiğinde belge **yeniden yazılmaz**; §A'daki şablona
uyan yeni bir `## N.` bölümü eklenir.

Her sayı `outputs/experiments/<experiment_id>/metrics/results_summary.csv` veya
`outputs/experiments_ledger.csv` dosyasından okunmuştur ve tablolarda hangi satırın okunduğu
açıkça yazılıdır. Çakışma hâlinde CSV esastır.

---

## 0. Bu belge nasıl okunur

Bu bölüm, belgedeki **her** tabloyu bağlar. Yeni bir bölüm eklendiğinde §0 yeniden yazılmaz,
yalnızca §0.3'ün matrisine satır eklenir.

### 0.1 Okuma kuralları

**(K-1) İl bazlı satır okunur, `Aggregate` satırı okunmaz.** Havuzlama eğrisinin kolları farklı
il kümeleri üzerinde eğitilir ve *farklı il kümeleri üzerinde skorlanır*; dolayısıyla
`Aggregate` satırları farklı popülasyonları kapsar ve kollar arasında karşılaştırılamaz.
Ölçülmüş örnek (smoke doğruluğunda, yalnızca gösterim amaçlı): Rize'ye Ankara eklendiğinde
`Aggregate` satırı gündüz RMSE'yi 115,83 → 107,56 gösterir, oysa `Rize` satırının gerçek
değişimi 115,83 → 113,13'tür. Aradaki fark model değil, ortalamaya karışan kolay Ankara
satırlarıdır. Her kolun `Rize` satırı **aynı** 109.043 gündüz elemanını kapsar (`n_elements`),
dolayısıyla karşılaştırma eleman-elemandır.

**(K-2) Başlık rakamı gündüz alt kümesidir** (`CLRSKY_SFC_SW_DWN > 0`, elemanların ≈%51,2'si).
Kalan %48,8 geometrik olarak gecedir, hedefleri tam sıfırdır ve `clamp_night_to_zero` onları
kesin sıfırlar. Gece satırları her modelin RMSE'sini bedavaya ~%28 düşürür ve R²'yi şişirir —
aynı iklimsel ortalama 24 saatte R² 0,923, gündüzde 0,856 verir. **Manşet, 24 ufuk adımının
havuzlanmış gündüz değeridir**; ufuk adımı bazlı kırılım tanısaldır, manşet değildir (§0.2).

**(K-3) Zemin çift eşiklidir.** İklimsel ortalamanın gündüz RMSE'si (106,86) *ve* akıllı
kalıcılığın gündüz MAE'si (60,19). İkisi birden geçilmeden "sonuç" yoktur. Naif kurallar 24
saat gecikmeli aramalardır ve **ufuk boyunca düzdür**, model ise bozulur; bu yüzden eşik
karşılaştırması ufuk adımı bazında da verilmelidir (§6.4).

**(K-4) Aralık metrikleri $B$'ye, kritere ve hedef dönüşümüne koşulludur — asla eksenler
arasında karşılaştırılmaz.** Havuzlanan öngörü dağılımı yalnızca epistemik belirsizlik taşır;
aleatorik terim hiçbir yerde eklenmez. $B{=}1$ satırlarının aralıkları yalnızca MC-Dropout
kaynaklıdır ve $B{=}8$ satırlarıyla **karşılaştırılamaz**. Ayrıca kalibrasyonun kendisi üç
ayrı eksende bozulur ve hiçbiri diğerini düzeltmez: doğruluk ($B$, §3.5), kapasite (B-8, §4.6)
ve formülasyon (§6.5). Bir kalibrasyon iddiası, hangi eksende ölçüldüğü söylenmeden yazılamaz.

**(K-5) Tek ilden genelleme yapılmaz — "Rize tuzağı".** Rize, transferin de doğruluğun da en
çok işe yaraması beklenen ildir; orada ölçülen bir etkinin **büyüklüğü üst sınırdır ve işareti
bile** diğer dört ile taşınmayabilir. Bu belgede iki kez oldu: §3.5 (bootstrap kalibrasyonu
"çözdü" sanıldı, il bazında dördünü bozuyordu) ve §7.4 (transferin belirsizliğe taşındığı
sanıldı, net etki sıfırdı). **Beş il kolu koşulmadan hiçbir "şu mekanizma şöyle çalışıyor"
cümlesi yazılmaz.**

**(K-6) Her bulgu bir konfigürasyona koşulludur** (§0.2, §0.3). Her `## N` bölümü bir
**geçerlilik künyesi** ile başlar; bulgular yalnızca o künyenin içinde geçerlidir.

**(K-7) Atıflar bölüm numarasına değil bulgu kimliğine yapılır.** Bölümler yeniden
numaralandırılabilir; `B-8`, `H1`, `T-4.5` gibi kimlikler sabittir. Bölüm numarası yalnızca
kolaylık için parantez içinde verilir.

### 0.2 Referans konfigürasyon — bulguların ölçüldüğü zemin

Aksi künyede belirtilmedikçe her bölüm bunu kullanır. Alan adları `ExperimentConfig`'in
alanlarıdır; ayrıntı `README.md`'nin konfigürasyon tablosunda.

| eksen | referans değer | nerede tanımlı |
| --- | --- | --- |
| **veri kümesi** | NASA POWER saatlik, 5 il, `LAST_VALID_TIMESTAMP`'e kadar kesilmiş; $F = 17$ öznitelik; `ALLSKY_KT` düşürülmüş; `CLRSKY_SFC_SW_DWN` maske sütunu (öznitelik değil) | `config.py`, `main_methodology.md` §3–§5 |
| **hedef** | `ALLSKY_SFC_SW_DWN`, `target_transform="raw"` | `main_methodology.md` §5.4 |
| **pencereleme** | `lookback=24`, `horizon=24`, `stride=1` | §8 |
| **bölme** | kronolojik, `train_ratio=0,74`, `val_ratio=0,11`, tam çerçeve üzerinde | §6 |
| **mimari** | `hidden_sizes=[64,32]`, `dropout=0,3`, `city_embedding_dim=4` | §9 |
| **optimizasyon** | `lr=1e-3`, `batch=128`, `lr_reduce_patience=7` | §10.2 |
| **kriter** | `loss_function`: §1 `mse`, §2 sonrası **`mae`** | §10.1.1 |
| **doğruluk** | `ABLATION_FULL`: $B=8$, $T=100$, `max_epochs=200`, `early_stop_patience=15`<br>`ABLATION_B1`: $B=1$, $T=100$, `max_epochs=100`, `early_stop_patience=15` | `configs/experiment_grid.py` |
| **kapsam** | beş il havuzlanmış (`training_scope="global"`, `excluded_cities=[]`) | §13.1 |
| **gece** | `clamp_night_to_zero=True` | §11.3 |
| **tekrarlanabilirlik** | CPU'da bit-birebir; **MPS'te değil** — havuzlanmışta ±%0,5, il bazında ±%1,5 (§1.10) | §13.3 |

**Bu tabanın altındaki farklar okunamaz.** MPS tekrar yayılımı ölçülmüş bir çözünürlük
sınırıdır; ondan küçük bir tek-koşu farkı, kaç tohum koşulursa koşulsun bir bulgu değildir.
Çok tohumlu eşleştirilmiş testler geçerliliğini korur, çünkü raporlanan tohum standart
sapmaları bu gürültüyü zaten içerir.

### 0.3 Değişiklik takip matrisi — bir eksen değişirse hangi bulgular yeniden ölçülmeli?

Bu belgenin ana kullanım biçimi budur. Mimari ya da veri kümesi değiştiğinde, bulguların
hangilerinin **taşındığı varsayılamayacağı** buradan okunur. Sütun "kanıt", o taşımamanın
ölçülmüş bir örneği varsa onu gösterir.

| değişen eksen | yeniden ölçülmesi gereken | neden / kanıt |
| --- | --- | --- |
| **`target_transform`** (`raw` → `kt`) | **§1–§5'in tamamı** — H1, transfer eğrisi, uç nokta ablasyonu, mimari merdiveni | **ÖLÇÜLDÜ, TAŞIMADI** (§7): havuzlamanın nokta kazancı kümelenmiş $p=0{,}0146$'dan $0{,}218$'e düştü ve işareti tutarsızlaştı. Kalibrasyon net sıfır oldu ($p=0{,}995$). Bu, belgedeki en güçlü "bulgular formülasyona koşulludur" kanıtıdır. |
| **`hidden_sizes` / kapasite** | aralık metriklerinin **tamamı**; B-8'in oran eşiği; nokta bulgularının **büyüklüğü** (işareti değil) | ÖLÇÜLDÜ (B-8, §4.6): CP 0,954 → 0,844, MPIW/RMSE 4,29 → 2,73. Nokta sıralaması korunur ama iller **eşit yararlanmaz** (B-7: Rize etkileşimi $+5{,}51$ puan, $p=0{,}032$). |
| **`loss_function`** | tüm nokta ve aralık metrikleri; havuzlama kazancının **büyüklüğü** | ÖLÇÜLDÜ (§1.5, §2.4): MSE→L1 havuzlama kazancını −1,53'ten −5,11'e büyüttü. Kriter değişirse eğri yeniden koşulur. |
| **$B$ (`n_bootstrap`)** | aralık metriklerinin **tamamı**; havuzlama kazancının büyüklüğü | ÖLÇÜLDÜ (§3.2, §3.5): $B{=}1 \to B{=}8$ H1'i −5,11'den −2,70'e indirdi ve kalibrasyonu **net olarak bozdu** ($p=0{,}0054$). $B$ farklı iki satır asla karşılaştırılmaz. |
| **öznitelik kümesi** ($F$) | **her şey.** Ledger'ın `n_features` sütunu bunu görür ama eski satırlar yeni satırlarla karşılaştırılamaz | ÖLÇÜLMEDİ. $F{=}18 \to 17$ geçişinde tüm eski satırlar geçersiz sayılıp yeniden koşulmuştu (`TODOs.md`). |
| **veri kümesi tazelenmesi** (yeni xlsx) | **her şey**, ve önce `LAST_VALID_TIMESTAMP` / `EXPECTED_TRIMMED_ROWS_PER_SHEET` / `FULL_ROWS_PER_SHEET` birlikte güncellenmeli | `data.py` bütünlük kontrolleri uyarmaz, **hata fırlatır**. Bölme tarihleri kayar, dolayısıyla `n_elements` değişir ve hiçbir eski satır karşılaştırılabilir olmaz. |
| **il kümesi** (yeni il eklenmesi) | havuzlama bulgularının tamamı; `CITY_TO_ID` **yeniden numaralandırılmaz** | Gömme tablosu `len(CITIES)` boyutundadır; yeni il eklemek gömmeyi ve bölme sayımlarını değiştirir. |
| **`lookback` / `horizon` / `stride`** | her şey — pencere sayısı ve `n_elements` değişir | ÖLÇÜLDÜ (B-2, §4.5): 48/72 saat referansı iyileştirmiyor, ama eğitim süresini iki katına çıkarıyor. |
| **cihaz** (`MERVE_DEVICE`) | hiçbiri — ama **tek koşu farkları** okunamaz hâle gelir | ÖLÇÜLDÜ (§1.10): MPS determinist değildir. Çok tohumlu ortalamalar tek bir arka uçtan gelmelidir. |
| **`clamp_night_to_zero`, gündüz maskesi** | tüm-saat metriklerinin tamamı; gündüz metrikleri etkilenmez | Gece elemanları tanım gereği kapsanır; tüm-saat CP yapısal olarak şişer. |
| **`conformal_mode`** | tüm aralık metrikleri (CP/PINW/MPIW/CWC/Reliability) **ve CRPS**; nokta metrikleri (RMSE/MAE/R²) tanım gereği **etkilenmez** | UYGULANDI (§8). Varsayılan `"none"`; ledger sütunu. Bir conformal satır yalnız aralığıyla ikizinden ayrılır. §6.5'in "il × ufuk" önerisi ölçülüp **yanlış çıktı**: ufuk ekseni null (C-1), doğru ikinci eksen **mevsim** (C-3, C-5). |
| **mevsimsel bileşim** (bölme oranları, veri penceresi) | conformal ızgaranın **tamamı**; kalibrasyon kümesinin hangi ayları kapsadığı doğrudan $k$'yi belirler | ÖLÇÜLDÜ (C-5, §8.4): $k$ yıl içinde 1,67–2,51 kat oynuyor. `train_ratio`/`val_ratio` değişirse doğrulama bölmesinin ay kapsaması ve dolayısıyla ızgara yeniden ölçülmelidir. |

### 0.4 Bölüm haritası

| bölüm | eksen | doğruluk | kriter | hedef dönüşümü | durum |
| --- | --- | --- | --- | --- | --- |
| §1 | havuzlama (Rize eğrisi), aşama 1'de kayıp seçimi | $B{=}1$ | mse → mae | raw | §2 ve §3 tarafından kısmen geçersiz kılındı |
| §2 | aynı eğri, L1 | $B{=}1$ | mae | raw | §3 tarafından üstünlendi |
| §3 | aynı eğri, tam doğruluk | $B{=}8$ | mae | raw | **birincil sonlanım noktası (H1)** |
| §4 | mimari merdiveni | $B{=}1$ | mae | raw | açık: kazanan mimari $B{=}8$'de ölçülmedi |
| §5 | beş il uç nokta ablasyonu | $B{=}8$ | mae | raw | tamam |
| §6 | hedef dönüşümü | $B{=}8$ | mae | **raw vs kt** | tamam |
| §7 | transferin formülasyona dayanıklılığı | $B{=}8$ | mae | kt | tamam; §1–§5'i koşullu kılar |
| §8 | conformal aralık katmanı, ızgara geometrisi | **$B{=}1$ + smoke** | mae/mse/huber | raw **ve** kt | geometri seçildi; **tam doğrulukta ölçülmedi** |

## 1. İl havuzlama (cross-city transfer) — Rize transfer eğrisi

> **Geçerlilik künyesi** — bu bölümün bulguları yalnızca bu konfigürasyonda geçerlidir (§0.2, §0.3).
>
> | veri kümesi | hedef dönüşümü | mimari | doğruluk | kriter | kapsam | tohum | cihaz |
> | --- | --- | --- | --- | --- | --- | --- | --- |
> | $F=17$, referans | `raw` | `[64,32]`, do 0,3 | $B{=}1$, $T{=}100$ | aşama 1 `mse`/`mae`/`huber`, aşama 2 `mse` | Rize eğrisi (5 kol) | 42 (kısmen 42–44) | cpu |
>
> **Bu bölümün hükümlerinin bir kısmı §2 ve §3 tarafından geçersiz kılınmıştır** (§2.4, §3.4). Ayrıca $B{=}1$ olduğu için aralık metrikleri K-4 gereği $B{=}8$ bölümleriyle karşılaştırılamaz.


### 1.1 Sınanan iddia

`main_methodology.md` (satır 56–59):

> **Küresel (global) model:** İl başına ayrı model eğitilmez. Beş ilin verisi tek bir modelde
> birleştirilir ve il kimliği yalnızca öğrenilen bir gömme vektörü olarak modele girer. Bu,
> makalenin iddialarından biridir: farklı iklim rejimleri arasında bilgi transferi sağlanır ve
> her il için ayrı ayrı eğitilmiş modellere kıyasla veri verimliliği artar.

İddia yönlüdür: havuzlama **her bir ilin** tahminini, o il için ayrı eğitilmiş modele kıyasla
iyileştirmelidir. Çalışma bu yönde kurulmuştur — Rize dışarı çıkarılmaz, **diğerleri** çıkarılır
ve Rize'nin bozulması izlenir. Her kol Rize'nin kendi test pencerelerinde skorlanır; bölme
sınırları dışlamadan **önce** tam çerçeveden hesaplandığı için bu pencereler bütün kollarda
birebir aynıdır (`experiment.py::run_experiment`, `compute_split_boundaries`).

### 1.2 Hipotezler ve onları doğuran EDA kanıtı

Rize en keskin sınavdır, çünkü EDA onu ayrı bir iklim rejimine yerleştirir
(`outputs/eda/tables/clearness_index_by_city.csv`, `descriptive_stats_by_city_daylight.csv`,
`daily_clearness_by_city.csv`; tartışma `outputs/eda/EDA.md` §1):

| Gösterge | Rize | Diğer dört il |
| --- | --- | --- |
| Günlük berraklık indeksi $k_t$ | **0.697** | 0.806 – 0.840 |
| Kapalı gün payı ($k_t < 0.3$) | **%8.0** | %0.97 – 2.80 |
| Gündüz hedef ortalaması (W/m²) | **300.4** | 377.1 – 404.6 |
| Günlük toplam (kWh/m²/gün) | **3.69** | 4.66 – 4.98 |
| Günler arası değişim katsayısı | **0.569** | 0.440 – 0.493 |
| En iyi mevsimi (yaz, günlük $k_t$) | **0.772** | diğerlerinin *kışına* yakın (0.679 – 0.750) |

Rize aynı zamanda modelin karşılığını verdiği yerdir: küresel bir ön koşu klimatoloji tabanını
Rize'de %14.1, diğerlerinde yalnızca %0.2–3.0 geçmiştir.

- **H1 —** Rize'nin tahmin hatası, eğitime daha fazla il katıldıkça **monoton olarak azalır.**
- **H2 —** Kazanç yalnızca veri hacmi etkisi değildir: **hangi** ilin eklendiği önemlidir.

H2 ayrı bir hipotezdir çünkü eğri boyunca eğitim kümesi büyüklüğü de artar; monoton bir eğri tek
başına "daha çok veri" ile "daha çeşitli veri"yi ayıramaz.

### 1.3 Kolların tam konfigürasyonu

Bütün kollar `configs/experiment_grid.py::_rize_curve_configs()` tarafından **tek bir fonksiyondan**
üretilir; kollar arasında yalnızca aşağıdaki tabloda görünen alanlar değişir.

**Ortak ayarlar — `ABLATION_FULL`** (tüm kollarda birebir aynı):

| Alan | Değer | Alan | Değer |
| --- | --- | --- | --- |
| `lookback_hours` | 24 | `learning_rate` | $10^{-3}$ |
| `horizon_hours` | 24 | `batch_size` | 128 |
| `window_stride` | 1 | `early_stop_patience` | 15 |
| `train_ratio` | 0.74 | `lr_reduce_factor` / `lr_reduce_patience` | 0.5 / 7 |
| `val_ratio` | 0.11 | `nonneg_penalty_weight` | 0.1 |
| `hidden_sizes` | [64, 32] | `mc_dropout_passes` | 100 |
| `dropout_rate` | 0.3 | `bootstrap_block_length` | 168 |
| `city_embedding_dim` | 4 | `clamp_night_to_zero` | True |
| `model_family` | lstm | `loss_daylight_only` | False |

`max_epochs` ve `early_stop_patience`, `ExperimentConfig` varsayılanlarının (100 / 10) üzerine
bilerek çıkarılmıştır: tek il gören bir model aynı `batch_size` ile epok başına beşte bir
optimizasyon adımı görür, dolayısıyla varsayılan sabır fiilen beş kat sıkıdır. İki uç de aynı
cömert bütçeyi alır ki hiçbiri kırpılmış eğitim üzerinden yargılanmasın.

**Kola göre değişen alanlar** (bölme sınırları her kolda aynı: `train_end = 2024-06-27 19:00`,
`val_end = 2025-03-26 01:00`):

| # | `experiment_id` | Aktif iller | `excluded_cities` | `training_scope` | `loss_function` | `seed` | Eğitim pencereleri |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **Aşama 1 — kayıp seçimi** ||||||||
| 1 | `abl_loss_mse_s42_b1` | 5 il | — | global | **mse** | 42 | 218 745 |
| 2 | `abl_loss_mae_s42_b1` | 5 il | — | global | **mae** | 42 | 218 745 |
| 3 | `abl_loss_huber_s42_b1` | 5 il | — | global | **huber** ($\delta=1$) | 42 | 218 745 |
| **Aşama 2 — transfer eğrisi** ||||||||
| 4 | `abl_rize_solo_s42_b1` | Rize | Ankara, Antalya, Konya, Van | **per_city** | mse | 42 | 43 749 |
| 5 | `abl_rize_solo_s43_b1` | Rize | " | per_city | mse | 43 | 43 749 |
| 6 | `abl_rize_solo_s44_b1` | Rize | " | per_city | mse | 44 | 43 749 |
| 7 | `abl_rize_plus_ankara_s42_b1` | Rize, Ankara | Antalya, Konya, Van | global | mse | 42 | 87 498 |
| 8 | `abl_rize_plus_antalya_s42_b1` | Rize, Antalya | Ankara, Konya, Van | global | mse | 42 | 87 498 |
| 9 | `abl_rize_minus_antalya_s42_b1` | Rize, Ankara, Konya, Van | Antalya | global | mse | 42 | 174 996 |
| 10 | `abl_rize_all5_s42_b1` | 5 il | — | global | mse | 42 | 218 745 |
| 11 | `abl_rize_all5_s43_b1` | 5 il | — | global | mse | 43 | 218 745 |
| 12 | `abl_rize_all5_s44_b1` | 5 il | — | global | mse | 44 | 218 745 |

Tek il için `training_scope="per_city"` zorunludur: `ExperimentConfig.__post_init__` tek illi bir
"global" konfigürasyonu reddeder, çünkü ledger satırı koşunun taşıyamayacağı bir iller-arası
sonuç iddia ederdi.

Dışlanan illerin gömme (embedding) satırları **yeniden numaralandırılmaz**: `CITY_TO_ID` sabittir
ve model her koşuda tam `len(CITIES)` satırlık bir gömme tablosu tutar; dışlanan ilin satırı
yalnızca hiç gradyan almaz. Numaralandırma değişseydi kayıtlı her checkpoint'teki her kimliğin
anlamı sessizce kayardı.

**Yeniden üretim.** Aşağıdaki komutlar tek tek her kolu üretir (`--only` yerine tüm grup için
`--group rize_curve_b1`):

```bash
uv run python scripts/01_prepare_base_data.py          # bir kez; outputs/processed/base_features.parquet
uv run python scripts/run_all_experiments.py --group rize_curve_b1 --only abl_loss_mse_s42_b1
uv run python scripts/run_all_experiments.py --group rize_curve_b1 --only abl_loss_mae_s42_b1
uv run python scripts/run_all_experiments.py --group rize_curve_b1 --only abl_loss_huber_s42_b1
uv run python scripts/run_all_experiments.py --group rize_curve_b1 --only abl_rize_solo_s42_b1
uv run python scripts/run_all_experiments.py --group rize_curve_b1 --only abl_rize_solo_s43_b1
uv run python scripts/run_all_experiments.py --group rize_curve_b1 --only abl_rize_solo_s44_b1
uv run python scripts/run_all_experiments.py --group rize_curve_b1 --only abl_rize_plus_ankara_s42_b1
uv run python scripts/run_all_experiments.py --group rize_curve_b1 --only abl_rize_plus_antalya_s42_b1
uv run python scripts/run_all_experiments.py --group rize_curve_b1 --only abl_rize_minus_antalya_s42_b1
uv run python scripts/run_all_experiments.py --group rize_curve_b1 --only abl_rize_all5_s42_b1
uv run python scripts/run_all_experiments.py --group rize_curve_b1 --only abl_rize_all5_s43_b1
uv run python scripts/run_all_experiments.py --group rize_curve_b1 --only abl_rize_all5_s44_b1
```

Tümünü sırayla, kesinti hâlinde kaldığı yerden devam ederek çalıştırmak için:

```bash
uv run python scripts/run_all_experiments.py --group rize_curve_b1 --skip-existing --continue-on-error
```

`--skip-existing`, `metrics/results_summary.csv` dosyasının varlığına bakar (henüz eğitim
başlamadan yazılan `config.json`'a değil), dolayısıyla yarıda kalmış bir koşu yeniden çalışır,
tamamlanmış olan atlanır — ve bu, "bir `experiment_id` yeniden kullanılmaz" kuralını kendiliğinden
uygular.

### 1.4 Doğruluk (fidelity) — bu koşuların `ABLATION_FULL`'dan farkı

**Bu kolların hepsi `n_bootstrap=1` ile koşmuştur ve id'leri bu yüzden `_b1` ile biter.**
Beyan edilen tam doğruluk (`ABLATION_FULL`: `n_bootstrap=8`, `mc_dropout_passes=100`,
`max_epochs=200`) bu makinede çalışmıyordu. Ölçüm — gerçek pencereler üzerinde zamanlama probu,
CPU-only ana makine, 12 çekirdek, torch 6 iş parçacığı:

| Eğitim kümesi | Pencere | s/epok | s/MC-geçiş |
| --- | --- | --- | --- |
| 5 il (havuzlanmış) | 218 745 | 25.7 | 1.83 |
| 4 il | 174 996 | ~20.6 | ~1.46 |
| 2 il | 87 498 | 9.9 | 0.72 |
| Rize tek | 43 749 | 5.0 | 0.37 |

Bu birim maliyetlerle on iki kollu çalışma, $B=8$ ve erken durdurma 40. epokta devreye girerse
**≈22 saat**, her replika 200-epok tavanına dayanırsa **≈96 saattir**. Bu bütçeye sığmıyordu.

Verilenler ve neden bunların verilebileceği:

- **`n_bootstrap` 8 → 1.** Bu ayrı bir kod yolu değil, `experiment.py`'deki *sanksiyonlu hızlı
  yol*dur: yeniden örnekleme yok, tek LSTM, hâlâ yalnızca MC-Dropout ile skorlanıyor. UQ
  katmanının veri/örneklem bileşenini kaldırır — bu yüzden bu kolların aralık metrikleri
  MC-Dropout kaynaklıdır ve **bir $B=8$ satırıyla karşılaştırılamaz** (K-4). Bu çalışmanın
  okuduğu nokta metrikleri, $T=100$ stokastik geçişin ortalamasıdır.
- **`max_epochs` 200 → 100**, `early_stop_patience` 15'te sabit. **Ölçülen sonuç: bu kısıt hiçbir
  kolda bağlayıcı olmadı.** Erken durdurma 18–39 epok arasında devreye girdi ve `hit_max_epochs`
  ledger'daki on iki kolun **hepsinde 0**'dır. Yani 200 ile 100 arasındaki fark bu çalışmanın
  hiçbir sayısını etkilemez; tam doğruluktan maddi olarak sapan tek eksen `n_bootstrap`'tir.
- `mc_dropout_passes` **değişmedi** (100), dolayısıyla yüzdelik CI aynı örnek büyüklüğünden
  kestirilir.

**Gözlenen yakınsama epoğuyla güncellenen tam-doğruluk tahmini.** 200 değil ~25 epokta durulduğu
ölçüldüğüne göre, $B=8$ tam çalışma tek akışta **≈15 saattir** — bu makinede bir gecelik iş,
GPU'lu sunucuda çok daha azı. 22–96 saatlik ilk tahmin, epok tavanının bağlayıcı olacağı
varsayımından geliyordu; ölçüm bunu çürüttü. **Öneri: eğri, `--group rize_curve` ile tam
doğrulukta sunucuda tekrarlanmalıdır**; aşağıdaki hükümlerin çoğu tohum gürültüsüne takılıyor ve
$B=8$ havuzlaması nokta tahmininin varyansını düşürecektir.

**Gerçekleşen maliyet** (`training_time_sec`, ledger; 2–3 koşu paralel olduğu için çekirdek
çekişmesi içerir):

| Kol tipi | Kol | Süre |
| --- | --- | --- |
| 5 il | `abl_loss_huber_s42_b1` | 1 299 s (21 epok) |
| 5 il | `abl_loss_mse_s42_b1` | 1 344 s (23 epok) |
| 5 il | `abl_loss_mae_s42_b1` | 1 507 s (29 epok) |
| 5 il | `abl_rize_all5_s42_b1` | 3 325 s (23 epok, 3 yönlü çekişme) |
| 5 il | `abl_rize_all5_s43_b1` | 3 349 s (24 epok, 3 yönlü çekişme) |
| 4 il | `abl_rize_minus_antalya_s42_b1` | 621 s (24 epok) |
| 2 il | `abl_rize_plus_ankara_s42_b1` | 449 s (19 epok) |
| 2 il | `abl_rize_plus_antalya_s42_b1` | 534 s (39 epok) |
| Rize | `abl_rize_solo_s42/43/44_b1` | 332 / 223 / 268 s (23 / 18 / 26 epok) |

On iki kolun toplam işlemci süresi ≈ 14 280 s (`abl_rize_all5_s44_b1` tek başına, çekişmesiz,
1 026 s / 23 epok); iki paralel akışla duvar saati ≈ 3 saat.

**Cihaz sağlaması (device provenance).** On iki kolun tamamı **CPU** üzerinde üretilmiştir ve bu
artık ledger'da `device` sütunuyla kayıtlıdır. Bu, kozmetik bir ayrıntı değil: `get_device()`
sırası MPS > CUDA > CPU'dur, yani Apple Silicon bir makinede koşu sessizce MPS'e düşer ve
MPS/CUDA/CPU aynı tohumdan bit düzeyinde aynı sonucu vermez (`utils.py::set_seed` docstring'i,
metodoloji §13.3). `abl_rize_all5_s44_b1` önce bir Mac'te MPS üzerinde koşturulmuş, sonuç
**atılmış** ve kol kardeşleriyle (`s42`, `s43`) aynı CPU ana makinesinde yeniden üretilmiştir;
aksi hâlde aşağıdaki `all5` ortalama ± sd'si üç tohumun değil, iki cihaz sınıfının karışımı
olurdu. Somut risk yalnızca teorik değildir: `hidden_sizes=[64, 32]` iki katmanlı bir LSTM
demektir ve `model.py` bu durumda `nn.LSTM(..., dropout=0.3)` kurar; PyTorch'ta LSTM'in
**katman-arası** dropout'unun MPS'te CPU'dan saptığına dair açık bir kayıt vardır
([pytorch#173640](https://github.com/pytorch/pytorch/issues/173640), 2026-01-28 tarihli, henüz
kapanmamış — bu çalışma kapsamında bağımsız olarak doğrulanmamıştır). Bu dropout, MC-Dropout
gürültüsünün kaynaklarından biridir, yani en çok etkilenecek metrikler tam da belirsizlik
katmanınınkilerdir.

Bir koşuyu belirli bir arka uca sabitlemek için `MERVE_DEVICE` ortam değişkeni kullanılır:

```bash
MERVE_DEVICE=cpu uv run python scripts/run_all_experiments.py \
    --group rize_curve_b1 --only abl_rize_all5_s44_b1
```

Çok tohumlu bir kolun tohumları **aynı cihaz sınıfında** koşturulmalıdır; aksi hâlde ortalama ±
sd temiz değildir.

### 1.5 Aşama 1 sonuçları — kayıp fonksiyonu seçimi

Beş il sabit, yalnızca eğitim kriteri değişiyor. Kaynak:
`outputs/experiments/abl_loss_{mse,mae,huber}_s42_b1/metrics/results_summary.csv`.

**Gündüz alt kümesi (başlık), `Aggregate` satırı — beş kol da aynı beş il üzerinde skorlandığı
için burada `Aggregate` okunabilir** (K-1 yalnızca farklı il kümeleri eğitilen Aşama 2 için
bağlayıcıdır); 546 130 eleman:

| Kayıp | RMSE ↓ | MAE ↓ | R² ↑ | CP (kalibre değil) | CWC | CRPS ↓ | Epok |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MSE | 96.99 | 73.83 | 0.8818 | 0.8254 | 164.8 | 54.49 | 23 |
| **MAE (L1)** | **93.93** | **66.84** | **0.8891** | **0.9451** | **0.83** | **49.33** | 29 |
| Huber ($\delta=1$) | 94.49 | 72.86 | 0.8878 | 0.7998 | 594.8 | 54.21 | 21 |
| *Taban: klimatoloji* | *106.86* | *73.38* | *0.8565* | — | — | — | — |
| *Taban: akıllı kalıcılık* | *109.04* | *60.19* | *0.8506* | — | — | — | — |
| *Taban: kalıcılık* | *116.13* | *68.00* | *0.8305* | — | — | — | — |

Aynı kollar, **Rize** satırı (109 043 gündüz elemanı):

| Kayıp | RMSE ↓ | MAE ↓ | R² ↑ | CP | CRPS ↓ |
| --- | --- | --- | --- | --- | --- |
| MSE | 112.88 | 84.94 | 0.7898 | 0.7499 | 61.71 |
| MAE (L1) | 109.56 | **75.50** | 0.8020 | **0.8945** | **54.90** |
| Huber | **108.17** | 82.98 | **0.8070** | 0.7034 | 60.83 |
| *Taban: klimatoloji* | *130.68* | *95.72* | *0.7183* | — | — |
| *Taban: akıllı kalıcılık* | *136.66* | *85.23* | *0.6919* | — | — |
| *Taban: kalıcılık* | *141.89* | *90.89* | *0.6679* | — | — |

24 saatlik (ikincil) değerler, `Aggregate`: MSE 69.63 / 38.05 / 0.9366, MAE 67.43 / 34.45 /
0.9406, Huber 67.84 / 37.55 / 0.9398; klimatoloji tabanı 76.71 / 37.82 / 0.9231.

**Seçim: MAE (L1).** Ve bu, `config.py::LOSS_FUNCTIONS` altında yazılı beklentiyi **çürütür**.
Orada şöyle deniyordu: "L1 ile eğitmenin MAE'yi iyileştirmesi, RMSE'yi kötüleştirmesi beklenir;
ödünleşim bulgunun kendisidir." Ölçülen ödünleşim yok: L1 hem MAE'de (73.83 → 66.84, %9.5) hem
RMSE'de (96.99 → 93.93) MSE'yi geçiyor, hem de R²'de. Beklenti, kestirimcinin koşullu ortalama mı
medyan mı olduğu argümanına dayanıyordu; ölçülen davranış, sağa çarpık ve %48.8'i tam sıfır olan
bir hedefte L1'in optimizasyonu kolaylaştırdığı yönünde. **Bu cümlenin `config.py` içinde
düzeltilmesi gerekir** — şu hâliyle gerçekleşmemiş bir tahmini olgu gibi sunuyor.

İkinci ve daha çarpıcı gözlem: **MAE kolunun CP'si 0.9451**, MSE ve Huber kollarında 0.80–0.83
iken. `METHODOLOGY_REVIEW.md` K3, düşük kapsamayı *yapısal* saymıştı (havuzlanan dağılımda
aleatorik terim yok). Ölçüm bunu nitelendiriyor: yetersiz kapsama yapının tek başına sonucu değil,
**eğitim kriterine de bağlı** — L1 ile eğitilen modelin MC-Dropout yayılımı belirgin biçimde
geniştir. Bu bir kalibrasyon iddiası **değildir** (K-4: $B=1$, aleatorik terim hâlâ yok, tek
tohum); ama K3'ün "yalnızca conformal/rezidüel-varyans eklentisi çözer" çerçevesinin eksik
olduğunu gösterir ve tam doğrulukta tekrarlanmayı hak eder.

### 1.6 Aşama 2 sonuçları — transfer eğrisi

**Bütün satırlar `Rize` satırından okunmuştur** (K-1), `n_elements = 109 043` gündüz elemanı,
her kolda birebir aynı. Kaynak: her kolun `metrics/results_summary.csv` dosyası.
Kayıp fonksiyonu tüm eğri boyunca **MSE**'dir (bkz. §1.8, tehdit T-1).

**Gündüz (başlık):**

| Kol | Eğitim ili | Eğitim penceresi | RMSE ↓ | MAE ↓ | R² ↑ | CP | CRPS ↓ |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `solo` (3 tohum) | 1 (Rize) | 43 749 | **113.22 ± 2.15** | **85.07 ± 1.15** | 0.7885 ± 0.0080 | 0.7798 | 62.30 |
| `plus_ankara` (s42) | 2 (+Ankara) | 87 498 | **109.80** | 83.00 | 0.8011 | 0.7748 | 60.68 |
| `plus_antalya` (s42) | 2 (+Antalya) | 87 498 | **119.66** | 87.55 | 0.7638 | 0.7526 | 64.50 |
| `minus_antalya` (s42) | 4 | 174 996 | 111.77 | 84.60 | 0.7939 | 0.7759 | 60.85 |
| `all5` (3 tohum) | 5 | 218 745 | **111.68 ± 1.06** | **83.71 ± 1.08** | 0.7942 ± 0.0039 | 0.7747 | 60.82 |
| *Taban: klimatoloji* | — | — | *130.68* | *95.72* | *0.7183* | — | — |
| *Taban: akıllı kalıcılık* | — | — | *136.66* | *85.23* | *0.6919* | — | — |
| *Taban: kalıcılık* | — | — | *141.89* | *90.89* | *0.6679* | — | — |

Tekil tohum değerleri (s42/s43/s44): `solo` RMSE 115.21 / 110.93 / 113.50; `all5` RMSE
112.88 / 111.30 / 110.86. `all5`'in üç tohumu da `solo` ortalamasının altındadır, ama üçü de
`solo` aralığının içinde kalır.

**24 saat (ikincil), `Rize` satırı:**

| Kol | RMSE ↓ | MAE ↓ | R² ↑ | CP |
| --- | --- | --- | --- | --- |
| `solo` (3 tohum) | 81.21 ± 1.54 | 43.77 ± 0.59 | 0.8758 ± 0.0047 | 0.8867 |
| `plus_ankara` | 78.76 | 42.70 | 0.8832 | 0.8841 |
| `plus_antalya` | 85.83 | 45.04 | 0.8612 | 0.8727 |
| `minus_antalya` | 80.17 | 43.52 | 0.8789 | 0.8847 |
| `all5` (3 tohum) | 80.11 ± 0.76 | 43.07 ± 0.55 | 0.8791 ± 0.0023 | 0.8841 |
| *Taban: klimatoloji* | *93.73* | *49.31* | *0.8345* | — |

**Taban değerleri hakkında uyarı.** Yukarıdaki taban satırları, gece kelepçesi naif tabanlara
uygulanmadan önce üretilmiş `baseline_*` koşularından okunmuştur (`80876ce` bunu düzeltti; ledger
satırları yeniden üretilecektir). **Gündüz sayıları etkilenmez** — kelepçe yalnızca gece
elemanlarını sıfırlar, gündüz alt kümesi tanım gereği dokunulmamıştır. Değişecek olan yalnızca 24
saatlik taban satırlarıdır (iyileşecek yönde), dolayısıyla bu bölümün başlık tablosu sağlamdır,
ikincil tablonun taban satırı ise yeniden üretildiğinde güncellenmelidir.

**Her kol tabanı geçiyor.** En kötü kol (`plus_antalya`, 119.66) bile klimatolojinin Rize gündüz
RMSE'sini (130.68) %8.4 geçiyor. Yani sorun modelin işe yaramaması değil; sorun havuzlamanın
katkısının ölçülememesi.

### 1.7 Karıştırıcı çözümlemesi — hacim mi, bilgi mi?

Eğri boyunca eğitim kümesi 43 749 → 218 745 pencereye çıkar, dolayısıyla eğrinin şekli tek başına
"daha çok veri" ile "daha uygun veri"yi ayıramaz. Ayıran şey **çift kollardır**:

| | `plus_ankara` | `plus_antalya` |
| --- | --- | --- |
| Eğitim penceresi | 87 498 | 87 498 (**birebir aynı**) |
| Eklenen ilin günlük $k_t$'si | 0.806 (diğer dördün **en bulutlusu**) | 0.840 (**en güneşlisi**) |
| Rize gündüz RMSE | **109.80** | **119.66** |
| Rize gündüz MAE | 83.00 | 87.55 |
| Rize gündüz R² | 0.8011 | 0.7638 |
| Tohum | 42 | 42 |

Pencere sayıları eşit, mimari eşit, tohum eşit, kayıp eşit. Değişen tek şey **hangi il**. Fark
**9.86 W/m² RMSE** — `solo` üçlüsünden ölçülen tohum-düzeyi gürültü ölçeğinin (sd 2.15; iki
tek-tohumlu kolun farkı için $\sqrt{2}\times 2.15 = 3.04$) **yaklaşık 3.2 katı.**

Bunun lisans verdiği ve vermediği şeyler:

- **Lisans verdiği:** iller-arası havuzlamanın etkisi bir hacim etkisi değildir. Eşit hacimde,
  iklimsel olarak yakın bir ortak (Ankara, $k_t$ 0.806, Rize'nin 0.697'sine en yakın) yardım
  ederken uzak bir ortak (Antalya, 0.840) zarar verir. Etkinin **işareti** ortağa bağlıdır.
- **Ayrıca lisans verdiği, ve makale için daha rahatsız edici olanı:** `plus_antalya` (119.66),
  `solo` ortalamasından (113.22 ± 2.15) **3 standart sapma kötüdür**. Bu **negatif transferdir**:
  iklimsel olarak uzak bir ille havuzlamak Rize'yi, kendi başına eğitilmiş bir modelden daha kötü
  hâle getirir. Makalenin iddiası "havuzlama iyileştirir" biçiminde koşulsuz yazıldığı sürece bu
  ölçüm onunla çelişir.
- **Lisans vermediği:** çift kolların her biri **tek tohumludur**. 9.86'lık fark gürültü ölçeğinin
  ~3.2 katıdır, yani salt şans açıklaması olası değildir — ama dışlanmış da değildir. Yayına
  girecek bir H2 iddiası için iki çift kolun da üç tohumla koşulması gerekir
  (`abl_rize_plus_{ankara,antalya}_s{43,44}_b1`; ~1 000 s'lik ek maliyet, en ucuz eksik iş).

Şekle ilişkin ikinci gözlem: 4 il (111.77) ile 5 il (111.68 ± 1.06) arasında fark yoktur;
beşinci il **Antalya**'dır, yani çift kollarda zarar verdiği ölçülen ildir. İki bağımsız kol aynı
yöne işaret ediyor.

### 1.8 Hüküm

**H1 — "Rize'nin hatası havuzlanan il sayısıyla monoton azalır": DESTEKLENMEDİ.**

Eğri monoton değildir. Gündüz RMSE'si 113.22 (1 il) → 109.80 (2 il, Ankara) → 119.66 (2 il,
Antalya) → 111.77 (4 il) → 111.68 (5 il) izler; il sayısına göre sıralandığında bile artıp
azalır — ve son iki nokta pratikte aynıdır.

Dahası, iddianın taşıyıcı olduğu **uçlar arası fark ölçülemiyor**. Üç tohumla her iki uçta:
`solo` 113.22 ± 2.15'e karşı `all5` 111.68 ± 1.06, fark **−1.53 W/m²**. Ortalamalar farkının
standart hatası (tohumlar bağımsız çekilişlerdir, $n=3$) $\sqrt{2.153^2/3 + 1.063^2/3} = 1.39$,
yani gözlenen fark **≈1.1 standart hatadır** — tespit eşiğinin çok altında. MAE'de fark −1.36,
standart hata 0.91 (≈1.5 SH); her ikisinde de `solo` ve `all5` tohum aralıkları örtüşür
(`solo` [110.93, 115.21], `all5` [110.86, 112.88]).

Üçüncü `all5` tohumu eklendiğinde fark −1.12'den −1.53'e büyüdü ve `all5`'in sapması yarıya
indi. Üç `all5` tohumu da `solo` **ortalamasının** altındadır — ama bu bir işaret testi değildir
ve tutarlılığı olduğundan güçlü gösterir. Tohumlar eşleştirilerek bakıldığında (aynı tohum,
iki kol) fark $[-2.33,\; +0.37,\; -2.64]$'tür: **`all5` üç tohumun ikisinde kazanıyor**, s43'te
kaybediyor. Eşleştirilmiş işaret testi $2/3$, yani $p = 0.5$; eşleştirilmiş $t$ testi
$t = -1.60$, $p = 0.250$; eşleştirmesiz Welch $t = -1.11$, $p = 0.352$. Üçü de aynı şeyi
söylüyor. Ayrıca üç `all5` değeri de `solo` aralığının içinde kalır ve $n=3$ ile standart hata
kestirimi zaten çok zayıftır.

Dürüst ifade: **bu doğrulukta, Rize için beş ili havuzlamanın tek-il modeline üstünlüğü tespit
edilememiştir.** Yön (küçük bir iyileşme) doğrudur ama büyüklüğü tohum gürültüsünün altındadır.
Bu, "havuzlama işe yaramıyor" demek değildir; "bu kanıtla havuzlamanın işe yaradığı
söylenemez" demektir — ve makalede §1.1'deki iddia bu koşuya dayandırılacaksa bu ayrım
korunmalıdır.

**H2 — "Hangi ilin eklendiği önemlidir, yalnızca kaç il eklendiği değil": DESTEKLENDİ (tek tohum
sınırıyla).**

Eşit eğitim hacminde (87 498 pencere) ortak değişimi Rize'nin gündüz RMSE'sini 109.80 ile 119.66
arasında oynatıyor — tohum gürültü ölçeğinin ~3.2 katı bir aralık — ve fark EDA'nın öngördüğü
yönde: Rize'ye iklimsel olarak en yakın il yardım ediyor, en uzak il zarar veriyor. H2, H1'in
aksine, ölçülebilir bir etki üretmiştir.

**İkisinin birlikte söylediği.** Makalenin taşıyabileceği ifade "havuzlama her ili iyileştirir"
değil, **"havuzlamanın etkisi iklimsel yakınlıkla yönetilir; benzer rejimli illerle havuzlama
yardım eder, uzak rejimli illerle havuzlama zarar verebilir"**dir. Bu, orijinalinden daha zayıf
ama ölçümle **desteklenen** ve literatürde daha ilginç bir iddiadır. Şu hâliyle `main_methodology.md`
satır 56–59'daki koşulsuz "veri verimliliği artar" cümlesi bu ölçümlerin arkasında duramaz.

**Yöntem düzeyinde bir uyarı: eğri, Aşama 1'in kaybedeniyle koşulmuştur.** Aşama 2 kolları
`loss_function`'ı `ExperimentConfig` varsayılanından (mse) alır, Aşama 1'in kazananından (mae)
değil — `_rize_curve_configs()` docstring'i bunun aksini ima ediyordu ve düzeltilmiştir. MAE
kaybı Rize gündüz RMSE'sini 112.88'den 109.56'ya çektiğine göre (§1.5), eğrinin MAE altında
tekrarlanması yalnızca daha iyi mutlak sayılar değil, farklı bir **şekil** de verebilir. Eğri,
mevcut hâliyle, seçilmemiş bir kriter altındaki transfer davranışını ölçmektedir.

### 1.9 Geçerlilik tehditleri

- **T-1 — Eğri, seçilmeyen kriterle koşuldu.** Yukarıda. En önemli tek eksik iş: eğrinin
  `loss_function="mae"` ile tekrarı (yeni id'ler gerekir).
- **T-2 — `Aggregate` tuzağı.** Kollar farklı il kümelerinde skorlandığı için `Aggregate`
  satırları karşılaştırılamaz. Ölçülmüş örnek K-1'de. Bu belgedeki Aşama 2 tablolarının tamamı
  `Rize` satırındandır; makaleye taşınırken bu korunmalıdır.
- **T-3 — Tohum kapsamı yetersiz.** Her iki uç 3 tohumludur (`solo`, `all5`), ara kollar
  **1** tohum. $n=3$, bir sapma kestirimi için asgarinin de altındadır: H1'in "tespit edilemedi"
  hükmü bu yüzden bir güç (power) ifadesidir, bir yokluk kanıtı değil. Ara kolların ve özellikle
  H2'nin dayandığı çift kolların tek tohumlu olması H2'yi "güçlü ama kesinleşmemiş" seviyesinde
  tutar.
- **T-4 — $B=1$ doğruluğu.** Nokta tahminleri 100 MC geçişin ortalamasıdır, 800'ün değil;
  $B=8$'in varyans azaltması yoktur, dolayısıyla tohumlar arası sapma tam doğruluktakinden
  büyüktür. Bu, H1'i tespit etmeyi **zorlaştıran** yöndedir: gerçek ama küçük bir havuzlama
  kazancı bu gürültünün altında kalmış olabilir. Bu yüzden H1 hükmü "desteklenmedi" değil
  "**tespit edilemedi**" biçimindedir.
- **T-5 — Epok tavanı.** Bağlayıcı olmadı: `hit_max_epochs` on iki kolun hepsinde 0, epoklar
  18–39. Ancak kollar **farklı sayıda epok** eğitildi (erken durdurma kararıyla), ve özellikle
  `plus_antalya` 39 epokla `plus_ankara`'nın 19'unun iki katı adım gördü. Bu bir kırpılma değil
  yakınsama farkıdır, ama H2'nin dayandığı çiftin iki kolunun eşit miktarda eğitilmediği
  kaydedilmelidir.
- **T-6 — Aralık metrikleri kalibre değil** (K-4). CP 0.75–0.79 bandındadır, hedef 0.95. Kollar
  arası CP farkları bir kalibrasyon bulgusu olarak okunmamalıdır.
- **T-7 — Dışlanan illerin gömme satırları eğitimsiz kalır ama kullanılmaz.** Model her koşuda
  tam `len(CITIES)` satırlık gömme tablosu tutar; dışlanan ilin satırı hiç gradyan almaz ve
  hiçbir ileri geçişte indekslenmez (test kümesi de aktif illerle sınırlıdır). Sonuçları
  etkilemez, ama checkpoint'ler arası karşılaştırmada bu satırların rastgele ilk değerlerinde
  kaldığı unutulmamalıdır.
- **T-8 — Örtüşen pencereler.** `window_stride=1` olduğu için 8 831 Rize test penceresi bağımsız
  gözlem değildir (ardışık pencereler 47 saat paylaşır). Yukarıdaki hiçbir yerde bir anlamlılık
  testi yapılmamıştır; "tohum sapmasının içinde/dışında" ifadeleri betimseldir ve $p$-değeri
  iddiası taşımaz.
- **T-9 — `per_city` kolunun kendi ölçekleyicisi vardır.** `solo` kolu `per_city_scaler=True`
  ile koşar, yani Rize kendi ölçekleyicisini kullanır ve kolda hiç iller-arası bilgi yoktur —
  istenen budur. Ancak il bazlı hedef ölçekleyicisi kaybı ve erken durdurma sinyalini de
  yeniden normalize eder; bu, `solo` kolunu modelin öğrendiğinden bağımsız olarak kayıran bir
  etkidir. `ablation` grubundaki `abl_sens_percity_globalscaler_s42` tam olarak bunu ölçmek için
  vardır ve **bu çalışmada koşulmamıştır**; H1 "tespit edilemedi" hükmü verildiğine göre, bu
  karıştırıcının hükmü değiştirmesi için `solo`'yu *kayırdığı* yönde çalışması gerekirdi, ki
  o durumda gerçek havuzlama kazancı ölçülenden biraz daha büyük olurdu.

### 1.10 Tekrarlanabilirlik — CPU'da tam, MPS'te **değil**

Ledger'da, `experiment_id` dışında konfigürasyonu birebir aynı olan beş kol kümesi vardır.
Kasıtlı kurgulanmamışlardı; aşamaların kesişmesinden doğdular ve birlikte **ölçülmüş bir
tekrarlanabilirlik tabanı** verirler.

| kol çifti | cihaz | gündüz `Aggregate` RMSE farkı |
| --- | --- | ---: |
| `abl_loss_mse_s42_b1` / `abl_rize_all5_s42_b1` | cpu / cpu | **0,000000 — bit-birebir** |
| `abl_rize_all5_s43_l1` / `abl_arch_base_s43` | mps / mps | 0,401 (%0,43) |
| `abl_rize_all5_s44_l1` / `abl_arch_base_s44` | mps / mps | 0,570 (%0,60) |
| `abl_parity_mps_s42` / `abl_rize_solo_s42_l1` | mps / mps | **1,637 (%1,47)**, Rize satırı |

**CPU deterministiktir; MPS değildir.** Aynı `seed`, aynı config, aynı kod — ve MPS'te iki
koşu havuzlanmış RMSE'de %0,4–0,6, tek il satırında **%1,47** ayrılıyor. Araya giren
commit'lerde eğitim yolunu değiştiren bir şey yok, yani bu arka uç kaynaklı determinizm
eksikliğidir.

**Sonuçları, önem sırasıyla:**

1. **`main_methodology.md` §13.3'ün determinizm iddiası yalnızca CPU'yu kapsar.** 126 ledger
   satırının 107'si MPS'tir. Makalede "tohum sabitlendi, sonuçlar tekrarlanabilir" cümlesi bu
   hâliyle yanlış olur; doğru cümle **"CPU'da bit-birebir; MPS'te sabit tohumda havuzlanmış
   metriklerde ±%0,5, il bazında ±%1,5"**tir.
2. **§1.11'in cihaz eşdeğerliği hükmü geçersizdir** — aşağıda.
3. **Tek koşu farkları okunamaz.** Bu, ölçülmüş bir çözünürlük alt sınırıdır: bu tabanın
   altındaki bir fark, kaç tohum koşulursa koşulsun tek bir koşu çiftinden okunamaz.
   Çok tohumlu eşleştirilmiş testler geçerliliğini korur — arka uç gürültüsü sistematik değil
   bağımsız gürültüdür, dolayısıyla raporladığımız tohum s.s.'leri onu **zaten içerir** ve test
   doğru varyansa karşı sınar. Değişen şey yorumdur: "6/6 tohum" altı bağımsız *tohum* etkisi
   değil, altı (tohum + arka uç gürültüsü) çekilişidir.

### 1.11 Cihaz eşdeğerliği — **hüküm geri çekildi**

`abl_parity_cpu_s42` / `abl_parity_mps_s42` çifti, doğrulanmamış bir `nn.LSTM` MPS dropout
iddiasını sınamak için koşulmuştu ve iddia doğrulanmadı: dropout işlevsiz olsaydı yayılım
*çökerdi*, gözlenen yön tersidir (MPIW %4,5 daha geniş). **Bu kısım ayaktadır.**

Geri çekilen kısım, o çiftten çıkarılan **eşdeğerlik hükmüdür**:

| metrik (Rize, gündüz) | CPU | MPS | iddia edilen "arka uç farkı" |
| --- | --- | --- | --- |
| RMSE | 110,557 | 110,832 | +%0,25 |
| CP | 0,8674 | 0,8894 | +0,0220 |
| MPIW | 318,38 | 332,66 | +%4,49 |

Belgenin önceki sürümü buradan **"nokta metrikleri arka uçlar arasında okunabilir, aralık
metrikleri okunamaz"** kuralını türetmişti. §1.10 bunu çürütüyor: **aynı arka uçta (MPS) aynı
config'in iki koşusu Rize RMSE'sinde %1,47 ayrılıyor**, yani iddia edilen CPU↔MPS nokta farkı
(%0,25) MPS'in kendi tekrar yayılımının **altıda biri**. Karşılaştırma, ölçmeye çalıştığı
büyüklükten büyük bir gürültünün içinde yapılmıştır ve hiçbir şeyi ölçmemektedir.

**Doğru hüküm:** CPU ↔ MPS farkı bu veriyle **ayrılamaz**; ayrılabilmesi için her arka uçta
çok tohumlu koşum gerekir (§1.11'in kendi "Sınır" paragrafı bunu zaten söylüyordu, ama hüküm
yine de yazılmıştı). Ledger'ın `device` sütunu yine de gereklidir — ama gerekçesi ölçülmüş bir
arka uç kayması değil, **MPS'in determinist olmaması**dır.

**Yapılabilir düzeltme (ucuz):** Rize tek başına, arka uç başına üç tohum, ≈3 × 100 s. Bu hem
CPU↔MPS farkını ayırır hem de §1.10'un MPS tekrar yayılımını üç yerine altı noktadan ölçer.

---

## 2. Aynı eğri, doğru kriterle — L1 altında transfer eğrisi

> **Geçerlilik künyesi** — bu bölümün bulguları yalnızca bu konfigürasyonda geçerlidir (§0.2, §0.3).
>
> | veri kümesi | hedef dönüşümü | mimari | doğruluk | kriter | kapsam | tohum | cihaz |
> | --- | --- | --- | --- | --- | --- | --- | --- |
> | $F=17$, referans | `raw` | `[64,32]`, do 0,3 | $B{=}1$, $T{=}100$ | `mae` | Rize eğrisi (5 kol) | 42–44 | mps |
>
> **§3 bu bölümü tam doğrulukta üstünlemiştir.** Buradaki etki büyüklükleri ($-5{,}11$) $B{=}1$'e aittir; makaleye giren değer §3'ünkidir.


§1'in eğrisi MSE ile koştu; §1.5 ise kriteri **L1 olarak seçti**. Bu bir tasarım hatasıydı
(§1.9, T-1): Aşama 2, kaybını `ExperimentConfig` varsayılanından alıyordu, Aşama 1'in
kazananından değil. Bu bölüm eğriyi seçilen kriterle ve **her kolda üç tohumla** yeniden koşar.
`rize_curve_l1` (15 kol) + `sens_scaler_l1` (3 kol), tümü `MERVE_DEVICE=mps`, `ABLATION_B1`
doğruluğu, tüm kollarda `hit_max_epochs=0`.

**Bu bölüm §1'in iki hükmünü geçersiz kılar.** Hangileri olduğu §2.4'te açıkça yazılıdır.
§1 silinmemiştir: kriterin eğriyi ne kadar taşıdığının tek ölçümü odur.

### 2.1 Sonuçlar (Rize satırı, gündüz, her kolda 109.043 eleman)

| kol | il | RMSE ort ± s.s. | tohumlar | MAE ort ± s.s. | CP |
| --- | --- | --- | --- | --- | --- |
| `solo` | 1 | 112,38 ± 0,58 | 112,47 / 111,76 / 112,92 | 79,23 ± 0,13 | 0,8869 |
| `plus_ankara` | 2 | 108,71 ± 1,92 | 110,71 / 108,54 / 106,88 | 75,68 ± 0,59 | 0,8959 |
| `plus_antalya` | 2 | 110,38 ± 2,64 | 113,24 / 109,84 / 108,05 | 77,25 ± 1,34 | 0,8967 |
| `minus_antalya` | 4 | **106,04 ± 0,38** | 106,48 / 105,78 / 105,86 | 75,26 ± 0,82 | 0,9044 |
| `all5` | 5 | 107,27 ± 2,32 | 107,30 / 104,93 / 109,57 | 75,52 ± 1,21 | **0,9134** |
| *kontrol:* `solo` + havuz ölçekleyici | 1 | 112,57 ± 0,91 | 111,59 / 113,38 / 112,73 | 79,17 ± 1,10 | — |
| *taban:* iklimsel ortalama | — | 130,68 | — | 95,72 | — |
| *taban:* akıllı kalıcılık | — | 136,66 | — | 85,23 | — |

### 2.2 H1 — havuzlama Rize'yi iyileştiriyor mu? **Evet.**

`solo` → `all5`: eşleştirilmiş fark **−5,11 W/m²**, tohum farkları `[−5,17, −6,83, −3,34]`,
**3/3 tohumda** havuzlama kazanıyor, eşleştirilmiş $t = -5{,}08$, $p = 0{,}037$.

§1'de aynı karşılaştırma −1,53 W/m² ve $p = 0{,}250$ ile "saptanamadı" idi. Etki **3,3 katına**
çıktı ve tespit edilebilir hâle geldi.

**Neden döndü — ve bu bulgunun kendisi.** Kriter değişimi kolları eşit etkilemedi:

| kol | MSE (s42) | L1 (3 tohum ort.) | değişim |
| --- | --- | --- | --- |
| `solo` | 115,21 | 112,38 | −2,83 |
| `plus_ankara` | 109,80 | 108,71 | −1,10 |
| `all5` | 112,88 | 107,27 | **−5,62** |
| `minus_antalya` | 111,77 | 106,04 | **−5,73** |
| `plus_antalya` | 119,66 | 110,38 | **−9,28** |

Havuzlanmış kollar L1'den `solo`'nun iki katı kazanıyor. Mekanizma ölçülmedi ama tutarlı bir
açıklaması var: havuzlanmış kollarda hedef ölçekleyicisi beş ilin üzerinde fit edilir ve MSE
karesel hatayı topladığı için yüksek varyanslı iller kaybı domine eder — Rize beş ilin **en
düşük varyanslısıdır** ($\sigma = 231{,}5$, havuz $\approx 280$). L1 hatayı mutlak değerle
tarttığından bu baskınlığı sıkıştırır. Yani MSE eğrisi transferi **olduğundan az gösteriyordu**;
küresel model iddiası zayıf değildi, ölçüm aleti zayıftı.

### 2.3 H2 — hangi ilin eklendiği önemli mi? **Yön evet, büyüklük hayır.**

`plus_ankara` 108,71 ± 1,92 vs `plus_antalya` 110,38 ± 2,64, eşit eğitim hacminde (87.498
pencere). Ankara **3/3 tohumda** daha iyi, eşleştirilmiş fark −1,67, $t = -3{,}83$,
$p = 0{,}062$. Ama eşleştirmesiz Welch $p = 0{,}43$: kolların kendi tohum saçılımı farktan
büyük.

**§1'in 9,86 W/m²'lik farkı büyük ölçüde tek-tohum şansıymış.** Üç tohumla fark 1,67'ye
iniyor — altıda bire. Yön korunuyor ve EDA'nın öngördüğü yönde (Ankara $k_t = 0{,}806$ Rize'nin
0,697'sine en yakın), ama "iklimsel yakınlık transferi yönetir" iddiası bu kanıtla
**zayıf-düşündürücü** seviyesindedir, kanıtlanmış değil.

### 2.4 §1'in geçersiz kılınan iki hükmü

**(i) "Negatif transfer" replike olmadı.** §1.7 `plus_antalya`'nın (119,66) `solo`'dan (113,21)
*kötü* olduğunu, yani yanlış partnerin zarar verdiğini raporluyordu. L1 ve üç tohumla
`plus_antalya` 110,38, `solo` 112,38 — Antalya eklemek **iyileştiriyor** (2/3 tohum,
$p = 0{,}344$). Tek tohumlu bir kola dayanan bulgu çoğaltılınca ayakta kalmadı.

**(ii) "Antalya'yı çıkarmak beş ili havuzlamaktan iyidir" gösterilemedi.** `minus_antalya`
ortalaması `all5`'ten düşük (106,04 vs 107,27) ama fark −1,23, 2/3 tohum, $p = 0{,}454$.
§1'de de tek tohumla −1,11 idi; iki koşuda da tespit eşiğinin altında.

Bu iki madde §1'in "havuzlamanın işareti iklimsel yakınlıkla belirlenir" cümlesini taşıyan
ayaktı. **O cümle bu kanıtla yazılamaz.** Ayakta kalan iddia daha basit ve makalenin asıl
istediği şey: *beş ili havuzlamak Rize'yi iyileştirir.*

### 2.5 Ölçekleyici karıştırıcısı elendi (T-9 kapandı)

`solo` kendi ölçekleyicisini kullanır, havuzlanmış kollar ortak ölçekleyiciyi. Bunun `solo`
lehine çalıştığından ve H1'in null'ını üretiyor olabileceğinden şüphelenilmişti. Kontrol kolu
(`solo`, `per_city_scaler=False`) farkı ölçtü: **+0,19 W/m², 2/3 tohum, $p = 0{,}826$.**

`solo` kendi ölçekleyicisinden hiçbir avantaj elde etmiyor. Karıştırıcı yok; H1'in §1'deki
null'ı ölçekleyici artefaktı değildi, kriter artefaktıydı (§2.2).

### 2.6 Yan bulgu — kalibrasyon "çözüldü" sanıldı, **çözülmedi**

> **DÜZELTME.** Bu bölümün hükmü, düzeltilmiş §3.5 tarafından geçersiz kılınmıştır ve
> K-5'in ("Rize tuzağı") bir örneğidir. Aşağıdaki gözlem — havuzlama arttıkça CP'nin
> yükselmesi — doğrudur, ama "alt-kapsamanın tamamı yapısal değilmiş" ve "rezidüel-varyans
> eklentisi artık bir ön koşul değil" sonuçları **çıkarılamaz**: il bazında bakıldığında
> $B$'yi büyütmek kalibrasyonu net olarak **bozar** (§3.5, kümelenmiş $p = 0{,}0054$), ve
> kalibrasyon üç ayrı eksende bağımsız olarak bozulur (K-4). Metin, ne düşünüldüğünün kaydı
> olarak bırakılmıştır.

Gündüz CP havuzlama arttıkça **tekdüze yükseliyor**: `solo` 0,8869 → `plus_*` 0,896 →
`minus_antalya` 0,9044 → `all5` 0,9134. Ve `all5` kolunun **`Aggregate`** gündüz CP'si üç
tohumda 0,9535 / 0,9570 / 0,9534 — yani hedefin üzerinde değil, **hedefte**.

~~Bu, `METHODOLOGY_REVIEW.md` K3'ün uyarısını önemli ölçüde yumuşatır… alt-kapsamanın tamamı
yapısal değilmiş… artık bir ön koşul değil.~~ **Geri çekildi** — yukarıdaki düzeltmeye bakınız.
Ayakta kalan gözlem yalnızca şudur: MSE altında CP 0,80–0,83 iken L1 + havuzlama ile
`Aggregate` gündüz CP'si 0,95 bandına gelir; yani **kriter seçimi kapsamayı belirgin biçimde
etkiler**. Bu, kalibrasyonun çözüldüğü anlamına gelmez.

`Aggregate` gündüz nokta başarımı da aynı kollarda RMSE 94,89 / 93,19 / 94,18 ve
R² 0,887–0,891 — iklimsel ortalama tabanının (106,86 / 0,8565) **%12 altında**.

### 2.7 Geçerlilik tehditleri

- **T-1 (kapandı).** Eğri artık Aşama 1'in seçtiği kriterle koşuyor.
- **T-9 (kapandı).** §2.5.
- **T-12 (yeni, GÜNCELLENDİ).** Bu 18 kol MPS'te, §1'in 12 kolu CPU'da koştu. §1.10'un
  ölçümüne göre **MPS determinist değildir** (havuzlanmışta ±%0,5, il bazında ±%1,5), ve
  §1.11'in CPU↔MPS eşdeğerlik hükmü geri çekilmiştir — o fark bu gürültünün altında kalır.
  Bölümler arası tek-koşu karşılaştırması bu nedenle yapılamaz; çok tohumlu eşleştirilmiş
  testler geçerliliğini korur. *(Eski gerekçe — geri çekildi:* ~~nokta metrikleri arka uçtan
  bağımsızdır (%0,25) ama aralık metrikleri değildir (%4,49)~~*.)*
- **T-13 (yeni).** $n = 3$ tohum. H1 $p = 0{,}037$ ile eşiği geçiyor ama üç gözlemle; H2
  ($p = 0{,}062$) geçmiyor. Tam doğruluk (B=8) ve daha fazla tohum ikisini de sağlamlaştırır.
- **Devam eden:** tüm kollar `n_bootstrap=1`, dolayısıyla aralık metrikleri MC-Dropout'a
  dayanır, bootstrap bileşeni yoktur (§1.4).

---

## 3. Tam doğruluk — aynı eğri, $B = 8$

> **Geçerlilik künyesi** — bu bölümün bulguları yalnızca bu konfigürasyonda geçerlidir (§0.2, §0.3).
>
> | veri kümesi | hedef dönüşümü | mimari | doğruluk | kriter | kapsam | tohum | cihaz |
> | --- | --- | --- | --- | --- | --- | --- | --- |
> | $F=17$, referans | `raw` | `[64,32]`, do 0,3 | **$B{=}8$, $T{=}100$** | `mae` | Rize eğrisi; H1 için `solo` ↔ `all5` | **42–47** (H1), 42–44 (diğer) | mps |
>
> **Birincil sonlanım noktası burasıdır (H1).** §7, bu bölümün `target_transform="raw"`'a koşullu olduğunu ölçmüştür.


`rize_curve_full_l1`: §2'nin on beş kolunun `ABLATION_FULL` doğruluğunda ($B = 8$, $T = 100$,
`max_epochs=200`) tekrarı. §2'den yalnızca `{n_bootstrap, max_epochs}` alanlarında ayrılır
(test sabitler). Tümü `MERVE_DEVICE=mps`, tüm kollarda `hit_max_epochs=0`, kol başına 8 model,
toplam duvar saati **5,8 saat**.

**Bu, metodolojinin tarif ettiği yöntemin ilk kez çalıştığı koşudur.** §1 ve §2'nin kolları
$B = 1$ idi, yani $\mathcal{P} = B \cdot T$ havuzunun **bootstrap yarısı hiç üretilmiyordu**.
Bu yüzden §1–§2'nin aralık metrikleri (CP/PINW/MPIW/CWC) yöntemin aralık başarımı olarak
alıntılanamaz; **bu bölümünkiler alıntılanabilir.**

### 3.1 Eğri (Rize satırı, gündüz, her kolda 109.043 eleman)

| kol | il | RMSE ort ± s.s. | tohumlar | MAE | CP |
| --- | --- | --- | --- | --- | --- |
| `solo` | 1 | 108,32 ± 1,76 | 107,31 / 110,34 / 107,29 | 77,28 | 0,9529 |
| `plus_ankara` | 2 | 106,41 ± 0,42 | 105,96 / 106,47 / 106,79 | 75,04 | 0,9476 |
| `plus_antalya` | 2 | 107,73 ± 1,61 | 106,98 / 109,57 / 106,63 | 76,40 | 0,9505 |
| `minus_antalya` | 4 | **104,93 ± 0,37** | 104,52 / 105,23 / 105,05 | **74,58** | 0,9528 |
| `all5` | 5 | 106,27 ± 0,81 | 105,33 / 106,70 / 106,78 | 75,70 | 0,9521 |
| *taban:* iklimsel ortalama | — | 130,68 | — | 95,72 | — |

### 3.2 H1 — altı tohumla desteklendi, ve etkinin küçülmesinin nedeni bulgunun kendisi

**Sonuç (birincil sonlanım noktası, $n = 6$, tohum 42–47):**

| | ortalama ± s.s. | tohumlar |
| --- | --- | --- |
| `solo` | 108,01 ± 1,31 | 107,31 / 110,34 / 107,29 / 106,84 / 107,53 / 108,73 |
| `all5` | **105,31 ± 1,33** | 105,33 / 106,70 / 106,78 / 104,90 / 104,95 / 103,20 |

Eşleştirilmiş fark **−2,70 W/m²**, tohum başına
$[-1{,}98,\; -3{,}65,\; -0{,}51,\; -1{,}95,\; -2{,}57,\; -5{,}54]$, **6/6 tohumda
havuzlama kazanıyor**, $t = -3{,}84$, $p = 0{,}0122$. Dağılımdan bağımsız çapraz kontrol
(Wilcoxon işaretli sıra) $p = 0{,}0312$. MAE'de daha da güçlü: −1,99 W/m², 6/6,
$p = 0{,}0050$.

$p = 0{,}0122$, §3.3'ün dört kontrastlı Benjamini–Hochberg eşiğini (sıra 1 için 0,0125) da
kıl payı geçmektedir. Yani H1'in birincil sonlanım noktası olarak önceden belirlenmiş olması
sonucu taşımak zorunda değildir; **kontrast seçimi düzeltilse bile ayakta kalır.**

İlk üç tohumda fark −2,05 ve $p = 0{,}152$ idi; üç tohum daha eklenince hem etki büyüdü
(−2,70) hem de güç arttı. Kısıt gerçekten güçtü, etkinin yokluğu değil.

**Ama §2'ye göre etki hâlâ küçüldü** (−5,11 → −2,70) ve nedeni ayrı bir bulgudur.

Neden, kolların $B{=}1 \to B{=}8$ geçişinden ne kazandığına bakılınca görülüyor:

| kol | eğitim penceresi | $B{=}1$ | $B{=}8$ | kazanç |
| --- | --- | --- | --- | --- |
| `solo` | 43.749 | 112,38 | 108,32 | **−4,07** |
| `plus_antalya` | 87.498 | 110,38 | 107,73 | −2,65 |
| `plus_ankara` | 87.498 | 108,71 | 106,41 | −2,30 |
| `minus_antalya` | 174.996 | 106,04 | 104,93 | −1,11 |
| `all5` | 218.745 | 107,27 | 106,27 | **−1,00** |

Kazanç, eğitim verisi hacmiyle **tekdüze ters orantılı**. Mekanizma açık: bootstrap topluluğu
bir varyans azaltma aracıdır ve az veriyle eğitilmiş bir modelin varyansı daha büyüktür,
dolayısıyla topluluktan daha çok kazanır.

**Bulgu şudur: veri havuzlamak ile model topluluğu kurmak kısmen birbirinin yerine geçen
varyans azaltma mekanizmalarıdır.** §2'de havuzlamanın faydası olarak ölçtüğümüz −5,11'in bir
bölümü, aslında havuzlanmış kolun tek-il kolundan daha düşük varyanslı olmasıydı; topluluk
kurulduğunda tek-il kolu bu açığın çoğunu kendi başına kapatıyor. Makale bu ikisini ayrı ayrı
sunmalıdır: havuzlamanın *kalan* katkısı −2,05 W/m²'dir.

### 3.3 Çoklu test düzeltmesi — hiçbir kontrast eşiği geçmiyor

Dört birincil kontrast, Benjamini–Hochberg, $\alpha = 0{,}05$:

| kontrast | fark | tohum tutarlılığı | $p$ | BH eşiği | sonuç |
| --- | --- | --- | --- | --- | --- |
| `minus_antalya` vs `all5` | −1,34 | 3/3 | 0,039 | 0,0125 | geçmez |
| `plus_antalya` vs `solo` | −0,59 | 3/3 | 0,046 | 0,0250 | geçmez |
| `all5` vs `solo` (H1) | −2,05 | 3/3 | 0,152 | 0,0375 | geçmez |
| `plus_ankara` vs `plus_antalya` (H2) | −1,32 | 2/3 | 0,300 | 0,0500 | geçmez |

**Yukarıdaki tablo $n = 3$ dönemine aittir ve H1 satırı artık geçerli değildir:** altı
tohumla H1 $p = 0{,}0122$'ye iner ve BH sıra-1 eşiğini (0,0125) geçer (§3.2). Diğer üç
kontrast hâlâ $n = 3$'tedir ve **hiçbiri düzeltmeden sağ çıkmaz.**

Bu asimetri bilinçlidir. H1 makalenin iddiasıdır ve birincil sonlanım noktası olarak
tohumlandırılmıştır; diğer üçü eğriye bakarken ortaya çıkmış gözlemlerdir ve **keşifsel**
olarak, anlamlılık iddiası olmadan raporlanmalıdır. Onları da eş-birincil saymak, hem BH'yi
gereksiz cezalandırıcı kılar hem de nasıl doğduklarını yanlış tarif eder. Tohum eklenirse
(`rize_curve_full_seeds` grubunda kolları hazırdır) durumları yeniden değerlendirilebilir.

### 3.4 §1'in "negatif transfer" bulgusu tersine döndü

§1, `plus_antalya`'nın `solo`'dan kötü olduğunu (119,66 vs 113,21, tek tohum, MSE) raporlamıştı.
Tam doğrulukta işaret terstir ve tutarlıdır: **`plus_antalya` − `solo` = −0,59, 3/3 tohum,
$p = 0{,}046$** (düzeltmesiz). Antalya eklemek Rize'ye zarar vermiyor, az da olsa yarıyor.

Buna karşılık `minus_antalya` beş kolun **en iyisidir** (104,93 ± 0,37, hem de en dar tohum
saçılımıyla) ve `all5`'i 3/3 tohumda geçer (−1,34, $p = 0{,}039$ düzeltmesiz). İkisi çelişmez;
birlikte okunduğunda söyledikleri şudur: **bir ilin marjinal katkısı, havuzda hâlihazırda ne
olduğuna bağlıdır.** Antalya, yalnız bir Rize modeline bilgi ekler; Ankara+Konya+Van'ın yanında
ise fazlalıktır ve seyreltir. Bu, "daha çok veri her zaman daha iyi değildir" biçiminde
ifade edilebilir ama **düzeltme sonrası anlamlı değildir**; hipotez üreten bir gözlem olarak
sunulmalıdır.

### 3.5 Kalibrasyon — Rize düzeliyor, **diğer dördü bozuluyor**

`all5` kolu, üç tohum, gündüz:

| il | CP | MPIW |
| --- | --- | --- |
| **Rize** | **0,9521 ± 0,0009** | 371,66 |
| Konya | 0,9813 ± 0,0019 | 457,80 |
| Van | 0,9829 ± 0,0014 | 463,20 |
| Antalya | 0,9837 ± 0,0011 | 459,70 |
| Ankara | 0,9842 ± 0,0006 | 440,46 |
| `Aggregate` | 0,977 ± 0,001 | 438,58 |

> **DÜZELTME (bağımsız review, `ABLATION_REVIEW_2.md`).** Bu bölümün önceki sürümü Rize
> satırını okuyup "$B{=}1 \to B{=}8$ kalibrasyonu düzeltti, `METHODOLOGY_REVIEW.md` K3 yanlıştı"
> hükmünü vermişti. **İl bazında okununca hüküm tersine döner.** $B{=}1 \to B{=}8$ geçişi,
> Reliability ($|CP - 0{,}95|$, küçük iyi), eşleştirilmiş üç tohum:
>
> | il | $B{=}1$ CP | $B{=}8$ CP | Rel. $B{=}1$ | Rel. $B{=}8$ | Δ | iyileşti | $p$ |
> | --- | ---: | ---: | ---: | ---: | ---: | :-: | ---: |
> | **Rize** | 0,9134 | **0,9521** | 0,0366 | **0,0021** | **−0,0345** | 3/3 | **0,0123** |
> | Antalya | 0,9690 | 0,9837 | 0,0190 | 0,0337 | +0,0147 | 0/3 | **0,0023** |
> | Van | 0,9674 | 0,9829 | 0,0174 | 0,0329 | +0,0156 | 0/3 | **0,0004** |
> | Konya | 0,9608 | 0,9813 | 0,0108 | 0,0313 | +0,0205 | 0/3 | **0,0003** |
> | Ankara | 0,9627 | 0,9842 | 0,0127 | 0,0342 | +0,0215 | 0/3 | **0,0158** |
> | **kümelenmiş** | | | | | **+0,0076** | | **0,0054** |
>
> Bootstrap bileşeni **net olarak kalibrasyonu bozuyor** ($p = 0{,}0054$): Rize'yi 0,913'ten
> 0,952'ye taşırken diğer dördünü zaten aştıkları hedeften daha da uzaklaştırıyor
> (0,961–0,969 → 0,981–0,984). Bu bir **yeniden dağıtımdır**, bir düzeltme değil — ve §7.7'de
> `target_transform` ekseninde ölçülen olgunun aynısıdır (orada net etki sıfır, burada net
> etki negatif).
>
> **Bu, §7.4'ün adını koyduğu "Rize tuzağı"nın belgedeki yakalanmamış örneğiydi** ve
> yakalanmasını bağımsız review'e borçluyuz. Rize, transferin ve doğruluğun en çok işe
> yaraması beklenen ildir; orada ölçülen her etkinin işareti bile diğer illere taşınmayabilir.

**Ayakta kalan kısım:** Rize'nin $B{=}8$'de nominal %95'e oturması gerçektir (CP 0,9521,
Reliability 0,0021, CWC 2,855 → 0,376) ve projedeki en büyük tek metrik iyileşmesidir.
`METHODOLOGY_REVIEW.md` K3'ün "aleatorik terim bir **ön koşuldur**" ifadesi de hâlâ fazla
güçlüdür — Rize onsuz nominale oturmaktadır. Ama K3'ün **yönü doğruydu**: aralık, artık
hatanın ne kadar olduğuna değil epistemik yayılımın ne kadar olduğuna göre boyutlanmaktadır,
ve $B$'yi büyütmek bunu düzeltmez, yalnızca hangi ilin şanslı olduğunu değiştirir. B-8 ve
§6.5 bu teşhise iki eksen daha ekler.

**Ayakta kalan ikinci kısım:** fazla kapsama "aralığı şişirip kapsama satın almak" değildir —
$B{=}1 \to B{=}8$ geçişinde **CRPS her ilde iyileşiyor** (−%1,8 … −%3,3). CRPS uygun bir
skordur; iyileşmesi dağılımın bir bütün olarak daha iyi olduğunu gösterir. Bozulan şey
dağılımın kendisi değil, ondan okunan %95'lik aralığın **boyutlandırılmasıdır**.

### 3.6 Toplulaştırılmış başarım ve taban çizgileri (beş il, `all5`, altı tohum, gündüz)

RMSE **91,985 ± 0,624** · MAE 67,515 ± 0,741 · R² 0,894 ± 0,001 · CRPS 49,400 ± 0,163 ·
CP 0,977 ± 0,001 · MPIW 440,8 ± 3,1.

> **Düzeltme.** Bu bölümün önceki sürümü yalnızca iklimsel ortalamayla karşılaştırıp
> "RMSE'de %13,5 iyileşme" diyordu. `CLAUDE.md`'nin koyduğu eşik **çifttir** — iklimsel
> ortalamanın RMSE'si *ve* akıllı kalıcılığın MAE'si — ve ikincisi atlanmıştı. Tam tablo:

| il | LSTM RMSE | iklimsel | akıllı kalıcılık | LSTM MAE | iklimsel | akıllı kalıcılık |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Ankara | **88,69** | 100,28 | 101,77 | 66,11 | 70,28 | **55,99** |
| Antalya | **84,25** | 95,02 | 92,42 | 62,49 | 61,75 | **47,35** |
| Konya | **90,23** | 100,55 | 101,76 | 67,97 | 69,72 | **54,30** |
| Van | **90,05** | 104,05 | 107,30 | 65,96 | 69,42 | **58,08** |
| **Rize** | **105,31** | 130,68 | 136,66 | **75,03** | 95,72 | 85,23 |
| `Aggregate` | **91,98** | 106,86 | 109,04 | 67,51 | 73,38 | **60,19** |

**RMSE'de beş ilin hepsinde kazanıyoruz** (%11,5–19,4; Rize %19,4 ile en büyüğü).
**MAE'de dört ilde kaybediyoruz**, yalnızca Rize'de kazanıyoruz (−%12,0).

Bu bir hata değil, mekanizması açık ve **hikâyeyi zayıflatmıyor, keskinleştiriyor:**

1. **Akıllı kalıcılık, modelin görmediği bir değişkeni kullanıyor.** Kuralı
   $\hat{y}(t{+}h) = k_t(t{+}h{-}24) \times \text{CLRSKY}(t{+}h)$; yani **hedef saatin tam
   berrak-gökyüzü zarfını** çarpan olarak alıyor. Model `CLRSKY`'yi asla girdi olarak görmez
   (`MASK_COLUMNS`), geometriyi `hour_sin/cos` + gün-içi kodlamasından çıkarmak zorundadır.
   Aynı şey iklimsel ortalama için de geçerlidir: (il, ay, saat) hücre ortalaması aynı
   geometriyi ezberler.
2. **MAE ile RMSE'nin ayrışması bu farkın imzasıdır.** Açık ve kararlı günlerde — ki çoğunluk —
   $k_t$ kalıcılığı neredeyse kusursuzdur ve MAE'yi alır. Bulut geçişlerinde ağır kuyruklu
   hatalar üretir ve RMSE'yi kaybeder. Model tam tersini yapar.
3. **Rize istisnası bulgunun kendisidir.** Rize, $k_t$ kalıcılığının çalışmadığı tek ildir
   (günlük $k_t$ 0,697, bulutlu gün payı %8,0) ve orada MAE'yi de model alır. **Modelin
   ayırt edici değeri tam olarak kalıcılığın başarısız olduğu yerdedir** — ki bu, §2.1–§3.2'nin
   havuzlama bulgusunun ölçüldüğü ildir.

Makalede bu, gizlenecek değil **kurulacak** bir argümandır: naif kurallar berrak-gökyüzü
zarfını ücretsiz alır, model onu öğrenmek zorundadır, ve buna rağmen her ilde RMSE'yi ve
en zor ilde MAE'yi kazanır.

> **Bundan doğan deney (temel bileşen, mimari değil):** hedef dönüşümü ekseni — `ALLSKY`
> yerine berraklık indeksi $k_t = \text{ALLSKY}/\text{CLRSKY}$ tahmin edip geri çarpmak, ya da
> `CLRSKY`'yi öznitelik olarak vermek. `CLRSKY` sızıntı **değildir** (saf güneş geometrisi, hava
> terimi içermez, enlem/boylam/zamandan hesaplanabilir); tabana verip modele vermemek modeli
> yanlış eksende cezalandırıyor olabilir. Ölçülmedi.

### 3.7 Makale için önerilen çerçeve

Altı tohumla H1 doğrudan sunulabilir hâle gelmiştir (§3.2): −2,70 W/m², 6/6 tohum,
$p = 0{,}0122$. Buna **tutumluluk** argümanı eklenmelidir — ama doğru biçimde.

> Beş ili tek bir modelde havuzlamak, Rize'de her il için ayrı model eğitmeye kıyasla altı
> tohumun altısında da daha düşük hata verir (−2,70 W/m², $p = 0{,}0122$) ve bunu **beş yerine
> tek bir modelle, beşte bir parametreyle** yapar.

> **Düzeltme — "beş kat ucuz" DEĞİLDİR.** Bu belgenin daha önceki bir sürümü tutumluluğu
> eğitim maliyeti üzerinden kuruyordu. Ölçüm bunu çürütür: havuzlanmış kol 2337 s, beş il
> bazlı kol toplamı 2571 s — havuzlanmış olan yalnızca **%9 ucuzdur**. Beklenen sonuçtur:
> epok başına gradyan işi toplamda aynıdır, yalnızca tek bir koşuda toplanmıştır. Tutumluluk
> iddiası **eğitim süresi üzerinden kurulmamalıdır**; parametre sayısı (58.444'e karşı
> 5 × 58.428 = 292.140), tek bir yapıt olarak dağıtım/bakım, ve yeni bir il eklendiğinde
> yeniden eğitim gerektirmemesi üzerinden kurulmalıdır.

### 3.8 Geçerlilik tehditleri

- **T-13 (açık, artık birincil kısıt).** $n = 3$. Üç kontrast 3/3 tutarlı ama BH'yi geçmiyor.
  En ucuz çare tohum eklemektir: `solo` + `all5` + `minus_antalya` için üçer tohum daha
  ≈4,2 saat (ölçülen kol maliyetleri: `solo` ~9 dk, `minus_antalya` ~33 dk, `all5` ~42 dk).
- **T-12 (açık, GÜNCELLENDİ).** Bu 15 kol MPS'te, §1'in kolları CPU'da. §1.11'in
  "nokta metrikleri arka uçtan bağımsız" hükmü **geri çekilmiştir**: §1.10 MPS'in determinist
  olmadığını ölçüyor (havuzlanmışta ±%0,5, il satırında ±%1,5) ve iddia edilen CPU↔MPS farkı
  (%0,25) bu gürültünün altındadır. §3'ün sayıları kendi içinde ve MPS içinde tutarlıdır;
  §1'in CPU sayılarıyla **tek koşu düzeyinde** karşılaştırılamaz. Çok tohumlu eşleştirilmiş
  testler etkilenmez.
- **T-14 (yeni).** Erken durdurma çok geç duruyor: `best_epoch` 3–9 arasında, koşulan epok
  19–25. `early_stop_patience=15` yüzünden sürenin ~%60-70'i optimumdan sonra harcanıyor.
  Sonuçları etkilemez (en iyi ağırlıklar geri yükleniyor) ama mimari taramasında sabrın
  düşürülmesi duvar saatini üçte bir kısaltır. Ayrıca 3–9 epokta yakınsama, mevcut mimarinin
  kapasitesinin sınırlayıcı olmadığına dair bir işarettir.
- **T-15 (yeni).** Dört il fazla kapsıyor (0,981–0,984). Aralık tablosu yayımlanacaksa il
  bazlı verilmelidir; `Aggregate` 0,977 iki karşıt hatanın ortalamasıdır. **§3.5'in düzeltmesi
  bunun nedenini veriyor:** $B$'yi büyütmek bu dört ili hedeften *uzaklaştırmıştır*.
- **T-16 (yeni).** §3.6'nın taban çizgisi karşılaştırması 24 ufuk adımının havuzudur. Naif
  kurallar ufuk boyunca düz, model bozuluyor; ufuk adımı bazlı kırılım §6.4'te verilmiştir ve
  makalede o da raporlanmalıdır (K-3).

---

## 4. Mimari taraması — kapasite, geriye bakış, düzenlileştirme ve öğrenme oranı

> **Geçerlilik künyesi** — bu bölümün bulguları yalnızca bu konfigürasyonda geçerlidir (§0.2, §0.3).
>
> | veri kümesi | hedef dönüşümü | mimari | doğruluk | kriter | kapsam | tohum | cihaz |
> | --- | --- | --- | --- | --- | --- | --- | --- |
> | $F=17$, referans | `raw` | **taranan eksen** | $B{=}1$, $T{=}100$ | `mae` | beş il havuzlanmış | 42–44 | mps |
>
> **Aralık metrikleri $B{=}1$'dir** (T-4.7): B-8'in oran eşiği $B{=}8$'e taşınamaz. Kazanan mimari tam doğrulukta **ölçülmemiştir**.


### 4.1 Sınanan iddia

`main_methodology.md` bir mimari **iddia etmez**; `TODOs.md` §B "katman sayısı / nöron sayıları
hâlâ açık" der ve `[64, 32]` referans mimarisi §1–§3'ün tamamının altında yatan seçimdir. Bu
bölümün sınadığı önerme dolayısıyla metodolojiden değil, **§1'in karıştırıcı tablosundan**
gelir:

> "Hiperparametreler küresel rejim altında seçildi. `[64,32]` / `dropout=0.3`, havuzlanmış
> 218.745 pencere için ayarlandı."

Eğer referans mimari kapasitesinin altındaysa, "havuzlama yardımcı oluyor" bulgusu "modeliniz
zaten küçüktü" itirazına açıktır. §4 bu itirazı doğrudan hedefler.

### 4.2 Kolların konfigürasyonu

Tek eksen sapmaları, hepsi `ABLATION_B1` doğruluğunda ($B = 1$, $T = 100$), L1 kaybı, beş il
havuzlanmış (`all5`), üç tohum (42/43/44), MPS. Ortak taban: `[64, 32]`, `dropout=0.3`,
`lookback=24`, `learning_rate=1e-3`, `lr_reduce_patience=7`, `max_epochs=100`,
`early_stop_patience=15`.

| grup | kollar | değişen |
| --- | --- | --- |
| `arch_sweep` | `h32x16`, `h128x64`, `h64x64x32`, `lookback48`, `lookback72`, `dropout02`, `dropout04` | tek eksen |
| `arch_sweep_x` | `base`, `lr3e4`, `h128x64_lr3e4` | referans ölçümü + öğrenme oranı |
| `arch_frontier` | `h256x128`, `h128x64_do04` | merdivenin bir üst basamağı + **bilinçli iki eksenli kol** |

`base` kolunun kendisi bir koşudur, `abl_rize_all5_s*_l1`'in yeniden etiketlenmesi **değildir**:
seçim kriteri `best_val_loss` ve o sütun eski satırlarda boştur (§4.7). Bir referansı olmayan
merdiven okunamaz.

### 4.3 Seçim kriteri: `best_val_loss`, test metriği değil

Mimari, doğrulama kaybına göre seçilir. Test RMSE'sine göre seçmek test kümesini model seçimine
dâhil eder — ölçekleyici sızıntısı kadar ciddi, gözden kaçması daha kolay bir hata. Sütun
`best_val_loss`'tur, `train_model`'ın **geri yüklediği** epok'un kaybıdır; son epok'unki değil
(§4.7'deki düzeltme kaydı).

Kriter yalnızca **aynı veri, aynı kayıp, aynı ölçekleyici** altındaki kollar arasında
karşılaştırılabilir. `lookback48`/`lookback72` kolları pencere sayısını değiştirdiği için
sınırdadır; bu iki kolun sıralaması bu nedenle test RMSE'siyle çapraz kontrol edilmiştir.

### 4.4 Merdiven (10 kol × 3 tohum, gündüz, `Aggregate`)

| konfigürasyon | parametre | `best_val_loss` ± s.s. | test RMSE | test MAE | CP | MPIW | `best_epoch` |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| **`[256,128]`** | 848.044 | **0,12000 ± 0,00244** | **88,58** | **57,41** | 0,844 | 124,8 | 2,7 |
| `[128,64]`, lr 3e-4 | 219.244 | 0,12476 ± 0,00124 | 90,91 | 61,30 | 0,896 | 160,2 | 14,0 |
| `[128,64]` | 219.244 | 0,12630 ± 0,00056 | 90,29 | 61,13 | 0,895 | 159,7 | 4,3 |
| `dropout 0,2` | 58.444 | 0,12951 ± 0,00113 | 91,21 | 62,92 | 0,912 | 166,2 | 10,3 |
| `[128,64]` × `dropout 0,4` | 219.244 | 0,13370 ± 0,00390 | 91,71 | 64,22 | 0,926 | 193,0 | 4,0 |
| `lookback 48` | 58.444 | 0,13894 ± 0,00338 | 94,87 | 67,74 | 0,950 | 211,0 | 14,7 |
| `lookback 72` | 58.444 | 0,14007 ± 0,00139 | 94,42 | 68,36 | 0,948 | 211,5 | 7,7 |
| `[64,64,32]` | 95.884 | 0,14165 ± 0,00215 | 97,85 | 72,06 | 0,964 | 215,0 | 13,0 |
| `[64,32]`, lr 3e-4 | 58.444 | 0,14248 ± 0,00179 | 94,75 | 69,76 | 0,954 | 208,8 | 15,3 |
| **`[64,32]` referans** | 58.444 | 0,14355 ± 0,00062 | 94,57 | 69,23 | 0,954 | 209,1 | 10,7 |
| `dropout 0,4` | 58.444 | 0,15785 ± 0,00158 | 101,69 | 77,32 | 0,974 | 251,6 | 14,3 |
| `[32,16]` | 16.444 | 0,17933 ± 0,00420 | 112,43 | 87,65 | 0,979 | 266,0 | 8,0 |

(MPIW sütunu ledger'ın tüm-saat değeridir; §4.6'nın gündüz MPIW'i ~2× büyüktür.)

Doğrulama kaybı ile test RMSE'si arasındaki sıra korelasyonu **Spearman $\rho = 0,84$
($p = 0,002$)** — kriter işini görüyor ama kusursuz değil: `[64,64,32]` doğrulamada referansı
geçerken testte 3,3 W/m² geride kalıyor. Kriter mimari **elemek** için yeterlidir, iki yakın kol
arasında hüküm vermek için değildir.

### 4.5 Bulgular

**B-1. Genişlik yardımcı, derinlik değil.** 32 → 64 → 128 doğrulama kaybında tekdüze iyileşiyor.
Üç LSTM katmanlı `[64,64,32]` ise iki katmanlı referansın **gerisinde**. Uyarı: `hidden_sizes`
aşırı yüklü — `[64,64,32]` yalnızca bir katman eklemez, stokastik katman sayısını da 3'ten 5'e
çıkarır, dolayısıyla temiz bir derinlik kolu değildir. "Derinlik yardımcı olmuyor" değil,
"**bu şekilde eklenen derinlik** yardımcı olmuyor" denmelidir.

**B-2. Daha uzun geriye bakış yardımcı değil.** 48 ve 72 saat, 24 saatlik referansa göre
doğrulama kaybında **daha kötü** (0,139 / 0,140 vs 0,144 — burada daha iyi, ama test RMSE'sinde
94,87 / 94,42 vs 94,57, yani ayırt edilemez) ve eğitim süresini iki katına çıkarıyor. EDA'nın
açıklık indeksi PACF kanıtı (2. günde 0,006–0,12) ile birlikte okununca **24 saatlik geriye
bakış savunulabilir**; bu kollar onun ampirik doğrulamasıdır.

**B-3. Öğrenme oranı bir sonuç değil — ama mekanizma doğrulandı.** `lr_reduce_patience=7` iken
`[128,64]`'ün `best_epoch`'u **4,3**'tü; hiçbir kol rafine etme aşamasına girmiyordu, dolayısıyla
merdivenin bir sonraki basamağında görülecek bir düşüş "kapasite sınırı" değil "optimize edici
artefaktı" olabilirdi. `lr = 3e-4` bu mekanizmayı **doğruladı**: `best_epoch` 4,3 → 14,0'a,
toplam epok 20,3 → 30,0'a çıktı, yani model gerçekten daha uzun eğitiliyor.

Ve **aynı yere varıyor**:

| kontrast | Δ`best_val_loss` | tohum başına | $p$ | Δ test RMSE | $p$ |
| --- | ---: | --- | ---: | ---: | ---: |
| `[64,32]`, 1e-3 → 3e-4 | −0,00108 | −0,0021 / +0,0006 / −0,0018 | 0,333 | +0,18 | 0,811 |
| `[128,64]`, 1e-3 → 3e-4 | −0,00155 | −0,0030 / −0,0007 / −0,0009 | 0,175 | +0,62 | 0,338 |

İki kapasitede de etki tohum gürültüsünün içinde. **Hüküm: `learning_rate=1e-3` korunuyor**, ve
merdivenin bir sonraki basamağı varsayılan oranda koşulabilir — optimize edici artefaktı
hipotezi ölçüldü ve reddedildi.

**B-4. Kapasite kazancı ile kalibrasyon ters yönlü.** Kapasite arttıkça CP 0,979 → 0,895'e,
MPIW 266 → 160'a iniyor. `dropout_rate` MC-Dropout'un **tek** rastgelelik kaynağı olduğundan
aynı anda hem düzenlileştirici hem aralık genişliği ayarıdır; doğrulama kaybına göre seçmek
yalnızca nokta doğruluğunu optimize eder ve aralığı serbest bırakır. `[128,64]`'ün gündüz CP'si
0,895, nominal 0,95'in **altında** — yani $B = 1$'de kazanan mimari daha keskin ama
kalibrasyonsuzdur.

> **Bu yüzden `[128,64]` tek başına benimsenemez.** Benimsenmesi, il × ufuk conformal ölçekleme
> katmanıyla **tek bir karar** olarak ele alınmalıdır (§6.2, kalan işler). $B = 1$ → $B = 8$
> geçişinin CP'yi kendiliğinden yükselttiği (§3.5) de hesaba katılmalı: bu tablo $B = 1$'dir ve
> **aralık metrikleri $B = 8$'e taşınamaz** (§0, kural 3).

**B-5. Kapasite kazancı ile ilin kimliği — manşeti koruyan bulgu.** `[64,32]` → `[128,64]`,
eşleştirilmiş üç tohum, gündüz, il satırı:

| il | `[64,32]` | `[128,64]` | Δ | % | $p$ |
| --- | ---: | ---: | ---: | ---: | ---: |
| Konya | 92,73 | 86,27 | −6,45 | −6,96 | 0,105 |
| Antalya | 87,25 | 81,06 | −6,19 | −7,09 | 0,039 |
| Ankara | 91,93 | 86,48 | −5,45 | −5,93 | 0,142 |
| Van | 92,25 | 88,57 | −3,68 | −3,99 | 0,058 |
| **Rize** | **107,43** | **106,86** | **−0,56** | **−0,52** | **0,845** |

Kapasiteyi 3,75 katına çıkarmak dört ili %4–7 iyileştiriyor, **Rize'yi hiç iyileştirmiyor**.
Rize gürültü-sınırlı: hatası modelin kapasitesinden değil, bulutluluğun kendisinden geliyor
(§2.5 il profili, günlük $k_t$ 0,697).

> **DÜZELTME — doğru sonuç, yanlış test** (bağımsız review, `ABLATION_REVIEW_2.md`).
> Yukarıdaki $p = 0{,}845$ bir **reddetmeme**dir, kanıt değildir: Rize'nin kapasite etkisinin
> %95 güven aralığı **[−11,47, +10,35]** olup diğer dört ilin nokta tahminlerinin (−3,68 …
> −6,45) **hepsini içerir**. "Rize duyarsız" iddiası bu testten çıkmaz.
>
> Doğru test bir **etkileşim** testidir: Rize'nin Δ'sı eksi diğer dördünün ortalama Δ'sı, tohum
> eşleştirilmiş. Ölçüldü:
>
> | | tohum başına | ortalama | işaret | $p$ |
> | --- | --- | ---: | :-: | ---: |
> | mutlak (W/m²) | +5,52 / +6,66 / +2,46 | **+4,88** | 3/3 | 0,060 |
> | göreli (puan) | +6,29 / +6,72 / +3,52 | **+5,51 pp** | 3/3 | **0,032** |
>
> **Sonuç güçleniyor:** Rize kapasiteden diğer illerden anlamlı olarak daha az yararlanıyor
> (göreli ölçekte $p = 0{,}032$, üç tohumun üçünde). Makalede kullanılacak sayı budur; bir
> non-anlamlı tek-il $p$'si değil.

### 4.6 Cephe koşusu — merdiven dönmedi, **ama kalibrasyon çöktü**

`arch_sweep_x`'in lr sonucu (B-3) `[256,128]`'i varsayılan oranda okumayı serbest bıraktı. Kol
koşuldu; `abl_arch_h256x128_lr3e4_*` **koşulmadı**, çünkü önceden yazılmış kural buydu:
`h256x128` doğrulama kaybında kazanırsa lr varyantına gerek yok, kazanç açıklama gerektirmez.

**B-6. Merdiven 848.044 parametrede hâlâ dönmedi.** `[128,64]` → `[256,128]`, eşleştirilmiş:

| metrik | `[128,64]` | `[256,128]` | Δ | tohum başına | $p$ |
| --- | ---: | ---: | ---: | --- | ---: |
| `best_val_loss` | 0,12630 | **0,12000** | −0,0063 | −0,0075 / −0,0039 / −0,0075 | **0,034** |
| test RMSE (gündüz) | 90,29 | 88,58 | −1,71 | +0,13 / −4,68 / −0,59 | 0,371 |
| test MAE (gündüz) | 61,13 | 57,41 | −3,72 | 3/3 | **0,021** |
| CRPS (gündüz) | 46,47 | 44,10 | −2,37 | 3/3 | **0,045** |
| **CP (gündüz)** | 0,895 | **0,844** | **−0,051** | 3/3 | **0,005** |

Kazanç azalıyor: `[64,32]` → `[128,64]` dört Anadolu ilinde ortalama −5,4 W/m², `[128,64]` →
`[256,128]` −2,0 — 3,87 kat parametre için kazancın üçte biri. Ama **işaret hâlâ aynı ve
doğrulama kaybı hâlâ anlamlı**, yani "merdiven döndü" denemez.

**B-7. Rize'nin kapasiteye duyarsızlığı 14,5 kat parametrede de sürüyor.** `[64,32]` →
`[256,128]`, gündüz RMSE, il satırı, üç tohum eşleştirilmiş:

| il | `[64,32]` | `[128,64]` | `[256,128]` | Δ (256 vs 64) | $p$ | `[256,128]` CP |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Antalya | 87,25 | 81,06 | 79,22 | −8,03 | **0,014** | 0,8951 |
| Konya | 92,73 | 86,27 | 83,54 | −9,18 | **0,000** | 0,8619 |
| Ankara | 91,93 | 86,48 | 84,45 | −7,48 | **0,005** | 0,8459 |
| Van | 92,25 | 88,57 | 87,01 | −5,25 | **0,047** | 0,8689 |
| **Rize** | **107,43** | **106,86** | **106,15** | **−1,28** | **0,462** | **0,7466** |

Kapasiteyi 14,5 katına çıkarmak dört ili 5–9 W/m² iyileştiriyor, Rize'yi hâlâ iyileştirmiyor.
§4.5'in B-5 bulgusu böylece merdivenin iki basamağı boyunca doğrulanmış oluyor: **Rize'nin
hatası modelin kapasitesinden değil, bulutluluğun kendisinden geliyor**, ve havuzlama kazancı
(§5) bir kapasite artefaktı değil.

**B-8. Aralık genişliği epistemik yayılımı izliyor, hatayı değil — ve bu kalibrasyon
teşhisini rafine ediyor.** Gündüz `Aggregate`, on iki kol, kalite sırasına göre:

| kol | RMSE | MPIW | CP | **MPIW/RMSE** | CRPS |
| --- | ---: | ---: | ---: | ---: | ---: |
| `[32,16]` | 112,43 | 516,2 | 0,9791 | 4,59 | 61,18 |
| `dropout 0,4` | 101,69 | 488,1 | 0,9744 | 4,80 | 56,49 |
| `[64,64,32]` | 97,85 | 417,1 | 0,9640 | 4,26 | 51,90 |
| `lookback 48` | 94,87 | 409,5 | 0,9495 | 4,32 | 50,86 |
| `[64,32]` lr3e-4 | 94,75 | 405,2 | 0,9541 | 4,28 | 50,77 |
| **`[64,32]` referans** | 94,57 | 405,8 | **0,9540** | **4,29** | 50,63 |
| `lookback 72` | 94,42 | 410,3 | 0,9475 | 4,35 | 50,98 |
| `[128,64]` × `do 0,4` | 91,71 | 374,5 | 0,9260 | 4,08 | 48,88 |
| `dropout 0,2` | 91,21 | 322,4 | 0,9120 | 3,53 | 46,73 |
| `[128,64]` lr3e-4 | 90,91 | 310,8 | 0,8958 | 3,42 | 46,55 |
| `[128,64]` | 90,29 | 309,9 | 0,8949 | 3,43 | 46,47 |
| `[256,128]` | **88,58** | 242,1 | **0,8436** | **2,73** | **44,10** |

MPIW/RMSE oranı model kalitesiyle **güçlü biçimde ama tekdüze olmayarak** düşüyor
(4,59 → 2,73) ve CP onu yakından izliyor.

> **DÜZELTME (bağımsız review, `ABLATION_REVIEW_2.md`).** Bu paragrafın önceki sürümü iki
> kelimeyi ve bir sayıyı fazla güçlü söylüyordu:
>
> - **"tekdüze" yanlış:** RMSE sırasına dizildiğinde oranda **11 adımda 5 işaret dönüşü** var
>   (`dropout 0,4` 4,80 > `[32,16]` 4,59; `[64,32]` 4,29 > `[64,64,32]` 4,26; vb.). Doğru ifade
>   "güçlü negatif sıra ilişkisi", "tekdüze" değil.
> - **"istisnasız" yanlış:** 3,92 eşiği **12 kolun 3'ünde ihlal ediliyor** — `lookback 48`
>   (oran 4,32, CP 0,9495), `lookback 72` (4,35, 0,9475) ve en açık örnek
>   `[128,64] × dropout 0,4` (4,08, CP **0,9260**).
> - **Eşik 3,92 değil.** CP'yi orana regrese edip 0,95'i çözünce ampirik kırılma noktası
>   **4,27** çıkıyor. Gauss haritası 12 kolun 10'unda CP'yi **fazla** öngörüyor — beklenen bir
>   sonuç, çünkü aralık yüzdelik tabanlıdır (havuzlanan örneğin 2,5/97,5'i), ortalama ± $z\sigma$
>   değil, ve havuzlanmış dağılım Gauss değildir.
>
> **Ama ihlallerin kimliği bilgi taşıyor:** üçü de saf kapasite/düzenlileştirme kolu *değildir*
> — ikisi geriye bakışı (yani girdi penceresini, dolayısıyla veriyi) değiştirir, biri
> bilinçli iki eksenli koldur. Yedi saf kolun (`[32,16]`, `[64,32]`, `[128,64]`, `[256,128]`,
> `dropout 0,2`, `dropout 0,4`, `[64,64,32]`) **hepsi eşikle uyumludur.** Yani ilişki, artık
> dağılımının şeklini sabit tutan kollar içinde geçerlidir ve dışında değildir — §6.5'in
> `target_transform` ekseninde bulduğunun aynısı, burada önceden görülebilirmiş.

Regresyon tarafı doğrulandı ($R^2 = 0{,}9486$). Tek-eksenli on kol üzerinde CP ile
$\log(\text{MPIW})$ arasındaki cephede `[256,128]` bu cephenin **2,19 s.s. altında**.
$\text{RMSE} \sim \log(\text{MPIW})$ cephesinde ise `[256,128]`'in gözlenen RMSE'si 88,58,
cephenin o genişlik için öngördüğü 80,50'nin **2,31 s.s. üstünde** — yani aralık, hatanın
düştüğünden **daha hızlı** daralıyor.

> **Mekanizma ve makale için sonucu.** Aralık, havuzlanmış $B \times T$ örneğinin yüzdelikleri;
> o örnek yalnızca **epistemik** yayılımı taşır (`main_methodology.md` §11.5), aleatorik terim
> yok. Model iyileştikçe epistemik yayılım daralır, ama gerçek artık hata aynı hızda daralmaz —
> bu yüzden kapasite arttıkça kapsama çöker. Referans `[64,32]`'nin CP 0,954'ü **kalibrasyonun
> başarısı değil, bir işletme noktasının tesadüfüdür**: oranı 4,29 ile 3,92'nin hemen üstünde
> kalmıştır.
>
> Bu, `METHODOLOGY_REVIEW.md` K3'ü ne doğruluyor ne yanlışlıyor; **rafine ediyor.** §3.5,
> $B = 1 \to B = 8$ geçişinin kapsamayı yükselttiğini gösterdi, yani sorun "yalnızca eksik
> aleatorik terim" değildi. B-8 bunun tersini gösteriyor: doğruluk sabit tutulduğunda
> **kapasite kapsamayı bozuyor**. İkisi birlikte doğru teşhisi veriyor — aralık, epistemik
> yayılımın ne kadar büyük olduğuna göre değişiyor, oysa kapsaması gereken şey artık hatadır.
> **Aralıklar hiçbir zaman inşa gereği kalibre değildi; tek bir işletme noktasında tesadüfen
> doğruydular.**

**B-9. İki eksenli kol cepheyi kaydırmıyor.** `[128,64] × dropout 0,4`, tek eksenli kolların
CP–$\log$(MPIW) cephesinin **1,07 s.s. içinde** — yani düzenlileştirmeyi artırarak kapasiteyi
büyütmek, "aynı genişlikte daha doğru model" vermiyor, yalnızca aynı eğri üzerinde geriye
kaydırıyor: `[128,64]`'e göre CP +0,031 ama RMSE +1,42 ($p = 0,047$), MAE +3,10, CRPS +1,24
($p = 0,010$), doğrulama kaybı +0,0074 ($p = 0,081$). **Kalibrasyon dropout ile satın
alınamaz.** Bu, conformal katmanı bir alternatif değil, tek yol hâline getirir.

### 4.7 Hüküm

- **Referans `[64,32]` kapasitesinin belirgin biçimde altında.** `[64,32]` → `[128,64]` →
  `[256,128]` doğrulama kaybını 0,1436 → 0,1263 → 0,1200, gündüz RMSE'yi 94,57 → 90,29 → 88,58
  getiriyor. **Merdiven 848.044 parametrede hâlâ dönmemiş durumda**, ama kazanç azalıyor.
- **Nokta doğruluğunun kazananı `[256,128]`; ama hiçbir mimari kararı tek başına verilemez**
  (B-4, B-8). Kapasite ile kapsama ters yönlüdür ve bu bir ayar sorunu değil, aralığın **neyi
  ölçtüğüyle** ilgili yapısal bir sorundur.
- **Kalibrasyon dropout ile satın alınamaz** (B-9): iki eksenli kol cepheyi kaydırmıyor.
  Kapasite yükseltmesi **il × ufuk conformal ölçekleme ile aynı karar** olarak ele alınmalı;
  ikisi ayrı ayrı benimsenirse ya doğruluk ya kapsama feda edilir.
- **Öğrenme oranı, geriye bakış ve derinlik eksenleri kapandı** (B-1, B-2, B-3): hiçbiri
  referansı iyileştirmiyor.
- **§1–§3 ve §5'in tamamı `[64,32]` altında geçerliliğini koruyor**, çünkü B-5 ve B-7 en büyük
  etkinin ölçüldüğü ilde (Rize) kapasitenin merdivenin **iki basamağı boyunca** etkisiz
  olduğunu gösteriyor.
- **Sıradaki tek karar noktası:** kazanan mimariyi $B = 8$'de + conformal katmanla ölçmek.
  $B = 1$'de seçip $B = 8$'de raporlamak §3.2–§3.4'ün gösterdiği gibi güvenli değil.

### 4.8 Geçerlilik tehditleri

- **T-4.1 — `learning_rate` koşu anında ledger sütunu değildi.** `ABLATION_REVIEW.md` §4-B bunu
  koşudan *önce* uyarmıştı ve uyarı uygulanmadı; `abl_arch_lr3e4_*` satırları üç gün boyunca
  `abl_arch_base_*` ile ledger'da ayırt edilemez durumdaydı. **Kapatıldı:** altı optimize edici
  düğmesi `LEDGER_COLUMNS`'a eklendi ve 100 satır kendi `config.json`'larından geri dolduruldu
  (kayıpsız, çünkü her koşunun konfigürasyonu diskte). Yeni bir test her `ExperimentConfig`
  alanının ya ledger sütunu ya da gerekçeli muaf olmasını zorunlu kılıyor.
- **T-4.2 — doğruluk.** Tüm kollar $B = 1$. Aralık metrikleri (CP, MPIW, PINW, CWC) $B = 8$
  satırlarıyla **karşılaştırılamaz**; §0 kural 3. Kazanan mimari tam doğrulukta yeniden
  ölçülmelidir.
- **T-4.3 — parametre sayısı ile karşılaştırma.** `[128,64]` 219.244 parametre, referansın
  3,75 katı. Makale tutumluluk iddiası kuruyorsa (§5 ve §3.7) bu sayının hangi mimariye ait
  olduğu her yerde belirtilmelidir.
- **T-4.4 — tek eksen kuralının tek bilinçli istisnası `h128x64_do04`.** Diğer her kol
  referanstan tam bir alanda ayrılır. İki eksenli kol, cephenin kaydırılıp kaydırılamayacağını
  sormanın tek yolu olduğu için koşuldu (B-9) ve sonucu tam da bu soruya cevap veriyor;
  başka hiçbir kolla tek-eksen karşılaştırması yapılamaz.
- **T-4.6 — `[256,128]`'in test RMSE farkı anlamlı değil** ($p = 0,371$), çünkü tohum 42 ters
  yönde. Doğrulama kaybı ($p = 0,034$), MAE ($p = 0,021$) ve CRPS ($p = 0,045$) anlamlı ve
  il bazında dördü de anlamlı; ama **"`[256,128]` RMSE'de anlamlı olarak daha iyi" cümlesi
  bu koşulardan çıkmaz.** Üç tohum yetersiz.
- **T-4.7 — B-8'in oran analizi $B = 1$ kollarıdır.** MPIW/RMSE oranı $B$ ile de değişir
  (§3.5: $B=1 \to B=8$ MPIW'i %7,4 genişletir). Mekanizma argümanı doğruluk sabit tutulduğu
  için geçerlidir; **mutlak oran eşiği (3,92) $B = 8$'e taşınamaz.**
- **T-4.5 — çekişme.** `arch_sweep_x` ve `percity_endpoints` aynı makinede eşzamanlı koştu;
  `training_time_sec` değerleri %10–20 şişkin olabilir. Metrikler etkilenmez, **maliyet
  projeksiyonu bu satırlardan yapılmamalıdır**.

---

## 5. Havuzlama beş ilin **hepsini** iyileştiriyor mu? — uç nokta ablasyonu

> **Geçerlilik künyesi** — bu bölümün bulguları yalnızca bu konfigürasyonda geçerlidir (§0.2, §0.3).
>
> | veri kümesi | hedef dönüşümü | mimari | doğruluk | kriter | kapsam | tohum | cihaz |
> | --- | --- | --- | --- | --- | --- | --- | --- |
> | $F=17$, referans | `raw` | `[64,32]`, do 0,3 | $B{=}8$, $T{=}100$ | `mae` | beş ilin her biri `solo` ↔ `all5` | 42–44 | mps |
>
> **§7.6 aynı tasarımı `kt` altında tekrarlamış ve sonuç taşımamıştır.** Bu bölümün 15/15 sonucu `raw`'a koşulludur.


### 5.1 Sınanan iddia

`main_methodology.md` §1 (`:54-57`):

> **Küresel (global) model:** İl başına ayrı model eğitilmez. […] Bu, makalenin iddialarından
> biridir: farklı iklim rejimleri arasında bilgi transferi sağlanır ve **her il için** ayrı ayrı
> eğitilmiş modellere kıyasla veri verimliliği artar.

§1–§3, bu iddiayı **yalnızca Rize'de** test etti — ve Rize, transferin en çok işe yaraması
beklenen ildi (en düşük $k_t$, en yüksek hata). Bir ilde ölçülen bir etkiyi "her il için"
diye yazmak, makalede karşılaşılacak ilk itirazdır.

### 5.2 Hipotez ve iki olası sonuç

**H3: Havuzlama her ilde solo modeli geçer.** Yanlışlanması makaleyi zayıflatmaz, **daha keskin
bir iddiaya çevirir:** eğer dört kolay il kaybederken Rize kazanıyorsa, bulgu "havuzlama
yardımcı olur" değil, "**küresel model doğruluğu veri-fakiri rejime yeniden dağıtır**" olur —
hakemin önce ulaşamayacağı, daha ilginç bir sonuç.

### 5.3 Kolların konfigürasyonu

Her il için, o il **tek başına** eğitilir (`training_scope="per_city"`, diğer dördü
`excluded_cities`), kendi test pencerelerinde puanlanır ve **aynı ilin** `all5` satırıyla,
**aynı tohumda** karşılaştırılır. §2'nin `solo` ↔ `all5` kontrastının birebir aynısıdır,
yalnızca il değişir.

| ne | değer |
| --- | --- |
| kollar | `abl_percity_{ankara,antalya,konya,van}_s{42,43,44}_full` + mevcut `abl_rize_solo_s{42,43,44}_full` |
| karşı kol | `abl_rize_all5_s{42,43,44}_full`, ilgili ilin satırı |
| doğruluk | `ABLATION_FULL` — $B = 8$, $T = 100$, sapma yok |
| kayıp | L1 (`mae`), §2.2'nin kriter seçimi |
| ölçekleyici | `per_city_scaler=True` her iki kolda da (solo kolu tek il olduğu için etkisiz) |
| eğitim penceresi | solo 43.749 · `all5` 218.745 (tam 5×) |
| epok | `max_epochs=200`, `early_stop_patience=15`; **`hit_max_epochs=0` her satırda** |
| süre | kol başına 504–627 s, MPS |

### 5.4 Sonuçlar — nokta doğruluğu (gündüz, il satırı, 3 tohum)

| il | solo RMSE | `all5` RMSE | Δ | % | işaret | $p$ | solo MAE | `all5` MAE | $n_{el}$ |
| --- | ---: | ---: | ---: | ---: | :-: | ---: | ---: | ---: | ---: |
| Ankara | 91,34 ± 0,74 | **89,27 ± 0,52** | −2,07 | −2,27 | 3/3 | **0,019** | 68,44 | 66,64 | 109.644 |
| Rize | 108,32 ± 1,76 | **106,27 ± 0,81** | −2,05 | −1,89 | 3/3 | 0,152 | 77,28 | 75,70 | 109.043 |
| Konya | 91,79 ± 0,10 | **90,48 ± 0,30** | −1,31 | −1,43 | 3/3 | **0,016** | 69,49 | 68,27 | 109.476 |
| Antalya | 85,67 ± 1,11 | **84,65 ± 0,76** | −1,02 | −1,19 | 3/3 | 0,113 | 63,24 | 63,00 | 108.468 |
| Van | 90,51 ± 0,70 | **90,09 ± 0,57** | −0,43 | −0,47 | 3/3 | 0,052 | 66,09 | 66,15 | 109.499 |

**Her ilde, her tohumda: 15/15.** Hiçbir il havuzlamadan zarar görmüyor.

İki tamamlayıcı test:

- **İl bazında, Benjamini–Hochberg ($m = 5$, $\alpha = 0,05$).** Sıralı $p$: 0,016 (Konya),
  0,019 (Ankara), 0,052 (Van), 0,113 (Antalya), 0,152 (Rize). Adım-yukarı prosedürde
  $p_{(2)} = 0,019 \le 2/5 \times 0,05 = 0,020$ sağlandığı için **Konya ve Ankara düzeltme
  sonrası anlamlı**. Rize'nin $p = 0,152$'si §3.2 ile çelişmez: orada altı tohum vardı
  ($p = 0,0122$), burada üç.
- **Tohum düzeyinde kümelenmiş test.** Tek bir `all5` modeli beş ilde puanlandığı için beş il
  farkı bir tohum içinde bağımsız değildir. Tohum başına beş ilin ortalama göreli kazancı:
  **−1,455 / −1,747 / −1,136 %**, ortalama **−1,45 %**, $t = -8,19$, **$p = 0,0146$**.

### 5.5 Sonuçlar — belirsizlik (gündüz, il satırı, 3 tohum)

| il | solo CP | `all5` CP | solo MPIW | `all5` MPIW | ΔMPIW | solo CRPS | `all5` CRPS | ΔCRPS |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Ankara | 0,9811 | 0,9842 | 452,4 | 440,5 | −%2,63 | 50,10 | 48,41 | −%3,38 |
| Antalya | 0,9854 | 0,9837 | 471,1 | 459,7 | −%2,42 | 47,87 | 46,92 | −%1,98 |
| Konya | 0,9816 | 0,9813 | 473,6 | 457,8 | −%3,33 | 51,39 | 49,87 | −%2,97 |
| Van | 0,9839 | 0,9829 | 477,7 | 463,2 | −%3,03 | 49,93 | 49,06 | −%1,74 |
| Rize | 0,9529 | 0,9521 | 387,3 | 371,7 | −%4,05 | 54,87 | 53,30 | −%2,85 |

**Bu tablo §5.4'ten daha güçlüdür ve makalede ayrı bir cümleyi hak eder.** Havuzlama:

1. **aralığı her ilde daraltıyor** (−%2,4 … −%4,1),
2. **kapsamayı pratikte bozmadan** (|ΔCP| ≤ 0,0032 — *düzeltme:* Ankara $p = 0{,}024$ ve
   Antalya $p = 0{,}005$ ile **istatistiksel olarak anlamlıdır**; belgenin önceki sürümü
   "hiçbiri anlamlı değil" diyordu ve bu yanlıştı. Anlamlıdırlar ama büyüklükleri ihmal
   edilebilirdir: +0,0032 ve −0,0017, yani nominalden sapmanın onda biri mertebesinde),
3. **CRPS'yi her ilde iyileştirerek** (−%1,7 … −%3,4).

Yani kazanç, aralığı kısaltıp kapsamayı feda etme takası değildir; dağılım bir bütün olarak
daha iyidir. Aralık genişliği epistemik belirsizliğin ölçüsü olduğundan bunun yorumu doğrudan:
**havuzlama model belirsizliğini azaltır**, ve bu tam olarak transfer iddiasının öngördüğü
şeydir.

### 5.6 Kazancın büyüklüğü iklimsel aykırılığı takip **etmiyor**

Plan, kazancın "iklimsel olarak aykırı ilde en büyük" olmasını bekliyordu. Ölçülen sıralama
Ankara (−2,07) ≈ Rize (−2,05) > Konya (−1,31) > Antalya (−1,02) > Van (−0,43); göreli olarak
Ankara −%2,27 > Rize −%1,89 > Konya −%1,43 > Antalya −%1,19 > Van −%0,47.

Rize ikinci sırada. Kazanç ne $k_t$ ile (Ankara 0,806 ve Rize 0,697 en üstte, Konya 0,832 ve
Antalya 0,840 ortada, Van 0,821 en altta) ne de solo hata düzeyiyle tekdüze bir ilişki
gösteriyor. **Bu bölüm bir mekanizma önermiyor; ölçülen sıralamayı raporluyor.** Üç tohumla
iller arası sıralamayı ayırt etmek için yeterli güç yok — §2.3'ün "hangi il eklendiği önemli mi"
sorusunun burada da açık kaldığı anlamına gelir.

### 5.7 Hüküm

- **H3 desteklendi.** Havuzlama beş ilin **hepsinde** nokta doğruluğunu ve olasılıksal skoru
  iyileştiriyor, hiçbirinde zarar vermiyor, 15/15 tohum-kol.
- **"Yeniden dağıtım" senaryosu (§5.2) gerçekleşmedi.** Makale bunu doğrudan
  yazabilir — "havuzlama Rize'yi diğer illerin pahasına iyileştirmiyor" cümlesi artık ölçüme
  dayalıdır.
- **Makalenin §1 iddiası artık "her il için" ifadesini taşıyabilir.** Önceki hâliyle tek il
  üzerinden genellenmiş bir iddiaydı.
- **Tutumluluk argümanı güçlendi:** beş yerine tek model, 58.444'e karşı 5 × 58.428 = 292.140
  parametre, **ve her ilde daha iyi**. (Eğitim süresi üzerinden değil — §3.7.)

### 5.8 Geçerlilik tehditleri

- **T-5.1 — üç tohum.** Rize dışında hiçbir il altı tohuma çıkarılmadı. İl bazında $p$
  değerleri (Van 0,052, Antalya 0,113) güç sınırında; **birincil sonlanım noktası hâlâ §3.2'nin
  altı tohumlu Rize kontrastıdır.**
- **T-5.2 — bağımlılık.** Beş il farkı tohum içinde aynı `all5` modelinden gelir. §5.4'ün
  kümelenmiş testi ($n = 3$) bunu doğru ele alan tek testtir; 15/15 işaret sayımı **bağımsız
  15 gözlem değildir** ve öyle sunulmamalıdır.
- **T-5.3 — solo kolun mimarisi.** Solo kollar `[64,32]` kullanıyor, yani havuzlanmış rejim
  için ayarlanmış kapasite. §4 B-5 bunun Rize için bağlayıcı olmadığını gösterdi, ama dört
  kolay il kapasiteye duyarlı: bir solo `[128,64]` kolu Ankara/Konya/Antalya'da farkı
  kapatabilir. **Ölçülmedi.** Adil karşılaştırma her kolda aynı mimariyi kullanmaktır ve o
  sağlanmıştır; ama "solo model en iyi hâlinde de kaybeder" iddiası bu koşulardan çıkmaz.
- **T-5.4 — aşırı kapsama.** Dört ilin CP'si 0,981–0,985, nominal 0,95'in üstünde (§3.5).
  MPIW karşılaştırması bu nedenle "iki kalibre aralık arasında" değil, "iki fazla-geniş aralık
  arasında" bir karşılaştırmadır. Yön (daralma) yorumlanabilir, mutlak genişlikler
  yorumlanamaz.
- **T-5.5 — çekişme.** §4'teki T-4.5 ile aynı: bu kollar `arch_sweep_x` ile eşzamanlı koştu.

---

## 6. Hedef dönüşümü — ışınım yerine berraklık indeksi

> **Geçerlilik künyesi** — bu bölümün bulguları yalnızca bu konfigürasyonda geçerlidir (§0.2, §0.3).
>
> | veri kümesi | hedef dönüşümü | mimari | doğruluk | kriter | kapsam | tohum | cihaz |
> | --- | --- | --- | --- | --- | --- | --- | --- |
> | $F=17$, referans | **`raw` ↔ `clearsky_index`** | `[64,32]`, do 0,3 | $B{=}8$, $T{=}100$ | `mae` | beş il havuzlanmış | 42–44 | mps |
>
> Tek eksen: karşılaştırılan çift `experiment_grid.py` içinde alan alan doğrulanmıştır. `kt` mimarisi **optimize edilmemiştir** — §4'ün merdiveni `raw` altında koşuldu (T-7.5).


### 6.1 Sınanan iddia

Bu bölüm metodolojiden değil, **§3.6'nın ölçümünden** doğdu: model gündüz RMSE'sini beş ilde de
kazanıyor ama gündüz MAE'sini dördünde akıllı kalıcılığa kaybediyor. Önerilen mekanizma şuydu:

> Naif kurallar hedef saatin berrak-gökyüzü zarfını **ücretsiz** alır (akıllı kalıcılık taşıdığı
> $k_t$'yi $\text{CLRSKY}(t{+}h)$ ile çarpar; iklimsel ortalamanın (il, ay, saat) hücresi aynı
> geometriyi ezberler), model ise zarfı `hour_sin/cos` ve gün-içi kodlamasından çıkarmak
> zorundadır.

Sınanan önerme: **modele aynı geometriyi vermek farkı kapatır mı?** `target_transform`
(`main_methodology.md` §5.4) ağa $k_t = \text{ALLSKY}/\text{CLRSKY}$ regrese ettirir ve ters
ölçeklemeden sonra zarfı geri çarpar. `CLRSKY` saf astronomidir, hava terimi içermez, sızıntı
değildir ve öznitelik olmaz — modele yalnızca bu dönüşüm üzerinden ulaşır.

### 6.2 Kolların konfigürasyonu

| ne | değer |
| --- | --- |
| kollar | `abl_target_kt_s{42,43,44}_full` (`clearsky_index`) |
| karşı kol | `abl_rize_all5_s{42,43,44}_full` (`raw`) — **aynı dict, tek alan farkı** |
| doğruluk | `ABLATION_FULL` — $B = 8$, $T = 100$, sapma yok |
| kayıp / kapsam | L1, beş il havuzlanmış, `[64,32]` |
| epok | `hit_max_epochs = 0` her satırda |
| süre | 3429–3945 s (ham kolun 2337 s'sine karşı) |

Ham kol yeniden koşulmadı: `configs/experiment_grid.py::_target_kt_pooled` çifti **alan alan**
karşılaştırıp yalnızca `target_transform`'da ayrıldığını doğruluyor. Karşılaştırılabilirlik
kuralının istediği budur; aynı konfigürasyonu yeni bir id ile tekrar koşmak iki saate ve mükerrer
bir satıra mal olurdu.

**Sayısal ön kontrol (uygulamadan önce, `base_features.parquet` üzerinde):** gündüz `CLRSKY`'nin
tabanı 2,40 W/m², yani bölme hiçbir yerde patlamıyor; $k_t$ medyanı 0,885, p99'u 1,000,
151.643 gündüz saatinin 138'i 1,0'ı ve **yalnızca biri** 1,5'i aşıyor (belgelenmiş Van
1215,88 geri-çatım artefaktı). Kırpma veya eşik uygulanmadı, gerekmedi.

**Kod yolu doğrulaması:** eşleştirilmiş smoke çifti (`smoke_kt_check` / `smoke_raw_check`,
tohum 42, $B=1$, $T=10$, 5 epok) aggregate gündüz RMSE 101,46 → 89,44 ve MAE 73,95 → 62,40
verdi. Smoke doğruluğu, tabloya girmez; pahalı koşudan önce yön ve mertebe kontrolüydü.

### 6.3 Sonuçlar (gündüz, il satırı, 3 tohum eşleştirilmiş)

| il | `raw` RMSE | `kt` RMSE | Δ | % | $p$ | `raw` MAE | `kt` MAE | Δ | % | $p$ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Ankara | 89,27 ± 0,52 | **79,97 ± 0,28** | −9,30 | −10,4 | **0,002** | 66,64 | **57,39** | −9,25 | −13,9 | **0,001** |
| Antalya | 84,65 ± 0,76 | **75,15 ± 0,51** | −9,50 | −11,2 | **0,000** | 63,00 | **53,63** | −9,37 | −14,9 | **0,002** |
| Konya | 90,48 ± 0,30 | **81,14 ± 0,34** | −9,34 | −10,3 | **0,001** | 68,27 | **58,42** | −9,85 | −14,4 | **0,002** |
| Van | 90,09 ± 0,57 | **80,63 ± 0,33** | −9,46 | −10,5 | **0,002** | 66,15 | **56,70** | −9,45 | −14,3 | **0,001** |
| Rize | 106,27 ± 0,81 | **100,53 ± 1,25** | −5,74 | −5,4 | **0,008** | 75,70 | **69,67** | −6,03 | −8,0 | **0,002** |
| `Aggregate` | 92,45 ± 0,45 | **83,95 ± 0,31** | −8,50 | −9,2 | **0,000** | 67,95 | **59,16** | −8,79 | −12,9 | **0,001** |

Tohum başına aggregate ΔRMSE −8,50 / −8,69 / −8,31; ΔMAE −8,52 / −9,23 / −8,63. **Yayılım
etkinin %5'inden küçük** — projedeki en temiz sinyal.

Diğer metrikler (gündüz, 3 tohum ortalaması):

| il | `raw` R² | `kt` R² | `raw` CRPS | `kt` CRPS | `raw` MPIW | `kt` MPIW | `raw` CP | `kt` CP |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Ankara | 0,9019 | 0,9213 | 48,41 | 42,56 | 440,5 | 400,5 | 0,9842 | 0,9207 |
| Antalya | 0,9126 | 0,9311 | 46,92 | 40,34 | 459,7 | 411,4 | 0,9837 | 0,9667 |
| Konya | 0,9027 | 0,9218 | 49,87 | 43,90 | 457,8 | 418,1 | 0,9813 | 0,9158 |
| Van | 0,9003 | 0,9202 | 49,06 | 42,88 | 463,2 | 417,4 | 0,9829 | 0,9238 |
| Rize | 0,8137 | 0,8333 | 53,30 | 48,90 | 371,7 | 345,5 | 0,9521 | 0,9107 |
| `Aggregate` | 0,8926 | **0,9114** | 49,51 | **43,72** | 438,6 | 398,6 | 0,9769 | 0,9275 |

### 6.4 Taban çizgisi eşiği — MAE açığı kapandı (toplulaştırılmışta)

`CLAUDE.md`'nin çift eşiği, gündüz:

| il | `kt` RMSE | iklimsel | geçti? | `kt` MAE | akıllı kalıcılık | geçti? | (`raw` MAE) |
| --- | ---: | ---: | :-: | ---: | ---: | :-: | ---: |
| Ankara | 79,97 | 100,28 | ✓ | 57,39 | 55,99 | ✗ | 66,64 |
| Antalya | 75,15 | 95,02 | ✓ | 53,63 | 47,35 | ✗ | 63,00 |
| Konya | 81,14 | 100,55 | ✓ | 58,42 | 54,30 | ✗ | 68,27 |
| Van | 80,63 | 104,05 | ✓ | **56,70** | 58,08 | **✓** | 66,15 |
| Rize | 100,53 | 130,68 | ✓ | **69,67** | 85,23 | **✓** | 75,70 |
| `Aggregate` | 83,95 | 106,86 | ✓ | **59,16** | 60,19 | **✓** | 67,95 |

`raw`'da MAE eşiği yalnızca Rize'de geçiliyordu; `kt` ile **toplulaştırılmışta ve iki ilde**
geçiliyor. Üç ilde hâlâ kaybediliyor, ama açık 8–13 W/m²'den 1,4–6,3'e indi. §3.6'nın önerdiği
mekanizma **doğrulandı**: farkın büyük kısmı gerçekten geometriye erişim farkıydı.

> **Ama bu geçiş 24 saatlik ortalamada gerçekleşiyor, her ufuk adımında değil**
> (bağımsız review, `ABLATION_REVIEW_2.md`). Üç naif kural 24 saat gecikmeli aramalardır,
> dolayısıyla ufuk boyunca **düzdür** (akıllı kalıcılık RMSE 108,89–109,19; iklimsel
> 106,84–106,88, dört anlamlı basamakta sabit). Model ise ufukla bozulur:
>
> | ufuk | `kt` MAE | akıllı kalıcılık MAE | kazanan | `kt` beceri (iklime göre) | `raw` beceri |
> | ---: | ---: | ---: | :-: | ---: | ---: |
> | h=1 | 42,59 | 60,13 | **kt** | %46,5 | %37,6 |
> | h=5 | 53,22 | 60,13 | **kt** | %29,7 | %19,6 |
> | h=9 | 59,95 | 60,14 | **kt** | %19,9 | %12,5 |
> | h=10 | 60,98 | 60,14 | akıllı | %18,9 | %12,3 |
> | h=12 | 63,03 | 60,17 | akıllı | %17,0 | %11,0 |
> | h=24 | 63,43 | 60,26 | akıllı | %15,0 | **%3,3** |
>
> `kt`, akıllı kalıcılığın MAE'sini **24 ufuk adımının 9'unda** ($h \le 9$) geçiyor, h=10'dan
> itibaren **her adımda** kaybediyor. Manşet 1–24 havuzu olduğu için §6.4'ün "geçti" hükmü
> geçerlidir, ama hakem gün-öncesi satırını hesaplayacaktır ve **makalede bu tablo önceden
> verilmelidir.**
>
> **Aynı tablo `kt` lehine çok güçlü bir argüman da taşıyor:** ufkun ucunda `raw`'ın iklimsel
> ortalamaya göre becerisi %3,3'e çöküyor, `kt`'ninki %15,0'te kalıyor — **4,5 katı.** Gün
> öncesi tahminde asıl yaşanan yer h=24'tür ve `kt`'nin üstünlüğü orada en büyüktür. Bu,
> §6.6'nın kt lehine gerekçesine eklenmelidir.

### 6.4.1 Görülmemiş katkı — `kt` modeli **her iklim bölgesinde eşit becerikli** kılıyor

Bağımsız review'ün (`ABLATION_REVIEW_2.md`) bulduğu ve §6'nın ilk sürümünün gözden kaçırdığı
sonuç. İklimsel ortalamaya göre RMSE becerisi ($1 - \text{RMSE}/\text{RMSE}_{\text{iklim}}$),
gündüz, üç tohum:

| il | `raw` beceri | `kt` beceri |
| --- | ---: | ---: |
| Konya | %10,01 | %19,30 |
| Antalya | %10,91 | %20,91 |
| Ankara | %10,98 | %20,26 |
| Van | %13,42 | %22,51 |
| **Rize** | **%18,68** | **%23,07** |
| **iller arası yayılım** | **8,67 puan** | **3,77 puan** |

`raw` altında beceri ile ilin bulutluluk rejimi arasında güçlü bir bağ var: model Rize'de
%18,7, Konya'da %10,0 beceri gösteriyor — yani **beş il için eşit derecede iyi değil**.
`kt` altında yayılım **2,3 katı daralıyor** ve beş il %19,3–23,1 bandına giriyor.

**Bunun makale için değeri, doğruluk artışından ayrı ve ondan bağımsızdır.** Beş il "farklı
iklim kuşaklarını kapsasın diye" bilinçle seçilmiştir (`main_methodology.md` §3); ama `raw`
altında bu seçim yalnızca bir **zorluk ölçeği** üretiyordu. `kt` ile aynı seçim
"**yöntem iklim rejiminden bağımsız olarak aynı beceriyi veriyor**" iddiasına dönüşüyor —
tasarımın karşılığını veren sonuç budur, ve `kt` manşetinin doğruluktan bağımsız ikinci
gerekçesidir.

### 6.5 Kalibrasyon — B-8'in oran yasası bu eksende **çöküyor**

CP 0,977 → 0,9275'e, MPIW 438,6 → 398,6'ya düşüyor. İlk bakışta B-8'e benziyor
(model iyileşir, epistemik yayılım daralır, kapsama düşer) — ama ölçüm bunu **desteklemiyor**.

B-8'in oran yasası şuydu: gündüz MPIW/RMSE oranı %95 nominal için gereken 3,92'nin üstündeyse
fazla, altındaysa eksik kapsama; on iki kolda istisnasız. Burada:

| | MPIW | RMSE | **MPIW/RMSE** | CP |
| --- | ---: | ---: | ---: | ---: |
| `raw` | 438,6 | 92,45 | **4,74** | 0,9769 |
| `kt` | 398,6 | 83,95 | **4,75** | **0,9275** |

**Oran aynı, kapsama 0,05 düşük.** Ufuk kırılımı farkı daha da keskinleştiriyor:

| ufuk | `raw` oran | `raw` CP | `kt` oran | `kt` CP |
| ---: | ---: | ---: | ---: | ---: |
| h=1 | 6,40 | 0,9948 | **6,70** | **0,9357** |
| h=8 | 4,74 | 0,9785 | 4,78 | 0,9351 |
| h=24 | 4,13 | 0,9530 | 4,38 | 0,9258 |

h=1'de `kt`'nin oranı `raw`'dan **daha büyük** (6,70 > 6,40) ama kapsaması 0,06 **daha düşük**.
Yasa bu eksende geçerli değil.

**Doğru okuma.** MPIW/RMSE, artık dağılımının *şeklini* sabit tutan bir kol ailesi içinde
(B-8'in dayandığı on iki kolun tamamı `raw` mimari merdivenidir) CP'yi öngörür; **formülasyon değiştiğinde
öngörmez.** Mekanizma açık: `kt` kolunda aralık genişliği inşa gereği
$\text{CLRSKY}(t{+}h) \times (\text{$k_t$ uzayındaki genişlik})$'tir, yani güneş geometrisiyle
tam orantılıdır — öğle geniş, alacakaranlık dar. `raw` kolunun aralığı ise gün boyunca çok daha
düzdür (`raw` MPIW ufuk boyunca ×1,001, yani neredeyse sabit). İki kol aynı *toplam* genişliği
aynı *toplam* hataya oranlıyor ama genişliği eleman düzeyinde farklı dağıtıyor, ve kapsama bir
eleman özelliğidir.

**Bunun conformal tasarımına doğrudan sonucu var, ve önceki planı geçersiz kılıyor:**

> **DÜZELTME (§8.7).** Aşağıdaki 1. maddenin ızgara önerisi **ölçüldü ve yanlış çıktı.** Ufuk
> ekseni null: 16 koşuda `city_horizon`, `per_city`'ye 24 kat hücre karşılığında 0,0005
> kazandırıyor (C-1). Doğru ikinci eksen **mevsim**dir (C-3), ve sürücü berrak-gökyüzü düzeyi
> değil **bulut rejiminin mevsimsel değişkenliği**dir (C-5). "Skaler yetmez" ise ayakta, ama
> doğru ifadesiyle: skaler **marjinal** kapsamayı tutturur, **koşullu** kapsamayı vermez (C-2).
> 2. ve 3. maddeler değişmedi. Bu blok, o zaman ne düşünüldüğünün kaydı olarak bırakılmıştır.

1. **Skaler bir düzeltme yetmez.** Toplam oran zaten "doğru" görünürken kapsama yanlış
   olduğuna göre, tek bir çarpan hiçbir şeyi düzeltmez. Katsayı **en azından il × ufuk**
   ızgarasında olmalı — muhtemelen berrak-gökyüzü düzeyine göre de.
2. **Düzeltmenin yönü kola bağlı.** `raw` her ufukta nominalin **üstünde** (0,953–0,995,
   daraltma gerekir), `kt` her ufukta **altında** (0,910–0,957, genişletme gerekir). Çarpansal
   bir katsayı ızgarası ikisini de karşılar; bunu tek yönlü bir "daraltma katmanı" olarak
   tasarlamak `kt` kolunu bozardı.
3. **Yine de derin teşhis ayakta:** aralık epistemik yayılıma göre boyutlanıyor, oysa kapsaması
   gereken artık hata. §3.5 (doğruluk), B-8 (kapasite) ve §6.5 (formülasyon) üç ayrı eksende
   aynı yere çıkıyor. Conformal katman ertelenebilir bir iyileştirme değil.

### 6.6 Hüküm

- **`clearsky_index` her metrikte ve her ilde kazanıyor**, tam doğrulukta, üç tohumun üçünde,
  $p \le 0{,}008$. Bu, projedeki tek en büyük iyileşme.
- **§3.6'nın mekanizma açıklaması doğrulandı** ve MAE açığı toplulaştırılmışta kapandı.
- **Kalibrasyon bedeli var** (CP 0,977 → 0,928) ve conformal katmanla birlikte ele alınmalı.
  §6.5 ayrıca conformal tasarımını değiştirdi: skaler bir katsayı yetmez, ızgara gerekir, ve
  düzeltme yönü kola göre ters işaretlidir.
- **Manşet konfigürasyonu değiştirme kararı henüz verilemez** (§6.7, T-6.1).

### 6.7 Geçerlilik tehditleri

- **T-6.1 — transfer sonucu `raw` altında ölçüldü.** §1–§5'in tamamı (H1 altı tohum, uç nokta
  ablasyonu) `target_transform="raw"` kollarıdır. `kt`'nin manşet olması hâlinde bunların hepsi
  yeniden ölçülmelidir, ve **taşınacağı varsayılamaz.** Kuşkunun yönü belirli: `raw` modelin
  öğrenmek zorunda olduğu şeyin büyük kısmı güneş-geometrisi zarfıdır, ki bu beş il arasında
  **en açık biçimde paylaşılan** yapıdır — yani havuzlamanın yardımcı olduğu şeyin ta kendisi
  olabilir. Zarfı bedava vermek transfer kazancını küçültebilir veya yok edebilir. `target_kt_h1`
  grubu (3 kol, ~0,7 sa) tam olarak bunu soruyor ve **her şeyden önce koşulmalıdır.**
- **T-6.2 — eksen iki etkiyi birlikte taşıyor ve ayrılamaz.** Hedef tanımı ve onun ima ettiği
  kayıp ağırlıklandırması ($k_t$ uzayında bulutlu öğle ile açık sabah benzer ağırlık taşır,
  W/m² uzayında yüksek ışınımlı saatler baskındır) tek bir değişikliktir. Kol bunlardan birini
  yalıtmaz; makale de öyle sunmamalıdır.
- **T-6.3 — `best_val_loss` iki kol arasında karşılaştırılamaz.** `kt` kolunun 0,28'i ile ham
  kolun 0,14'ü farklı birimlerdeki kayıplardır. Ledger sütununun uyarısı buna göre genişletildi.
- **T-6.4 — üç tohum.** Etki tohum yayılımının mertebelerce üstünde, ama H1'in birincil sonlanım
  noktası altı tohumdur; `kt` altında da altıya çıkarılmalıdır (`target_kt_full`).
- **T-6.5 — kapsama düştü.** §6.3'ün aralık metrikleri nominalin altında; `kt` kolunun CP'si
  Rize'de 0,9107. Kaynak makaleyle PICP karşılaştırması bu kolda **yeniden kurulmalıdır**
  (`main_methodology.md` §11.5, sonuç 3).

---

## 7. Transfer iddiası formülasyona dayanıklı mı? — hayır, ama kayıp yerine bir şey kazanıyor

> **Geçerlilik künyesi** — bu bölümün bulguları yalnızca bu konfigürasyonda geçerlidir (§0.2, §0.3).
>
> | veri kümesi | hedef dönüşümü | mimari | doğruluk | kriter | kapsam | tohum | cihaz |
> | --- | --- | --- | --- | --- | --- | --- | --- |
> | $F=17$, referans | **`clearsky_index`** | `[64,32]`, do 0,3 | $B{=}8$, $T{=}100$ | `mae` | beş ilin her biri `solo` ↔ `all5` | 42–44 | mps |
>
> §3 ve §5'in `kt` altındaki tekrarıdır. **Bu bölüm §0.3'ün matrisindeki en güçlü satırın kanıtıdır:** bulgular formülasyona koşulludur.


### 7.1 Sınanan iddia

§6 `clearsky_index`'i her metrikte kazanan hâle getirdi, ama §1–§5'in **tamamı** `raw` altında
ölçülmüştü. `ABLATION_REVIEW`den değil, §6.7'nin T-6.1'inden gelen kuşku belirli bir yöne
işaret ediyordu ve bu bölüm onu koşumdan **önce** yazılmış hâliyle sınıyor:

> `raw` modelin öğrenmek zorunda olduğu şeyin büyük kısmı güneş-geometrisi zarfıdır, ki bu beş
> il arasında **en açık biçimde paylaşılan** yapıdır — yani havuzlamanın yardımcı olduğu şeyin
> ta kendisi olabilir. Zarfı bedava vermek transfer kazancını küçültebilir veya yok edebilir.

### 7.2 Kolların konfigürasyonu

`target_kt_h1` grubu: `abl_target_kt_solo_s{42,43,44}_full` (Rize tek başına, `clearsky_index`).
Eşleşen havuzlanmış kol §6'nın `abl_target_kt_s{42,43,44}_full`'ü. Karşılaştırma **§2.2/§3.2'nin
`solo` ↔ `all5` kontrastının birebir aynısıdır**, yalnızca `target_transform` değişir.
$B = 8$, $T = 100$, L1, `[64,32]`, `hit_max_epochs = 0`, kol başına 700–774 s.

### 7.3 Sonuç — nokta tahmininde transfer **kayboluyor**

Rize satırı, gündüz, üç tohum eşleştirilmiş:

| dönüşüm | `solo` RMSE | `all5` RMSE | Δ | % | işaret | $p$ | tohum başına |
| --- | ---: | ---: | ---: | ---: | :-: | ---: | --- |
| `raw` | 108,32 ± 1,76 | 106,27 ± 0,81 | **−2,05** | −1,89 | 3/3 | 0,152 | −1,98 / −3,65 / −0,51 |
| `clearsky_index` | 101,33 ± 1,93 | 100,53 ± 1,25 | **−0,79** | −0,78 | 2/3 | 0,348 | −1,30 / −1,59 / **+0,50** |

MAE'de daha da net: `raw` −1,58 (3/3, $p = 0{,}050$) → `kt` **−0,01** (2/3, $p = 0{,}985$).
Etki **tamamen** yok oluyor.

**Hipotez doğrulandı.** Havuzlamanın satın aldığı şeyin büyük kısmı gerçekten paylaşılan
berrak-gökyüzü zarfıydı. Zarf modele doğrudan verildiğinde, ondan öğrenilecek bir şey kalmıyor.

> **Bu, "havuzlama işe yaramıyor" demek değildir; "havuzlamanın ne yaptığını artık biliyoruz"
> demektir.** Ve bu, ölçülmemiş bir iddiadan daha güçlü bir bilimsel ifadedir. Ama makalenin
> §1'deki iddiasını **olduğu gibi bırakamaz.**

### 7.4 Rize'de kazanılan şey — ve neden bunu genellemek hataydı

Stage 1 yalnızca Rize'yi ölçmüştü ve orada tablo şuydu:

| metrik | `raw` solo → all5 | Δ | $p$ | `kt` solo → all5 | Δ | $p$ |
| --- | --- | ---: | ---: | --- | ---: | ---: |
| **CP** | 0,9529 → 0,9521 | −0,0008 | 0,840 | 0,8800 → **0,9107** | **+0,0307** | **0,0001** |
| MPIW | 387,3 → 371,7 | −15,7 | 0,028 | 350,1 → 345,5 | −4,6 | **0,010** |
| CRPS | 54,87 → 53,30 | −1,56 | 0,065 | 50,11 → 48,90 | −1,21 | 0,058 |

Bu belgenin önceki sürümü buradan **"transfer ortalamadan belirsizliğe taşınıyor"** sonucunu
çıkarmıştı. **Bu genelleme yanlıştı** ve beş il koşulunca (§7.8) çöktü: diğer üç ilde havuzlama
kalibrasyonu **bozuyor**, net etki tam olarak sıfır. Doğru ifade §7.8'dedir.

> **Tekrarlayan hata biçimi.** §0'ın "Aggregate tuzağı"nın kardeşi: **Rize tuzağı.** Rize
> transferin en çok işe yaraması beklenen ildir, dolayısıyla orada ölçülen her etki üst
> sınırdır ve işareti bile diğer illere taşınmayabilir. §5 bu dersi bir kez verdi (kazanç
> iklimsel aykırılığı takip etmiyordu); §7.4 aynı hatayı bir kez daha üretti. **Tek ilden
> genelleme yapılmaz** — beş il kolu koşulmadan hiçbir "transfer şu biçimde çalışıyor"
> cümlesi yazılmamalıdır.

### 7.5 Güç çözümlemesi — daha fazla tohum yanlış yatırım

Ölçülen `kt` RMSE etkisi −0,795, eşleştirilmiş s.s. 1,132. Buradan:

| $n$ | beklenen $t$ | beklenen $p$ |
| ---: | ---: | ---: |
| 3 (mevcut) | 1,22 | 0,348 |
| 6 | 1,72 | 0,146 |
| 10 | 2,22 | 0,054 |
| 20 | 3,14 | 0,005 |

Altı tohuma çıkmak (~3,7 sa) beklenen $p \approx 0{,}15$ verir — sonuç değil. Yirmi tohum
(~12 sa) tek bir ilin nokta tahmini için ödenemez. **Doğru yatırım beş il uç nokta
ablasyonudur** (`target_kt_endpoints`, 12 kol, ~2,7 sa): §5'in kümelenmiş testi üç tohumla
$p = 0{,}0146$'ya ulaşmıştı, çünkü beş il tek bir tohumun içinde beş kontrast üretiyor.

**Koşuldu** (§7.6–§7.7) ve karar verdi: 2,7 saat, tek ilde 12 saat harcamanın veremeyeceği bir
cevap üretti — hem de üç ilde işaretin ters döndüğünü göstererek, ki tohum sayısını artırmak
bunu asla ortaya çıkaramazdı.

### 7.6 Beş il uç nokta ablasyonu, `kt` altında — net kazanç yok, **yeniden dağıtım var**

`target_kt_endpoints` (12 kol) + §7.2'nin Rize kolu. Her il tek başına, aynı ilin `all5` satırı,
aynı tohum, gündüz, üç tohum eşleştirilmiş:

| il | solo RMSE | `all5` RMSE | Δ | % | işaret | $p$ | ΔMAE | $p$ |
| --- | ---: | ---: | ---: | ---: | :-: | ---: | ---: | ---: |
| Ankara | 80,68 | 79,97 | −0,72 | −0,89 | 3/3 | **0,035** | +0,33 | 0,400 |
| Antalya | 74,76 | 75,15 | **+0,39** | **+0,52** | 1/3 | 0,318 | **+2,38** | **0,043** |
| Konya | 81,20 | 81,14 | −0,06 | −0,07 | 2/3 | 0,902 | +0,10 | 0,531 |
| Van | 81,58 | 80,63 | −0,95 | −1,17 | 2/3 | 0,192 | −0,21 | 0,825 |
| Rize | 101,33 | 100,53 | −0,79 | −0,78 | 2/3 | 0,348 | −0,01 | 0,985 |

İki formülasyon yan yana (ΔRMSE, aynı kontrast, aynı tohumlar):

| il | `raw` Δ | `raw` % | `kt` Δ | `kt` % |
| --- | ---: | ---: | ---: | ---: |
| Ankara | −2,07 | −2,27 | −0,72 | −0,89 |
| Antalya | −1,02 | −1,19 | **+0,39** | **+0,52** |
| Konya | −1,31 | −1,43 | −0,06 | −0,07 |
| Van | −0,43 | −0,47 | −0,95 | −1,17 |
| Rize | −2,05 | −1,89 | −0,79 | −0,78 |

**Tohum düzeyinde kümelenmiş test** (bağımsızlığı doğru ele alan tek test, §5.4):

| dönüşüm | tohum başına ort. göreli kazanç | ortalama | $t$ | $p$ |
| --- | --- | ---: | ---: | ---: |
| `raw` | −1,455 / −1,747 / −1,136 % | **−1,446 %** | −8,19 | **0,0146** |
| `clearsky_index` | −0,326 / −0,986 / −0,100 % | −0,471 % | −1,77 | **0,2184** |

`raw` altında **15/15 tohum-kol** havuzlamayı destekliyordu. `kt` altında işaret karışıyor
(Antalya tersine dönüyor), etki %67 küçülüyor ve kümelenmiş test **null**.

### 7.7 Kalibrasyon da net sıfır — ama güçlü biçimde yeniden dağıtıyor

Reliability ($|CP - 0{,}95|$, küçük iyi), `kt`, gündüz, üç tohum eşleştirilmiş:

| il | solo CP | `all5` CP | solo Rel. | `all5` Rel. | Δ Rel. | iyileşti | $p$ |
| --- | ---: | ---: | ---: | ---: | ---: | :-: | ---: |
| **Rize** | 0,8800 | **0,9107** | 0,0700 | **0,0393** | **−0,0307** | 3/3 | **0,0001** |
| Antalya | 0,9332 | 0,9667 | 0,0168 | 0,0167 | −0,0002 | 1/3 | 0,949 |
| Van | 0,9304 | 0,9238 | 0,0196 | 0,0262 | **+0,0065** | 0/3 | **0,013** |
| Ankara | 0,9289 | 0,9207 | 0,0211 | 0,0293 | **+0,0082** | 0/3 | 0,060 |
| Konya | 0,9319 | 0,9158 | 0,0181 | 0,0342 | **+0,0160** | 0/3 | **0,0066** |
| **kümelenmiş** | | | | | **+0,0000** | | **0,995** |

Havuzlama Rize'nin kalibrasyonunu belirgin biçimde **iyileştiriyor** ve üç ilinkini
**bozuyor**; net etki **tam olarak sıfır** ($t = -0{,}01$, $p = 0{,}995$). CRPS de aynı biçimde
karışık (Ankara −0,41 $p = 0{,}017$ ve Rize −1,21 $p = 0{,}058$ iyileşiyor; Antalya +1,17
$p = 0{,}010$ kötüleşiyor).

> **Bu tam olarak `percity_endpoints`'in docstring'inde öngörülen "yeniden dağıtım"
> senaryosudur** — `raw` altında **gerçekleşmemişti** (§5.7: hiçbir il zarar görmüyordu), `kt`
> altında **gerçekleşiyor**, ve nokta tahmininde değil kalibrasyonda. Küresel model, zarf
> verildikten sonra kalan kapasitesini veri-fakiri/gürültülü rejime yeniden tahsis ediyor,
> kolay illerin pahasına.

### 7.8 Hüküm ve makale için sonuç

- **H1 formülasyona dayanıklı değildir.** `kt` altında nokta tahmininde havuzlamanın net kazancı
  yok (kümelenmiş $p = 0{,}218$), işaret karışık, Antalya tersine dönüyor. §1–§5'in tamamı
  **`raw`'a koşulludur.**
- **Kalibrasyonda da net kazanç yok** ($p = 0{,}995$) — ama dağılım **kuvvetle yeniden
  dağıtıcıdır**: Rize −0,0307 ($p = 0{,}0001$), Konya +0,0160 ($p = 0{,}0066$), Van +0,0065
  ($p = 0{,}013$).
- **Öngörülen mekanizma doğrulandı.** Havuzlamanın satın aldığı şeyin büyük kısmı beş il
  arasında paylaşılan güneş-geometrisi zarfıydı; zarf modele doğrudan verildiğinde ondan
  öğrenilecek bir şey kalmıyor.
- **Makale için en güçlü çerçeve `kt` manşet + `raw` → `kt` geçişinin ablasyon olarak
  sunulmasıdır.** Gerekçe:
  - `kt` mutlak doğrulukta %9–13 daha iyi ve akıllı kalıcılığın MAE eşiğini toplulaştırılmışta
    geçiyor (§6.4). "Neden berraklık indeksi tahminlemediniz?" solar tahmin yazınının standart
    sorusudur ve `raw` manşetle savunulamaz.
  - Transfer iddiası **ölçülmemiş bir varsayımdan, mekanizması ölçülmüş bir açıklamaya**
    dönüşüyor: havuzlama ışınım uzayında yardımcıdır çünkü paylaşılan geometriyi öğretir;
    geometri verildiğinde kalan rol yeniden dağıtımdır.
  - Yeniden dağıtım iddiası ("küresel model doğruluğu ve kalibrasyonu veri-fakiri rejime
    tahsis eder") **hakemin ilk ulaşacağı itiraz değildir** ve tek il üzerinden değil, beş il
    ve üç tohum üzerinden ölçülmüştür.
- **Bu bir yokluk sonucu değil, bir küçülme/yeniden dağıtım sonucudur** (§7.9, T-7.1).

### 7.9 Geçerlilik tehditleri

- **T-7.1 — bu bir yokluk sonucu DEĞİLDİR.** §7.6 "havuzlamanın etkisi yok" demiyor;
  "net etki üç tohumla saptanamayacak kadar küçüldü ve **işaret iller arasında tutarsızlaştı**"
  diyor. İkincisi birincisinden güçlüdür ve tohum sayısıyla düzelmez: Antalya'nın RMSE'de
  (+0,39) ve MAE'de (+2,38, $p = 0{,}043$) ters yönde olması bir güç sorunu değildir.
- **T-7.2 — üç tohum.** İl bazlı $p$'lerin çoğu güç sınırında. Kümelenmiş test doğru araçtır
  ve o da $n = 3$ ile çalışıyor; `raw` altında bu $p = 0{,}0146$ vermeye yetmişti, dolayısıyla
  `kt`'deki $p = 0{,}218$ yalnızca güç eksikliğiyle açıklanamaz — etki büyüklüğü üçte bire
  inmiştir.
- **T-7.3 — kalibrasyon karşılaştırması nominalin altındaki bir bölgede.** `kt` kollarının
  CP'si 0,880–0,967, çoğu %95'in altında. "Havuzlama Rize'nin kalibrasyonunu iyileştiriyor"
  doğrudur; "kalibre ediyor" değildir. Conformal katman her iki kolda da gereklidir
  (`main_methodology.md` §11.5).
- **T-7.4 — dönüşüm ile kayıp ağırlıklandırması ayrılamaz** (§6.7, T-6.2). Transfer kazancının
  küçülmesi zarfın verilmesinden değil, kayıp ağırlıklandırmasının değişmesinden de
  kaynaklanıyor olabilir. İki etki tek değişikliktir ve bu kollar onları ayırmaz. Ayıracak kol
  düşünülebilir (`kt` hedefi + W/m² uzayında ağırlıklandırılmış kayıp) ama koşulmamıştır.
- **T-7.5 — `raw` kolları `[64,32]`, `kt` kolları da `[64,32]`.** Mimari sabittir, dolayısıyla
  karşılaştırma adildir; ancak `kt` formülasyonunun optimal kapasitesi ölçülmemiştir. §4'ün
  merdiveni `raw` altında koşuldu ve `kt` altında farklı sonuçlanabilir.
- **T-7.6 — tek ilden genelleme.** §7.4'ün kayıt altına aldığı hata biçimi. Bu bölümdeki her
  cümle beş il × üç tohum üzerinden kurulmuştur; Rize satırı tek başına hiçbir şeyin kanıtı
  değildir.

---

## 8. Conformal aralık katmanı — kapsamayı yeniden kuran ızgaranın geometrisi

> **Geçerlilik künyesi** — bu bölümün bulguları yalnızca bu konfigürasyonda geçerlidir (§0.2, §0.3).
>
> | veri kümesi | hedef dönüşümü | mimari | doğruluk | kriter | kapsam | tohum | cihaz |
> | --- | --- | --- | --- | --- | --- | --- | --- |
> | $F=17$, referans | `raw` **ve** `clearsky_index` | `[64,32]`, do 0,3 | **$B{=}1$ (teşhis), smoke (kod yolu)** | `mae`, `mse`, `huber` | beş il havuzlanmış ve alt kümeler | 42–44 | cpu |
>
> **Bu bölümde tam doğrulukta ölçülmüş hiçbir sayı yoktur.** Geometri seçimi 16 bitmiş $B{=}1$
> koşusunun tahmin dökümlerinden, kod yolu doğrulaması smoke doğrulukta yapıldı. Doğruluk
> aralığın *ne olduğunu* değiştirir (§0.3, $B$ satırı), dolayısıyla buradaki $k$ değerleri
> $B{=}8$'in $k$ değerleri **değildir** — taşınan şey yapıdır, sayılar değil. `conformal`
> grubunun altı kolu koşulduğunda bu künye güncellenir.

### 8.1 Sınanan iddia

Havuzlanmış Bootstrap × MC-Dropout örneği yalnızca **epistemik** yayılım taşır — modelin kendi
ortalamasının nerede olabileceği — oysa aralık **gözlemi** kapsayıp kapsamadığına göre puanlanır,
ki bu ek olarak artık (aleatorik) terimi de içerir. Boru hattında ikisini uzlaştıran hiçbir adım
yoktur, bu yüzden kapsama bu uyumsuzluğun ne verdiğiyse odur — ve üç bağımsız eksende, birbirini
düzeltmeyecek biçimde bozulur (§3.5 doğruluk, §4.6 kapasite, §6.5 formülasyon).

§6.5 bundan bir tasarım önerisi çıkarmıştı: düzeltme **skaler olamaz**, **en azından il × ufuk**
ızgarası olmalı, ve **işareti kola göre değişmeli** (`raw` daraltma, `kt` genişletme). Bu bölüm o
öneriyi ölçtü. İki maddesi doğrulandı, biri **yanlış çıktı.**

### 8.2 Düzeltmenin biçimi — aralığın değil, **dağılımın** ölçeklenmesi

Katman öngörü dağılımını kendi ortalaması etrafında yeniden ölçekler:

$$x \;\longmapsto\; m + k\,(x - m),$$

hücre başına tek bir $k$ ile. Bu bilinçli olarak **aralık hakkında değil, dağılım hakkında** bir
ifadedir ve üç sonucu vardır:

1. Dönüşüm afin ve artan olduğu için yeniden ölçeklenmiş örneğin 2,5/97,5 yüzdelikleri, tam
   olarak yeniden ölçeklenmiş yüzdeliklerdir — CP/PINW/MPIW/CWC **ve CRPS** birbiriyle tutarlı
   kalır. Uç noktaları toplamsal kaydıran CQR biçimi aralığı düzeltir ama CRPS'i düzeltilmemiş
   bir dağılımı betimler hâlde bırakırdı; tek ledger satırında iki uyumsuz nesne olurdu.
2. Ortalama **değişmez**, dolayısıyla RMSE/MAE/R² son hanesine kadar aynıdır. Uçtan uca test
   edilmiştir (`tests/test_conformal.py`).
3. $k$ doğrudan okunur: $k<1$ epistemik yayılım artıklara göre fazla genişti, $k>1$ dardı.
   Yazımın istediği sayı budur.

Kalibrasyon skoru, bir elemanı kapsayacak **en küçük** $k$'dir:

$$s = \frac{y-m}{U-m}\ \ (y \ge m), \qquad s = \frac{m-y}{m-L}\ \ (y < m),$$

ve hücrenin $k$'si $\{s_i\}$'nin $\lceil (n+1)(1-\alpha)\rceil$'inci en küçüğüdür — kapsama
garantisini asimptotik değil **sonlu örnekte kesin** kılan düzeltme.

**Gece hiçbir zaman kalibre edilmez ve hiçbir zaman düzeltilmez.** Ufkun altında $m=L=U=0$ ve
$y=0$, yani skor $0/0$; bu elemanlar aralık genişliği hakkında bilgi taşımaz, uyuma girmez ve
$k=1$'de bırakılır.

### 8.3 Izgara geometrisi — C-1…C-4

`scripts/07_conformal_diagnostic.py`, tahmin dökümü olan **16 bitmiş koşunun** test
pencerelerinin yarısında her modu uyarlayıp diğer yarısında puanlıyor. Dört kalibrasyon
geometrisi karşılaştırılıyor; makaleye giren `production_like` (rastgele yarı, **Nisan ve Mayıs
çıkarılmış** — gerçek doğrulama bölmesinin deliği), ölçüt **il başına en kötü** $|CP-0{,}95|$,
16 koşunun ortalaması:

| mod | hücre | exchangeable | season_balanced | **production_like** | temporal |
| --- | ---: | ---: | ---: | ---: | ---: |
| düzeltilmemiş | 0 | 0,2015 | 0,2001 | **0,2052** | 0,2510 |
| `global` | 1 | 0,0224 | 0,0256 | **0,0314** | 0,0608 |
| `per_horizon` | 24 | 0,0217 | 0,0250 | **0,0302** | 0,0614 |
| `per_season` | 4 | 0,0304 | 0,0462 | **0,0282** | 0,0483 |
| `per_city` | 5 | 0,0032 | 0,0113 | **0,0136** | 0,0905 |
| `city_horizon` | 120 | 0,0031 | 0,0109 | **0,0131** | 0,0914 |
| **`city_season`** | 20 | 0,0032 | 0,0202 | **0,0099** | 0,0507 |

Toplulaştırılmış $|CP-0{,}95|$ aynı sırayla: düzeltilmemiş 0,1556 → `global` 0,0069 →
`city_season` **0,0035**.

- **C-1: ufuk ekseni null.** `city_horizon`, `per_city`'ye 24 kat hücre karşılığında 0,0005
  kazandırıyor, ve bu **dört geometrinin hepsinde** böyle. §6.5'in "en azından il × ufuk"
  önerisi **ölçülüp yanlış çıktı**; ufuk eksenini eklemek hücreleri inceltmekten başka bir şey
  yapmıyor. (Düzeltme kaydı §8.7'de.)
- **C-2: il ekseni koşullu kapsamayı düzelten eksendir.** 0,0314 → 0,0136, 2,3 kat. Skaler bir
  çarpan **toplulaştırılmış** kapsamayı zaten tutturuyor (0,0069) — dört ili fazla, Rize'yi
  eksik kapsayarak. Bu, **Aggregate tuzağının (K-1) kapsama biçimidir** ve §6.5'in "skaler
  yetmez" iddiasının doğru ifadesidir: skaler **marjinal** kapsamayı verir, **koşullu**
  kapsamayı vermez.
- **C-3: kimsenin önermediği mevsim ekseni %27 daha kazandırıyor** (0,0136 → 0,0099) ve
  `city_horizon`'un 120 hücresi yerine 20 hücre kullanıyor.
- **C-4: mevsim ekseni en kötü durumda da en dayanıklısıdır.** `temporal` geometride (kalibrasyon
  ilkbahar-yaz, değerlendirme sonbahar-kış) `per_city` **en kötü** moda düşüyor (0,0905), mevsim
  modları en iyide kalıyor (0,0483–0,0507): mevsim hücresi hiç değilse bir yaz katsayısını kışa
  uygulamıyor.

**Ayrıştırma — hangi tehdit gerçek?** `temporal` geometride hiçbir mod nominale ulaşmıyor
(toplulaştırılmış $|CP-0{,}95|$ 0,032–0,056), `season_balanced` geometride (aylar dönüşümlü:
zamansal olarak iç içe ama mevsimsel olarak dengeli) her mod 0,003–0,014'e dönüyor. Yani hasar
**mevsimsel bileşimden** kaynaklanıyor, yıldan yıla kaymadan değil. On iki ayın onunu kapsayan
bir doğrulama bölmesinin çalışabilir bir kalibrasyon kümesi, kronolojik ilk yarının ise
olmamasının nedeni budur.

### 8.4 C-5 — $k$ mevsimle 1,7–2,5 kat oynuyor

`outputs/tables/conformal_month_stability_test.csv`: $k$ ay ay yeniden uyarlandığında **16
koşunun hepsinde** yıl içinde 1,67–2,51 kat salınıyor. Üç temsilci koşu, aylık $k$:

| koşu | 01 | 02 | 03 | 04 | 05 | 06 | 07 | 08 | 09 | 10 | 11 | 12 | salınım |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `abl_loss_mae_s42_b1` | 1,04 | 1,35 | 1,42 | 1,30 | 1,13 | 0,79 | 0,74 | 0,82 | 0,94 | 0,95 | 0,88 | 0,97 | 1,91× |
| `abl_rize_all5_s42_b1` | 1,49 | 1,64 | 1,56 | 1,60 | 1,34 | 0,82 | 0,91 | 1,09 | 1,34 | 1,49 | 1,49 | 1,53 | 2,00× |
| `abl_loss_huber_s42_b1` | 1,57 | 1,68 | 1,61 | 1,59 | 1,40 | 0,99 | 1,10 | 1,33 | 1,51 | 1,54 | 1,59 | 1,64 | 1,70× |

Mekanizma: **bulut değişkenliği mevsimseldir, epistemik yayılım değildir.** Haziran–Temmuz'da
gökyüzü berrak, artıklar küçük, mevcut aralık zaten yeterince geniş ($k \approx 0{,}74$–1,10);
Şubat–Nisan'da bulut rejimi oynak, artıklar büyük, aralığın %60'a varan genişletilmesi gerekiyor
($k \approx 1{,}35$–1,68). Bu, §6.5'in "muhtemelen berrak-gökyüzü düzeyine göre de" tahminini de
**düzeltiyor**: sürücü geometrik zarf değil, atmosferik değişkenliktir. Zarf zaten `kt`
dönüşümünün işidir (§6).

**Doğrudan sonucu:** doğrulama bölmesinin Nisan–Mayıs deliği tam olarak $k$'nin en yüksek olduğu
mevsime denk düşüyor. Mevsim ızgarası bu deliği **hayatta kalınabilir** kılan şeydir: MAM hücresi
yalnız Mart'tan uyarlanıyor (il başına 6.660 kalibrasyon elemanı, `MIN_CELL_N`=200'ün çok
üstünde) ve Nisan ile Mayıs'ı taşıyor. Mart'ın $k$'si Nisan'ınkine yakın (1,42 ↔ 1,30;
1,56 ↔ 1,60; 1,61 ↔ 1,59), bu yüzden vekil savunulabilir.

### 8.5 Kod yolu doğrulaması — smoke, **sonuç değil**

`smoke_conformal_{raw,kt}` ↔ `smoke_{raw,kt}_check`. Çiftler, katmandan önce var olan **her
config alanında birebir aynıdır** (`config.json`'lar alan alan karşılaştırıldı). Gündüz alt
kümesi:

| kol | RMSE | MAE | R² | CP önce | CP sonra | MPIW önce | MPIW sonra |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `raw` | 101,459 | 73,946 | 0,8706 | 0,8229 | **0,9427** | 291,6 | 429,1 |
| `kt` | 89,444 | 62,399 | 0,8995 | 0,7678 | **0,9455** | 263,0 | 511,0 |

RMSE/MAE/R² **son hanesine kadar değişmiyor** — değişmezlik gerçek veride de tutuyor. İl bazında,
`raw` / `kt`:

| il | CP önce | CP sonra | CWC önce | CWC sonra |
| --- | ---: | ---: | ---: | ---: |
| Ankara | 0,834 / 0,786 | 0,943 / 0,942 | 94,9 / 985 | 0,98 / 1,18 |
| Antalya | 0,866 / 0,819 | 0,947 / 0,949 | 20,3 / 186 | 0,86 / 0,96 |
| Konya | 0,835 / 0,780 | 0,945 / 0,943 | 95,6 / 1.350 | 0,99 / 1,22 |
| **Rize** | **0,751 / 0,684** | **0,946 / 0,948** | **5.022 / 131.225** | **1,04 / 1,14** |
| Van | 0,828 / 0,770 | 0,933 / 0,945 | 131,2 / 2.096 | 1,36 / 1,17 |

En kötü kalibre edilmiş il en iyi kalibre edilmiş il oluyor ve CWC — CLAUDE.md'nin "aşırı
güvenli modelin bayrağı" dediği metrik — beş büyüklük mertebesi düşüyor.

**Bu sayılar tabloya girmez** ($B{=}1 \times T{=}10$ aralık metrikleri anlamsızdır, K-4).
Doğrulanan şey kod yoludur: kalibrasyon geçişi, ızgara uyumu, üç CSV, ve gerçek mevsimsel delikle
üretim geometrisinin çalıştığı.

### 8.6 Geçerlilik tehditleri

- **T-8.1 — kalibrasyon kümesi erken durdurmanın gördüğü kümedir.** Gerçek bir değişilebilirlik
  ihlali. Zayıf bir ihlal (erken durdurma 32.315 pencerenin ortalama kaybından **tek bir tam
  sayı** seçer) ama sıfır değil. Temiz sürüm, hiçbir eğitim kararının dokunmadığı bir kalibrasyon
  bölmesi ister.
- **T-8.2 — doğrulama bölmesinde Nisan ve Mayıs yok** (2024-06-27 → 2025-03-24, on ay), gündüz
  oranı 0,489'a karşı testin 0,515'i. §8.4 bunu ölçtü ve mevsim ızgarasıyla hafifletti, ama
  ortadan kaldırmadı.
- **T-8.3 — geometri testte seçildi.** §8.3'ün teşhisi test döneminin içinde uyarlanıp
  puanlanıyor; bu bir hiperparametreyi test kümesinde seçmektir. Desteklediği sonuçlar **yapısal**
  (hangi eksen sinyal taşıyor, $k$ mevsimle ne kadar oynuyor) ve herhangi bir bölmede görünürdü.
  Yine de her conformal koşu artık `calibration_predictions.npz` yazıyor, böylece aynı
  karşılaştırma **doğrulama bölmesinde** — seçimin dürüst olduğu yerde — tekrarlanabilir. İlk
  `conformal` grubu koştuktan sonra yapılacak iş budur.
- **T-8.4 — bütün teşhis $B{=}1$.** Doğruluk aralığın ne olduğunu değiştirir (§0.3). $k$
  değerleri taşınmaz.
- **T-8.5 — pencereler örtüşüyor.** Stride-1'de bir hücrenin ~3.200 elemanı kabaca 3.200/24
  bağımsız gözlem eder; sonlu-örnek yüzdeliği ham sayının önerdiğinden gürültülüdür.
  `MIN_CELL_N`=200 bu yüzden biçimsel olarak gereken ~19'un çok üstündedir.
- **T-8.6 — CRPS ve nokta metrikleri.** CRPS yeniden ölçeklenmiş **örnekten** hesaplanır, yani
  düzeltmeyi görür; RMSE/MAE/R² tanım gereği görmez. Bir conformal satır ile düzeltilmemiş
  ikizi arasındaki tek fark aralıktır.

### 8.7 Hüküm ve düzeltme kaydı

**Öneri: `conformal_mode="city_season"`.** Dört geometrinin ikisinde en iyi, birinde ikinci, ve
üretime en yakın olanında (`production_like`) hem koşullu (0,0099) hem marjinal (0,0035) kapsamada
en iyi. 20 hücre, `city_horizon`'un 120'sine karşı.

**Düzeltme — §6.5'in ızgara önerisi.** §6.5 "katsayı **en azından il × ufuk** ızgarasında olmalı —
muhtemelen berrak-gökyüzü düzeyine göre de" diyordu. Ölçüldü, **iki bakımdan yanlış:**

1. Ufuk ekseni null (C-1). Doğru ikinci eksen **mevsim**dir (C-3).
2. Sürücü berrak-gökyüzü düzeyi (geometri) değil, **bulut rejiminin mevsimsel değişkenliği**dir
   (C-5). Geometrik zarfı `kt` dönüşümü zaten hallediyor (§6).

§6.5'in geri kalan iki maddesi **ayakta**: skaler bir düzeltme koşullu kapsamayı vermez (C-2), ve
düzeltmenin işareti kola göre değişir — smoke çiftinde her iki kol da $k>1$ istedi, ama tam
doğrulukta `raw` nominalin üstündedir (CP 0,977, $k<1$ beklenir) ve `kt` altındadır (0,928,
$k>1$). Çarpansal ızgara ikisini de karşılar.

**Açık kalan:** tam doğrulukta hiçbir conformal koşu yok. `conformal` grubu (6 kol, **~5,8 sa**)
ve opsiyonel `conformal_grid` grubu (5 kol, ~4,0 sa) tanımlı ve koşulmayı bekliyor. Süreler
ölçülmüştür: altı ikiz kola `süre = epok × c_epok + B{\cdot}T × c_mc` uydurulduğunda Mac/MPS'te
epok başına 10,22 s ve MC geçişi başına 0,662 s çıkıyor (en büyük artık 9 s); kalibrasyon geçişi
bunun 32.315/44.155 = 0,732 katı, yani **+%13**. Koşulduğunda
§8.5 gerçek sayılarla değiştirilir, künye güncellenir ve T-8.3 doğrulama bölmesi üzerinden
kapatılır.

---

## A. Bu belge bir şablondur — yeni bir ablasyon nasıl eklenir

§1, sonraki ablasyonlar için kalıptır. Yeni bir eksen geldiğinde **§1 düzenlenmez**; `## 2.`,
`## 3.` … olarak yeni bölüm eklenir ve §0'daki dört okuma kuralı olduğu gibi geçerli kalır.

Bir bölümün taşıması gereken alt başlıklar, §1'deki sırayla:

| Alt başlık | İçerik |
| --- | --- |
| **Geçerlilik künyesi** | Başlığın hemen altında, alıntı bloğu içinde: veri kümesi · hedef dönüşümü · mimari · doğruluk · kriter · kapsam · tohum · cihaz. §0.2'nin referans konfigürasyonundan sapan her alan **kalın** yazılır. Bu tablo olmadan bölüm, mimari veya veri kümesi değiştiğinde okunamaz hâle gelir. |
| `N.1` Sınanan iddia | `main_methodology.md`'den **doğrudan alıntı**, satır numarasıyla. Alıntılanacak bir cümle yoksa ablasyon henüz bir iddiaya bağlanmamıştır. |
| `N.2` Hipotezler + EDA kanıtı | H1/H2…, ve her birini doğuran `outputs/eda/tables/*.csv` satırı. |
| `N.3` Kolların tam konfigürasyonu | Ortak ayar tablosu + kola göre değişen alanlar tablosu + kol başına yeniden üretim komutu. Bu tablo, kodu okumadan koşuyu tekrarlatabilmelidir. |
| `N.4` Doğruluk | Beyan edilen doğruluktan sapma varsa: ölçülmüş birim maliyet, projeksiyon, neyin verildiği ve **neden verilebildiği**. Sapma yoksa "`ABLATION_FULL`, sapma yok" yazılır. |
| `N.5`… Sonuç tabloları | Gündüz başlık, 24 saat ikincil, taban satırları tabloya gömülü, çoklu tohumda ortalama ± sd. |
| `N.x` Karıştırıcı çözümlemesi | Ekseni değiştirirken birlikte değişen ne var, ve hangi kol çifti onu sabitliyor. |
| `N.y` Hüküm | Her hipotez için ayrı ayrı; "desteklenmedi" / "tespit edilemedi" geçerli ve beklenen sonuçlardır. |
| `N.z` Geçerlilik tehditleri | En azından: satır seçimi (K-1), epok tavanları, tohum kapsamı, doğruluk sapması, aralık kalibrasyonu. |

Yeni bir eksen eklerken **koddan** gereken değişiklikler:

0. **§0.3'ün değişiklik takip matrisine satır ekleyin:** bu eksen değişirse hangi bulgular
   yeniden ölçülmelidir, ve taşımadığına dair ölçülmüş bir kanıt var mı? Bu satır, belgenin
   sonraki oturumlarda referans olarak kullanılabilmesini sağlayan şeydir.
1. **Ekseni `ExperimentConfig`'e alan olarak ekleyin** (varsayılanı, mevcut ledger satırlarının
   üretildiği davranışı koruyacak biçimde seçin — varsayılan değiştirmek eski satırların
   tamamını yetim bırakır).
2. **Ekseni `experiment.py::LEDGER_COLUMNS` ve `_ledger_row()`'a ekleyin.** Bu yapılmazsa iki kol
   ledger'da ayırt edilemez ve `assert_ledger_schema_ok()` şema uyuşmazlığında koşuyu
   milisaniyeler içinde durdurur (mevcut ledger'ı kenara alıp yeniden üretmek gerekir).
3. **Kolları `configs/experiment_grid.py`'de tek bir ortak ayar sözlüğünden üretin** — §1'deki
   `ABLATION_FULL` / `_rize_curve_configs(fidelity, suffix)` kalıbı gibi. Elle yazılmış iki blok
   sessizce birbirinden ayrışır; tek fonksiyondan üretilen kollar "yalnızca şu alanda
   farklılar"ı kanıtlanabilir kılar.
4. **Grubu `EXPERIMENT_GROUPS`'a ekleyin**, böylece saatler süren koşu `--group` ile hedeflenebilir.
5. **Doğruluk düşürecekseniz yeni bir id soneki verin** (`_b1` gibi) ve düşürülmüş doğruluğu
   sayıların geçtiği **her yerde** tekrarlayın.

Ölçüm disiplini, eksenden bağımsız:

- Koşmadan önce **bir kolu zamanlayın** ve toplamı çıkarın; saatler süren bir koşuyu ölçmeden
  başlatmayın.
- Pahalı koşudan önce **smoke doğrulukta** yeni kod yolunu uçtan uca geçirin (`rize_curve_smoke`
  grubu bunun örneğidir): metrik adımında ölen bir koşu en pahalı hata biçimidir.
- Koşu bitince **`hit_max_epochs`'u her ledger satırında kontrol edin.**
- Her aşamadan sonra **commit + push**; uzak makine git ile senkronlanır.

---

## Kaynak dosyalar

| Ne | Nerede |
| --- | --- |
| Kol tanımları | `configs/experiment_grid.py` (`ABLATION_FULL`, `ABLATION_B1`, `RIZE_CURVE_ARMS`, `_rize_curve_configs`, `ARCH_SWEEP_AXES`, `_percity_endpoints_configs`) |
| Kol başına metrikler | `outputs/experiments/<experiment_id>/metrics/results_summary.csv` (il bazlı), `results_by_horizon.csv` (ufuk adımı bazlı) |
| Kol başına koşu günlüğü | `outputs/experiments/<experiment_id>/log.txt` (cihaz, bölme tarihleri, pencere sayıları, replika başına epok) |
| Kol başına konfigürasyon | `outputs/experiments/<experiment_id>/config.json` |
| Toplu tablo | `outputs/experiments_ledger.csv` (`hit_max_epochs`, `training_time_sec` dâhil) |
| Taban çizgileri | `outputs/experiments/baseline_{climatology,persistence,smart_persistence}/` |
| EDA kanıtı | `outputs/eda/tables/`, tartışma `outputs/eda/EDA.md` |
| Aralık kalibrasyonu sınırı | `METHODOLOGY_REVIEW.md` K3 |
| Conformal ızgara ve etkisi | `outputs/experiments/<id>/metrics/conformal_{grid,effect,month_stability}.csv` |
| Conformal geometri seçimi | `outputs/tables/conformal_mode_selection.csv`, `conformal_month_stability_test.csv` (üreten: `scripts/07_conformal_diagnostic.py`) |
