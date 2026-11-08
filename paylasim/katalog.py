"""Instagram müzik kütüphanesini tarar.

Instagram API'si yalnızca üçüncü taraf kullanımına lisanslı parçaları döndürür. Bu modül
muzik/sorgular.json'daki her arama için sonuçları toplar, isteğe bağlı olarak her parçanın
geçici önizlemesinden ses özelliklerini (tempo, ton, enerji, parlaklık, vurmalı oranı) çıkarır
ve muzik/katalog.json'a yazar. Ses dosyası saklanmaz.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone

from .ortak import KOK, ApiHatasi, istek, log, ozet

SORGULAR = KOK / "muzik" / "sorgular.json"
KATALOG = KOK / "muzik" / "katalog.json"
NOTALAR = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
# Krumhansl–Kessler ton profilleri
MAJOR = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
MINOR = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]


def ozellikler(url: str) -> dict:
    """Önizlemeden ses özellikleri. Kütüphaneler sadece katalog işinde kurulur."""
    import numpy as np
    import librosa

    with tempfile.NamedTemporaryFile(suffix=".m4a") as f:
        f.write(istek("GET", url, deneme=2, timeout=60).content)
        f.flush()
        y, sr = librosa.load(f.name, sr=22050, mono=True, duration=60)
    if y.size < sr * 3:
        return {}
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    tempo = float(np.atleast_1d(tempo)[0])
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr).mean(axis=1)
    en_iyi = (-2.0, "", "")
    for i in range(12):
        for profil, mod in ((MAJOR, "major"), (MINOR, "minor")):
            r = float(np.corrcoef(chroma, np.roll(profil, i))[0, 1])
            if r > en_iyi[0]:
                en_iyi = (r, NOTALAR[i], mod)
    rms = librosa.feature.rms(y=y)[0]
    harm, perk = librosa.effects.hpss(y)
    onset = librosa.onset.onset_detect(y=y, sr=sr)
    return {
        "tempo": round(tempo, 1),
        "ton": f"{en_iyi[1]} {en_iyi[2]}", "ton_guven": round(en_iyi[0], 2),
        "enerji_db": round(float(20 * np.log10(np.mean(rms) + 1e-9)), 1),
        "dinamik_db": round(float(20 * np.log10((np.percentile(rms, 95) + 1e-9) / (np.percentile(rms, 20) + 1e-9))), 1),
        "parlaklik_hz": int(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr))),
        "vurmali_oran": round(float(np.sum(perk ** 2) / (np.sum(y ** 2) + 1e-9)), 2),
        "nota_yogunlugu": round(len(onset) / (len(y) / sr), 2),
        "onizleme_sn": round(len(y) / sr, 1),
    }


def katalog_olustur() -> int:
    from .main import instagram_istemcisi

    ig = instagram_istemcisi()
    ig.hesap()
    sorgular = json.loads(SORGULAR.read_text(encoding="utf-8"))
    eski = json.loads(KATALOG.read_text(encoding="utf-8")) if KATALOG.exists() else {"parcalar": {}}
    parcalar: dict = eski.get("parcalar", {})
    for p in parcalar.values():
        p["sorgular"] = []
    onizleme: dict[str, str] = {}
    for sorgu in sorgular:
        try:
            sonuc = ig.muzik_ara(sorgu, sayfa=3)
        except ApiHatasi as e:
            log(f"  '{sorgu}': hata {e}")
            continue
        log(f"  '{sorgu or '(trend)'}': {len(sonuc)} parça")
        for a in sonuc:
            aid = str(a.get("audio_id") or "")
            if not aid:
                continue
            p = parcalar.setdefault(aid, {"baslik": a.get("title"), "sanatci": a.get("display_artist")})
            p["baslik"], p["sanatci"] = a.get("title"), a.get("display_artist")
            if a.get("duration_in_ms"):
                p["sure_sn"] = round(a["duration_in_ms"] / 1000)
            p["reklam_uygun"] = a.get("is_ads_eligible")
            p.setdefault("sorgular", []).append(sorgu or "(trend)")
            if a.get("download_url"):
                onizleme[aid] = a["download_url"]
    if os.environ.get("ANALIZ", "true") == "true":
        try:
            import librosa  # noqa: F401
            analiz = True
        except ImportError:
            log("librosa yok; ses özellikleri çıkarılmadı")
            analiz = False
        if analiz:
            for i, (aid, url) in enumerate(onizleme.items(), 1):
                if parcalar[aid].get("ozellik"):
                    continue
                try:
                    parcalar[aid]["ozellik"] = ozellikler(url)
                except Exception as e:  # noqa: BLE001
                    log(f"  analiz edilemedi {aid}: {e}")
                if i % 25 == 0:
                    log(f"  {i}/{len(onizleme)} önizleme incelendi")
    parcalar = {k: v for k, v in parcalar.items() if v.get("sorgular")}
    KATALOG.write_text(json.dumps({"guncelleme": datetime.now(timezone.utc).isoformat(timespec="minutes"),
                                   "sorgu_sayisi": len(sorgular), "parcalar": parcalar},
                                  ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    analizli = sum(1 for p in parcalar.values() if p.get("ozellik"))
    ozet(f"🎵 Katalog: {len(parcalar)} parça, {analizli} tanesinin ses özellikleri çıkarıldı.")
    return 0
