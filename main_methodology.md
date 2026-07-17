Bu makalede belirsizlik tahmini (**Uncertainty Quantification - UQ**) modelin kendisinden bağımsız bir katmandır. Yani **PCNN yerine LSTM kullansan bile aynı UQ metodunu uygulayabilirsin.** Aslında makalenin yaptığı şey şöyledir:

> **Prediction = LSTM**
>
> **Uncertainty = Bootstrap Ensemble + Monte Carlo Dropout**

Yani LSTM yalnızca nokta tahmini üretir. Daha sonra aynı modelden birçok farklı tahmin üretilerek bu tahminlerin dağılımı belirsizlik olarak yorumlanır. Makale bunu Bootstrap ve MC Dropout'u birlikte kullanarak yapmaktadır. 

---

# Genel Mimari

```text
                    Dataset
                       │
         ┌─────────────┼──────────────┐
         │             │              │
 Bootstrap 1     Bootstrap 2     Bootstrap 3
         │             │              │
      LSTM1         LSTM2         LSTM3
         │             │              │
         └─────────────┼──────────────┘
                       │
             Monte Carlo Dropout
             (100 Forward Pass)
                       │
                       ▼
          Prediction Distribution
                       │
        ┌──────────────┴───────────────┐
        │                              │
     Mean Prediction            Std Prediction
        │                              │
        └──────────────┬───────────────┘
                       ▼
               95% Confidence Interval
```

---

# Yöntem 1 — Monte Carlo Dropout

Bu yöntem en kolay uygulanandır.

Normalde inference sırasında

```python
model.eval()
```

kullanılır.

MC Dropout'ta ise

dropout **kapatılmaz**.

Yani

```python
model.train()
```

modunda prediction yapılır.

Sebebi

Dropout her forward pass'te farklı nöronları kapatacaktır.

Dolayısıyla

aynı sample

100 defa modele verilince

100 farklı prediction elde edilir.

Makaledeki epistemic uncertainty tam olarak budur. 

---

## Kod

```python
def mc_predict(model, X, T=100):

    model.train()        # dropout aktif

    preds = []

    with torch.no_grad():

        for _ in range(T):

            y = model(X)

            preds.append(y.cpu().numpy())

    preds = np.stack(preds)

    mean = preds.mean(axis=0)

    std = preds.std(axis=0)

    return mean, std
```

---

Örneğin

```
100 prediction

520

525

521

518

527

523

...

```

Mean

```
522
```

Std

```
3.2
```

95% CI

```
522 ± 1.96×3.2
```

---

# Confidence Interval

```python
lower = mean - 1.96 * std

upper = mean + 1.96 * std
```

Makalede kullanılan

CI95%

budur. 

---

# Yöntem 2 — Bootstrap Ensemble

Bu yöntem aleatoric uncertainty'yi yakalamaya çalışır.

Makalede

B adet bootstrap dataset oluşturuluyor.

Örneğin

```
Original Dataset

↓

Bootstrap 1

↓

Train LSTM1


Original Dataset

↓

Bootstrap 2

↓

Train LSTM2


Original Dataset

↓

Bootstrap 3

↓

Train LSTM3
```

Her model

aynı sample için

bir tahmin üretir.

Makaledeki bootstrap tanımı şöyledir. 

---

Kod

```python
from sklearn.utils import resample

models = []

for i in range(10):

    Xb, yb = resample(
        X_train,
        y_train,
        replace=True
    )

    model = LSTM()

    train(model, Xb, yb)

    models.append(model)
```

Prediction

```python
preds = []

for model in models:

    pred = model(X_test)

    preds.append(pred.detach().numpy())

preds = np.stack(preds)
```

Mean

```python
mean = preds.mean(axis=0)
```

Std

```python
std = preds.std(axis=0)
```

---

# Makalenin Yaptığı Hibrit Yaklaşım

Makale aslında

Bootstrap

*

MC Dropout

birlikte kullanıyor.

Yani

Bootstrap model uncertainty

MC Dropout parameter uncertainty

yakalıyor.

```text
Bootstrap 1
      │
      ▼
MC Dropout
100 prediction

Bootstrap 2
      │
      ▼
MC Dropout
100 prediction

Bootstrap 3
      │
      ▼
MC Dropout
100 prediction

...

↓

1000 prediction

↓

Prediction Distribution

↓

Mean

↓

Std

↓

95% CI
```

Bu yöntem makalenin önerdiği hibrit UQ yaklaşımıdır. 

---

# Sonuçların Hesaplanması

Makalede

her test örneği için

```
Prediction Mean

Prediction Std

Lower CI

Upper CI
```

hesaplanıyor.

Kod

```python
mean = predictions.mean(axis=0)

std = predictions.std(axis=0)

lower = np.percentile(predictions, 2.5, axis=0)

upper = np.percentile(predictions, 97.5, axis=0)
```

Dikkat edersen burada **percentile tabanlı güven aralığı**, normal dağılım varsayımı gerektirmediği için makalenin bootstrap yaklaşımıyla daha uyumludur. 

---

# Coverage Probability (CP)

Makalenin kullandığı ilk UQ metriği

```python
inside = (
    (y_test >= lower) &
    (y_test <= upper)
)

CP = inside.mean()
```

Örneğin

```
95% Confidence Interval

↓

Gerçek değerlerin

94%

CI içinde kalıyor

↓

CP=0.94
```

Makaledeki tanım bu şekildedir. 

---

# Prediction Interval Normalized Width (PINW)

İkinci metrik

```
CI ne kadar geniş?
```

Kod

```python
PINW = np.mean(
    upper - lower
) / (y_test.max() - y_test.min())
```

İdeal durumda:

* **CP yüksek** olmalıdır (ör. %95'lik aralık için ≈0.95).
* **PINW düşük** olmalıdır; yani güven aralıkları gereksiz yere geniş olmadan gerçek değerleri kapsamalıdır. Bu ikisi birlikte modelin belirsizlik tahmininin kalitesini gösterir. 

## LSTM için önerilen uygulama

Akademik açıdan ve hesaplama maliyeti açısından en dengeli yapı şu olur:

1. Multivariate LSTM modelini dropout katmanlarıyla eğit.
2. Eğitim bittikten sonra **5–10 adet zaman serisine uygun bootstrap model** oluştur (tercihen moving block bootstrap veya residual bootstrap; klasik rastgele bootstrap zaman bağımlılığını bozabilir. Makale de zaman serisine duyarlı yeniden örnekleme önerir. ).
3. Her bootstrap modeli için inference sırasında **50–100 MC Dropout forward pass** çalıştır.
4. Elde edilen tüm tahminleri (örneğin 10 × 100 = 1000 tahmin) tek bir dağılım olarak değerlendir.
5. Dağılımdan ortalama tahmin, standart sapma, %95 güven aralığı, Coverage Probability ve PINW hesapla.

Bu yaklaşım, makalenin uncertainty quantification metodolojisini LSTM tabanlı bir forecasting modeline en sadık şekilde uyarlayan çözümdür.

