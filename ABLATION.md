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
  ledger'daki on bir kolun **hepsinde 0**'dır. Yani 200 ile 100 arasındaki fark bu çalışmanın
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

On bir kolun toplam işlemci süresi ≈ 13 250 s; iki paralel akışla duvar saati ≈ 2.5–3 saat.

**Eksik kol.** `abl_rize_all5_s44_b1` bu makinede tamamlanmadı; kullanıcı isteğiyle durduruldu ve
sunucuda koşulmak üzere bırakıldı. Ledger satırı ve çıktı klasörü yoktur, dolayısıyla mükerrer
satır riski de yoktur. Bu nedenle **`all5` ucu üç değil iki tohumla raporlanmaktadır** ve
aşağıdaki `all5` sapması (±) iki gözlemden hesaplanmıştır — zayıf bir kestirimdir. Tamamlamak için:

```bash
git pull
uv run python scripts/run_all_experiments.py --group rize_curve_b1 \
    --only abl_rize_all5_s44_b1 --skip-existing --continue-on-error
git add outputs/experiments/abl_rize_all5_s44_b1 outputs/experiments_ledger.csv
git commit -m "Add the third all5 seed of the Rize transfer curve" && git push
```

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
0.9406, Huber 67.84 / 37.55 / 0.9398; klimatoloji tabanı 76.71 / 37.86 / 0.9231.

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
| `all5` (2 tohum) | 5 | 218 745 | **112.09 ± 1.12** | **83.95 ± 1.41** | 0.7927 ± 0.0041 | 0.7733 | 61.00 |
| *Taban: klimatoloji* | — | — | *130.68* | *95.72* | *0.7183* | — | — |
| *Taban: akıllı kalıcılık* | — | — | *136.66* | *85.23* | *0.6919* | — | — |
| *Taban: kalıcılık* | — | — | *141.89* | *90.89* | *0.6679* | — | — |

Tekil tohum değerleri: `solo` RMSE 115.21 / 110.93 / 113.50 (s42/s43/s44); `all5` RMSE
112.88 / 111.30 (s42/s43; s44 sunucuda beklemede).

**24 saat (ikincil), `Rize` satırı:**

| Kol | RMSE ↓ | MAE ↓ | R² ↑ | CP |
| --- | --- | --- | --- | --- |
| `solo` (3 tohum) | 81.21 ± 1.54 | 43.77 ± 0.59 | 0.8758 ± 0.0047 | 0.8867 |
| `plus_ankara` | 78.76 | 42.70 | 0.8832 | 0.8841 |
| `plus_antalya` | 85.83 | 45.04 | 0.8612 | 0.8727 |
| `minus_antalya` | 80.17 | 43.52 | 0.8789 | 0.8847 |
| `all5` (2 tohum) | 80.40 ± 0.80 | 43.19 ± 0.72 | 0.8782 ± 0.0024 | 0.8833 |
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

Şekle ilişkin ikinci gözlem: 4 il (111.77) ile 5 il (112.09 ± 1.12) arasında iyileşme yoktur;
beşinci il **Antalya**'dır, yani çift kollarda zarar verdiği ölçülen ildir. İki bağımsız kol aynı
yöne işaret ediyor.

### 1.8 Hüküm

**H1 — "Rize'nin hatası havuzlanan il sayısıyla monoton azalır": DESTEKLENMEDİ.**

Eğri monoton değildir. Gündüz RMSE'si 113.22 (1 il) → 109.80 (2 il, Ankara) → 119.66 (2 il,
Antalya) → 111.77 (4 il) → 112.09 (5 il) izler; il sayısına göre sıralandığında bile artıp
azalır. Dahası, iddianın taşıyıcı olduğu **uçlar arası fark ölçülemiyor**: `solo` 113.22 ± 2.15'e
karşı `all5` 112.09 ± 1.12, fark **−1.12 W/m²**, ki bu `solo` tohum sapmasının (2.15) yarısından
azdır. MAE'de de aynı: 85.07 ± 1.15'e karşı 83.95 ± 1.41, fark −1.13, yine sapmanın içinde.

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
- **T-3 — Tohum kapsamı yetersiz.** `solo` 3 tohum, `all5` **2** tohum (üçüncüsü sunucuda
  beklemede), ara kollar **1** tohum. H1 hükmü zaten "tespit edilemedi"dir; ara kolların ve
  özellikle çift kolların tek tohumlu olması H2'yi "güçlü ama kesinleşmemiş" seviyesinde tutar.
- **T-4 — $B=1$ doğruluğu.** Nokta tahminleri 100 MC geçişin ortalamasıdır, 800'ün değil;
  $B=8$'in varyans azaltması yoktur, dolayısıyla tohumlar arası sapma tam doğruluktakinden
  büyüktür. Bu, H1'i tespit etmeyi **zorlaştıran** yöndedir: gerçek ama küçük bir havuzlama
  kazancı bu gürültünün altında kalmış olabilir. Bu yüzden H1 hükmü "desteklenmedi" değil
  "**tespit edilemedi**" biçimindedir.
- **T-5 — Epok tavanı.** Bağlayıcı olmadı: `hit_max_epochs` on bir kolun hepsinde 0, epoklar
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
| Kol tanımları | `configs/experiment_grid.py` (`ABLATION_FULL`, `ABLATION_B1`, `RIZE_CURVE_ARMS`, `_rize_curve_configs`) |
| Kol başına metrikler | `outputs/experiments/<experiment_id>/metrics/results_summary.csv` (il bazlı), `results_by_horizon.csv` (ufuk adımı bazlı) |
| Kol başına koşu günlüğü | `outputs/experiments/<experiment_id>/log.txt` (cihaz, bölme tarihleri, pencere sayıları, replika başına epok) |
| Kol başına konfigürasyon | `outputs/experiments/<experiment_id>/config.json` |
| Toplu tablo | `outputs/experiments_ledger.csv` (`hit_max_epochs`, `training_time_sec` dâhil) |
| Taban çizgileri | `outputs/experiments/baseline_{climatology,persistence,smart_persistence}/` |
| EDA kanıtı | `outputs/eda/tables/`, tartışma `outputs/eda/EDA.md` |
| Aralık kalibrasyonu sınırı | `METHODOLOGY_REVIEW.md` K3 |
