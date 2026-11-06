# minix otomatik paylaşım

@minixanima videolarını her gün **12:30** ve **20:00**'de (İstanbul) Instagram Reels ve YouTube Shorts'a paylaşır.
TikTok için 5 günde bir 10 videoluk paket hazırlar (TikTok Studio'da elle planlanır).

Kurulum rehberi: https://claude.ai/artifact/N2q7RZswzuAQ5uZuVkt6VX

## İşlemler (Actions)

| İşlem | Ne zaman | Ne yapar |
| --- | --- | --- |
| Paylaş | Her gün 12:20 ve 19:50 (saati bekler) | Instagram: video + takvimdeki şarkı + açıklama + ilk yorum. YouTube: Shorts. |
| İstatistik | Her gün 23:35 | İzlenme, erişim, beğeni, kaydetme… `istatistik/` klasörüne yazar. |
| TikTok paketi | Her gün 09:40 (gerekirse) | Sıradaki 10 videoyu zip'ler, Releases'e koyar, Issues'ta haber verir. |
| Kontrol | Pazartesi 10:10 + elle | Anahtarları, şarkıları, videoları ve takvimin bitişini kontrol eder. |
| YouTube kanal ayarları | Elle | Kanal kapağı, açıklama ve anahtar kelimeler (`kanal/`). |

Elle çalıştırma: **Actions → işlem → Run workflow**. Paylaş'ta *deneme* seçilirse Instagram'a yüklenir ama
yayınlanmaz, YouTube'a gizli yüklenir.

## Dosyalar

- `takvim.json` – paylaşılacak slotlar (başlık, açıklama, şarkı, sabit yorum, video, kapak karesi)
- `videolar/` – sesli videolar
- `durum.json` – ne zaman, nereye paylaşıldı (bağlantılarıyla)
- `istatistik/` – günlük istatistikler
- `tiktok.json` – hangi slotlar TikTok paketine girdi
- `paylasim/` – kod (Python, sadece `requests`)

## Sırlar (Settings → Secrets and variables → Actions)

`META_TOKEN` · `YT_CLIENT_ID` · `YT_CLIENT_SECRET` · `YT_REFRESH_TOKEN` (isteğe bağlı: `IG_USER_ID`)

Değişkenler (Variables, isteğe bağlı): `MUZIK` (`kapali`), `MUZIK_SES` (35), `VIDEO_SES` (100), `PLATFORMLAR`.
