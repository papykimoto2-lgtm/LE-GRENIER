"""Génère une capsule publicitaire verticale de 30 s pour l'app Le Grenier CI
(pas un livre — la marketplace elle-même).

Usage : python3 produits-numeriques/app-video.py
Sortie : produits-numeriques/dist/promo/
  le-grenier-app-video.mp4   1080×1920, 30 s, sans son (statut WhatsApp, Reels, TikTok)
  le-grenier-app-voix.txt    texte à lire par-dessus (CapCut, InShot…)

Même pipeline que video.py (rendu HTML→images via Playwright, encodage H.264
via ffmpeg) mais contenu propre à l'app : pas de couverture de livre, pas de
QR code d'achat — juste le lien du site.
"""
import json
import os
import pathlib
import subprocess

import imageio_ffmpeg
import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import RoundedModuleDrawer

RACINE = pathlib.Path(__file__).parent
DIST = RACINE / "dist"
SORTIE = DIST / "promo"
SITE = "https://le-grenier.vercel.app/"
ICONE = RACINE.parent / "icon-512.png"

DUREE = 30
IPS = 25
FONCE = "#0D5C35"
COULEUR = "#1A7A48"
OR = "#F5B82E"

ACCROCHE = ["Vendre.", "Acheter.", "En toute sécurité."]
POINTS = [
    "Annonces, jobs, logements, restos…",
    "🛡️ Achat protégé : ton argent est retenu jusqu'à la livraison",
    "💳 Paiement en plusieurs fois disponible",
    "📱 Wave · Orange Money · MTN · Moov",
]
VOIX = (
    "Vendre un article, trouver un logement, un petit boulot, un plat près de chez toi… "
    "et payer en toute sécurité. Bienvenue sur Le Grenier CI, la marketplace ivoirienne. "
    "Avec l'achat protégé, ton argent est retenu jusqu'à ce que tu confirmes avoir bien reçu ton article. "
    "Tu peux même payer en plusieurs fois. Wave, Orange Money, MTN, Moov : tous acceptés. "
    "Rejoins Le Grenier CI dès aujourd'hui — l'inscription est gratuite."
)


def qr_png(url, couleur):
    q = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=16, border=2)
    q.add_data(url)
    img = q.make_image(image_factory=StyledPilImage, module_drawer=RoundedModuleDrawer())
    img = img.convert("RGB")
    r, g, b = int(couleur[1:3], 16), int(couleur[3:5], 16), int(couleur[5:7], 16)
    px = img.load()
    for x in range(img.width):
        for y in range(img.height):
            if px[x, y][0] < 128:
                px[x, y] = (r, g, b)
    import io
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def data_uri(octets, mime="image/png"):
    import base64
    return f"data:{mime};base64,{base64.b64encode(octets).decode()}"


def page(icone_uri, qr_uri):
    accroche = "".join(
        f'<div class="ligne" style="animation-delay:{0.3 + i * 1.3}s">{t}</div>' for i, t in enumerate(ACCROCHE))
    points = "".join(f'<li style="animation-delay:{12 + i * 1.6}s">{p}</li>' for i, p in enumerate(POINTS))
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
@font-face {{ font-family: Poppins; font-weight: 400; src: url('polices/poppins-latin-400-normal.woff2'); }}
@font-face {{ font-family: Poppins; font-weight: 700; src: url('polices/poppins-latin-700-normal.woff2'); }}
@font-face {{ font-family: Poppins; font-weight: 800; src: url('polices/poppins-latin-800-normal.woff2'); }}
@font-face {{ font-family: Fraunces; font-weight: 900; src: url('polices/fraunces-latin-900-normal.woff2'); }}
* {{ box-sizing: border-box; margin: 0; }}
body {{ width: 1080px; height: 1920px; overflow: hidden; color: #fff; font-family: Poppins, 'Noto Color Emoji', sans-serif;
  background: radial-gradient(circle at 80% 10%, {COULEUR} 0%, {FONCE} 60%); }}
.fond {{ position: absolute; inset: -200px; background: radial-gradient(circle at 20% 90%, rgba(255,255,255,.12), transparent 40%);
  animation: derive {DUREE}s linear both; }}
