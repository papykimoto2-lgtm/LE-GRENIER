"""Génère une vidéo de présentation verticale de 30 s par livre.

Usage : python3 produits-numeriques/video.py   (après build.py et promo.py)
Sortie : produits-numeriques/dist/promo/
  <slug>-video.mp4     1080×1920, 30 s, sans son (statut WhatsApp, Reels, TikTok)
  voix-off.txt         texte à lire par-dessus chaque vidéo (CapCut, InShot…)

Le QR code final porte la source « qr-video » pour mesurer les ventes dans l'admin.
Les images sont calculées une à une (animations figées à l'instant t) puis
encodées en H.264 : rendu fluide quelle que soit la vitesse de la machine.
"""
import html
import json
import os
import pathlib
import re
import subprocess

import imageio_ffmpeg

from promo import DIST, LIVRES, RACINE, SORTIE, data_uri, lien, qr_png

DUREE = 30
IPS = 25
PHOTO_AUTEUR = RACINE / "photos" / "auteur-800x1000-0.72-0.5-1.45.jpg"

SCRIPTS = {
    "app-sans-code": {
        "accroche": ["15 logiciels.", "Zéro ligne de code.", "30 millions de FCFA en 3 mois."],
        "voix": "Quinze logiciels. Zéro ligne de code. Trente millions de francs CFA en trois mois. "
                "Je suis Cyrille Kessie, et dans « Zéro Code, 30 Millions », je te montre exactement "
                "comment j'ai fait : les outils, les prompts à copier, et comment encaisser par Mobile Money. "
                "Quinze mille francs. Scanne le QR code, paie par Wave, Orange, MTN ou Moov, "
                "et reçois ton livre tout de suite.",
    },
    "vendre-whatsapp-facebook": {
        "accroche": ["Tu publies tous les jours…", "… mais personne n'achète ?", "Voici la méthode qui fait vendre."],
        "voix": "Tu publies tous les jours sur WhatsApp et Facebook, mais personne n'achète ? "
                "Dans « Vendre sur WhatsApp et Facebook », je te donne les messages à copier, "
                "les photos qui font vendre et un plan d'action de trente jours. "
                "Cinq mille francs seulement. Scanne le QR code, paie par Mobile Money, "
                "et commence à vendre dès ce soir.",
    },
    "boutique-50000": {
        "accroche": ["50 000 F en poche ?", "C'est assez pour démarrer.", "Voici le plan exact."],
        "voix": "Tu as cinquante mille francs et tu veux lancer ta boutique ? C'est assez pour démarrer. "
                "Dans « Lancer sa boutique avec 50 000 F », je te donne la répartition exacte de ton budget, "
                "le calcul des prix sans perte et un plan d'action de soixante jours. "
                "Dix mille francs. Scanne le QR code, paie par Mobile Money et reçois ton guide tout de suite.",
    },
    "ne-plus-abandonner": {
        "accroche": ["Licencié.", "Des années de procédure.", "Et j'ai gagné… sans être payé."],
        "voix": "Licencié en décembre 2022. Des années de procédure. Puis une décision de justice en ma faveur… "
                "et l'argent qui n'arrivait toujours pas. Dans « Le jour où j'ai décidé de ne plus abandonner », "
                "je raconte mon combat, comment l'intelligence artificielle m'a aidé à comprendre et à tenir, "
                "et comment je suis passé de victime à entrepreneur. Cinq mille francs. "
                "Scanne le QR code, paie par Mobile Money et reçois le livre tout de suite.",
    },
}


def texte(t):
    """Échappe le texte et garde les montants (« 50 000 F ») sur une seule ligne."""
    return re.sub(r"(?<=\d) (?=\d{3}\b|F\b)", "\u00a0", html.escape(t))


def page(livre, script, couv_uri, qr_uri, auteur_uri):
    f, c = livre["fonce"], livre["couleur"]
    accroche = "".join(
        f'<div class="ligne" style="animation-delay:{0.3 + i * 1.3}s">{texte(t)}</div>'
        for i, t in enumerate(script["accroche"]))
    points = "".join(
        f'<li style="animation-delay:{12 + i * 1.8}s">✅ {texte(p)}</li>' for i, p in enumerate(livre["points"]))
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
@font-face {{ font-family: Poppins; font-weight: 400; src: url('../../polices/poppins-latin-400-normal.woff2'); }}
@font-face {{ font-family: Poppins; font-weight: 700; src: url('../../polices/poppins-latin-700-normal.woff2'); }}
@font-face {{ font-family: Poppins; font-weight: 800; src: url('../../polices/poppins-latin-800-normal.woff2'); }}
@font-face {{ font-family: Fraunces; font-weight: 900; src: url('../../polices/fraunces-latin-900-normal.woff2'); }}
* {{ box-sizing: border-box; margin: 0; }}
body {{ width: 1080px; height: 1920px; overflow: hidden; color: #fff; font-family: Poppins, 'Noto Color Emoji', sans-serif;
  background: radial-gradient(circle at 80% 10%, {c} 0%, {f} 60%); }}
