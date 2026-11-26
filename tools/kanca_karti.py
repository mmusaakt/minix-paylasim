"""İlk saniye kancası + son replik kartı: orijinal videodan tek geçişte videolar/<slug>-rk.mp4.

12 madde kontrol listesinin iki açığı için (27 Kasım 2026):
  - İlk saniye hook'u ve merak: ilk karede, sonu videoda cevaplanan büyük bir soru.
  - Tartışma payı: açıklamada kapanış sorusunun hemen önüne itiraz edilebilir bir cümle.

Kullanım:
  python tools/kanca_karti.py --uygula [--ilk SLOT]
      tools/kanca_tartisma.json'daki metinleri slotlara yazar: "kanca", "tartisma" alanları ve
      açıklamada kapanış sorusunun (👇 ile biten paragraf) önüne tartışma cümlesi. İlk satır değişmez.
  python tools/kanca_karti.py --onizle [--ilk SLOT] [--son SLOT] cikti_klasoru
      Her slotun ilk karesini kancayla, son karesini kartla PNG olarak çizer (hızlı göz kontrolü).
  python tools/kanca_karti.py --takvim [--ilk SLOT] [--son SLOT] [--kuru]
      Orijinal videodan (videolar/<slug>.mp4) iki kartlı videolar/<slug>-rk.mp4 üretir, slotun
      "video" alanını çevirir ve "deneme": "kanca+replik_karti" yazar. Var olan -rk dosyası
      yeniden basılmaz (--yeniden ile basılır).

Kanca kartı: InterDisplay Bold 64/58/52/48 px, en fazla 2 satır ("\\n" satırı böler), ilk kareden
görünür; yazı 2,35–2,6 sn'de, kutu 2,6–2,9 sn'de söner (örtülen başlık yazıyla üst üste binmez).
Yer sırası (önce 64/58 px'te, sığmazsa 52/48 px'te):
  1. başlık ile etiketlerin arasındaki boşluk (yarı saydam kutu; hiçbir şeyi örtmez),
  2. başlığın üstü (y=236'dan etiketlere kadar; başlığı 3 sn örter, koyu zemin),
  3. etiket satırını örter (sahneye taşmaz, koyu zemin),
  4. başlık + etiketler (son çare).
Replik kartı tools/replik_karti.py ile birebir aynı (aynı yer, aynı boy, son 3,2 sn).
"""
import json, os, subprocess, sys, tempfile
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import replik_karti as rk  # noqa: E402

W, H = rk.W, rk.H
KANCA_FONT = rk.INTER + "InterDisplay-Bold.otf"
KANCA_BOYLAR = (64, 58, 52, 48)
UST_EN_AZ = 236          # Reels/Shorts üst arayüzünün altı
YAZI_SON, YAZI_SONME = 2.35, 0.25   # kanca yazısı 2,35 sn'de sönmeye başlar, 2,6'da biter
KUTU_SON, KUTU_SONME = 2.6, 0.3     # kutu yazıdan sonra söner, 2,9'da biter
GENISLIK = 900


def satirla(metin, font, c):
    if "\n" in metin:
        return [s.strip() for s in metin.split("\n") if s.strip()]
    return rk.sar(metin, font, GENISLIK, c)


def kanca_olcu(metin, boylar=KANCA_BOYLAR):
    """(boy, satırlar, kutu_yüksekliği): her satırı 900 px'e sığan en büyük boy."""
    c = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    for boy in boylar:
        f = ImageFont.truetype(KANCA_FONT, boy)
        s = satirla(metin, f, c)
        if len(s) <= 2 and all(c.textlength(x, font=f) <= GENISLIK for x in s):
            ara = round(boy * 1.22)
            return boy, s, 46 + (len(s) - 1) * ara + boy + 46
    raise ValueError(f"Kanca 2 satıra sığmıyor, kısaltılmalı: {metin!r}")


def kanca_png(metin, yol, ust, alt=None, alfa=150, boylar=KANCA_BOYLAR, yazi_yol=None):
    """yazi_yol verilirse kutu `yol`a, yazı ayrı katman olarak `yazi_yol`a yazılır (ayrı sönsünler diye)."""
    boy, satirlar, h = kanca_olcu(metin, boylar)
    f = ImageFont.truetype(KANCA_FONT, boy)
    ara = round(boy * 1.22)
    alt = max(alt or 0, ust + h)
    y0 = ust + (alt - ust - h) // 2 + 46
    zemin = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(zemin).rounded_rectangle((60, ust, W - 60, alt), radius=36, fill=(0, 0, 0, alfa))
    yazi = Image.new("RGBA", (W, H), (255, 255, 255, 0))  # beyaz-saydam zemin: kenar yumuşatması kararmaz
    c = ImageDraw.Draw(yazi)
    for i, s in enumerate(satirlar):
        w = c.textlength(s, font=f)
        # harflerin üst boşluğunu dengelemek için yazının görünen kutusuna göre ortala
        c.text(((W - w) / 2, y0 + i * ara - round(boy * 0.08)), s, font=f, fill=(255, 255, 255, 255))
    if yazi_yol:
        zemin.save(yol)
        yazi.save(yazi_yol)
    else:
        Image.alpha_composite(zemin, yazi).save(yol)


