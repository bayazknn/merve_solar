# Yapılacaklar

Yalın liste. Gerekçe ve sayılar burada **tekrarlanmaz**, kaynak dosya gösterilir:
`ABLATION.md` (ablasyon sonuçları, §0 önce okunur) · `outputs/eda/EDA.md` (betimsel bulgular) ·
`outputs/eda/README.md` (nasıl üretildi + düzeltme kaydı) · `main_methodology.md` (Yöntem) ·
`ABLATION_REVIEW_2.md` (son bağımsız review).

---

## 1. Kritik yol — makale sayıları buna bağlı

- [x] ~~**Conformal aralık katmanı — kod.**~~ `conformal.py`, `conformal_mode` ekseni + ledger
      sütunu, varsayılan `"none"`. Izgara **`city_season`** (il × mevsim), §6.5'in önerdiği
      il × ufuk **değil**: ufuk ekseni ölçüldü ve null çıktı. → `ABLATION.md` §8,
      `main_methodology.md` §11.6
- [ ] **Conformal `conformal` grubunu koş** (6 kol, ~4,6 sa: `raw` × `kt` × 3 tohum). Tam
      doğrulukta hiç ölçülmedi; §8.5 hâlâ smoke sayılarıyla duruyor. Opsiyonel: `conformal_grid`
      (5 kol, ~3,8 sa) geometri ablasyonunu tam doğrulukta tekrarlar.
- [ ] **Izgara geometrisini doğrulama bölmesinde yeniden seç** (T-8.3). Şu anki seçim test
      döneminin içinde uyarlanıp puanlandı. Her conformal koşu `calibration_predictions.npz`
      yazıyor; `07_conformal_diagnostic.py` o dosyayı okuyacak biçimde genişletilmeli.
- [ ] **Manşet formülasyon kararı: `raw` mı `kt` mi?** `kt` doğrulukta %9–13 önde ve MAE eşiğini
      geçiyor; ama transfer iddiası `kt` altında net kazanç vermiyor, yeniden dağıtıma dönüşüyor.
      → `ABLATION.md` §6, §7, ve §7.8'in üç seçeneği
- [ ] **Kazanan mimari tam doğrulukta ölçülmedi** (`abl_arch_h128x64_full_s{42,43,44}`, ~2,0 sa).
      Grid'de **tanımlı değil**. $B{=}1$'de seçip $B{=}8$'de raporlamak güvenli değil.
      → `ABLATION.md` §4.8 T-4.2, §4.7

## 2. Savunulmamış varsayılanlar — tarama yok

- [ ] **$B$ taraması** ($B \in \{1,2,4,8\}$, `all5`, 3 tohum, ~1,5 sa). $B{=}8$ miras alınmış bir
      seçim; iki uç nokta dışında hiç taranmadı. → `ABLATION.md` §3.2 (ikame bulgusu)
- [ ] **`bootstrap_block_length` taraması** ($L \in \{24,48,168,336\}$, ~5,8 sa). Hareketli blok
      bootstrap'ın tek ayar düğmesi, hiç taranmadı, ölçülen korelasyon ölçeğinin ~7 katına ayarlı.
- [ ] **Erken durdurma verimliliği.** `best_epoch` 3–9, koşu 19–25 epok; sürenin ~%60-70'i
      optimumdan sonra. Kazanan mimari seçildikten sonra kendi tek-eksen değişikliği olarak.

## 3. Analiz altyapısı — yeni koşum gerektirmez

- [ ] **DM / Benjamini–Hochberg anlamlılık testleri.** HAC bant genişliği tabanı **47**
      (stride-1 pencereler saatleri hem hedef hem girdi olarak paylaşır). `postprocess.py`
      üzerine oturur; npz'ler yalnız koşumun yapıldığı makinede.
- [ ] `scripts/make_scope_comparison.py` — karşılaştırma tablosu betiği, hâlâ yazılmadı.
- [ ] **`ABLATION_REVIEW_2.md`'nin işlenmemiş katkı adayları.** İşlenen: beceri eşitlenmesi
      (§6.4.1), ufuk kırılımı (§6.4), tekrarlanabilirlik tabanı (§1.10). Bekleyen: yeniden
      dağıtımın genel bir varyans-azaltma özelliği olması, aralık genişliğinin ilin iklimsel
      ışınım düzeyine kilitli olması, havuzlama kazancının bulut rejimi *değişkenliğini* takip
      etmesi, il × ufuk bozulma tablosu.

