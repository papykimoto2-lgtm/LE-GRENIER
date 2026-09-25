"""Télécharge la capture d'une page photo Pexels et en extrait la photo.

Usage : python3 recuperer_photo.py <id> "<photographe>" "<url de la capture>"
Les photos Pexels sont sous licence Pexels (usage commercial autorisé, sans
attribution obligatoire) ; on garde tout de même le crédit dans credits.json.
"""
import io
import json
import pathlib
import sys
import urllib.request

from PIL import Image

DOSSIER = pathlib.Path(__file__).parent / "photos-brutes"
CREDITS = DOSSIER / "credits.json"


def extraire(img):
    """La photo est la plus grande zone non blanche sous l'en-tête Pexels."""
    g = img.convert("L")
    w, h = g.size
    px = g.load()

    def ligne_non_blanche(y):
        return sum(1 for x in range(0, w, 8) if px[x, y] < 245) > (w / 8) * 0.25

    y0 = next(y for y in range(150, h) if ligne_non_blanche(y))
    y1 = y0
    while y1 < h - 1 and ligne_non_blanche(y1 + 1):
        y1 += 1
    milieu = (y0 + y1) // 2

    def col_non_blanche(x):
        return sum(1 for y in range(y0, y1, 8) if px[x, y] < 245) > ((y1 - y0) / 8) * 0.25

    x0 = next(x for x in range(w) if col_non_blanche(x))
    x1 = next(x for x in range(w - 1, 0, -1) if col_non_blanche(x))
    return img.crop((x0 + 2, y0 + 2, x1 - 2, y1 - 2)), milieu


if __name__ == "__main__":
    ident, auteur, url = sys.argv[1], sys.argv[2], sys.argv[3]
    DOSSIER.mkdir(exist_ok=True)
    brut = Image.open(io.BytesIO(urllib.request.urlopen(url, timeout=60).read())).convert("RGB")
    photo, _ = extraire(brut)
    photo.save(DOSSIER / f"{ident}.jpg", quality=90)
    credits = json.loads(CREDITS.read_text()) if CREDITS.exists() else {}
    credits[ident] = {"auteur": auteur, "source": f"https://www.pexels.com/photo/{ident}/"}
    CREDITS.write_text(json.dumps(credits, ensure_ascii=False, indent=1))
    print(ident, photo.size)
