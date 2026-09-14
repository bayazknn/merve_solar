# Betimsel istatistik çıktıları (EDA) — nasıl üretildi

Bu belge `outputs/eda/` altındaki her çıktının **nasıl** üretildiğini, hangi veriyi
kapsadığını ve hangi tuzaklara karşı hangi kararın alındığını anlatır.

**Bulguların ne anlama geldiği bu belgede değil, yanındaki `EDA.md`'dedir.** İkisi
bilinçli olarak ayrılmıştır: önceki turda bulgu anlatısı iki belgede birden tutuluyordu ve
sonuç, CSV dosyalarıyla README arasında **15 ayrı tutarsızlık** oldu. Artık sayı yorumu tek
bir yerde (EDA.md), üretim yöntemi tek bir yerde (burada). Her ikisinde de bir sayı ile
`tables/` altındaki dosya çelişirse **dosya esastır**.

Yeniden üretmek için:

```bash
uv run python scripts/01_prepare_base_data.py     # base_features.parquet (bir kez)
uv run python scripts/02_descriptive_analysis.py  # tüm tablolar ve figürler
```

## Girdi

| | |
|---|---|
| Kaynak dosya | `SolarData_Merve(140926).xlsx` (14 Eylül 2026 dışa aktarımı) — **tek kaynak** |
| Ara ürün | `outputs/processed/base_features.parquet` |
| Kapsam | 2019-06-30 00:00 → 2026-05-30 23:00 |
| İl başına satır | 60.648 kesintisiz saatlik satır (2.527 gün) |
| Havuzlanmış | 303.240 satır; gündüz alt kümesi **152.893** (%50.42) |
| Öznitelik | 16 |

**Bu dosya öncekinden farklı ayarlarla alınmıştır** — birimler, parametre seçimi ve kayıt
uzunluğu değişti, ve `CLRSKY_SFC_SW_DWN` artık yok. Hepsinin ayrıntısı `EDA.md` §0'dadır;
okumadan buradaki hiçbir sayı eskisiyle kıyaslanmamalıdır.

**Berrak gökyüzü sütununun yerini güneş geometrisi aldı** (`src/merve_solar/solar.py`). Depoda
başka hiçbir veri dosyası yoktur; her şey bu excelden ve astronomiden türer.

- `solar_elevation` — her saatin orta noktasındaki görünür güneş yüksekliği (derece), il
  koordinatlarından ve zaman damgasından NREL algoritmasıyla. `> 0` gündüz demektir ve
  `clamp_night_to_zero` bunun işaretine bakar.
- `toa_horizontal` — atmosfer üstü yatay ışınım (W/m²), berraklık indeksinin paydası.

İkisi de frame'de **maske** olarak durur, modele asla öznitelik olarak girmez.

---

## Makaleye yazarken dikkat edilecek altı yöntem noktası

**1. "Gündüz" hesaplanmış güneş yüksekliğiyle tanımlıdır: `solar_elevation > 0`.** Saatin orta
noktasında güneşin ufkun üzerinde olması. Yalnız (il, zaman damgası) fonksiyonudur; hiçbir
ölçümü, özellikle hedefi okumaz.

İki alternatif denendi, ikisi de reddedildi:

- *`ışınım > 0` değer eşiği.* Bu veride 303.240 satırın 303.204'ünde aynı sonucu verir, yine de
  kabul edilemez: (a) başlık metriklerinin paydasını sonuca göre seçer — bulutlu bir
  alacakaranlık saati sıfır okur ve modelin en kötü olduğu yerden elenir; (b) **24 saat ilerisi
  için hesaplanamaz**, oysa `clamp_night_to_zero` tam da orada karar vermek zorundadır. İkinci
  madde belirleyicidir: geometriye zaten mecburuz, ve elde geometri varken metrik için başka
  bir tanım kullanmak tutarsızlık olur. Gerekçenin tamamı `solar.py`'nin başındadır.
- *Klimatolojik (il, ay, saat) hücre ortalaması > 0* ilk EDA turunda kullanıldı ve **çok kaba
  olduğu için hatalıydı** — ayrıntı en alttaki *Düzeltme kaydı*'nda.