## 4. Karşılaştırma modelleri (makale için zorunlu)

- [ ] SVM, GRU, Random Forest / MLP (Prophet bu çerçevede zorsa atlanır).
      **Aynı pencereler, aynı bölmeler, aynı `metrics.py`, aynı ledger** — `run_experiment`
      arkasında model varyantı olarak. → CLAUDE.md *Comparability rules*
- [ ] Merve'nin gönderdiği makalelerden "optimal LSTM konfigürasyonu" dosyası.

## 5. Ertelenen öznitelik işleri

Her ikisi de mevcut ledger satırlarını geçersiz kılar; yeni id ile koşulmalı.

- [ ] **`log1p(PRECTOTCORR)` + ikili "yağış var" göstergesi.** → `outputs/eda/EDA.md` §3.4
      *Not:* TODOs'un eski sürümündeki ikili-gösterge korelasyonları (−0.435…−0.480) ile
      EDA.md §3.4'ünkiler (−0.097…−0.215) **uyuşmuyor** — farklı koşullandırma; kullanılmadan
      önce hangisinin hangi tanım olduğu netleştirilmeli.
- [ ] **Öznitelik kümesi 17 → 15** (`T2MDEW`, `WS50M` çıkar). LSTM için performans değil
      *gerekçelendirme* adımı; planlanan SVM/RF/MLP için **kritik**. → `outputs/eda/EDA.md` §5.3
- [ ] **`PRECTOTCORR` birim etiketi teyidi** (mm/saat şüpheli). Modellemeye zararsız, figür
      ekseni ve makale metni için gerekli. → `outputs/eda/README.md`

## 6. Makale metni ve figürler

- [ ] **5 ilin haritası** + iklim/coğrafya farklılıkları paragrafı (dış geoveri gerektirir).
- [ ] Kısmi korelasyon tablosu ve gerekçesi — öznitelik seçiminin asıl argümanı.
      → `outputs/eda/EDA.md`
- [ ] Rize'nin ayrı bir rejim olarak tartışılması (+ "Rize hariç" agregat satırı zaten üretiliyor).
- [ ] Saat ekseninin il-bazlı yerel güneş saati (LST) olduğu — Yöntem'e bir cümle.
- [ ] Gündüz tanımının `CLRSKY_SFC_SW_DWN > 0` olduğu ve neden sızıntı olmadığı — dipnot.
- [ ] Ufuk profili tablosu: naif kurallar ufuk boyunca düz, model bozuluyor. Hakem gün-öncesi
      satırını hesaplayacak. → `ABLATION.md` §6.4

**Alıntılanmayacak sayı:** Van'ın 1215,9 W/m² maksimumu ($k_t = 3{,}28$, geri-çatım artefaktı).
Savunulabilir maksimum 1068,7. → `outputs/eda/README.md` §1

---

## Tamamlananlar

| iş | tarih | nerede |
| --- | --- | --- |
| Veri kümesi kararları (`ALLSKY_KT` düşürüldü, `CLRSKY` maske sütunu, $F = 17$) | 2026-08-28 | `config.py` |
| Betimsel istatistik katmanı (28 tablo, 34 figür) | 2026-08-28 | `outputs/eda/` |
| Gündüz tanımı düzeltmesi (klimatolojik hücre → `CLRSKY > 0`) | 2026-08-28 | `outputs/eda/README.md` |
| Naif referans zemini boru hattından ledger'a | 2026-08-28 | `baselines.py` |
| R² metrik tablosuna eklendi | 2026-08-28 | `metrics.py` |
| Geriye bakış 24 saatte sabitlendi (EDA + ampirik doğrulama) | 2026-08-30 | `ABLATION.md` B-2 |
| Gündüz-only eğitim sorusu: `loss_daylight_only` varsayılan **kapalı** | 2026-08-28 | `ABLATION.md` §0, `main_methodology.md` §10.1.1 |
| Ablasyonlar §1–§7 (transfer, kriter, tam doğruluk, mimari, uç noktalar, hedef dönüşümü) | 2026-08-31 | `ABLATION.md` |
| İki bağımsız review; ikincisinin düzeltmeleri uygulandı | 2026-08-31 | `ABLATION_REVIEW*.md` |
| İl × ufuk metrik tablosu (koşum sonrası, yeniden eğitimsiz) | 2026-08-31 | `postprocess.py` |
