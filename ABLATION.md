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

## 0. Bu belgedeki tüm koşular için geçerli okuma kuralları

Bu dört kural bölümler arasında değişmez ve her tabloyu bağlar.

**(K-1) İl bazlı satır okunur, `Aggregate` satırı okunmaz.** Havuzlama eğrisinin kolları farklı
il kümeleri üzerinde eğitilir ve *farklı il kümeleri üzerinde skorlanır*; dolayısıyla
`Aggregate` satırları farklı popülasyonları kapsar ve kollar arasında karşılaştırılamaz.
Ölçülmüş örnek — Rize'ye Ankara eklendiğinde `Aggregate` satırı gündüz RMSE'yi 115.83 → 107.56
gösterir, oysa `Rize` satırının gerçek değişimi 115.83 → 113.13'tür
(`abl_rize_solo_s42_smoke` ve `abl_rize_plus_ankara_s42_smoke`). Aradaki fark model değil,
ortalamaya karışan kolay Ankara satırlarıdır. Her kolun `results_summary.csv` dosyasındaki
`Rize` satırı **aynı** 109 043 gündüz elemanını kapsar (`n_elements`), dolayısıyla
karşılaştırma eleman-eleman aynıdır.

**(K-2) Başlık rakamı gündüz alt kümesidir.** Satırların %48.8'i geometrik olarak gecedir ve
hedefleri tam sıfırdır; `clamp_night_to_zero` bu saatleri kesin olarak sıfırlar. Gece satırları
her modelin RMSE'sini bedavaya ~%28 düşürür ve R²'yi şişirir — aynı klimatoloji referansı 24
saatte R² 0.923, gündüzde 0.856 verir. Tüm hükümler gündüz satırından verilir; 24 saatlik
değerler yalnızca ikincil olarak raporlanır.

**(K-3) Zemin, kalıcılık değil klimatolojidir.** 24 saat ilerisi bir tahminde kalıcılığı geçmek
sonuç değildir. İlgili taban değerleri her tablonun altında verilir.

**(K-4) Aralık metrikleri (CP/PINW/MPIW/CWC) kalibre değildir ve kalibrasyon bulgusu olarak
okunamaz.** Havuzlanan öngörü dağılımı yalnızca epistemik (model) belirsizliğini taşır;
aleatorik (gözlem gürültüsü) terimi hiçbir yerde eklenmez (`METHODOLOGY_REVIEW.md` K3). Bu
belgedeki koşular ayrıca `n_bootstrap=1` olduğu için bootstrap/örneklem bileşeni de yoktur:
aralıklar **yalnızca MC-Dropout** kaynaklıdır. Raporlanırlar, ama %95 hedefine göre bir
kalibrasyon iddiası taşımazlar ve `n_bootstrap=8` satırlarıyla karşılaştırılamazlar.

---

## 1. İl havuzlama (cross-city transfer) — Rize transfer eğrisi

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

### 1.10 Yan bulgu — tekrarlanabilirlik doğrulaması

