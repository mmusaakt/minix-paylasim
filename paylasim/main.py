"""minix otomatik paylaşım.

Kullanım:
  python -m paylasim paylas [--slot 2026-11-20-1230] [--platform hepsi|instagram|youtube] [--deneme] [--beklemeden]
  python -m paylasim kontrol
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
from datetime import timedelta

from . import ortak
from .ortak import (ApiHatasi, ERKEN_BASLAMA, GEC_KALMA_SINIRI, KOK, durum_oku, kaydet, log, ozet,
                    paylasildi_mi, simdi, slot_zamani, soru_eki, takvim_oku, tr_cumle)

PLATFORMLAR = ("instagram", "youtube")


# ---------------------------------------------------------------- platform ayarları

def acik_platformlar(istek: str = "hepsi") -> list[str]:
    var = []
    if os.environ.get("META_TOKEN"):
        var.append("instagram")
    if all(os.environ.get(a) for a in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN")):
        var.append("youtube")
    kisit = [p.strip() for p in os.environ.get("PLATFORMLAR", "").split(",") if p.strip()]
    if kisit:
        var = [p for p in var if p in kisit]
    if istek and istek != "hepsi":
        var = [p for p in var if p == istek]
    return var


def instagram_istemcisi():
    from .instagram import Instagram
    return Instagram(os.environ["META_TOKEN"], os.environ.get("IG_USER_ID") or None)


def youtube_istemcisi():
    from .youtube import YouTube
    return YouTube(os.environ["YT_CLIENT_ID"], os.environ["YT_CLIENT_SECRET"], os.environ["YT_REFRESH_TOKEN"])


# ---------------------------------------------------------------- metinler

def youtube_basligi(slot: dict) -> str:
    baslik = slot["baslik"].strip()
    parca = [p.strip() for p in re.split(r"\s*/\s*", slot.get("etiketler", "")) if p.strip()]
    if len(parca) == 2:
        sol, sag = tr_cumle(parca[0]), ortak.tr_kucuk(parca[1])
        soru = f"{sol} {soru_eki(sol.split()[-1])}, {sag} {soru_eki(sag.split()[-1])}?"
        tam = f"{baslik} {soru}"
        if len(tam) <= 100:
            return tam
    return baslik[:100]


def hashtagler(metin: str) -> list[str]:
    return [h.lstrip("#") for h in re.findall(r"#[\wçğıöşüÇĞİÖŞÜ]+", metin)]


def youtube_aciklamasi(slot: dict) -> str:
    return slot["aciklama"].rstrip() + " #Shorts"


def youtube_etiketleri(slot: dict) -> list[str]:
    e = hashtagler(slot["aciklama"]) + ["minix", "animasyon", "shorts"]
    return list(dict.fromkeys(e))


# ---------------------------------------------------------------- slot seçimi

def slot_sec(slotlar: list[dict], durum: dict, platformlar: list[str], slot_id: str | None) -> dict | None:
    if slot_id:
        for s in slotlar:
            if s["id"] == slot_id:
                return s
        ortak.hata_cik(f"Takvimde böyle bir slot yok: {slot_id}")
    an = simdi()
    adaylar = [s for s in slotlar
               if an - GEC_KALMA_SINIRI <= slot_zamani(s) <= an + ERKEN_BASLAMA
               and not all(paylasildi_mi(durum, s["id"], p) for p in platformlar)]
    if not adaylar:
        return None
    return max(adaylar, key=slot_zamani)  # en yakın (en son) slot; eskiler atlanır


def bekle(slot: dict) -> None:
    hedef = slot_zamani(slot)
    kalan = (hedef - simdi()).total_seconds()
    if kalan > 0:
        log(f"Paylaşım saati bekleniyor: {hedef:%H:%M} ({int(kalan)} sn)")
        time.sleep(kalan)


# ---------------------------------------------------------------- paylaş

def paylas(args) -> int:
    slotlar = takvim_oku()
    durum = durum_oku()
    platformlar = acik_platformlar(args.platform)
    if not platformlar:
        if os.environ.get("GITHUB_EVENT_NAME") == "schedule":
            # Kurulum bitmeden zamanlanmış çalışmalar hata e-postası göndermesin
            log("Henüz hiçbir platformun anahtarı girilmemiş; zamanlanmış paylaşım atlandı.")
            ozet("⏸️ Anahtarlar henüz girilmedi (Settings → Secrets and variables → Actions); paylaşım atlandı.")
            return 0
        ortak.hata_cik("Hiçbir platform ayarlı değil (GitHub sırları eksik).")
    slot = slot_sec(slotlar, durum, platformlar, args.slot or None)
    if not slot:
        log("Şu an paylaşılacak slot yok.")
        ozet("Şu an paylaşılacak slot yok.")
        return 0
    sid = slot["id"]
    video = KOK / slot["video"]
    if not video.exists():
        ortak.hata_cik(f"{sid}: video dosyası yok ({slot['video']})")
    deneme = args.deneme
    log(f"Slot {sid} · {slot['baslik']} · platformlar: {', '.join(platformlar)}{' · DENEME' if deneme else ''}")
    ozet(f"### {slot['tarih']} {slot['saat']} · {slot['baslik']}{' (deneme)' if deneme else ''}")
    hatalar = []
    beklenecek = not (args.beklemeden or args.slot or deneme)

    # --- Instagram: önce hazırla (yükle + işle), saat gelince yayınla
    if "instagram" in platformlar and (deneme or not paylasildi_mi(durum, sid, "instagram")):
        try:
            hatalar += instagram_paylas(slot, video, durum, deneme, beklenecek)
        except Exception as e:  # noqa: BLE001 – her hatayı rapora yaz, YouTube yine denensin
            hatalar.append(f"Instagram: {e}")
            if not deneme and not paylasildi_mi(durum, sid, "instagram"):
                kaydet(durum, sid, "instagram", {"durum": "hata", "hata": str(e)[:500],
                                                 "zaman": simdi().isoformat()})
    elif "instagram" in platformlar:
        log("Instagram: bu slot zaten paylaşılmış")

    # --- YouTube
    if "youtube" in platformlar and (deneme or not paylasildi_mi(durum, sid, "youtube")):
        try:
            if beklenecek:
                bekle(slot)
            yt = youtube_istemcisi()
            gizlilik = "private" if deneme else "public"
            vid = yt.yukle(video, youtube_basligi(slot), youtube_aciklamasi(slot), youtube_etiketleri(slot), gizlilik)
            link = f"https://youtube.com/shorts/{vid}"
            log(f"YouTube: yüklendi ({gizlilik}) {link}")
            ozet(f"- YouTube: [{link}]({link}){' — gizli deneme, Studio’dan silebilirsin' if deneme else ''}")
            if not deneme:
                kaydet(durum, sid, "youtube", {"durum": "paylasildi", "video_id": vid, "link": link,
                                               "zaman": simdi().isoformat()})
        except Exception as e:  # noqa: BLE001
            hatalar.append(f"YouTube: {e}")
            if not deneme:
                kaydet(durum, sid, "youtube", {"durum": "hata", "hata": str(e)[:500], "zaman": simdi().isoformat()})
    elif "youtube" in platformlar:
        log("YouTube: bu slot zaten paylaşılmış")

    for h in hatalar:
        log("HATA:", h)
        ozet(f"- ❌ {h}")
    return 1 if hatalar else 0


def instagram_paylas(slot: dict, video, durum: dict, deneme: bool, beklenecek: bool) -> list[str]:
    sid = slot["id"]
    ig = instagram_istemcisi()
    hesap = ig.hesap()
    log(f"Instagram: @{hesap.get('username')} hesabı")
    if not deneme:
        onceki = ig.zaten_paylasilmis(slot["aciklama"])
        if onceki:
            log("Instagram: aynı gönderi zaten paylaşılmış, atlanıyor")
            kaydet(durum, sid, "instagram", {"durum": "paylasildi", "medya_id": onceki["id"],
                                             "link": onceki.get("permalink"), "zaman": simdi().isoformat(),
                                             "not": "önceden paylaşılmış bulundu"})
            return []
    muzik = None
    if os.environ.get("MUZIK", "acik").lower() not in ("kapali", "kapalı", "0", "false", "hayir", "hayır"):
        muzik = ig.muzik_bul(slot.get("muzik", ""))
    kid, kullanilan = ig.hazirla(
        video, slot["aciklama"], slot.get("kapak_ms"), muzik,
        muzik_ses=int(os.environ.get("MUZIK_SES", "35")), video_ses=int(os.environ.get("VIDEO_SES", "100")),
        ses_adi=f"minix • {slot['baslik'].strip()}")
    muzik_metni = f"{kullanilan.get('title')} – {kullanilan.get('display_artist')}" if kullanilan else "yok"
    if deneme:
        log(f"Instagram (deneme): video hazırlandı, yayınlanmadı. Müzik: {muzik_metni}")
        ozet(f"- Instagram (deneme): video yüklendi ve işlendi, **yayınlanmadı**. Müzik: {muzik_metni}")
        return []
    if beklenecek:
        bekle(slot)
    medya_id = ig.yayinla(kid, slot["aciklama"])
    link = ig.kalici_link(medya_id)
    log(f"Instagram: yayınlandı {link or medya_id} · müzik: {muzik_metni}")
    bilgi = {"durum": "paylasildi", "medya_id": medya_id, "link": link, "muzik": muzik_metni,
             "zaman": simdi().isoformat()}
    kaydet(durum, sid, "instagram", bilgi)
    ozet(f"- Instagram: [{link or medya_id}]({link or ''}) · müzik: {muzik_metni}")
    hatalar = []
    if slot.get("sabitYorum"):
        yid = ig.yorum_yaz(medya_id, slot["sabitYorum"])
        if yid:
            bilgi["yorum_id"] = yid
            kaydet(durum, sid, "instagram", bilgi)
            ozet("- Instagram: ilk yorum yazıldı (sabitleme API'de yok)")
        else:
            hatalar.append("Instagram: gönderi paylaşıldı ama ilk yorum yazılamadı")
    return hatalar


# ---------------------------------------------------------------- kontrol

_GIT_DOSYALARI: set[str] | None = None


def video_var(yol: str) -> bool:
    """Dosya diskte ya da (seyrek checkout'ta) git'te kayıtlıysa True."""
    global _GIT_DOSYALARI
    if (KOK / yol).exists():
        return True
    if _GIT_DOSYALARI is None:
        import subprocess
        try:
            cikti = subprocess.run(["git", "ls-files"], cwd=KOK, capture_output=True, text=True, check=True).stdout
            _GIT_DOSYALARI = set(cikti.splitlines())
        except (OSError, subprocess.CalledProcessError):
            _GIT_DOSYALARI = set()
    return yol in _GIT_DOSYALARI


def kontrol(args) -> int:
    sorun = []
    slotlar = takvim_oku()
    durum = durum_oku()
    an = simdi()
    gelecek = [s for s in slotlar if slot_zamani(s) >= an - timedelta(minutes=30)]
    ozet("### Sıradaki paylaşımlar")
    ozet("| Zaman | Başlık | Video | Durum |")
    ozet("|---|---|---|---|")
    for s in gelecek[:6]:
        d = ", ".join(f"{p}: {durum.get(s['id'], {}).get(p, {}).get('durum', '-')}" for p in PLATFORMLAR)
        var = video_var(s["video"])
        ozet(f"| {s['tarih']} {s['saat']} | {s['baslik']} | {'✅' if var else '❌ yok'} | {d} |")
    eksik = [s["id"] for s in gelecek if not video_var(s["video"])]
    if eksik:
        sorun.append(f"{len(eksik)} slotun videosu eksik: {', '.join(eksik[:5])}")
    if gelecek:
        son = slot_zamani(gelecek[-1])
        kalan_gun = (son - an).total_seconds() / 86400
        ozet(f"\nTakvimdeki son paylaşım: {son:%d.%m.%Y %H:%M} ({kalan_gun:.1f} gün sonra)")
        if kalan_gun < 3:
            sorun.append("Takvimde 3 günden az paylaşım kaldı; yeni bölüm eklenmeli")
    else:
        sorun.append("Takvimde gelecek paylaşım kalmadı")

    platformlar = acik_platformlar()
    ozet(f"\nAçık platformlar: {', '.join(platformlar) or 'yok'}")
    if "instagram" in platformlar:
        try:
            ig = instagram_istemcisi()
            h = ig.hesap()
            ozet(f"- Instagram: @{h.get('username')} · {h.get('followers_count', '?')} takipçi")
            try:
                dbg = ig._get("debug_token", input_token=ig.token).get("data", {})
                bitis = dbg.get("expires_at")
                if bitis == 0:
                    ozet("- Meta anahtarı: süresiz ✅")
                elif bitis:
                    kalan = (bitis - time.time()) / 86400
                    ozet(f"- Meta anahtarı: {kalan:.0f} gün sonra bitiyor")
                    if kalan < 10:
                        sorun.append(f"Meta anahtarının süresi {kalan:.0f} gün içinde doluyor")
            except ApiHatasi:
                pass
            try:
                lim = ig.paylasim_limiti()
                ozet(f"- Instagram 24 saatlik paylaşım kullanımı: {lim.get('quota_usage', '?')}")
            except ApiHatasi:
                pass
            for s in gelecek[:3]:
                m = ig.muzik_bul(s.get("muzik", ""))
                isim = f"{m.get('title')} – {m.get('display_artist')}" if m else "bulunamadı (müziksiz paylaşılır)"
                ozet(f"- Müzik · {s['baslik']}: {isim}")
        except Exception as e:  # noqa: BLE001
            sorun.append(f"Instagram bağlantısı: {e}")
    if "youtube" in platformlar:
        try:
            yt = youtube_istemcisi()
            yt.erisim()
            k = yt.kanal()
            ozet(f"- YouTube: bağlantı tamam{(' · kanal: ' + k['ad']) if k else ''}")
        except Exception as e:  # noqa: BLE001
            sorun.append(f"YouTube bağlantısı: {e}")
    for s in sorun:
        ozet(f"- ❌ {s}")
        log("SORUN:", s)
    if not sorun:
        ozet("\n✅ Her şey yolunda.")
    return 1 if sorun else 0


# ---------------------------------------------------------------- kanal ayarları

def kanal(args) -> int:
    import json
    ayar = json.loads((KOK / "kanal" / "kanal.json").read_text(encoding="utf-8"))["youtube"]
    if "youtube" not in acik_platformlar():
        ortak.hata_cik("YouTube sırları eksik")
    yt = youtube_istemcisi()
    url = None
    if ayar.get("kapak") and not args.kapaksiz:
        url = yt.kapak_yukle(KOK / ayar["kapak"])
        log("Kanal kapağı yüklendi")
    yt.kanal_guncelle(ayar.get("aciklama"), ayar.get("anahtar_kelimeler"), url)
    log("Kanal açıklaması ve anahtar kelimeler güncellendi")
    ozet("✅ YouTube kanal kapağı, açıklaması ve anahtar kelimeleri güncellendi.")
    return 0


# ---------------------------------------------------------------- istatistik

def istatistik(args) -> int:
    import json
    durum = durum_oku()
    slotlar = {s["id"]: s for s in takvim_oku()}
    an = simdi()
    cikti = {"guncelleme": an.isoformat(timespec="minutes"), "hesap": {}, "slotlar": {}}
    sorun = []
    platformlar = acik_platformlar()
    if not platformlar:
        log("Anahtarlar henüz girilmedi; istatistik toplanmadı.")
        ozet("⏸️ Anahtarlar henüz girilmedi; istatistik toplanmadı.")
        return 0
    if "instagram" in platformlar:
        try:
            ig = instagram_istemcisi()
            h = ig.hesap()
            cikti["hesap"]["instagram"] = {k: h.get(k) for k in ("username", "followers_count", "media_count")}
            for sid, d in sorted(durum.items()):
                m = d.get("instagram", {})
                if m.get("durum") == "paylasildi" and m.get("medya_id"):
                    cikti["slotlar"].setdefault(sid, {})["instagram"] = ig.medya_istatistikleri(m["medya_id"])
        except Exception as e:  # noqa: BLE001
            sorun.append(f"Instagram istatistikleri: {e}")
    if "youtube" in platformlar:
        try:
            yt = youtube_istemcisi()
            idler = {d["youtube"]["video_id"]: sid for sid, d in durum.items()
                     if d.get("youtube", {}).get("durum") == "paylasildi" and d["youtube"].get("video_id")}
            if idler:
                for vid, st in yt.istatistikler(list(idler)).items():
                    cikti["slotlar"].setdefault(idler[vid], {})["youtube"] = st
                try:
                    ilk = min(durum[s]["youtube"]["zaman"][:10] for s in idler.values())
                    for vid, an_ in yt.analitik(list(idler), ilk, an.date().isoformat()).items():
                        cikti["slotlar"].setdefault(idler[vid], {}).setdefault("youtube", {}).update(an_)
                except Exception as e:  # noqa: BLE001 – analitik izni yoksa sadece temel sayılar
                    log(f"YouTube Analytics okunamadı: {e}")
            k = yt.kanal()
            if k:
                cikti["hesap"]["youtube"] = k
        except Exception as e:  # noqa: BLE001
            sorun.append(f"YouTube istatistikleri: {e}")
    for sid, v in cikti["slotlar"].items():
        s = slotlar.get(sid, {})
        v["baslik"], v["konu"], v["saat"] = s.get("baslik"), s.get("konu"), s.get("saat")
    klasor = KOK / "istatistik"
    (klasor / "gunluk").mkdir(parents=True, exist_ok=True)
    metin = json.dumps(cikti, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    (klasor / "son.json").write_text(metin, encoding="utf-8")
    (klasor / "gunluk" / f"{an.date().isoformat()}.json").write_text(metin, encoding="utf-8")
    ozet(f"İstatistik: {len(cikti['slotlar'])} gönderi güncellendi.")
    for s in sorun:
        ozet(f"- ❌ {s}")
        log("SORUN:", s)
    return 1 if sorun else 0


def ana(argv=None) -> int:
    p = argparse.ArgumentParser(prog="paylasim")
    alt = p.add_subparsers(dest="komut", required=True)
    pp = alt.add_parser("paylas")
    pp.add_argument("--slot", default="")
    pp.add_argument("--platform", default="hepsi", choices=["hepsi", *PLATFORMLAR])
    pp.add_argument("--deneme", action="store_true")
    pp.add_argument("--beklemeden", action="store_true")
    alt.add_parser("kontrol")
    pk = alt.add_parser("kanal")
    pk.add_argument("--kapaksiz", action="store_true")
    alt.add_parser("istatistik")
    args = p.parse_args(argv)
    return {"paylas": paylas, "kontrol": kontrol, "kanal": kanal, "istatistik": istatistik}[args.komut](args)


if __name__ == "__main__":
    sys.exit(ana())
