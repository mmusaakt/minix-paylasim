# minix otomatik paylaşım

@minixanima videolarını her gün **12:30** ve **20:00**'de (İstanbul) Instagram Reels ve YouTube Shorts'a paylaşır.

Kurulum rehberi: https://claude.ai/artifact/N2q7RZswzuAQ5uZuVkt6VX

## İşlemler (Actions)

| İşlem | Ne zaman | Ne yapar |
| --- | --- | --- |
| Paylaş | 11:00–12:50 ve 18:30–20:20 arası 10 dakikada bir (GitHub gecikmesine karşı); slotu 12:30 / 20:00'de paylaşır | Instagram: video + takvimdeki şarkı + açıklama + ilk yorum. YouTube: Shorts. |
| İstatistik | Her gün 23:35 | İzlenme, erişim, beğeni, kaydetme… `istatistik/` klasörüne yazar. |
| Kontrol | Pazartesi 10:10 + elle | Anahtarları, şarkıları, videoları ve takvimin bitişini kontrol eder. |
| YouTube kanal ayarları | Elle | Kanal kapağı, açıklama ve anahtar kelimeler (`kanal/`). |

Elle çalıştırma: **Actions → işlem → Run workflow**. Paylaş'ta *deneme* seçilirse Instagram'a yüklenir ama
yayınlanmaz, YouTube'a gizli yüklenir.

## Dosyalar

- `takvim.json` – paylaşılacak slotlar (başlık, açıklama, şarkı, sabit yorum, video, kapak karesi)
- `videolar/` – sesli videolar
- `durum.json` – ne zaman, nereye paylaşıldı (bağlantılarıyla)
- `istatistik/` – günlük istatistikler
- `paylasim/` – kod (Python, sadece `requests`)

## Sırlar (Settings → Secrets and variables → Actions)

`META_TOKEN` · `YT_CLIENT_ID` · `YT_CLIENT_SECRET` · `YT_REFRESH_TOKEN` (isteğe bağlı: `IG_USER_ID`)

Değişkenler (Variables, isteğe bağlı): `MUZIK` (`kapali`), `MUZIK_SES` (40), `VIDEO_SES` (70), `PLATFORMLAR`.

Müzik: Instagram API'si yalnızca lisanslı kütüphane parçalarını veriyor. `Müzik kataloğu` işlemi kütüphaneyi tarayıp
`muzik/katalog.json`'a yazar; her slotun parçası `takvim.json`'daki `muzik_id` alanında.