.fond {{ position: absolute; inset: -200px; background: radial-gradient(circle at 20% 90%, rgba(255,255,255,.12), transparent 40%);
  animation: derive {DUREE}s linear both; }}
@keyframes derive {{ to {{ transform: translate(120px, -160px) rotate(8deg); }} }}
.barre {{ position: absolute; top: 0; left: 0; height: 12px; width: 100%; background: #F5B82E; transform-origin: left;
  animation: barre {DUREE}s linear both; }}
@keyframes barre {{ from {{ transform: scaleX(0); }} to {{ transform: scaleX(1); }} }}
.marque {{ position: absolute; top: 60px; width: 100%; text-align: center; font-size: 26px; letter-spacing: .2em;
  font-weight: 800; opacity: .8; text-transform: uppercase; }}
.scene {{ position: absolute; inset: 140px 70px 120px; display: flex; flex-direction: column; align-items: center;
  justify-content: center; text-align: center; opacity: 0; }}
@keyframes scene {{ 0% {{ opacity: 0; transform: scale(.94); }} 8%, 92% {{ opacity: 1; transform: none; }}
  100% {{ opacity: 0; transform: scale(1.04); }} }}
@keyframes entree {{ 0% {{ opacity: 0; transform: scale(.94); }} 100% {{ opacity: 1; transform: none; }} }}
@keyframes monte {{ from {{ opacity: 0; transform: translateY(60px); }} to {{ opacity: 1; transform: none; }} }}
@keyframes pop {{ 0% {{ opacity: 0; transform: scale(.6); }} 70% {{ transform: scale(1.06); }} 100% {{ opacity: 1; transform: none; }} }}
.s1 {{ animation: scene 5s 0s both; }}
.s2 {{ animation: scene 6s 5s both; }}
.s3 {{ animation: scene 7s 11s both; }}
.s4 {{ animation: scene 5s 18s both; }}
.s5 {{ animation: entree .6s 23s both; }}
.ligne {{ font-family: Fraunces, serif; font-weight: 900; font-size: 104px; line-height: 1.08; margin: 18px 0;
  animation: monte .7s both; }}