@keyframes derive {{ to {{ transform: translate(120px, -160px) rotate(8deg); }} }}
.barre {{ position: absolute; top: 0; left: 0; height: 12px; width: 100%; background: {OR}; transform-origin: left;
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
.ligne:last-child {{ color: {OR}; }}
.logo {{ width: 320px; height: 320px; border-radius: 64px; box-shadow: 0 40px 90px rgba(0,0,0,.5);
  animation: couv 6s 5s both; }}
@keyframes couv {{ 0% {{ transform: translateY(200px) scale(.7); }} 18% {{ transform: none; }} 100% {{ transform: scale(1.05); }} }}
.nomapp {{ font-family: Fraunces, serif; font-weight: 900; font-size: 96px; line-height: 1.05; margin-top: 60px;
  animation: monte .8s 6.2s both; }}
.tagline {{ font-size: 42px; font-weight: 700; opacity: .95; margin-top: 20px; max-width: 820px;
  animation: monte .8s 6.8s both; }}
ul {{ list-style: none; padding: 0; }}
li {{ font-size: 50px; font-weight: 800; line-height: 1.25; margin: 26px 0; background: rgba(255,255,255,.12);
  border-radius: 28px; padding: 32px 38px; animation: pop .6s both; }}
.confiance {{ font-family: Fraunces, serif; font-weight: 900; font-size: 68px; line-height: 1.2; margin-bottom: 30px;
  animation: monte .8s .2s both; }}
.fondateur {{ font-size: 34px; opacity: .9; animation: monte .8s .6s both; }}
.achat {{ background: #fff; color: #1F1A17; border-radius: 48px; padding: 60px 50px; width: 100%; animation: pop .7s both; }}
.gratuit {{ font-family: Fraunces, serif; font-weight: 900; font-size: 96px; line-height: 1; color: {FONCE}; }}
.qr {{ width: 460px; height: 460px; margin: 26px auto 10px; display: block; animation: pouls 1.4s 1.2s infinite; }}
@keyframes pouls {{ 50% {{ transform: scale(1.04); }} }}
.scan {{ font-size: 52px; font-weight: 800; }}
.moyens {{ font-size: 32px; color: #555; margin-top: 10px; }}
.url {{ font-size: 40px; font-weight: 700; margin-top: 46px; animation: monte .6s .3s both; }}
</style></head><body>
<div class="fond"></div><div class="barre"></div>
<div class="marque">Le Grenier CI</div>
<div class="scene s1">{accroche}</div>
<div class="scene s2"><img class="logo" src="{icone_uri}"><div class="nomapp">Le Grenier CI</div>
  <div class="tagline">La marketplace ivoirienne qui protège tes achats</div></div>
<div class="scene s3"><ul>{points}</ul></div>
<div class="scene s4"><div class="confiance">Vendeurs vérifiables.<br>Paiements sécurisés.</div>
  <div class="fondateur">Fondé par Cyrille KESSIE<br>SANIX AFRICA Technologies</div></div>
<div class="scene s5"><div class="achat"><div class="gratuit">Gratuit</div><img class="qr" src="{qr_uri}">
  <div class="scan">📱 Scanne pour rejoindre</div><div class="moyens">Inscription vendeur ou acheteur en 2 minutes</div></div>
  <div class="url">le-grenier.vercel.app</div></div>
</body></html>"""


RENDU = """
const { chromium } = require('playwright');
const { spawn } = require('child_process');
(async () => {
  const [html, mp4, ffmpeg, duree, ips, chromiumPath] = JSON.parse(process.argv[1]);
  const b = await chromium.launch({ executablePath: chromiumPath || process.env.CHROMIUM_PATH || undefined });
  const p = await b.newPage({ viewport: { width: 1080, height: 1920 } });
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
  await b.close();
})();"""


def main():
    SORTIE.mkdir(parents=True, exist_ok=True)
    icone = data_uri(ICONE.read_bytes())
    qr = data_uri(qr_png(SITE + "?src=qr-video-app", FONCE))
    html_f = SORTIE / "le-grenier-app-video.html"
    html_f.write_text(page(icone, qr), encoding="utf-8")
    mp4_f = SORTIE / "le-grenier-app-video.mp4"
    (SORTIE / "le-grenier-app-voix.txt").write_text(VOIX, encoding="utf-8")

    chromium_path = os.environ.get("CHROMIUM_PATH") or (
        "/opt/pw-browsers/chromium" if pathlib.Path("/opt/pw-browsers/chromium").exists() else None)
    params = json.dumps([str(html_f), str(mp4_f), imageio_ffmpeg.get_ffmpeg_exe(), DUREE, IPS, chromium_path])
    racine_npm = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip()
    node_path_extra = os.environ.get("APP_VIDEO_NODE_PATH", "")
    env = {**os.environ, "NODE_PATH": os.pathsep.join(filter(None, [node_path_extra, os.environ.get("NODE_PATH"), racine_npm]))}
    subprocess.run(["node", "-e", RENDU, params], check=True, cwd=RACINE, env=env)
    html_f.unlink()
    print("Vidéo :", mp4_f)


if __name__ == "__main__":
    main()
