"""Instagram'da lisanslı müziğin hangi yükleme yöntemiyle eklenebildiğini dener.

Hiçbir şey yayınlanmaz: her deneme için bir Reels konteyneri oluşturulur, video yüklenir ya da
Instagram'ın indirmesi için adres verilir, işlenip işlenmediğine bakılır. Yayınlanmayan
konteynerler Instagram'da kendiliğinden silinir.
"""
from __future__ import annotations

import json
import time

from .ortak import ApiHatasi, KOK, log, ozet, takvim_oku


def _bekle(ig, kid: str, sure_sn: int = 420) -> dict:
    bitis = time.monotonic() + sure_sn
    son: dict = {}
    while time.monotonic() < bitis:
        son = ig._get(kid, fields="status_code,status")
        if son.get("status_code") in ("FINISHED", "PUBLISHED", "ERROR", "EXPIRED"):
            return son
        time.sleep(8)
    return son


def muzik_testi(slot_id: str, muzik_id: str | None = None) -> int:
    from .main import instagram_istemcisi

    ig = instagram_istemcisi()
    ig.hesap()
    slot = next(s for s in takvim_oku() if s["id"] == slot_id)
    video = KOK / slot["video"]
    aid = str(muzik_id or slot.get("muzik_id") or "")
    trend = ig.muzik_ara("")
    trend_id = str(trend[0]["audio_id"]) if trend else ""
    log(f"Parça: {aid} · trend parça: {trend_id}")
    tam = {"audio_id": aid, "audio_volume": 40, "video_volume": 70}
    kapak = slot.get("kapak_ms")
    gercek = slot["aciklama"]
    # (ad, yöntem, adres, ses ayarı, kapak karesi ms, açıklama)
    varyantlar = [
        ("ses 40/70 · kapak son kare · gerçek açıklama (paylaşımın aynısı)", "resumable", None, tam, kapak, gercek),
        ("ses 40/70 · kapak son kare · kısa açıklama", "resumable", None, tam, kapak, "deneme"),
        ("ses 40/70 · kapak yok · gerçek açıklama", "resumable", None, tam, None, gercek),
        ("ses 40/70 · kapak son kareden 1 sn önce · gerçek açıklama", "resumable", None, tam,
         (kapak - 1000) if kapak else None, gercek),
        ("yalnız audio_id · kapak son kare · gerçek açıklama", "resumable", None, {"audio_id": aid}, kapak, gercek),
    ]
    sonuclar = []
    for ad, yontem, adres, ses, kapak_ms, aciklama in varyantlar:
        veri = {"media_type": "REELS", "caption": aciklama, "share_to_feed": "true"}
        if yontem == "resumable":
            veri["upload_type"] = "resumable"
        else:
            veri["video_url"] = adres
        if kapak_ms is not None:
            veri["thumb_offset"] = str(int(kapak_ms))
        if ses:
            veri["audio_configuration"] = json.dumps(ses)
        sonuc = "?"
        try:
            k = ig._post(f"{ig.ig_id}/media", **veri)
            kid = k["id"]
            if yontem == "resumable":
                ig.video_yukle(k["uri"], video)
            durum = _bekle(ig, kid)
            sonuc = f"{durum.get('status_code')} {durum.get('status') or ''}".strip()
        except ApiHatasi as e:
            sonuc = f"HATA {e}"
        except Exception as e:  # noqa: BLE001
            sonuc = f"HATA {type(e).__name__}: {e}"
        log(f"[test] {ad}: {sonuc}")
        sonuclar.append((ad, sonuc))
    ozet("### Müzik testi (hiçbiri yayınlanmadı)")
    for ad, sonuc in sonuclar:
        ozet(f"- {'✅' if sonuc.startswith('FINISHED') else '❌'} {ad}: {sonuc}")
    return 0