.ligne:last-child {{ color: #F5B82E; }}
.couv {{ height: 1060px; border-radius: 18px; box-shadow: 0 40px 90px rgba(0,0,0,.5);
  animation: couv 6s 5s both; }}
@keyframes couv {{ 0% {{ transform: translateY(300px) rotate(-12deg) scale(.8); }} 18% {{ transform: rotate(-2deg); }}
  100% {{ transform: rotate(-2deg) scale(1.06); }} }}
.titre {{ font-family: Fraunces, serif; font-weight: 900; font-size: 76px; line-height: 1.05; margin-top: 60px;
  animation: monte .8s 6.2s both; }}
.dans {{ font-size: 40px; font-weight: 800; letter-spacing: .12em; text-transform: uppercase; color: #F5B82E;
  margin-bottom: 50px; }}
ul {{ list-style: none; padding: 0; }}
li {{ font-size: 56px; font-weight: 800; line-height: 1.2; margin: 34px 0; background: rgba(255,255,255,.12);
  border-radius: 28px; padding: 34px 40px; animation: pop .6s both; }}
.photo {{ width: 560px; height: 700px; object-fit: cover; border-radius: 280px 280px 40px 40px;
  border: 10px solid #F5B82E; box-shadow: 0 40px 90px rgba(0,0,0,.45); animation: monte .8s 18.2s both; }}
.nom {{ font-family: Fraunces, serif; font-weight: 900; font-size: 80px; margin-top: 50px; }}
.role {{ font-size: 38px; line-height: 1.4; opacity: .9; margin-top: 14px; }}
.achat {{ background: #fff; color: #1F1A17; border-radius: 48px; padding: 60px 50px; width: 100%;
  animation: pop .7s 23.3s both; }}
.prix {{ font-family: Fraunces, serif; font-weight: 900; font-size: 150px; line-height: 1; color: {f}; }}
.qr {{ width: 560px; height: 560px; margin: 30px auto 10px; display: block; animation: pouls 1.4s 24.5s infinite; }}
@keyframes pouls {{ 50% {{ transform: scale(1.04); }} }}
.scan {{ font-size: 58px; font-weight: 800; }}
.moyens {{ font-size: 36px; color: #555; margin-top: 12px; }}
.url {{ font-size: 40px; font-weight: 700; margin-top: 50px; animation: monte .6s 24.5s both; }}
</style></head><body>
<div class="fond"></div><div class="barre"></div>
<div class="marque">Le Grenier CI · Nouveau livre</div>
<div class="scene s1">{accroche}</div>
<div class="scene s2"><img class="couv" src="{couv_uri}"><div class="titre">{texte(livre['titre'])}</div></div>
<div class="scene s3"><div class="dans">Dans ce livre</div><ul>{points}</ul></div>
<div class="scene s4"><img class="photo" src="{auteur_uri}"><div class="nom">Cyrille KESSIE</div>
  <div class="role">Fondateur de SANIX AFRICA Technologies<br>et de Le Grenier CI</div></div>
<div class="scene s5"><div class="achat"><div class="prix">{livre['prix']}</div><img class="qr" src="{qr_uri}">
  <div class="scan">📱 Scanne et paie</div><div class="moyens">Wave · Orange Money · MTN · Moov<br>PDF à télécharger tout de suite</div></div>
  <div class="url">le-grenier.vercel.app</div></div>
</body></html>"""


RENDU = """
const { chromium } = require('playwright');
const { spawn } = require('child_process');
(async () => {
  const [travaux, ffmpeg, duree, ips] = JSON.parse(process.argv[1]);
  const b = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
  const p = await b.newPage({ viewport: { width: 1080, height: 1920 } });
  for (const [html, mp4] of travaux) {
    await p.goto('file://' + html); await p.evaluate(() => document.fonts.ready);
    await p.evaluate(() => document.getAnimations().forEach(a => a.pause()));
    const enc = spawn(ffmpeg, ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(ips), '-i', '-',
      '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', mp4],
      { stdio: ['pipe', 'inherit', 'inherit'] });
    const fini = new Promise((ok, ko) => enc.on('close', c => c ? ko(new Error('ffmpeg ' + c)) : ok()));
    for (let i = 0; i < duree * ips; i++) {
      await p.evaluate(t => document.getAnimations().forEach(a => { a.currentTime = t; }), i * 1000 / ips);
      const img = await p.screenshot({ type: 'jpeg', quality: 92 });
      if (!enc.stdin.write(img)) await new Promise(r => enc.stdin.once('drain', r));
    }
    enc.stdin.end(); await fini;
  }
  await b.close();
})();"""


def main():
    SORTIE.mkdir(parents=True, exist_ok=True)
    auteur = data_uri(PHOTO_AUTEUR.read_bytes(), "image/jpeg")
    travaux, voix = [], []
    for livre in LIVRES:
        script = SCRIPTS[livre["slug"]]
        couv = data_uri((DIST / f"{livre['fichier']}-couverture.png").read_bytes())
        qr = data_uri(qr_png(lien(livre["slug"], "qr-video"), livre["fonce"]))
        f = SORTIE / f"{livre['slug']}-video.html"
        f.write_text(page(livre, script, couv, qr, auteur), encoding="utf-8")
        travaux.append((str(f), str(SORTIE / f"{livre['slug']}-video.mp4")))
        voix += [f"{livre['titre']} ({livre['prix']})", script["voix"],
                 f"Lien à mettre en légende : {lien(livre['slug'], 'lien-video')}", ""]
    (SORTIE / "voix-off.txt").write_text("\n".join(voix), encoding="utf-8")
    params = json.dumps([travaux, imageio_ffmpeg.get_ffmpeg_exe(), DUREE, IPS])
    racine_npm = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip()
    env = {**os.environ, "NODE_PATH": os.pathsep.join(filter(None, [os.environ.get("NODE_PATH"), racine_npm]))}
    subprocess.run(["node", "-e", RENDU, params], check=True, cwd=RACINE.parent, env=env)
    for f, _ in travaux:
        pathlib.Path(f).unlink()
    print("Vidéos :", SORTIE)


if __name__ == "__main__":
    main()