**Eşik ayarlanmamıştır.** Tarayınca hedefe daha iyi uyan bir değer bulunabiliyor (−2.0°,
uyumsuzluğu 3.034'ten 587 satıra düşürüyor), ama geometrik bir maskeyi hedefe göre ayarlamak
maskenin var olma nedenini ortadan kaldırır. Bedeli ölçüldü: klimatoloji zemini gündüz RMSE
108.78 → 109.86.

**2. Aylık kutu grafiği saatlik değil, günlük toplam üzerindendir.** Gündüz *saatlik*
değerlerle çizilen bir kutunun genişliğinin büyük kısmı gün içi güneş geometrisidir ve
kışın kutu daralır — okuyucu "kış daha stabil" sonucuna varır. Gerçek tersidir (bkz.
`EDA.md` §3.4). Günlük toplam ayrıca gündüz filtresinden bağımsızdır, çünkü gece tam 0
katar.

**3. Saat ekseni il-bazlı yerel güneş saatidir (LST), ortak bir saat dilimi değil.**
Doğrulaması ve sonuçları `EDA.md` §2.1'de. Pratik kurallar:

- `HR=11` Rize'de ve Ankara'da farklı fiziksel andır; **saatler iller arasında
  karşılaştırılmaz**, her il kendi paneline bakılır.
- Saat etiketi ilgili saat aralığının **başlangıcıdır**; figürlerde aralık ortasına
  (`HR + 0.5`) çizilir.
- Eksenler "yerel saat (LST)" olarak etiketlenir.

**4. p-değeri ve anlamlılık yıldızı bilinçli olarak yoktur.** n ≈ 156.000 otokorelasyonlu
saatlik satırda her |r| > 0.01 "p < 0.001" çıkar; etkin örneklem büyüklüğü bunun kat kat
altındadır. Anlamlılık yerine etki büyüklüğü ve `partial_r_within_hour` raporlanır.

**5. Kısmi korelasyon (`partial_r_within_hour`) ham korelasyondan önce okunmalıdır.**
(İl, ay, saat) hücre ortalaması çıkarıldıktan sonraki korelasyondur; hava sinyalini güneş
geometrisinden ayırır. Fark yalnız büyük değil, **işaret değiştirecek kadar** büyüktür
(`EDA.md` §6.1).

**6. Kısmi yıllar 3B yüzeye girmez.** 2019 (30 Haziran'da başlıyor) ve 2026 (30 Mayıs'ta
bitiyor) kısmidir; `month_year_surface_*` ve `month_year_anomaly_panel` yalnız tam takvim
yıllarını (2020–2025) kullanır.

---

## Tablolar (`tables/`)

**Kapsam kuralı: bir istisna dışında her tablo verinin tamamını kullanır** — 2019-06-30 →
2026-05-30, il başına 60.648 saat / 2.527 gün, havuzlanmış 303.240 satır (gündüz alt kümesi
152.893). Tek istisna `monthly_target_stats.csv`'dir: son 12 ayın kutu grafiğinin verisidir
ve bilerek 2025-06 → 2026-05 ile sınırlıdır. Figürlerde iki istisna vardır:
`monthly_boxplot_last12m_*` (son 12 ay) ve `month_year_surface_*` /
`month_year_anomaly_panel` (yalnız 2020–2025).

| Dosya | İçerik | Kapsam |
|---|---|---|
| `descriptive_stats_by_city_daylight.csv/.md/.tex` | **Birincil tablo.** Gündüz saatleri, il bazında + havuzlanmış. | tam veri (gündüz, n = 152.893) |
| `descriptive_stats_by_city_24h.csv/.md/.tex` | Aynı tablo 24 saat üzerinden — modelin eğitildiği dağılım budur. | tam veri (n = 303.240) |
| `temporal_coverage_by_city.csv` | Kapsam, saat/gün sayısı, gündüz payı, mevsime göre ortalama günlük gündüz süresi, hedefin mevsimsel özetleri. | tam veri |
| `target_by_hour_by_city.csv` | Hedefin (il, mevsim, LST saati) dağılımı — günlük profil figürünün verisi. | tam veri |
| `time_feature_explained_variance.csv` | Saat ve yılın günü için η² ve harmonik R². Sin/cos sütunlarına karşı Pearson *r* yerine bu raporlanır: deterministik bir saat fonksiyonuna karşı korelasyon yorumlanamaz. | tam veri (hem 24 saat hem gündüz) |
| `wind_direction_circular_stats.csv` | Rüzgâr yönü dairesel istatistiği (aşağıda). | tam veri (24 saat, hız > 1 m/s) |
| `correlation_pearson_<il>.csv`, `correlation_spearman_<il>.csv`, `..._pooled.csv` | 8 fiziksel değişkenin korelasyon matrisleri. | tam veri (gündüz) |
| `target_correlation_by_city.csv` | Hedefle ham korelasyon + `partial_r_within_hour`. | tam veri (gündüz) |
| `collinear_pairs.csv` | \|r\| > 0.9 çiftler. | tam veri (gündüz) |
| `seasonal_target_stats.csv` | Mevsim bazında saatlik ve günlük toplam özetleri. | tam veri (2.527 gün/il) |
| `daily_clearness_by_city.csv` | **Ampirik** berraklık oranı (günlük toplam ÷ aynı yılın-günü için gözlenen 95. persentil) ve açık/kapalı gün payları — illeri enlemden bağımsız kıyaslar. | tam veri (2.525 gün/il; 29 Şubat'lar hizalama için düşülür) |
| `monthly_target_stats.csv` | Son 12 ayın günlük toplam özetleri — kutu grafiğinin verisi. | **SADECE 2025-06 → 2026-05** |
| `clearness_index_by_city.csv` | **Standart** berraklık indeksi kt = GHI / (I₀ cos θz), saatlik ve günlük, il × mevsim. Saatlik değerler `toa_horizontal > 20 W/m²` ile sınırlıdır (alacakaranlıkta bölme patlar). Gökyüzü durumu eşikleri literatürün bantlarıdır: berrak kt > 0.65, kapalı kt < 0.35. | tam veri |
| `autocorrelation_clearness.csv` | kt'nin ACF ve PACF'i, saatlik (gecikme 1–72) ve günlük (1–30). `lookback_hours` kararının dayanağı. | tam veri |
| `ramp_stats_by_city.csv` | Saatlik \|ΔIşınım\| ve \|Δkt\| dağılımı, il × mevsim. | tam veri (gündüz) |
| `daylight_block_structure.csv` | Gece satırları silinseydi oluşacak kesintisiz blok uzunlukları. | tam veri (gündüz) |
| `persistence_baseline.csv` | Referans zemin: kalıcılık ve klimatoloji için RMSE/MAE/R²/yanlılık. Akıllı kalıcılık kaldırıldı (`EDA.md` §0.3). Bu tablo betimsel bir ikizdir; makaleye girecek sayılar `scripts/03_run_naive_baselines.py`'nin boru hattından geçen çıktısıdır ve payda farkı yüzünden birkaç ondalık ayrışır. | **modelin test penceresi** (val_end sonrası, 9.097 saat/il) |

Üç okuma notu:

**Basıklık Fisher (fazlalık) tanımıdır** — normal dağılım için 0, 3 değil.

**Havuzlanmış ("Tümü") satırın standart sapması** iller-içi ve iller-arası varyansın
karışımıdır; iller-arası bileşen `between_city_sd` sütununda ayrıca verilir.

**Rüzgâr yönü ana tablodan çıkarılmıştır:** dairesel bir değişkenin aritmetik ortalaması
anlamsızdır. Ayrı tabloda hız-ağırlıklı dairesel ortalama, bileşke uzunluk *R*
(0 = yönsüz, 1 = tek yön) ve dairesel SD verilir; ilgili hız sütunu ≤ 1 m/s olan sakin
saatler dışlanır ve dışlanan saat sayısı tabloda yazılıdır. Yön klimatolojisi gündüzle
sınırlı değil, 24 saat üzerinden hesaplanır.

## Figürler (`figures/`)

Her figür hem `.png` (300 dpi) hem `.pdf` (vektör, Type 42 yazı tipi) olarak yazılır.
Arka plan her yerde beyazdır; mevsimler renk **ve** çizgi tipiyle ayrışır, böylece
siyah-beyaz baskıda ve renk körlüğünde kimlik korunur.

| Dosya | Ne gösterir | Filtre |
|---|---|---|
| `correlation_heatmap_<il>`, `_pooled` | 8 değişkenin korelasyon matrisi | gündüz |
| `target_correlation_panel` | Değişken × il, hedefle korelasyon | gündüz |
| `scatter_vs_target_<il>` | Her değişkenin hedefe karşı saçılımı + binlenmiş medyan eğrisi | gündüz |
| `monthly_boxplot_last12m_<il>`, `_panel` | Son 12 ayın günlük toplamları | 24 saat (toplam) |
| `month_year_surface_<il>`, `_panel` | 3B ay × yıl × ışınım yüzeyi, 2020–2025 | 24 saat (toplam) |
| `month_year_anomaly_panel` | Aynı verinin 2B anomali görünümü | 24 saat (toplam) |
| `seasonal_diurnal_profile` | Mevsimlere göre günlük profil, LST saati | **24 saat** |
| `seasonal_dayofyear` | Yıl içi gün × günlük toplam, mevsim bantlı | 24 saat (toplam) |
| `target_histogram` | Gündüz ışınımının il bazında dağılımı | gündüz |
| `monthly_boxplot_all_years` | Ay bazında kutu grafiği, tüm yıllar havuzlanmış | 24 saat (toplam) |
| `autocorrelation_hourly`, `autocorrelation_daily` | kt'nin ACF/PACF'i, il bazında | gündüz (kt tanımlı saatler) |
| `ramp_distribution` | \|Saatlik değişim\| birikimli dağılımı, mevsim bazında | gündüz |
| `persistence_baseline` | Modelin aşması gereken RMSE ve R² zemini | gündüz |
| `rize_comparison` | Rize'yi diğer dört ile karşı dört eksende toplayan panel | karışık (alt panellerde yazılı) |

**Saçılım paneli ızgarası öznitelik setinden türetilir.** Önceki dışa aktarımda 8 ham
meteorolojik değişken vardı ve 2×4 ızgara tam oturuyordu; yenisinde 7 var. Izgara artık
`RAW_METEO_COLUMNS`'tan hesaplanır ve artan hücreler kapatılır.

**Günlük profil figüründe gündüz filtresi bilinçli olarak uygulanmaz:** gece sıfırları
fiziksel bilgidir; filtrelenirse eğri sıfırdan yükselip sıfıra dönmez ve kış sabahı gibi az
örnekli saatlerde yapay sıçrama oluşur. IQR bandı yalnız Kış ve Yaz için çizilir (dört bant
üst üste binince okunmaz oluyor) ve **güven aralığı değil, günler arası IQR**'dir.

**3B yüzey tek başına yanıltıcıdır** ve `month_year_anomaly_panel` ile birlikte
değerlendirilmelidir: yüzeyin kabartmasının büyük kısmı mevsim eğrisinin altı kez
tekrarıdır; yıllar arası sinyali gerçekten gösteren figür anomali haritasıdır.

`seasonal_dayofyear`'da **29 Şubat düşürülür** ve artık yıllarda Mart'tan sonraki günler bir
gün geri kaydırılır; aksi hâlde 2020 ve 2024 diğer yıllara göre kayar ve klimatoloji
bulanıklaşır. Düzleştirme, per-gün klimatolojik ortalamanın 7 günlük merkezli hareketli
ortalamasıdır ve seri 3× döşenerek hesaplanır, böylece 31 Aralık/1 Ocak dikişinde kopukluk
olmaz.

## Mevsim tanımı

Meteorolojik mevsimler: **Kış** = Aralık, Ocak, Şubat · **İlkbahar** = Mart, Nisan, Mayıs ·
**Yaz** = Haziran, Temmuz, Ağustos · **Sonbahar** = Eylül, Ekim, Kasım.

---

## Düzeltme kaydı

### 2026-09-14 — veri seti değişti; tüm EDA yeniden üretildi

Kaynak dosya `SolarData_Merve_All(16July).xlsx` → `SolarData_Merve(140926).xlsx`. Aynı NASA
POWER kaydı, farklı dışa aktarım ayarları. Üç eksende değişiklik var ve **bu klasördeki
her sayı yeniden üretilmiştir**; eski sürümden alıntılanmış hiçbir rakam geçerli değildir.

| | Eski | Yeni |
|---|---|---|
| Hedef birimi | W/m² | MJ/m²/saat → okurken W/m²'ye çevriliyor |
| Yağış birimi | mm/gün | mm/saat |
| Öznitelik sayısı | 17 | 16 (`QV2M`, `WS50M`, `WD50M` gitti; `WS2M`, `WD2M` geldi) |
| Gündüz tanımı | `CLRSKY_SFC_SW_DWN > 0` | **`solar_elevation > 0`** (hesaplanmış) |
| Berraklık indeksi | `ALLSKY / CLRSKY` | **`GHI / (I₀ cos θz)`** (standart tanım) |
| Kayıt sonu | 2026-03-30 | 2026-05-30 (+61 gün) |
| İl başına satır | 59.184 | 60.648 |
| Gündüz satırı / payı | 151.643 / %51.2 | 152.893 / %50.42 |
| Test penceresi | 8.878 saat / 370 gün | 9.097 saat / 379 gün |
| Naif zemin (gündüz) | klim. 106.8 / kal. 116.4 | klim. **109.86** / kal. **121.56** |

**Eski excel (`SolarData_Merve_All(16July).xlsx`) depodan silinmiştir.** Bir ara sürümde
`CLRSKY_SFC_SW_DWN` oradan yeniden inşa ediliyordu; o köprü kaldırıldı ve yerini güneş
geometrisi aldı, böylece proje tek bir veri dosyasına bağlı. Bunun iki bedeli var ve ikisi de
ölçülerek kabul edildi: gündüz maskesi %1 kayıyor (klimatoloji RMSE 108.78 → 109.86) ve berrak
gökyüzü **büyüklüğüne** dayanan iki analiz — akıllı kalıcılık referansı ile `clearsky_index`
hedef dönüşümü — kaldırıldı. Gerekçeler `EDA.md` §0.2 ve §0.3'te.

Ayrıntılı gerekçe, ölçümler ve sonuçları `EDA.md` §0'dadır. Bu turda ayrıca **daha önce
bu belgede yazılı olan iki ifade düzeltildi**:

1. *"Açık-hava ışınımı saf geometrik bir büyüklüktür."* Ölçüldü ve fazla güçlü bulundu:
   güneşin konumu sabitken bile NASA POWER'ın değeri yıllar arasında %4–8 geziyor. Yalnız
   **işareti** geometrikti. Bu artık tarihsel bir not: sütun tamamen kullanımdan kalktı ve
   yerine gerçekten saf geometri olan hesaplanmış güneş yüksekliği geçti.
2. *"`PRECTOTCORR`'un birim etiketi şüpheli."* Çözüldü: eski dosya mm/gün, yeni dosya
   mm/saat. `VARIABLE_LABELS_TR`'deki "mm/saat" etiketi eski veride yanlıştı, yeni veride
   doğrudur. `EDA.md` §0.1 ve §4.1.

Önceki turda README ile CSV dosyaları arasında bulunan 15 tutarsızlık, bulgu anlatısının iki
belgede birden tutulmasından kaynaklanıyordu. Bu tur anlatı tek bir yere (`EDA.md`) taşındı
ve bu belge yalnız üretim yöntemini anlatıyor.

### 2026-08-28 — gündüz tanımı değişti

İlk EDA turunda gündüz, klimatolojik bir (il, ay, saat) hücre ortalaması ile tanımlanmıştı.
Gerekçe, `ışınım > 0` eşiğinin bağımlı değişkene koşullama yapmasıydı. Bu gerekçe doğruydu
ama seçilen çözüm yanlıştı: hücre **çok kabaydı.**

Bir ay içinde gün doğumu/batımı 30–60 dakika kayar, bu yüzden hücrenin kenar saati ayın bir
kısmında aydınlık, kalanında karanlıktır; hücre ortalaması saatin tamamını gündüz sayıyordu.
Sonuç: berrak gökyüzü değeri tam 0 olan — yani gece olan — **5.266 satır** gündüz kümesine
giriyor ve her ilin gündüz ortalamasını 10–14 W/m² aşağı çekiyordu.

Yeni tanım `CLRSKY_SFC_SW_DWN > 0`: per-timestamp, geometrik, hedefe hiç bakmıyor — hem
koşullama itirazını hem de kabalık sorununu birlikte çözüyor. Aynı tanım metrik kırılımı ve
(açılırsa) kayıp maskesi için de kullanılır, böylece projede tek bir gündüz tanımı olur.

Nitel sonuçların hiçbiri o turda değişmedi. Bu kaydın sayıları 16 Temmuz veri sürümüne
aittir ve yalnızca tarihsel kayıt olarak durur.
