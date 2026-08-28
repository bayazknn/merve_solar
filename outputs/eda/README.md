# Betimsel istatistik çıktıları (EDA)

Tümü `scripts/02_descriptive_analysis.py` tarafından üretilir; girdi
`outputs/processed/base_features.parquet` (5 il, 2019-06-30 00:00 → 2026-03-30 23:00, il
başına 59 184 kesintisiz saatlik satır). `DROPPED_COLUMNS` (`ALLSKY_KT`,
`CLRSKY_SFC_SW_DWN`) okuma anında düşürüldüğü için bu çıktılarda hiç yer almaz.

Yeniden üretmek için:

```bash
uv run python scripts/02_descriptive_analysis.py
```

## Makaleye yazarken dikkat edilecek beş nokta

**1. "Gündüz" klimatolojik olarak tanımlıdır, ölçülen değere göre değil.**
Bir satır, kendi (il, ay, saat) hücresinin ortalaması > 0 ise gündüzdür. Yaygın olan
`ışınım > 0` filtresi bağımlı değişkene koşullama yapıyor: klimatolojik olarak gündüz olup
ölçümü tam 0 olan 5 266 satırı (en bulutlu saatler) siliyor, üstelik iller arasında
dengesiz (Antalya 760, Rize 1 253). Bu, gündüz ortalamasını yapay olarak 9.9–14.4 W/m²
yukarı kaydırır ve tam da raporlanan nem/yağış korelasyonlarını zayıflatır.
Havuzlanmış gündüz payı: **%53.0**.

**2. Aylık kutu grafiği saatlik değil, günlük toplam üzerindendir.**
Gündüz *saatlik* değerlerle çizilen bir kutunun genişliğinin ~%91'i gün içi güneş
geometrisidir ve kışın kutu daralır — okuyucu "kış daha stabil" sonucuna varır. Gerçek
tersidir: Ankara 2025'te gündüz-saatlik IQR Ocak 276 < Temmuz 588 W/m², ama günlük
toplamlarla Ocak 1.33 kWh/m² (CV 0.34) > Temmuz 0.72 kWh/m² (CV 0.08). Günlük toplam ayrıca
gündüz filtresinden bağımsızdır (gece 0 katar).

**3. Saat ekseni NASA POWER'ın il-bazlı yerel güneş saatidir (LST), ortak bir saat dilimi
değil.** Ortalama ışınımın zirve saati Konya 11.25, Ankara 11.26, Antalya 11.41, Van 11.56,
Rize 11.89. Ortak saatte doğudaki iller *erken* zirve yapmalıydı; sıralama tersi.
Boylamdan hesaplanan LST beklentileri (Ankara 11.81, Konya 11.83, Antalya 11.95, Van 12.11,
Rize 12.30) gözlemle 0.1 saat içinde örtüşüyor. Sonuçları:
- `HR=11` Rize'de ve Ankara'da farklı fiziksel andır; **saatler iller arasında
  karşılaştırılmaz**, her il kendi paneline bakılır.
- Saat etiketi ilgili saat aralığının **başlangıcıdır**; figürlerde aralık ortasına
  (`HR + 0.5`) çizilir.
- Bu, `data.py`'deki `hour_sin`/`hour_cos` kodlaması için aslında avantajdır: her il kendi
  güneş saatinde kodlanmış olur. Makalenin yöntem bölümünde bir cümleyle belirtilmeli.

**4. p-değeri ve anlamlılık yıldızı bilinçli olarak yoktur.** n ≈ 157 000 otokorelasyonlu
saatlik satırda her |r| > 0.01 "p < 0.001" çıkar; etkin örneklem büyüklüğü bunun kat kat
altındadır. Anlamlılık yerine etki büyüklüğü ve `partial_r_within_hour` raporlanır.

