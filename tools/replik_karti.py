"""Videonun son ~3 saniyesine replik + 'SEN HANGİSİSİN?' kartı bindirir.

Kullanım:
  python tools/replik_karti.py girdi.mp4 cikti.mp4 "Replik metni" [baslangic_sn]
  python tools/replik_karti.py --takvim [--ilk 2026-11-27-1230] [--kuru]
      takvim.json'daki sıradaki slotların videolarına kartı ekler (videolar/<slug>-r.mp4),
      slotun "video" alanını değiştirir ve "deneme": "replik_karti" yazar. Replik, slotta
      "replik" alanı varsa ondan, yoksa açıklamanın ilk satırından alınır.

Yerleşim kendiliğinden seçilir (25 Kasım DOSTLUK denemesi, 834 bin izlenme, temel görünüm):
  1. "varsayilan": kutu y=412'den başlar (DOSTLUK'taki yer), etiket satırının üstünde kalır.
  2. "yukari":     kutu başlık/alt başlığın hemen altından başlar, yine etiketlerin üstünde.
  3. "ortu":       yer yoksa kutu başlığın altından etiket satırının altına kadar uzar ve etiketleri
                   tamamen örter (koyu zemin); sahneye taşmayacak en büyük yazı boyu seçilir.
Replik 54 px'te 2 satıra sığmazsa 48, sonra 44 px denenir; yine sığmazsa hata verir
(slota daha kısa bir "replik" yazılmalı).
"""
import json, os, subprocess, sys, tempfile
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
INTER = "/usr/share/fonts/opentype/inter/"
EMOJI = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
VARSAYILAN_UST = 412


def sar(metin, font, genislik, ciz):
    satirlar, s = [], ""
    for k in metin.split():
        d = (s + " " + k).strip()
        if ciz.textlength(d, font=font) <= genislik:
            s = d
        else:
            satirlar.append(s); s = k
    satirlar.append(s)
    return satirlar


