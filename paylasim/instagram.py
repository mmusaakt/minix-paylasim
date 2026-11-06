"""Instagram Reels paylaşımı: Instagram API with Facebook Login (graph.facebook.com).

Akış: (müzik ara) -> konteyner oluştur (resumable) -> videoyu yükle -> işlenmesini bekle
-> yayınla -> ilk yorumu yaz.
Belgeler:
  https://developers.facebook.com/docs/instagram-platform/content-publishing/
  https://developers.facebook.com/docs/instagram-platform/content-publishing/audio-api/
"""
from __future__ import annotations

import difflib
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .ortak import ApiHatasi, istek, log, sadelestir

VARSAYILAN_SURUM = "v26.0"
ISTENMEYEN = ("remix", "cover", "sped up", "slowed", "karaoke", "instrumental",
              "live", "acoustic", "8d", "nightcore", "reverb", "piano version", "lofi", "lo fi")


class Instagram:
    def __init__(self, token: str, ig_user_id: str | None = None, surum: str | None = None,
                 kullanici_adi: str | None = None):
        self.token = token
        self.surum = surum or os.environ.get("META_GRAPH_VERSION") or VARSAYILAN_SURUM
        self.taban = f"https://graph.facebook.com/{self.surum}"
        self.ig_id = ig_user_id or None
        self.kullanici_adi = (kullanici_adi or os.environ.get("IG_USERNAME") or "minixanima").lstrip("@").lower()
        self.hesap_adi: str | None = None

    # ------------------------------------------------------------------ temel
    def _get(self, yol: str, **params) -> dict:
        params["access_token"] = self.token
        return istek("GET", f"{self.taban}/{yol.lstrip('/')}", params=params).json()

    def _post(self, yol: str, tekrar_dene: bool = True, **veri) -> dict:
        veri["access_token"] = self.token
        return istek("POST", f"{self.taban}/{yol.lstrip('/')}", data=veri, tekrar_dene=tekrar_dene).json()

    # ------------------------------------------------------------------ hesap
    def hesap(self) -> dict:
        """Instagram hesabının kimliğini ve kullanıcı adını bulur."""
        if self.ig_id:
            v = self._get(self.ig_id, fields="id,username,followers_count,media_count")
            self.hesap_adi = v.get("username")
            return v
        adaylar: list[dict] = []
        try:
            sayfalar = self._get("me/accounts", fields="name,instagram_business_account{id,username}", limit=100)
            for s in sayfalar.get("data", []):
                iba = s.get("instagram_business_account")
                if iba:
                    adaylar.append({**iba, "sayfa": s.get("name")})
        except ApiHatasi:
            pass
        if not adaylar:  # sayfa anahtarı (Page token) olabilir
            try:
                ben = self._get("me", fields="name,instagram_business_account{id,username}")
                if ben.get("instagram_business_account"):
                    adaylar.append({**ben["instagram_business_account"], "sayfa": ben.get("name")})
            except ApiHatasi:
                pass
        if not adaylar:
            raise ApiHatasi("Anahtarla erişilebilen bir Instagram profesyonel hesabı bulunamadı. "
                            "Instagram hesabı bir Facebook sayfasına bağlı mı, anahtara sayfa izni verildi mi?")
        secilen = next((a for a in adaylar if str(a.get("username", "")).lower() == self.kullanici_adi), adaylar[0])
        self.ig_id = secilen["id"]
        self.hesap_adi = secilen.get("username")
        return self._get(self.ig_id, fields="id,username,followers_count,media_count")

    # ------------------------------------------------------------------ müzik
    def muzik_ara(self, sorgu: str) -> list[dict]:
        assert self.ig_id
        v = self._get("ig_audio", audio_type="music", user_id=self.ig_id, search_query=sorgu)
        return v.get("data", [])

    def muzik_bul(self, muzik: str) -> dict | None:
        """'Şarkı Adı – Sanatçı' metnine en iyi uyan Instagram müziğini döndürür; yoksa None."""
        if not muzik:
            return None
        ad, _, sanatci = muzik.replace(" - ", " – ").partition(" – ")
        ad, sanatci = ad.strip(), sanatci.strip()
        sorgular = [f"{ad} {sanatci}".strip(), ad]
        # Parantezli adlar için kısa sürümü de dene: "Vincent (Starry, Starry Night)" -> "Vincent"
        kisa = sadelestir(ad)
        if kisa and kisa != ad.lower():
            sorgular.append(f"{kisa} {sanatci}".strip())
        gorulen: dict[str, dict] = {}
        for sorgu in dict.fromkeys(sorgular):
            try:
                for a in self.muzik_ara(sorgu):
                    if a.get("audio_id"):
                        gorulen.setdefault(str(a["audio_id"]), a)
            except ApiHatasi as e:
                log(f"  müzik araması başarısız ({sorgu!r}): {e}")
        en_iyi, en_puan = None, 0.0
        for a in gorulen.values():
            p = muzik_puani(ad, sanatci, a.get("title", ""), a.get("display_artist", ""))
            if p > en_puan:
                en_iyi, en_puan = a, p
        if en_iyi and en_puan >= 0.80:
            log(f"  müzik bulundu: {en_iyi.get('title')} – {en_iyi.get('display_artist')} (puan {en_puan:.2f})")
            return en_iyi
        log(f"  müzik bulunamadı: {muzik} ({len(gorulen)} sonuç incelendi)")
        return None

    # ------------------------------------------------------------------ yükleme
    def konteyner_olustur(self, aciklama: str, kapak_ms: int | None, muzik_id: str | None,
                          muzik_ses: int, video_ses: int, ses_adi: str | None) -> dict:
        veri = {
            "media_type": "REELS",
            "upload_type": "resumable",
            "caption": aciklama,
            "share_to_feed": "true",
        }
        if kapak_ms is not None:
            veri["thumb_offset"] = str(int(kapak_ms))
        if muzik_id:
            veri["audio_configuration"] = json.dumps(
                {"audio_id": str(muzik_id), "audio_volume": int(muzik_ses), "video_volume": int(video_ses)})
        elif ses_adi:
            veri["audio_name"] = ses_adi
        return self._post(f"{self.ig_id}/media", **veri)

    def video_yukle(self, uri: str, video: Path) -> None:
        boyut = video.stat().st_size
        with open(video, "rb") as f:
            veri = f.read()
        istek("POST", uri, data=veri, headers={
            "Authorization": f"OAuth {self.token}",
            "offset": "0",
            "file_size": str(boyut),
            "Content-Type": "application/octet-stream",
        }, timeout=600)

    def islenmesini_bekle(self, konteyner_id: str, sure_sn: int = 900) -> dict:
        bitis = time.monotonic() + sure_sn
        son = {}
        while time.monotonic() < bitis:
            son = self._get(konteyner_id, fields="status_code,status")
            kod = son.get("status_code")
            if kod in ("FINISHED", "PUBLISHED"):
                return son
            if kod in ("ERROR", "EXPIRED"):
                raise ApiHatasi(f"Instagram videoyu işleyemedi: {son.get('status') or kod}", 400, son)
            time.sleep(10)
        raise ApiHatasi(f"Instagram işleme zaman aşımı (son durum: {son})")

    def hazirla(self, video: Path, aciklama: str, kapak_ms: int | None = None,
                muzik: dict | None = None, muzik_ses: int = 35, video_ses: int = 100,
                ses_adi: str | None = None) -> tuple[str, dict | None]:
        """Konteyneri oluşturup videoyu yükler ve işlenmesini bekler.

        Müzikle başarısız olursa bir kez müziksiz dener. (konteyner_id, kullanılan_müzik) döndürür."""
        denemeler = [muzik, None] if muzik else [None]
        son_hata: Exception | None = None
        for m in denemeler:
            try:
                k = self.konteyner_olustur(aciklama, kapak_ms, m and m.get("audio_id"),
                                           muzik_ses, video_ses, ses_adi)
                kid, uri = k["id"], k.get("uri")
                if not uri:
                    raise ApiHatasi(f"Instagram yükleme adresi vermedi: {k}")
                log(f"  konteyner {kid} oluşturuldu{' (müzikli)' if m else ''}; video yükleniyor…")
                self.video_yukle(uri, video)
                self.islenmesini_bekle(kid)
                log("  video işlendi")
                return kid, m
            except ApiHatasi as e:
                son_hata = e
                if m:
                    log(f"  müzikli hazırlık başarısız ({e}); müziksiz deneniyor")
                    continue
                raise
        assert son_hata is not None
        raise son_hata

    # ------------------------------------------------------------------ yayın
    def son_paylasimlar(self, adet: int = 6) -> list[dict]:
        v = self._get(f"{self.ig_id}/media", fields="id,caption,timestamp,permalink", limit=adet)
        return v.get("data", [])

    def zaten_paylasilmis(self, aciklama: str, saat: int = 12) -> dict | None:
        """Aynı açıklamayla son saatlerde paylaşılmış bir gönderi varsa döndürür."""
        ilk_satir = aciklama.strip().splitlines()[0].strip() if aciklama.strip() else ""
        if not ilk_satir:
            return None
        sinir = datetime.now(timezone.utc) - timedelta(hours=saat)
        for m in self.son_paylasimlar():
            try:
                zaman = datetime.strptime(m.get("timestamp", ""), "%Y-%m-%dT%H:%M:%S%z")
            except ValueError:
                continue
            if zaman >= sinir and (m.get("caption") or "").strip().startswith(ilk_satir):
                return m
        return None

    def yayinla(self, konteyner_id: str, aciklama: str) -> str:
        for deneme in range(4):
            try:
                return self._post(f"{self.ig_id}/media_publish", tekrar_dene=False, creation_id=konteyner_id)["id"]
            except ApiHatasi as e:
                log(f"  yayınlama hatası: {e}")
                # Yayınlanmış ama yanıt kaybolmuş olabilir: önce kontrol et.
                time.sleep(15)
                onceki = self.zaten_paylasilmis(aciklama, saat=1)
                if onceki:
                    log("  gönderi aslında yayınlanmış, tekrar paylaşılmıyor")
                    return onceki["id"]
                kod = e.govde.get("error", {}).get("code") if isinstance(e.govde, dict) else None
                # 9007: medya henüz hazır değil -> beklemeye değer
                if not e.gecici and kod != 9007 and deneme >= 1:
                    raise
                time.sleep(20 * (deneme + 1))
        raise ApiHatasi("Instagram'da yayınlama 4 denemede de başarısız oldu")

    def kalici_link(self, medya_id: str) -> str | None:
        try:
            return self._get(medya_id, fields="permalink").get("permalink")
        except ApiHatasi:
            return None

    def yorum_yaz(self, medya_id: str, mesaj: str) -> str | None:
        for deneme in range(4):
            try:
                time.sleep(5 if deneme == 0 else 20)
                return self._post(f"{medya_id}/comments", tekrar_dene=False, message=mesaj).get("id")
            except ApiHatasi as e:
                log(f"  yorum yazılamadı ({e})")
        return None

    # ------------------------------------------------------------------ istatistik
    REELS_METRIKLERI = ("views", "reach", "likes", "comments", "shares", "saved", "total_interactions",
                        "ig_reels_avg_watch_time", "ig_reels_video_view_total_time")

    def medya_istatistikleri(self, medya_id: str) -> dict:
        """Bir Reels gönderisinin metrikleri. Geçersiz metrik olursa tek tek dener."""
        sonuc: dict = {}
        try:
            alan = self._get(medya_id, fields="like_count,comments_count,timestamp,permalink")
            sonuc.update({k: alan[k] for k in ("like_count", "comments_count", "timestamp", "permalink") if k in alan})
        except ApiHatasi as e:
            sonuc["hata_alan"] = str(e)[:200]

        def oku(metrikler):
            v = self._get(f"{medya_id}/insights", metric=",".join(metrikler))
            for m in v.get("data", []):
                deger = (m.get("values") or [{}])[0].get("value", m.get("total_value", {}).get("value"))
                sonuc[m["name"]] = deger
        try:
            oku(self.REELS_METRIKLERI)
        except ApiHatasi:
            for m in self.REELS_METRIKLERI:
                try:
                    oku([m])
                except ApiHatasi:
                    pass
        return sonuc

    def paylasim_limiti(self) -> dict:
        v = self._get(f"{self.ig_id}/content_publishing_limit", fields="quota_usage,config")
        return (v.get("data") or [{}])[0]


def muzik_puani(istenen_ad: str, istenen_sanatci: str, ad: str, sanatci: str) -> float:
    """0–1 arası benzerlik. Sanatçı tutmazsa düşük puan; remix/cover gibi sürümler cezalı."""
    a1, a2 = sadelestir(istenen_ad), sadelestir(ad)
    s1, s2 = sadelestir(istenen_sanatci), sadelestir(sanatci)
    if not a1 or not a2:
        return 0.0
    ad_puan = difflib.SequenceMatcher(None, a1, a2).ratio()
    if a1 == a2 or a2.startswith(a1 + " ") or a1.startswith(a2 + " "):
        ad_puan = max(ad_puan, 0.95)
    if s1:
        sanatci_tutar = bool(s2) and (s1 in s2 or s2 in s1 or difflib.SequenceMatcher(None, s1, s2).ratio() >= 0.75)
    else:
        sanatci_tutar = True
    puan = ad_puan if sanatci_tutar else ad_puan * 0.5
    ham = (ad or "").lower()
    if any(k in ham for k in ISTENMEYEN) and not any(k in istenen_ad.lower() for k in ISTENMEYEN):
        puan *= 0.6
    return puan