def kanca_bantlar(video):
    a = None
    for t in (0.0, 0.7, 1.4, 2.1, 2.8):
        k = rk.kare(video, t)
        a = k if a is None else np.maximum(a, k)
    med = np.median(a, axis=1, keepdims=True)
    sayi = ((a - med) > 60).sum(axis=1)
    satir = sayi > 3
    out, bas_ = [], None
    for y in range(150, 1400):
        if satir[y] and bas_ is None:
            bas_ = y
        if not satir[y] and bas_ is not None:
            if out and bas_ - out[-1][1] <= 12:
                out[-1] = (out[-1][0], y)
            else:
                out.append((bas_, y))
            bas_ = None
    # Yıldız, toz gibi küçük parıltılar bant sayılmaz: bandın parlak piksel alanı en az 300 olmalı
    return [(u, l) for u, l in out if sayi[u:l].sum() >= 300]


def kanca_yerlesim(video, metin):
    """(tür, üst, alt, alfa, boylar)."""
    b = kanca_bantlar(video)
    baslik = [x for x in b if x[0] < 410]
    ust_sinir = (baslik[-1][1] if baslik else 330) + 22
    alt = [x for x in b if x[0] >= max(410, ust_sinir)]
    etiket = alt[0][0] if alt else 1400
    etiket_alt = alt[0][1] if alt else ust_sinir
    sahne = alt[1][0] if len(alt) > 1 else 1400

    def yer(tur, boy):
        try:
            _, _, h = kanca_olcu(metin, (boy,))
        except ValueError:
            return None
        if tur == "bosluk" and ust_sinir + h <= etiket - 15:   # başlık ile etiketler arası, ortada
            return ust_sinir + ((etiket - 15) - ust_sinir - h) // 2, None, 150
        if tur == "baslik" and UST_EN_AZ + h <= etiket - 15:   # başlığı örter
            return UST_EN_AZ, etiket - 15, 255
        if tur == "etiket":                                     # etiket satırını örter
            kutu_alt = max(ust_sinir + h, etiket_alt + 16)
            if kutu_alt <= sahne - 12:
                return ust_sinir, kutu_alt, 255
        if tur == "hepsi":                                      # başlık + etiketler
            kutu_alt = max(UST_EN_AZ + h, etiket_alt + 16)
            if kutu_alt <= sahne - 12:
                return UST_EN_AZ, kutu_alt, 255
        return None

    # Yazı önce 64/58 px'te her yer sırasıyla denenir; hiçbir yere sığmazsa 52/48 px'te.
    for kademe in ((64, 58), (52, 48)):
        for tur in ("bosluk", "baslik", "etiket", "hepsi"):
            for boy in kademe:
                y = yer(tur, boy)
                if y:
                    return (tur, *y, (boy,))
    _, _, h = kanca_olcu(metin, (48,))
    return "zorunlu", UST_EN_AZ, UST_EN_AZ + h, 255, (48,)


def orijinal(video):
    for ek in ("-rk.mp4", "-r.mp4"):
        if video.endswith(ek):
            return video[: -len(ek)] + ".mp4"
    return video


def planla(slot):
    gir = orijinal(slot["video"])
    kanca = slot["kanca"]
    replik = slot.get("replik") or slot["aciklama"].split("\n")[0].strip()
    sure = rk.sure_of(gir)
    bas = round(sure - 3.2, 2)
    k = kanca_yerlesim(gir, kanca)
    r = rk.yerlesim(gir, replik, bas, sure)
    return gir, kanca, replik, sure, bas, k, r


def bas2(gir, cik, kanca, k, replik, bas, r):
    """Önce yazı söner (2,35–2,6 sn), sonra kutu (2,6–2,9 sn): örten kutunun altındaki başlık ya da
    etiketler yazıyla üst üste binmeden ortaya çıkar."""
    d = tempfile.mkdtemp()
    kp = os.path.join(d, "kanca_kutu.png")
    yp = os.path.join(d, "kanca_yazi.png")
    rp = os.path.join(d, "kart.png")
    _, kust, kalt, kalfa, kboy = k
    kanca_png(kanca, kp, kust, kalt, kalfa, kboy, yazi_yol=yp)
    _, rust, ralfa, ralt, rboy = r
    rk.kart(replik, rp, rust, ralfa, ralt, rboy)
    filtre = (f"[1:v]format=rgba,fade=out:st={YAZI_SON}:d={YAZI_SONME}:alpha=1[ky];"
              f"[2:v]format=rgba,fade=out:st={KUTU_SON}:d={KUTU_SONME}:alpha=1[kz];"
              f"[3:v]format=rgba,fade=in:st={bas}:d=0.4:alpha=1[k];"
              f"[0:v][kz]overlay=0:0:shortest=1:format=auto[a];"
              f"[a][ky]overlay=0:0:shortest=1:format=auto[b];"
              f"[b][k]overlay=0:0:shortest=1:format=auto,format=yuv420p[v]")
    gecici = cik + ".tmp.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", gir,
                    "-framerate", "30", "-loop", "1", "-i", yp,
                    "-framerate", "30", "-loop", "1", "-i", kp,
                    "-framerate", "30", "-loop", "1", "-i", rp,
                    "-filter_complex", filtre, "-map", "[v]", "-map", "0:a?",
                    "-c:v", "libx264", "-crf", "18", "-preset", "slow", "-profile:v", "high", "-r", "30",
                    "-c:a", "copy", "-movflags", "+faststart", gecici], check=True)
    os.replace(gecici, cik)