def emoji(ch, boy):
    f = ImageFont.truetype(EMOJI, 109)
    im = Image.new("RGBA", (136, 128), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((0, 0), ch, font=f, embedded_color=True)
    im = im.crop(im.getbbox())
    return im.resize((boy, int(im.height * boy / im.width)), Image.LANCZOS)


def olcu(replik, boylar=(54, 48, 44)):
    """(font_boyu, satirlar, kutu_yuksekligi) — 2 satıra sığan en büyük boy."""
    c = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    for boy in boylar:
        f = ImageFont.truetype(INTER + "Inter-SemiBold.otf", boy)
        s = sar(replik, f, 900, c)
        if len(s) <= 2:
            ara = round(boy * 4 / 3)
            return boy, s, 40 + (len(s) - 1) * ara + boy + 120
    raise ValueError(f"Replik 2 satıra sığmıyor, kısaltılmalı: {replik!r}")


def kart(replik, yol, ust=VARSAYILAN_UST, alfa=120, alt=None, boylar=(54, 48, 44)):
    """ust: kutunun üst kenarı (px; DOSTLUK'ta 412). alt verilirse kutu o kenara kadar uzar ve
    içerik dikeyde ortalanır (etiket satırını tamamen örtmek için)."""
    boy, satirlar, h = olcu(replik, boylar)
    f = ImageFont.truetype(INTER + "Inter-SemiBold.otf", boy)
    ara = round(boy * 4 / 3)
    alt = max(alt or 0, ust + h)
    y0 = ust + 40 + ((alt - ust) - h) // 2
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    zemin = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(zemin).rounded_rectangle((60, ust, W - 60, alt),
                                             radius=36, fill=(0, 0, 0, alfa))
    im = Image.alpha_composite(im, zemin); c = ImageDraw.Draw(im)
    for i, s in enumerate(satirlar):
        w = c.textlength(s, font=f)
        c.text(((W - w) / 2, y0 + i * ara), s, font=f, fill=(255, 255, 255, 255))
    q = ImageFont.truetype(INTER + "Inter-Medium.otf", 34)
    harfler = list("SEN HANGİSİSİN?"); bosluk = 5
    w = sum(c.textlength(h, font=q) for h in harfler) + bosluk * (len(harfler) - 1)
    ey = 44
    x = (W - (w + 2 * (ey + 18))) / 2
    yq = y0 + (len(satirlar) - 1) * ara + boy + 42
    sag = emoji("👉", ey); sol = sag.transpose(Image.FLIP_LEFT_RIGHT)
    im.alpha_composite(sol, (int(x), int(yq - 4)))
    x += ey + 18
    for h in harfler:
        c.text((x, yq), h, font=q, fill=(200, 200, 200, 255)); x += c.textlength(h, font=q) + bosluk
    x += 18 - bosluk
    im.alpha_composite(sag, (int(x), int(yq - 4)))
    im.save(yol)


def kare(video, t):
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", video, "-frames:v", "1",
                          "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(H, W).astype(int)


def bantlar(video, bas, sure):
    """Kartın göründüğü aralıktaki içerik satırlarını bant listesi olarak döndürür [(üst, alt), …]."""
    a = None
    for t in (bas + 0.2, (bas + sure) / 2, sure - 0.1):
        k = kare(video, t); a = k if a is None else np.maximum(a, k)
    med = np.median(a, axis=1, keepdims=True)
    satir = ((a - med) > 60).sum(axis=1) > 3
    out, bas_ = [], None
    for y in range(200, 1400):
        if satir[y] and bas_ is None:
            bas_ = y
        if not satir[y] and bas_ is not None:
            if out and bas_ - out[-1][1] <= 12:
                out[-1] = (out[-1][0], y)
            else:
                out.append((bas_, y))
            bas_ = None
    return out


def yerlesim(video, replik, bas, sure):
    _, _, h = olcu(replik)
    b = bantlar(video, bas, sure)
    baslik = [x for x in b if x[0] < 410]
    ust_sinir = (baslik[-1][1] if baslik else 330) + 22
    alt = [x for x in b if x[0] >= max(410, ust_sinir)]
    etiket = alt[0][0] if alt else 1400
    if VARSAYILAN_UST >= ust_sinir and VARSAYILAN_UST + h <= etiket - 15:
        return "varsayilan", VARSAYILAN_UST, 120, None, (54, 48, 44)
    if ust_sinir + h <= etiket - 15:
        return "yukari", ust_sinir, 120, None, (54, 48, 44)
    # Yer yok: kutu etiket satırını tamamen örter. Sahnenin (sonraki bant) üstünde kalacak
    # en büyük yazı boyu seçilir.
    etiket_alt = alt[0][1] if alt else ust_sinir
    sahne = alt[1][0] if len(alt) > 1 else 1400
    for boylar in ((54, 48, 44), (48, 44), (44,)):
        try:
            _, _, h2 = olcu(replik, boylar)
        except ValueError:
            continue
        kutu_alt = max(ust_sinir + h2, etiket_alt + 16)
        if kutu_alt <= sahne - 12:
            return "ortu", ust_sinir, 250, kutu_alt, boylar
    return "ortu", ust_sinir, 250, max(ust_sinir + h2, etiket_alt + 16), (44,)


def bindir(gir, cik, replik, bas, ust=VARSAYILAN_UST, alfa=120, alt=None, boylar=(54, 48, 44)):
    d = tempfile.mkdtemp()
    png = os.path.join(d, "kart.png"); kart(replik, png, ust, alfa, alt, boylar)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", gir, "-loop", "1", "-i", png,
                    "-filter_complex",
                    f"[1:v]format=rgba,fade=in:st={bas}:d=0.4:alpha=1[k];[0:v][k]overlay=0:0:shortest=1:format=auto,format=yuv420p[v]",
                    "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-crf", "18", "-preset", "slow",
                    "-profile:v", "high", "-r", "30", "-c:a", "copy", "-movflags", "+faststart", cik], check=True)


def sure_of(video):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video],
                                capture_output=True, text=True, check=True).stdout)


def takvim_modu(argv):
    ilk = argv[argv.index("--ilk") + 1] if "--ilk" in argv else "0"
    kuru = "--kuru" in argv
    yol = "takvim.json"
    veri = json.load(open(yol, encoding="utf-8"))
    yapilan = {}
    for s in sorted(veri["slotlar"], key=lambda x: x["id"]):
        if s["id"] < ilk or s["video"].endswith("-r.mp4"):
            continue
        gir = s["video"]
        cik = gir[:-4] + "-r.mp4"
        replik = s.get("replik") or s["aciklama"].split("\n")[0].strip()
        if gir not in yapilan:
            sure = sure_of(gir); bas = round(sure - 3.2, 2)
            tur, ust, alfa, alt, boylar = yerlesim(gir, replik, bas, sure)
            print(f"{s['id']} {s['slug']}: {tur} ust={ust} alt={alt} boy={olcu(replik, boylar)[0]} | {replik}", flush=True)
            if not kuru:
                bindir(gir, cik, replik, bas, ust, alfa, alt, boylar)
            yapilan[gir] = cik
        if not kuru:
            s["video"] = yapilan[gir]
            s["deneme"] = "replik_karti"
    if not kuru:
        with open(yol, "w", encoding="utf-8") as f:
            json.dump(veri, f, ensure_ascii=False, indent=1)
            f.write("\n")


def main():
    if "--takvim" in sys.argv:
        return takvim_modu(sys.argv)
    gir, cik, replik = sys.argv[1:4]
    bas = float(sys.argv[4]) if len(sys.argv) > 4 else 10.8
    bindir(gir, cik, replik, bas)


if __name__ == "__main__":
    main()
