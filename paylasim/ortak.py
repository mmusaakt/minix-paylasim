"""Ortak yardımcılar: ayarlar, takvim, durum dosyası, zaman, HTTP ve Türkçe metin."""
from __future__ import annotations

import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

KOK = Path(__file__).resolve().parent.parent
TAKVIM_DOSYASI = KOK / "takvim.json"
DURUM_DOSYASI = KOK / "durum.json"
ISTANBUL = ZoneInfo("Europe/Istanbul")

# Planlı çalışmada bir slot en fazla bu kadar gecikmeyle paylaşılır; daha eskisi atlanır.
GEC_KALMA_SINIRI = timedelta(hours=3)
# Planlı çalışma slottan en fazla bu kadar önce başlarsa slotu bekler; daha erken başlayan hemen çıkar.
# (Paylaş işi slot çevresinde 10 dakikada bir tetiklenir, çünkü GitHub'ın zamanlayıcısı 45–60 dk gecikebiliyor.)
ERKEN_BASLAMA = timedelta(minutes=12)


def log(*parca) -> None:
    print(*parca, flush=True)


def ozet(satir: str) -> None:
    """GitHub Actions çalışma özetine bir satır ekler (yerelde sadece yazdırır)."""
    yol = os.environ.get("GITHUB_STEP_SUMMARY")
    if yol:
        with open(yol, "a", encoding="utf-8") as f:
            f.write(satir + "\n")
    else:
        log("[özet]", satir)


def simdi() -> datetime:
    sahte = os.environ.get("MINIX_SIMDI")  # testler için: "2026-11-20T12:25"
    if sahte:
        return datetime.fromisoformat(sahte).replace(tzinfo=ISTANBUL)
    return datetime.now(ISTANBUL)


def slot_zamani(slot: dict) -> datetime:
    return datetime.fromisoformat(f"{slot['tarih']}T{slot['saat']}").replace(tzinfo=ISTANBUL)


# ---------------------------------------------------------------- takvim / durum

def takvim_oku() -> list[dict]:
    with open(TAKVIM_DOSYASI, encoding="utf-8") as f:
        veri = json.load(f)
    slotlar = veri["slotlar"] if isinstance(veri, dict) else veri
    return sorted(slotlar, key=lambda s: (s["tarih"], s["saat"]))


def durum_oku() -> dict:
    if DURUM_DOSYASI.exists():
        with open(DURUM_DOSYASI, encoding="utf-8") as f:
            return json.load(f)
    return {}


def durum_yaz(durum: dict) -> None:
    tmp = DURUM_DOSYASI.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(durum, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    tmp.replace(DURUM_DOSYASI)


def kaydet(durum: dict, slot_id: str, platform: str, bilgi: dict) -> None:
    """Bir platformun sonucunu hemen diske yazar (çökme olursa tekrar paylaşmamak için)."""
    durum.setdefault(slot_id, {})[platform] = bilgi
    durum_yaz(durum)


def paylasildi_mi(durum: dict, slot_id: str, platform: str) -> bool:
    return durum.get(slot_id, {}).get(platform, {}).get("durum") == "paylasildi"


# ---------------------------------------------------------------- HTTP

class ApiHatasi(Exception):
    def __init__(self, mesaj: str, durum_kodu: int | None = None, govde=None):
        super().__init__(mesaj)
        self.durum_kodu = durum_kodu
        self.govde = govde

    @property
    def gecici(self) -> bool:
        """Tekrar denemeye değer bir hata mı?"""
        if self.durum_kodu is None or self.durum_kodu >= 500 or self.durum_kodu == 429:
            return True
        hata = (self.govde or {}).get("error", {}) if isinstance(self.govde, dict) else {}
        if hata.get("is_transient"):
            return True
        return hata.get("code") in (1, 2, 4, 17, 32, 341, 613)


def istek(yontem: str, url: str, *, deneme: int = 4, bekleme: float = 5.0,
          tekrar_dene: bool = True, **kw) -> requests.Response:
    """Zaman aşımı ve geçici hatalarda tekrar deneyen basit HTTP isteği."""
    kw.setdefault("timeout", 120)
    son_hata: Exception | None = None
    for i in range(deneme if tekrar_dene else 1):
        try:
            r = requests.request(yontem, url, **kw)
        except requests.RequestException as e:  # ağ hatası
            son_hata = ApiHatasi(f"Ağ hatası: {e}")
        else:
            if r.status_code < 400:
                return r
            try:
                govde = r.json()
            except ValueError:
                govde = r.text[:500]
            son_hata = ApiHatasi(f"HTTP {r.status_code}: {hata_metni(govde)}", r.status_code, govde)
            if not son_hata.gecici:
                raise son_hata
        if i + 1 < deneme and tekrar_dene:
            time.sleep(bekleme * (2 ** i))
    assert son_hata is not None
    raise son_hata


def hata_metni(govde) -> str:
    if isinstance(govde, dict):
        h = govde.get("error")
        if isinstance(h, dict):
            parca = [str(h.get("message", "")), f"(kod {h.get('code')}"]
            if h.get("error_subcode"):
                parca[-1] += f", alt kod {h.get('error_subcode')}"
            parca[-1] += ")"
            if h.get("error_user_msg"):
                parca.append("– " + str(h["error_user_msg"]))
            return " ".join(p for p in parca if p)
        if isinstance(h, str):
            return h + " " + str(govde.get("error_description", ""))
    return str(govde)[:500]


# ---------------------------------------------------------------- Türkçe metin

def tr_kucuk(s: str) -> str:
    return s.replace("I", "ı").replace("İ", "i").lower()


def tr_cumle(s: str) -> str:
    """'YARDIM İSTEYEN' -> 'Yardım isteyen'."""
    k = tr_kucuk(s.strip())
    if not k:
        return k
    ilk = k[0]
    ilk = {"i": "İ", "ı": "I"}.get(ilk, ilk.upper())
    return ilk + k[1:]


def soru_eki(kelime: str) -> str:
    """Büyük ünlü uyumuna göre soru eki: mı / mi / mu / mü."""
    for h in reversed(tr_kucuk(kelime)):
        if h in "aı":
            return "mı"
        if h in "ei":
            return "mi"
        if h in "ou":
            return "mu"
        if h in "öü":
            return "mü"
    return "mi"


def sadelestir(s: str) -> str:
    """Müzik eşleştirme için: aksanları, parantezleri ve noktalamayı at."""
    s = re.sub(r"[\(\[].*?[\)\]]", " ", s)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9ğüşöçı ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def gerekli_ortam(*adlar: str) -> dict[str, str]:
    eksik = [a for a in adlar if not os.environ.get(a)]
    if eksik:
        raise SystemExit("Eksik GitHub sırrı: " + ", ".join(eksik))
    return {a: os.environ[a] for a in adlar}


def hata_cik(mesaj: str) -> None:
    log("HATA:", mesaj)
    ozet(f"❌ {mesaj}")
    sys.exit(1)