def onizle_kare(video, t, png_yol):
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", video, "-frames:v", "1",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    im = Image.frombytes("RGB", (W, H), raw).convert("RGBA")
    im.alpha_composite(Image.open(png_yol).convert("RGBA"))
    return im.convert("RGB")


def slotlar(argv):
    ilk = argv[argv.index("--ilk") + 1] if "--ilk" in argv else "2026-11-27-1230"
    son = argv[argv.index("--son") + 1] if "--son" in argv else "9999"
    veri = json.load(open("takvim.json", encoding="utf-8"))
    sec = [s for s in sorted(veri["slotlar"], key=lambda x: x["id"]) if ilk <= s["id"] <= son]
    return veri, sec


def yaz(veri):
    with open("takvim.json", "w", encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=False, indent=1)
        f.write("\n")


def uygula(argv):
    metinler = json.load(open("tools/kanca_tartisma.json", encoding="utf-8"))
    veri, sec = slotlar(argv)
    for s in sec:
        m = metinler.get(s["slug"])
        if not m:
            print(f"{s['id']} {s['slug']}: metin yok, atlandı")
            continue
        kanca_olcu(m["kanca"])  # sığmazsa hata
        s["kanca"] = m["kanca"]
        if s.get("tartisma") != m["tartisma"]:
            par = s["aciklama"].split("\n\n")
            if s.get("tartisma") and s["tartisma"] in par:
                par.remove(s["tartisma"])
            i = max(j for j, p in enumerate(par) if p.rstrip().endswith("👇"))
            par.insert(i, m["tartisma"])
            s["aciklama"] = "\n\n".join(par)
            s["tartisma"] = m["tartisma"]
        assert len(s["aciklama"]) <= 2200, s["id"]
        print(f"{s['id']} {s['slug']}: kanca + tartışma ({len(s['aciklama'])} karakter)")
    yaz(veri)


def onizle(argv):
    klasor = argv[-1]
    os.makedirs(klasor, exist_ok=True)
    _, sec = slotlar(argv)
    for s in sec:
        gir, kanca, replik, sure, bas, k, r = planla(s)
        d = tempfile.mkdtemp()
        kp, rp = os.path.join(d, "k.png"), os.path.join(d, "r.png")
        kanca_png(kanca, kp, k[1], k[2], k[3], k[4])
        rk.kart(replik, rp, r[1], r[2], r[3], r[4])
        a = onizle_kare(gir, 0.0, kp).resize((360, 640))
        b = onizle_kare(gir, sure - 0.1, rp).resize((360, 640))
        tuval = Image.new("RGB", (730, 640), "white")
        tuval.paste(a, (0, 0)); tuval.paste(b, (370, 0))
        tuval.save(os.path.join(klasor, f"{s['id']}_{s['slug']}.png"))
        print(f"{s['id']} {s['slug']}: kanca {k[0]} üst={k[1]} alt={k[2]} boy={kanca_olcu(kanca, k[4])[0]} | kart {r[0]}", flush=True)


def takvim_modu(argv):
    kuru, yeniden = "--kuru" in argv, "--yeniden" in argv
    veri, sec = slotlar(argv)
    for s in sec:
        if not s.get("kanca"):
            print(f"{s['id']} {s['slug']}: kanca yok, atlandı")
            continue
        gir, kanca, replik, sure, bas, k, r = planla(s)
        cik = gir[:-4] + "-rk.mp4"
        print(f"{s['id']} {s['slug']}: kanca {k[0]} | kart {r[0]} -> {cik}", flush=True)
        if kuru:
            continue
        if yeniden or not os.path.exists(cik):
            bas2(gir, cik, kanca, k, replik, bas, r)
        s["video"] = cik
        s["deneme"] = "kanca+replik_karti"
        yaz(veri)  # her videodan sonra kaydet: yarıda kalırsa basılanlar takvimde olsun


def main():
    if "--uygula" in sys.argv:
        return uygula(sys.argv)
    if "--onizle" in sys.argv:
        return onizle(sys.argv)
    if "--takvim" in sys.argv:
        return takvim_modu(sys.argv)
    print(__doc__)


if __name__ == "__main__":
    main()
