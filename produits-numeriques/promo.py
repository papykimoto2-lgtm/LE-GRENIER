"""Génère les QR codes et visuels de vente des livres.

Usage : python3 produits-numeriques/promo.py
Sortie : produits-numeriques/dist/promo/
  <slug>-qr.png            QR code seul (lien d'achat direct)
  <slug>-statut.png        visuel 1080×1920 (statut WhatsApp, story)
  <slug>-carre.png         visuel 1080×1080 (Facebook, Instagram)
  <slug>-flyer.pdf         flyer A5 à imprimer
  liens.txt                liens d'achat direct par livre et par canal

Chaque canal a sa propre source (?src=…) pour mesurer les ventes dans l'admin.
"""
import base64
import html
import io
import pathlib
import subprocess

import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import RoundedModuleDrawer

RACINE = pathlib.Path(__file__).parent
DIST = RACINE / "dist"
SORTIE = DIST / "promo"
SITE = "https://le-grenier.vercel.app/"

LIVRES = [
    {"slug": "app-sans-code", "fichier": "guide-app-sans-code", "titre": "Zéro Code, 30 Millions",
     "accroche": "15 logiciels créés avec l'IA. 30 millions de FCFA en 3 mois. La méthode, pas à pas.",
     "prix": "15 000 F", "fonce": "#0B2A5B", "couleur": "#1A5FBF",
     "points": ["Les outils et prompts à copier", "Encaisser par Mobile Money", "Plan d'action 30 jours"]},
    {"slug": "vendre-whatsapp-facebook", "fichier": "guide-vendre-whatsapp-facebook",
     "titre": "Vendre sur WhatsApp et Facebook", "accroche": "La méthode pas à pas pour trouver des clients et encaisser par Mobile Money.",
     "prix": "5 000 F", "fonce": "#0D5C35", "couleur": "#1A7A48",
     "points": ["Messages à copier", "Photos qui font vendre", "Plan d'action 30 jours"]},
    {"slug": "boutique-50000", "fichier": "guide-boutique-50000", "titre": "Lancer sa boutique avec 50 000 F",
     "accroche": "Le plan complet pour démarrer petit, sans s'endetter, et grandir.",
     "prix": "10 000 F", "fonce": "#5B2466", "couleur": "#7C3A8A",
     "points": ["Répartition exacte des 50 000 F", "Calcul des prix sans perte", "Plan d'action 60 jours"]},
    {"slug": "ne-plus-abandonner", "fichier": "livre-ne-plus-abandonner-court",
     "titre": "Le jour où j'ai décidé de ne plus abandonner",
     "accroche": "Licencié en 2022. Des années de procédure. Et une victoire qu'il a encore fallu faire exécuter.",
     "prix": "5 000 F", "fonce": "#2A1215", "couleur": "#9A2B2B",
     "points": ["Une histoire vraie", "Gagner n'est pas encaisser", "L'IA comme alliée"]},
]
CANAUX = {"statut": "qr-statut", "carre": "qr-reseaux", "flyer": "qr-flyer"}


def lien(slug, source):
    return f"{SITE}?guide={slug}&achat=1&src={source}"


def qr_png(url, couleur):
    q = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=16, border=2)
    q.add_data(url)
    img = q.make_image(image_factory=StyledPilImage, module_drawer=RoundedModuleDrawer())
    img = img.convert("RGB")
    # Recoloriser les modules noirs dans la couleur foncée du livre
    r, g, b = int(couleur[1:3], 16), int(couleur[3:5], 16), int(couleur[5:7], 16)
    px = img.load()
    for x in range(img.width):
        for y in range(img.height):
            if px[x, y][0] < 128:
                px[x, y] = (r, g, b)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def data_uri(octets, mime="image/png"):
    return f"data:{mime};base64,{base64.b64encode(octets).decode()}"


def page(livre, format_, qr_uri, couv_uri):
    w, h = {"statut": (1080, 1920), "carre": (1080, 1080), "flyer": (1240, 1754)}[format_]
    points = "".join(f"<li>✅ {html.escape(p)}</li>" for p in livre["points"])
    vertical = format_ != "carre"
    long = len(livre["titre"]) > 32  # titre long : on réduit titre et couverture pour garder le QR visible
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
@font-face {{ font-family: Poppins; font-weight: 400; src: url('../../polices/poppins-latin-400-normal.woff2'); }}
@font-face {{ font-family: Poppins; font-weight: 700; src: url('../../polices/poppins-latin-700-normal.woff2'); }}
@font-face {{ font-family: Poppins; font-weight: 800; src: url('../../polices/poppins-latin-800-normal.woff2'); }}
@font-face {{ font-family: Fraunces; font-weight: 900; src: url('../../polices/fraunces-latin-900-normal.woff2'); }}
* {{ box-sizing: border-box; margin: 0; }}
body {{ width: {w}px; height: {h}px; font-family: Poppins, 'Noto Color Emoji', sans-serif; color: #fff; overflow: hidden;
  background: radial-gradient(circle at 80% 10%, {livre['couleur']} 0%, {livre['fonce']} 55%); }}
