"""TikTok paketi: sıradaki 10 slotun videoları + açıklamaları (TikTok Studio'da elle planlamak için).

TikTok kişisel otomatik paylaşıma izin vermediği için videolar TikTok Studio'dan 10 gün ileriye
kadar planlanır. Paket, önceki paketin son paylaşımına 2 günden az kalınca hazırlanır.
"""
from __future__ import annotations

import json
import os
import zipfile
from datetime import timedelta

from .ortak import KOK, log, ozet, simdi, slot_zamani, takvim_oku

DURUM = KOK / "tiktok.json"
PAKET_BOYU = 10
ONCEDEN = timedelta(days=2)
AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim",
         "Kasım", "Aralık"]


def tarih_metni(slot: dict) -> str:
    z = slot_zamani(slot)
    return f"{z.day} {AYLAR[z.month - 1]} {z:%H:%M}"


def durum_oku() -> dict:
    return json.loads(DURUM.read_text(encoding="utf-8")) if DURUM.exists() else {"paketler": []}


def paket_hazirla(zorla: bool = False, cikti_klasoru=None) -> dict | None:
    """Gerekirse yeni paketi hazırlar; bilgi sözlüğü döndürür ya da None."""
    slotlar = takvim_oku()
    durum = durum_oku()
    an = simdi()
    son = durum.get("son_slot")
    if son and not zorla:
        son_slot = next((s for s in slotlar if s["id"] == son), None)
        if son_slot and slot_zamani(son_slot) - an > ONCEDEN:
            log(f"Önceki paket {tarih_metni(son_slot)} tarihine kadar yetiyor; yeni paket gerekmiyor.")
            return None
    sonraki = [s for s in slotlar if (s["id"] > son if son else slot_zamani(s) > an + timedelta(hours=2))]
    # Geçmişte kalan slotları atla (paket geç kaldıysa)
    sonraki = [s for s in sonraki if slot_zamani(s) > an + timedelta(minutes=30)][:PAKET_BOYU]
    if not sonraki:
        log("Takvimde TikTok için yeni slot yok.")
        return None
    ilk, sonuncu = sonraki[0], sonraki[-1]
    klasor = cikti_klasoru or (KOK / "dist")
    os.makedirs(klasor, exist_ok=True)
    zip_yolu = os.path.join(klasor, f"tiktok_{ilk['id']}.zip")
    satirlar = [f"minix TikTok paketi: {tarih_metni(ilk)} – {tarih_metni(sonuncu)}", "",
                "Her videoyu TikTok Studio'da (bilgisayardan) yazan saate planla, açıklamayı yapıştır.", ""]
    md = [f"**{len(sonraki)} video:** {tarih_metni(ilk)} – {tarih_metni(sonuncu)}. "
          "Zip'i bu sayfanın altındaki bağlantıdan indir; her videoyu TikTok Studio'da yazan saate planla, "
          "açıklamayı kutunun sağ üstündeki kopyala düğmesiyle al.", ""]
    with zipfile.ZipFile(zip_yolu, "w", compression=zipfile.ZIP_STORED) as z:
        for i, s in enumerate(sonraki, 1):
            ad = f"{i:02d}_{s['tarih']}_{s['saat'].replace(':', '')}_{s['slug']}.mp4"
            z.write(KOK / s["video"], ad)
            satirlar += [f"{i:02d}) {tarih_metni(s)} · {s['baslik']} · dosya: {ad}", "", s["aciklama"].strip(), "",
                         "-" * 40, ""]
            md += [f"### {i}. {tarih_metni(s)} · {s['baslik']}", f"Dosya: `{ad}`", "", "```text",
                   s["aciklama"].strip(), "```", ""]
        z.writestr("aciklamalar.txt", "\n".join(satirlar))
    md_yolu = os.path.join(klasor, f"tiktok_{ilk['id']}.md")
    with open(md_yolu, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    bilgi = {"ilk": ilk["id"], "son": sonuncu["id"], "adet": len(sonraki), "zip": zip_yolu, "md": md_yolu,
             "baslik": f"TikTok paketi: {tarih_metni(ilk)} – {tarih_metni(sonuncu)}",
             "etiket": f"tiktok-{ilk['id']}", "olusturma": an.isoformat(timespec="minutes")}
    durum["son_slot"] = sonuncu["id"]
    durum.setdefault("paketler", []).append({k: bilgi[k] for k in ("ilk", "son", "adet", "olusturma")})
    DURUM.write_text(json.dumps(durum, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    log(f"Paket hazır: {bilgi['baslik']} ({len(sonraki)} video) -> {zip_yolu}")
    ozet(f"📦 {bilgi['baslik']}")
    cikti = os.environ.get("GITHUB_OUTPUT")
    if cikti:
        with open(cikti, "a", encoding="utf-8") as f:
            for k in ("zip", "md", "baslik", "etiket"):
                f.write(f"{k}={bilgi[k]}\n")
    return bilgi