`abl_loss_mse_s42_b1` ile `abl_rize_all5_s42_b1` konfigürasyonları `experiment_id` dışında
**birebir aynıdır** (beş il, global, mse, tohum 42, aynı doğruluk). İki ayrı süreçte, saatler
arayla koşulmuşlardır ve `results_summary.csv` çıktıları tüm metriklerde aynıdır — gündüz
`Aggregate` RMSE 96.9915 / MAE 73.8333 / R² 0.8818 / CP 0.8254, gündüz `Rize` RMSE 112.8847.
Bu, `main_methodology.md` §13.3'ün determinizm iddiası için ölçülmüş bir doğrulamadır. Kasıtlı
kurgulanmamıştı — Aşama 1 ile Aşama 2'nin kesişmesinden doğdu — ama makalede alıntılanmaya
değer. (Maliyeti bir koşudur; ileride grid'de bu çakışma bilerek korunabilir veya kaldırılabilir.)

### 1.11 Cihaz eşdeğerliği (parity) — MPS ile CPU aynı sayıları vermez

`abl_parity_cpu_s42` ve `abl_parity_mps_s42`, `experiment_id` dışında **birebir aynı**
konfigürasyondur (Rize tek başına, `per_city`, L1, tohum 42, B=1, T=100); tek fark
`MERVE_DEVICE` ile sabitlenen arka uçtur. Amaç, bir denetimde ileri sürülen ama
**doğrulanamamış** bir iddiayı sınamaktı: `nn.LSTM`'in katmanlar arası dropout'unun MPS'te
CPU'dan ayrıştığı. `hidden_sizes=[64, 32]` gerçekten `nn.LSTM(num_layers=2, dropout=0.3)`
kuruyor ve o dropout çıkarım anındaki MC-Dropout gürültü kaynaklarından biri, yani maruziyet
gerçek — iddia doğrulanmamış olsa bile.

| metrik (Rize, gündüz) | CPU | MPS | fark |
| --- | --- | --- | --- |
| RMSE | 110,557 | 110,832 | **+%0,25** |
| MAE | 77,559 | 77,920 | +%0,46 |
| R² | 0,7984 | 0,7974 | −%0,13 |
| CP | 0,8674 | 0,8894 | **+0,0220** |
| MPIW | 318,38 | 332,66 | **+%4,49** |
| PINW | 0,3248 | 0,3394 | +%4,49 |
| CRPS | 57,055 | 56,579 | −%0,83 |
| süre | 155,2 s | 71,4 s | **2,17× hızlı** |

**Sonuç 1 — iddia edilen hata bu biçimde görünmüyor.** Dropout MPS'te işlevsiz olsaydı öngörü
dağılımının yayılımı *çökerdi*: MPIW daralır, CP düşerdi. Gözlenen yön tam tersidir (MPIW %4,5
daha *geniş*). Koşular gerçekten farklı çekilişlerdir — erken durdurma CPU'da 28, MPS'te 30
epokta bağladı — ama benzer bir çözüme yakınsamışlardır (doğrulama kaybı 0,1912 / 0,1915).

**Sonuç 2 — ama arka uçlar aralık metriklerinde değiştirilebilir değil.** Ölçek için: aynı
kolun üç tohumu arasında MPIW standart sapması ortalamanın **%0,91'i**, tüm aralık %1,82'dir.
Arka uç farkı %4,49 — yani **tohum s.s.'sının ≈5 katı ve üç tohumun tüm aralığının 2,5 katı**.
CP'de de fark (0,0220) üç tohumun tüm aralığından (0,0182) geniştir. Nokta metriklerinde ise
fark %0,25 ile tohum gürültüsünün çok altında kalır.

Pratik kural: **nokta metrikleri arka uçlar arasında okunabilir, aralık metrikleri okunamaz.**
Bir çok-tohumlu ortalama tek bir arka uçtan gelmelidir; ledger'ın `device` sütunu bunun
kontrol edilebilmesi için vardır.

**Sınır:** bu tek bir tohumla yapılmış tek bir karşılaştırmadır. %4,49'un sistematik bir arka
uç kayması mı yoksa şanssız tek bir çekiliş mi olduğunu ayırmak için her arka uçta üç tohum
gerekir. Bu koşuların maliyeti düşüktür (Rize tek başına, arka uç başına ≈3 × 100 s) ve
belirsizlik katmanı hakkında bir tablo yayımlanacaksa yapılması önerilir.

---

## 2. Aynı eğri, doğru kriterle — L1 altında transfer eğrisi

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

### 2.6 Yan bulgu — kalibrasyon büyük ölçüde çözüldü

Gündüz CP havuzlama arttıkça **tekdüze yükseliyor**: `solo` 0,8869 → `plus_*` 0,896 →
`minus_antalya` 0,9044 → `all5` 0,9134. Ve `all5` kolunun **`Aggregate`** gündüz CP'si üç
tohumda 0,9535 / 0,9570 / 0,9534 — yani hedefin üzerinde değil, **hedefte**.

Bu, `METHODOLOGY_REVIEW.md` K3'ün "aleatorik terim eklenmediği için %95 kapsamaya ilkesel
olarak ulaşılamayabilir" uyarısını önemli ölçüde yumuşatır: MSE altında CP 0,80–0,83 iken L1 ve
havuzlama ile 0,95'e ulaşılıyor. Alt-kapsamanın tamamı yapısal değilmiş. Rezidüel-varyans
eklentisi hâlâ değerli olabilir ama artık bir **ön koşul** değil.

`Aggregate` gündüz nokta başarımı da aynı kollarda RMSE 94,89 / 93,19 / 94,18 ve
R² 0,887–0,891 — iklimsel ortalama tabanının (106,86 / 0,8565) **%12 altında**.

### 2.7 Geçerlilik tehditleri

- **T-1 (kapandı).** Eğri artık Aşama 1'in seçtiği kriterle koşuyor.
- **T-9 (kapandı).** §2.5.
- **T-12 (yeni).** Bu 18 kol MPS'te, §1'in 12 kolu CPU'da koştu. §1.11'in ölçümüne göre nokta
  metrikleri arka uçtan bağımsızdır (%0,25) ama **aralık metrikleri değildir** (%4,49). §2.2–2.5
  yalnızca nokta metriklerine dayanır ve etkilenmez; §2.6'nın CP sayıları **arka uç içinde**
  karşılaştırılabilir, §1'in CP'leriyle yan yana konmamalıdır.
- **T-13 (yeni).** $n = 3$ tohum. H1 $p = 0{,}037$ ile eşiği geçiyor ama üç gözlemle; H2
  ($p = 0{,}062$) geçmiyor. Tam doğruluk (B=8) ve daha fazla tohum ikisini de sağlamlaştırır.
- **Devam eden:** tüm kollar `n_bootstrap=1`, dolayısıyla aralık metrikleri MC-Dropout'a
  dayanır, bootstrap bileşeni yoktur (§1.4).

---

## 3. Tam doğruluk — aynı eğri, $B = 8$

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

### 3.5 Kalibrasyon — §1 ve §2'nin teşhisini geçersiz kılar

`all5` kolu, üç tohum, gündüz:

| il | CP | MPIW | 
| --- | --- | --- |
| **Rize** | **0,9521 ± 0,0009** | 371,66 |
| Konya | 0,9813 ± 0,0019 | 457,80 |
| Van | 0,9829 ± 0,0014 | 463,20 |
| Antalya | 0,9837 ± 0,0011 | 459,70 |
| Ankara | 0,9842 ± 0,0006 | 440,46 |
| `Aggregate` | 0,977 ± 0,001 | 438,58 |

Bootstrap bileşeni **tam da eksik kapsanan ili düzeltti**: Rize $B{=}1$'de CP 0,910 /
Reliability 0,040 / CWC 2,855 iken, $B{=}8$'de 0,9521 / 0,001 / 0,376 — nominal %95'e pratikte
tam oturma ve projedeki en büyük tek metrik iyileşmesi (CWC −%87).

`METHODOLOGY_REVIEW.md` K3, alt-kapsamanın **yapısal** olduğunu ve aleatorik bir terim
eklenmesinin **ön koşul** olduğunu söylüyordu. Yanlıştı: sorun eksik aleatorik terim değil,
**eksik doğruluktu**. Üstelik o eklenti yapılsaydı diğer dört ili (0,981–0,984) daha da fazla
kapsatırdı. Kalan iş **daraltmadır**, genişletme değil.

Fazla kapsamanın "aralığı şişirip kapsama satın almak" olmadığının kanıtı: $B{=}1 \to B{=}8$
geçişinde **CRPS her ilde iyileşiyor** (−%1,8 … −%3,3). CRPS uygun (proper) bir skordur ve hem
kalibrasyonu hem keskinliği cezalandırır; iyileşmesi dağılımın bir bütün olarak daha iyi
olduğunu gösterir.

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
- **T-12 (açık).** Bu 15 kol MPS'te, §1'in kolları CPU'da. Nokta metrikleri etkilenmez (%0,25),
  aralık metrikleri etkilenir (%4,49) — §1.11. §3'ün aralık sayıları kendi içinde tutarlıdır.
- **T-14 (yeni).** Erken durdurma çok geç duruyor: `best_epoch` 3–9 arasında, koşulan epok
  19–25. `early_stop_patience=15` yüzünden sürenin ~%60-70'i optimumdan sonra harcanıyor.
  Sonuçları etkilemez (en iyi ağırlıklar geri yükleniyor) ama mimari taramasında sabrın
  düşürülmesi duvar saatini üçte bir kısaltır. Ayrıca 3–9 epokta yakınsama, mevcut mimarinin
  kapasitesinin sınırlayıcı olmadığına dair bir işarettir.
- **T-15 (yeni).** Dört il fazla kapsıyor (0,981–0,984). Aralık tablosu yayımlanacaksa il
  bazlı verilmelidir; `Aggregate` 0,977 iki karşıt hatanın ortalamasıdır.

---

## 4. Mimari taraması — kapasite, geriye bakış, düzenlileştirme ve öğrenme oranı

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

(MPIW sütunu ledger'ın tüm-saat değeridir; §4.8'in gündüz MPIW'i ~2× büyüktür.)

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
(§2.5 il profili, günlük $k_t$ 0,697). Bu, "havuzlama kazancınız aslında yetersiz kapasitenin
telafisiydi" itirazını kapatır — daha büyük model Rize'de kazanç üretmiyor, havuzlama üretiyor.

### 4.8 Cephe koşusu — merdiven dönmedi, **ama kalibrasyon çöktü**

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

MPIW/RMSE oranı model kalitesiyle **tekdüze** düşüyor (4,59 → 2,73) ve CP tam olarak onu
izliyor. Gauss varsayımı altında nominal %95 için gereken oran $2 \times 1{,}96 = 3{,}92$'dir:
oranın 3,92'nin üstünde olduğu her kol fazla kapsıyor, altında olduğu her kol eksik kapsıyor,
istisnasız.

Aynı şey regresyonla da görülür. Tek-eksenli on kol üzerinde CP ile $\log(\text{MPIW})$
arasında $R^2 = 0{,}95$'lik bir cephe var; `[256,128]` bu cephenin **2,19 s.s. altında**.
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
> aleatorik terim" değildi. §4.8 bunun tersini gösteriyor: doğruluk sabit tutulduğunda
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

### 4.6 Hüküm

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

### 4.7 Geçerlilik tehditleri

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
2. **kapsamayı bozmadan** (|ΔCP| ≤ 0,0031, hiçbiri anlamlı değil),
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

## A. Bu belge bir şablondur — yeni bir ablasyon nasıl eklenir

§1, sonraki ablasyonlar için kalıptır. Yeni bir eksen geldiğinde **§1 düzenlenmez**; `## 2.`,
`## 3.` … olarak yeni bölüm eklenir ve §0'daki dört okuma kuralı olduğu gibi geçerli kalır.

Bir bölümün taşıması gereken alt başlıklar, §1'deki sırayla:

| Alt başlık | İçerik |
| --- | --- |
| `N.1` Sınanan iddia | `main_methodology.md`'den **doğrudan alıntı**, satır numarasıyla. Alıntılanacak bir cümle yoksa ablasyon henüz bir iddiaya bağlanmamıştır. |
| `N.2` Hipotezler + EDA kanıtı | H1/H2…, ve her birini doğuran `outputs/eda/tables/*.csv` satırı. |
| `N.3` Kolların tam konfigürasyonu | Ortak ayar tablosu + kola göre değişen alanlar tablosu + kol başına yeniden üretim komutu. Bu tablo, kodu okumadan koşuyu tekrarlatabilmelidir. |
| `N.4` Doğruluk | Beyan edilen doğruluktan sapma varsa: ölçülmüş birim maliyet, projeksiyon, neyin verildiği ve **neden verilebildiği**. Sapma yoksa "`ABLATION_FULL`, sapma yok" yazılır. |
| `N.5`… Sonuç tabloları | Gündüz başlık, 24 saat ikincil, taban satırları tabloya gömülü, çoklu tohumda ortalama ± sd. |
| `N.x` Karıştırıcı çözümlemesi | Ekseni değiştirirken birlikte değişen ne var, ve hangi kol çifti onu sabitliyor. |
| `N.y` Hüküm | Her hipotez için ayrı ayrı; "desteklenmedi" / "tespit edilemedi" geçerli ve beklenen sonuçlardır. |
| `N.z` Geçerlilik tehditleri | En azından: satır seçimi (K-1), epok tavanları, tohum kapsamı, doğruluk sapması, aralık kalibrasyonu. |

Yeni bir eksen eklerken **koddan** gereken değişiklikler:

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
