"""Videonun son ~3 saniyesine replik + 'SEN HANGİSİSİN?' kartı bindirir.
Kullanım: python replik.py girdi.mp4 cikti.mp4 "Replik metni" [baslangic_sn]"""
import subprocess, sys, tempfile, os
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
INTER = "/usr/share/fonts/opentype/inter/"
EMOJI = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"


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


def kart(replik, yol):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    c = ImageDraw.Draw(im)
    f = ImageFont.truetype(INTER + "Inter-SemiBold.otf", 54)
    satirlar = sar(replik, f, 900, c)
    ara = 72
    y0 = 515 - (len(satirlar) - 1) * ara / 2 - 27
    # okunurluk için hafif koyu zemin
    zemin = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(zemin).rounded_rectangle((60, y0 - 40, W - 60, y0 + (len(satirlar) - 1) * ara + 54 + 120),
                                             radius=36, fill=(0, 0, 0, 120))
    im = Image.alpha_composite(im, zemin); c = ImageDraw.Draw(im)
    for i, s in enumerate(satirlar):
        w = c.textlength(s, font=f)
        c.text(((W - w) / 2, y0 + i * ara), s, font=f, fill=(255, 255, 255, 255))
    q = ImageFont.truetype(INTER + "Medium.otf" if False else INTER + "Inter-Medium.otf", 34)
    soru = "SEN HANGİSİSİN?"
    # harf aralığı
    harfler = list(soru); bosluk = 5
    w = sum(c.textlength(h, font=q) for h in harfler) + bosluk * (len(harfler) - 1)
    ey = 44
    toplam = w + 2 * (ey + 18)
    x = (W - toplam) / 2
    yq = y0 + (len(satirlar) - 1) * ara + 54 + 42
    sag = emoji("👉", ey); sol = sag.transpose(Image.FLIP_LEFT_RIGHT)
    im.alpha_composite(sol, (int(x), int(yq - 4)))
    x += ey + 18
    for h in harfler:
        c.text((x, yq), h, font=q, fill=(200, 200, 200, 255)); x += c.textlength(h, font=q) + bosluk
    x += 18 - bosluk
    im.alpha_composite(sag, (int(x), int(yq - 4)))
    im.save(yol)


def main():
    gir, cik, replik = sys.argv[1:4]
    bas = float(sys.argv[4]) if len(sys.argv) > 4 else 10.8
    d = tempfile.mkdtemp()
    png = os.path.join(d, "kart.png"); kart(replik, png)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", gir, "-loop", "1", "-i", png,
                    "-filter_complex",
                    f"[1:v]format=rgba,fade=in:st={bas}:d=0.4:alpha=1[k];[0:v][k]overlay=0:0:shortest=1:format=auto,format=yuv420p[v]",
                    "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-crf", "18", "-preset", "slow",
                    "-profile:v", "high", "-r", "30", "-c:a", "copy", "-movflags", "+faststart", cik], check=True)


if __name__ == "__main__":
    main()