.c {{ height: 100%; display: flex; flex-direction: {'column' if vertical else 'row'}; align-items: center;
  justify-content: space-between; padding: {'90px 80px' if vertical else '60px'}; gap: {'40px' if vertical else '50px'}; text-align: {'center' if vertical else 'left'}; }}
.marque {{ font-size: {26 if vertical else 22}px; letter-spacing: .2em; font-weight: 800; opacity: .8; text-transform: uppercase; }}
.couv {{ height: {(640 if long else 760) if format_ == 'statut' else (480 if long else 560) if format_ == 'flyer' else 600}px; flex-shrink: 0; border-radius: 14px; box-shadow: 0 30px 70px rgba(0,0,0,.45); transform: rotate(-2deg); }}
h1 {{ font-family: Fraunces, serif; font-weight: 900; font-size: {(66 if long else 84) if vertical else (44 if long else 50)}px; line-height: 1.02; margin: 14px 0 18px; }}
.accroche {{ margin-bottom: {0 if vertical else 30}px; font-size: {34 if vertical else 24}px; line-height: 1.35; opacity: .95; }}
ul {{ list-style: none; padding: 0; margin: 26px 0; font-size: {32 if vertical else 26}px; font-weight: 700; line-height: 1.7; }}
.achat {{ display: flex; align-items: center; gap: {36 if vertical else 24}px; background: #fff; color: #1F1A17; border-radius: 34px; padding: 28px 34px;
  {'justify-content: center;' if vertical else ''} }}
.achat img {{ width: {300 if vertical else 190}px; height: {300 if vertical else 190}px; flex-shrink: 0; }}
.prix {{ white-space: nowrap; font-family: Fraunces, serif; font-weight: 900; font-size: {72 if vertical else 46}px; color: {livre['fonce']}; line-height: 1; }}
.scan {{ font-size: {30 if vertical else 24}px; font-weight: 800; margin-top: 10px; }}
.moyens {{ font-size: {24 if vertical else 20}px; color: #555; margin-top: 8px; }}
.url {{ font-size: {24 if vertical else 20}px; opacity: .85; }}
</style></head><body><div class="c">
{'<div class="marque">Le Grenier CI · Nouveau livre</div>' if vertical else ''}
<img class="couv" src="{couv_uri}">
<div>
  {'' if vertical else '<div class="marque">Le Grenier CI · Nouveau livre</div>'}
  <h1>{html.escape(livre['titre'])}</h1>
  <div class="accroche">{html.escape(livre['accroche'])}</div>
  {'<ul>' + points + '</ul>' if vertical else ''}
  <div class="achat"><img src="{qr_uri}"><div style="text-align:left">
    <div class="prix">{livre['prix']}</div>
    <div class="scan">📱 Scanne et paie</div>
    <div class="moyens">Wave · Orange Money · MTN · Moov<br>PDF à télécharger</div>
  </div></div>
</div>
{'<div class="url">le-grenier.vercel.app</div>' if vertical else ''}
</div></body></html>""", w, h


def main():
    SORTIE.mkdir(parents=True, exist_ok=True)
    liens = []
    travaux = []
    for livre in LIVRES:
        couv = (DIST / f"{livre['fichier']}-couverture.png").read_bytes()
        (SORTIE / f"{livre['slug']}-qr.png").write_bytes(qr_png(lien(livre["slug"], "qr"), livre["fonce"]))
        liens.append(f"{livre['titre']} ({livre['prix']})")
        for canal, src in [("WhatsApp (statut, message)", "lien-whatsapp"), ("Facebook / Instagram", "lien-reseaux"),
                           ("QR code", "qr")]:
            liens.append(f"  {canal} : {lien(livre['slug'], src)}")
        liens.append("")
        for format_, src in CANAUX.items():
            contenu, w, h = page(livre, format_, data_uri(qr_png(lien(livre["slug"], src), livre["fonce"])), data_uri(couv))
            f = SORTIE / f"{livre['slug']}-{format_}.html"
            f.write_text(contenu, encoding="utf-8")
            travaux.append((str(f), w, h, format_))
    (SORTIE / "liens.txt").write_text("\n".join(liens), encoding="utf-8")
    script = """
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
  const p = await b.newPage();
  for (const [f, w, h, fmt] of JSON.parse(process.argv[1])) {
    await p.setViewportSize({ width: w, height: h });
    await p.goto('file://' + f); await p.evaluate(() => document.fonts.ready);
    if (fmt === 'flyer') await p.pdf({ path: f.replace('.html', '.pdf'), width: '148mm', height: '210mm', printBackground: true, pageRanges: '1',
      scale: 148 / (w / 96 * 25.4) });
    else await p.screenshot({ path: f.replace('.html', '.png') });
  }
  await b.close();
})();"""
    import json
    subprocess.run(["node", "-e", script, json.dumps(travaux)], check=True)
    for f in SORTIE.glob("*.html"):
        f.unlink()
    print("Visuels et QR codes :", SORTIE)


if __name__ == "__main__":
    main()
