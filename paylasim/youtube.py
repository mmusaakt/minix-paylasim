"""YouTube Shorts yükleme: YouTube Data API v3, OAuth yenileme anahtarı ile.

Belge: https://developers.google.com/youtube/v3/docs/videos/insert
"""
from __future__ import annotations

import json
from pathlib import Path

from .ortak import ApiHatasi, istek, log

TOKEN_URL = "https://oauth2.googleapis.com/token"
API = "https://www.googleapis.com/youtube/v3"
UPLOAD = "https://www.googleapis.com/upload/youtube/v3/videos"


class YouTube:
    def __init__(self, istemci_id: str, istemci_sirri: str, yenileme_anahtari: str):
        self.istemci_id = istemci_id
        self.istemci_sirri = istemci_sirri
        self.yenileme = yenileme_anahtari
        self._erisim: str | None = None

    def erisim(self) -> str:
        if not self._erisim:
            r = istek("POST", TOKEN_URL, data={
                "client_id": self.istemci_id,
                "client_secret": self.istemci_sirri,
                "refresh_token": self.yenileme,
                "grant_type": "refresh_token",
            })
            self._erisim = r.json()["access_token"]
        return self._erisim

    def _bas(self) -> dict:
        return {"Authorization": f"Bearer {self.erisim()}"}

    def kanal(self) -> dict | None:
        """Bağlı kanalın adı. (youtube.upload izni kanal okumaya yetmeyebilir; o zaman None.)"""
        try:
            v = istek("GET", f"{API}/channels", params={"part": "snippet,statistics", "mine": "true"},
                      headers=self._bas(), deneme=2).json()
        except ApiHatasi as e:
            log(f"  kanal bilgisi okunamadı ({e}); yükleme izni yine de çalışabilir")
            return None
        oge = (v.get("items") or [None])[0]
        if not oge:
            return None
        st = oge.get("statistics", {})
        k = {"id": oge["id"], "ad": oge["snippet"]["title"]}
        if not st.get("hiddenSubscriberCount") and "subscriberCount" in st:
            k["abone"] = int(st["subscriberCount"])
        for alan, ad in (("viewCount", "toplam_izlenme"), ("videoCount", "video_sayisi")):
            if alan in st:
                k[ad] = int(st[alan])
        return k

    # ------------------------------------------------------------------ kanal ayarları
    def kapak_yukle(self, gorsel: Path) -> str:
        """Kanal kapağını (banner) yükler ve kanala uygular. 'youtube' izni gerekir."""
        tur = "image/png" if gorsel.suffix.lower() == ".png" else "image/jpeg"
        r = istek("POST", "https://www.googleapis.com/upload/youtube/v3/channelBanners/insert",
                  params={"uploadType": "media"}, data=gorsel.read_bytes(),
                  headers={**self._bas(), "Content-Type": tur}, timeout=300)
        return r.json()["url"]

    def kanal_guncelle(self, aciklama: str | None = None, anahtar_kelimeler: str | None = None,
                       kapak_url: str | None = None, ulke: str = "TR", dil: str = "tr") -> dict:
        v = istek("GET", f"{API}/channels", params={"part": "brandingSettings", "mine": "true"},
                  headers=self._bas()).json()
        oge = (v.get("items") or [None])[0]
        if not oge:
            raise ApiHatasi("Bu Google hesabına bağlı bir YouTube kanalı bulunamadı")
        bs = oge.get("brandingSettings", {})
        kanal = bs.setdefault("channel", {})
        if aciklama is not None:
            kanal["description"] = aciklama[:1000]
        if anahtar_kelimeler is not None:
            kanal["keywords"] = anahtar_kelimeler[:500]
        kanal["country"] = ulke
        kanal["defaultLanguage"] = dil
        if kapak_url:
            bs.setdefault("image", {})["bannerExternalUrl"] = kapak_url
        govde = {"id": oge["id"], "brandingSettings": {k: bs[k] for k in ("channel", "image") if k in bs}}
        r = istek("PUT", f"{API}/channels", params={"part": "brandingSettings"},
                  headers={**self._bas(), "Content-Type": "application/json; charset=UTF-8"},
                  data=json.dumps(govde))
        return r.json()

    # ------------------------------------------------------------------ yüklenenler
    def yuklemeler(self, adet: int = 50) -> list[dict]:
        """Kanalın son yüklemeleri (yeniden eskiye): id, başlık, gizlilik, zaman."""
        v = istek("GET", f"{API}/channels", params={"part": "contentDetails", "mine": "true"},
                  headers=self._bas(), deneme=2).json()
        oge = (v.get("items") or [None])[0]
        if not oge:
            return []
        liste_id = oge["contentDetails"]["relatedPlaylists"]["uploads"]
        sonuc: list[dict] = []
        sayfa = None
        while len(sonuc) < adet:
            p = {"part": "snippet,status,contentDetails", "playlistId": liste_id, "maxResults": 50}
            if sayfa:
                p["pageToken"] = sayfa
            v = istek("GET", f"{API}/playlistItems", params=p, headers=self._bas(), deneme=2).json()
            for o in v.get("items", []):
                sonuc.append({"id": o["contentDetails"]["videoId"], "baslik": o["snippet"].get("title", ""),
                              "gizlilik": o.get("status", {}).get("privacyStatus", ""),
                              "zaman": o["contentDetails"].get("videoPublishedAt") or o["snippet"].get("publishedAt", "")})
            sayfa = v.get("nextPageToken")
            if not sayfa:
                break
        return sonuc[:adet]

    def zaten_yuklenmis(self, baslik: str) -> str | None:
        """Aynı başlıkla herkese açık bir Shorts zaten varsa onun id'si (gizli deneme yüklemeleri sayılmaz)."""
        aranan = " ".join(baslik[:100].split())
        for y in self.yuklemeler(50):
            if y["gizlilik"] == "public" and " ".join(y["baslik"].split()) == aranan:
                return y["id"]
        return None

    def sil(self, video_id: str) -> None:
        istek("DELETE", f"{API}/videos", params={"id": video_id}, headers=self._bas(), deneme=2)

    # ------------------------------------------------------------------ istatistik
    def istatistikler(self, video_idleri: list[str]) -> dict[str, dict]:
        sonuc: dict[str, dict] = {}
        for i in range(0, len(video_idleri), 50):
            parca = video_idleri[i:i + 50]
            v = istek("GET", f"{API}/videos", params={"part": "statistics", "id": ",".join(parca)},
                      headers=self._bas()).json()
            for oge in v.get("items", []):
                s = oge.get("statistics", {})
                sonuc[oge["id"]] = {k: int(s[k]) for k in ("viewCount", "likeCount", "commentCount") if k in s}
        return sonuc

    def analitik(self, video_idleri: list[str], baslangic: str, bitis: str) -> dict[str, dict]:
        """İzlenme süresi ve izlenme yüzdesi (yt-analytics.readonly izni varsa)."""
        sonuc: dict[str, dict] = {}
        metrikler = "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,likes,shares,subscribersGained"
        for i in range(0, len(video_idleri), 200):
            parca = video_idleri[i:i + 200]
            v = istek("GET", "https://youtubeanalytics.googleapis.com/v2/reports", deneme=2, params={
                "ids": "channel==MINE", "startDate": baslangic, "endDate": bitis, "metrics": metrikler,
                "dimensions": "video", "filters": "video==" + ",".join(parca), "maxResults": 200,
            }, headers=self._bas()).json()
            basliklar = [c["name"] for c in v.get("columnHeaders", [])]
            for satir in v.get("rows", []) or []:
                d = dict(zip(basliklar, satir))
                sonuc[d.pop("video")] = d
        return sonuc

    def yukle(self, video: Path, baslik: str, aciklama: str, etiketler: list[str],
              gizlilik: str = "public", kategori: str = "1") -> str:
        meta = {
            "snippet": {
                "title": baslik[:100],
                "description": aciklama[:5000],
                "tags": etiketler[:30],
                "categoryId": kategori,
                "defaultLanguage": "tr",
            },
            "status": {
                "privacyStatus": gizlilik,
                "selfDeclaredMadeForKids": False,
                "embeddable": True,
                "license": "youtube",
                "containsSyntheticMedia": False,
            },
        }
        boyut = video.stat().st_size
        son_hata: Exception | None = None
        for deneme in range(3):
            try:
                baslat = istek("POST", UPLOAD, params={"uploadType": "resumable", "part": "snippet,status"},
                               headers={**self._bas(), "Content-Type": "application/json; charset=UTF-8",
                                        "X-Upload-Content-Type": "video/mp4",
                                        "X-Upload-Content-Length": str(boyut)},
                               data=json.dumps(meta), tekrar_dene=False)
                adres = baslat.headers.get("Location")
                if not adres:
                    raise ApiHatasi("YouTube yükleme adresi vermedi")
                with open(video, "rb") as f:
                    r = istek("PUT", adres, data=f.read(),
                              headers={**self._bas(), "Content-Type": "video/mp4"},
                              tekrar_dene=False, timeout=600)
                return r.json()["id"]
            except ApiHatasi as e:
                son_hata = e
                log(f"  YouTube yükleme denemesi {deneme + 1} başarısız: {e}")
                if not e.gecici:
                    raise
                self._erisim = None
        assert son_hata is not None
        raise son_hata
