# minix otomatik paylaşım

@minixanima videolarını her gün **12:30** ve **20:00**'de (İstanbul) Instagram Reels ve YouTube Shorts'a paylaşır.

Kurulum rehberi: https://claude.ai/artifact/N2q7RZswzuAQ5uZuVkt6VX

## İşlemler (Actions)

| İşlem | Ne zaman | Ne yapar |
| --- | --- | --- |
| Paylaş | 11:00–12:50 ve 18:30–20:20 arası 10 dakikada bir (GitHub gecikmesine karşı); slotu 12:30 / 20:00'de paylaşır. 9–20 Kasım'da ayrıca 16:00 ve 22:30 (yalnız YouTube) | Instagram: video + takvimdeki şarkı + açıklama + ilk yorum. YouTube: Shorts. |
| İstatistik | Her gün 23:35 | İzlenme, erişim, beğeni, kaydetme… `istatistik/` klasörüne yazar. |
| Kontrol | Pazartesi 10:10 + elle | Anahtarları, şarkıları, videoları ve takvimin bitişini kontrol eder. |
| YouTube kanal ayarları | Elle | Kanal kapağı, açıklama ve anahtar kelimeler (`kanal/`). |
| Müzik kataloğu | Elle | Instagram'ın lisanslı müzik kütüphanesini tarar, parçaların temposunu ve tonunu çıkarır (`muzik/`). |
| Müzik testi | Elle | Şarkının videoya eklenip eklenmediğini yayın yapmadan dener. |
| YouTube kopyaları | Elle | Kanalda aynı başlıkla birden çok yüklenmiş videoları listeler; *sil* işaretliyse fazlalarını siler (daha çok izleneni bırakır). |

Elle çalıştırma: **Actions → işlem → Run workflow**. Paylaş'ta *deneme* seçilirse Instagram'a yüklenir ama
yayınlanmaz, YouTube'a gizli yüklenir.

## Dosyalar

- `takvim.json` – paylaşılacak slotlar (başlık, açıklama, şarkı, sabit yorum, video, kapak karesi). `"platformlar": ["youtube"]` olan slot yalnız YouTube'a gider: 9–20 Kasım'da Instagram'da elle paylaşılmış 23 bölüm YouTube'a da yükleniyor.
- `videolar/` – sesli videolar
- `durum.json` – ne zaman, nereye paylaşıldı (bağlantılarıyla)
- `istatistik/` – günlük istatistikler
- `paylasim/` – kod (Python, sadece `requests`)

## Sırlar (Settings → Secrets and variables → Actions)

`META_TOKEN` · `YT_CLIENT_ID` · `YT_CLIENT_SECRET` · `YT_REFRESH_TOKEN` (isteğe bağlı: `IG_USER_ID`)

Değişkenler (Variables, isteğe bağlı): `MUZIK` (`kapali`), `MUZIK_SES` (40), `VIDEO_SES` (70), `PLATFORMLAR`.

Müzik: Instagram API'si yalnızca lisanslı kütüphane parçalarını veriyor. `Müzik kataloğu` işlemi kütüphaneyi tarayıp
`muzik/katalog.json`'a yazar; her slotun parçası `takvim.json`'daki `muzik_id` alanında. Şarkı %40, videonun efekt
sesi %70 çalar (`MUZIK_SES`, `VIDEO_SES` ile değişir). Müzikli yükleme ara sıra reddedilirse üç kez denenir, yine
olmazsa video müziksiz paylaşılır (özette "Müzik: yok" yazar). `Müzik testi` işlemi müziğin eklenip eklenmediğini
yayın yapmadan dener.