**5. 2026-03 ayı 31 değil 30 günlüktür** (kaynak veri 2026-03-30 23:00'da bitiyor) ve 3B
yüzey yalnız tam takvim yıllarını (2020–2025) kullanır; 2019 (30 Haziran'da başlıyor) ve
2026 kısmi olduğu için dışarıdadır.

## Tablolar (`tables/`)

| Dosya | İçerik |
|---|---|
| `descriptive_stats_by_city_daylight.csv/.md/.tex` | **Birincil tablo.** Gündüz saatleri, il bazında + havuzlanmış. |
| `descriptive_stats_by_city_24h.csv/.md/.tex` | Aynı tablo 24 saat üzerinden — modelin eğitildiği dağılım budur, hakem sorarsa tamamlayıcı olarak verilir. |
| `temporal_coverage_by_city.csv` | Zaman feature'larının tarifi: kapsam, saat/gün sayısı, gündüz payı, mevsime göre ortalama günlük gündüz süresi, hedefin mevsimsel özetleri. |
| `target_by_hour_by_city.csv` | Hedefin (il, mevsim, LST saati) dağılımı — günlük profil figürünün verisi. |
| `time_feature_explained_variance.csv` | Saat ve yılın günü için η² ve harmonik R². Sin/cos sütunlarına karşı Pearson *r* yerine bu raporlanır: deterministik bir saat fonksiyonuna karşı korelasyon yorumlanamaz. |
| `wind_direction_circular_stats.csv` | Rüzgâr yönü dairesel istatistiği (bkz. aşağıda). |
| `correlation_pearson_<il>.csv`, `correlation_spearman_<il>.csv`, `..._pooled.csv` | 9 fiziksel değişkenin korelasyon matrisleri, gündüz saatleri. |
| `target_correlation_by_city.csv` | Hedefle korelasyon + `partial_r_within_hour` (bkz. aşağıda). |
| `collinear_pairs.csv` | \|r\| > 0.9 çiftler. |
| `monthly_target_stats.csv` | Son 12 ay, günlük toplam özetleri. |
| `seasonal_target_stats.csv` | Mevsim bazında saatlik ve günlük toplam özetleri. |

**Basıklık Fisher (fazlalık) tanımıdır:** normal dağılım için 0, 3 değil. Gündüz verisinde
hedefin çarpıklığı 0.47, fazlalık basıklığı −0.92 — yani ağır kuyruklu değil, basık/iki
tepeli. Spearman bu yüzden değil, **doğrusal olmayan** ilişkiler için raporlanır.

**Havuzlanmış ("Tümü") satırın standart sapması** iller-içi ve iller-arası varyansın
karışımıdır; iller-arası bileşen `between_city_sd` sütununda ayrıca verilir (hedef için
43.6 W/m²).

**Rüzgâr yönü** ana tablodan çıkarılmıştır: dairesel bir değişkenin aritmetik ortalaması
anlamsızdır (havuzlanmış ham hesap "189.5° ± 107°" verir, bu bir istatistik değil bir
artefakttır). Ayrı tabloda hız-ağırlıklı dairesel ortalama, bileşke uzunluk *R* (0 = yönsüz,
1 = tek yön) ve dairesel SD verilir; `WS10M ≤ 1 m/s` sakin saatler dışlanır ve dışlanan
saat sayısı tabloda yazılıdır. Yön klimatolojisi gündüzle sınırlı değildir, 24 saat
üzerinden hesaplanır. Van belirgin şekilde en yönlü ildir (R = 0.46).

**`partial_r_within_hour`**, (il, ay, saat) hücre ortalaması çıkarıldıktan sonraki
korelasyondur; hava sinyalini güneş geometrisinden ayırır. Fark büyüktür ve makaleye
girmelidir: havuzlanmış gündüz verisinde sıcaklık 0.53 → 0.30, özgül nem +0.04 → −0.27,
basınç −0.03 → +0.26 (işaret değiştiriyor), bağıl nem −0.64 → −0.51. Yani ham
korelasyonların önemli bir kısmı, değişkenlerin de güneş yüksekliğini takip etmesinden
kaynaklanıyor; gerçek bulut sinyali bağıl nem ve yağışta.

## Figürler (`figures/`)

Her figür hem `.png` (300 dpi) hem `.pdf` (vektör, Type 42 yazı tipi) olarak yazılır.
Arka plan her yerde beyazdır; mevsimler renk **ve** çizgi tipiyle ayrışır, böylece
siyah-beyaz baskıda ve renk körlüğünde kimlik korunur.

| Dosya | Ne gösterir | Filtre |
|---|---|---|
| `correlation_heatmap_<il>`, `_pooled` | 9 değişkenin korelasyon matrisi | gündüz |
| `target_correlation_panel` | Değişken × il, hedefle korelasyon | gündüz |
| `scatter_vs_target_<il>` | Her değişkenin hedefe karşı saçılımı + binlenmiş medyan eğrisi | gündüz |
| `monthly_boxplot_last12m_<il>`, `_panel` | Son 12 ayın günlük toplamları | 24 saat (toplam) |
| `month_year_surface_<il>`, `_panel` | 3B ay × yıl × ışınım yüzeyi, 2020–2025 | 24 saat (toplam) |
| `month_year_anomaly_panel` | Aynı verinin 2B anomali görünümü | 24 saat (toplam) |
| `seasonal_diurnal_profile` | Mevsimlere göre günlük profil, LST saati | **24 saat** |
| `seasonal_dayofyear` | Yıl içi gün × günlük toplam, mevsim bantlı | 24 saat (toplam) |

**Günlük profil figüründe gündüz filtresi bilinçli olarak uygulanmaz:** gece sıfırları
fiziksel bilgidir, filtrelenirse eğri sıfırdan yükselip sıfıra dönmez ve kış sabahı gibi az
örnekli saatlerde yapay sıçrama oluşur. IQR bandı yalnız Kış ve Yaz için çizilir (dört bant
üst üste binince okunmaz oluyor) ve **güven aralığı değil, günler arası IQR**'dir.

**3B yüzey tek başına yanıltıcıdır**, `month_year_anomaly_panel` ile birlikte
değerlendirilmelidir: aylık ortalamalarda mevsimsel aralık 193–247 W/m², aynı ayın yıllar
arası standart sapması ise medyan 8–16 W/m². Yani yüzeyin kabartmasının ~%95'i mevsim
eğrisinin 6 kez tekrarıdır; yıllar arası sinyali gerçekten gösteren figür anomali
haritasıdır.

`seasonal_dayofyear`'da **29 Şubat düşürülür** ve artık yıllarda Mart'tan sonraki günler bir
gün geri kaydırılır; aksi halde 2020 ve 2024 diğer yıllara göre bir gün kayar ve
klimatoloji bulanıklaşır. Düzleştirme, per-gün klimatolojik ortalamanın 7 günlük merkezli
hareketli ortalamasıdır ve seri 3× döşenerek hesaplanır, böylece 31 Aralık/1 Ocak dikişinde
kopukluk olmaz.

## Mevsim tanımı

Meteorolojik mevsimler: **Kış** = Aralık, Ocak, Şubat · **İlkbahar** = Mart, Nisan, Mayıs ·
**Yaz** = Haziran, Temmuz, Ağustos · **Sonbahar** = Eylül, Ekim, Kasım.
