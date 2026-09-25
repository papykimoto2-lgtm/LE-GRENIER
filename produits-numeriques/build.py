"""Construit les guides PDF illustrés de la boutique numérique.

Usage : python3 produits-numeriques/build.py
Entrée : produits-numeriques/src/*.md (en-tête : titre, sous_titre, edition,
         couleur, fonce, badges « a | b | c »)
Sortie : produits-numeriques/dist/<slug>.pdf (A5) et <slug>-couverture.png

Conventions dans le Markdown :
  > 💬 …   message du vendeur (bulle WhatsApp verte, à copier)
  > 🙋 …   message du client (bulle blanche)
  > 📣 …   exemple de publication Facebook
  > 📖 …   histoire / exemple illustratif
  > 🚀 …   prochaine étape
  > **Conseil / Astuce / Important / Le dernier mot …** encadrés colorés
  - [ ] …  case à cocher
  ### Exercice  → encadré « À toi de jouer »
"""
import html
import pathlib
import re
import subprocess
import sys

import markdown
from pypdf import PdfReader, PdfWriter

RACINE = pathlib.Path(__file__).parent
SRC = RACINE / "src"
DIST = RACINE / "dist"
sys.path.insert(0, str(RACINE))
from scenes import SCENES  # noqa: E402


def lire(fichier):
    texte = fichier.read_text(encoding="utf-8")
    entete, corps = re.match(r"^---\n(.*?)\n---\n(.*)$", texte, re.S).groups()
    meta = dict(ligne.split(": ", 1) for ligne in entete.splitlines())
    return meta, corps


POLICES = """
@font-face { font-family: 'Poppins'; font-weight: 400; src: url('../polices/poppins-latin-400-normal.woff2'); }
@font-face { font-family: 'Poppins'; font-weight: 400; font-style: italic; src: url('../polices/poppins-latin-400-italic.woff2'); }
@font-face { font-family: 'Poppins'; font-weight: 600; src: url('../polices/poppins-latin-600-normal.woff2'); }
@font-face { font-family: 'Poppins'; font-weight: 700; src: url('../polices/poppins-latin-700-normal.woff2'); }
@font-face { font-family: 'Poppins'; font-weight: 800; src: url('../polices/poppins-latin-800-normal.woff2'); }
@font-face { font-family: 'Fraunces'; font-weight: 700; src: url('../polices/fraunces-latin-700-normal.woff2'); }
@font-face { font-family: 'Fraunces'; font-weight: 900; src: url('../polices/fraunces-latin-900-normal.woff2'); }
"""

CSS_COMMUN = """
* { box-sizing: border-box; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { font-family: 'Poppins', 'Noto Color Emoji', sans-serif; margin: 0; color: #1F1A17; }
"""


# ── Transformations du HTML produit par Markdown ────────────────────────
def _bulles(contenu):
    out = []
    for p in re.findall(r"<p>(.*?)</p>", contenu, re.S):
        p = p.strip()
        if p.startswith("🙋"):
            out.append(f'<div class="b b-client">{p[1:].strip()}</div>')
        elif p.startswith("💬"):
            out.append(f'<div class="b b-vendeur">{p[1:].strip()}<span class="b-heure">✓✓</span></div>')
    return ('<div class="chat"><div class="chat-entete"><span class="chat-avatar"></span>'
            '<span><strong>Modèle à copier</strong><br><small>adapte le nom et les prix</small></span></div>'
            f'<div class="chat-fil">{"".join(out)}</div></div>')


def encadres(h):
    def remplacer(m):
        contenu = m.group(1).strip()
        premier = re.sub(r"<[^>]+>", "", contenu)[:40].strip()
        if premier.startswith(("💬", "🙋")):
            return _bulles(contenu)
        for emoji, classe, etiquette in [("📣", "post", ""), ("📖", "histoire", ""), ("🚀", "etape", "")]:
            if premier.startswith(emoji):
                contenu = contenu.replace(emoji, "", 1)
                if classe == "post":
                    return ('<div class="post"><div class="post-entete"><span class="post-avatar"></span>'
                            '<span><strong>Ta page Facebook</strong><br><small>Exemple de publication · 🌍</small></span></div>'
                            f'<div class="post-corps">{contenu}</div>'
                            '<div class="post-actions"><span>👍 J\'aime</span><span>💬 Commenter</span><span>↗ Partager</span></div></div>')
                return f'<div class="{classe}">{contenu}</div>'
        if re.match(r"(Conseil|Astuce|Négocie|Pourquoi)", premier):
            return f'<div class="encadre conseil"><span class="ico">💡</span><div>{contenu}</div></div>'
        if re.match(r"(Important|Attention)", premier):
            return f'<div class="encadre alerte"><span class="ico">⚠️</span><div>{contenu}</div></div>'
        if re.match(r"(Le dernier mot|La règle)", premier):
            return f'<div class="encadre etoile"><span class="ico">⭐</span><div>{contenu}</div></div>'
        return f'<blockquote>{contenu}</blockquote>'
    return re.sub(r"<blockquote>(.*?)</blockquote>", remplacer, h, flags=re.S)


def exercices(h):
    return re.sub(r"<h3>Exercice</h3>(.*?)(?=<h2|<h3|\Z)",
                  lambda m: f'<div class="atoi"><div class="atoi-titre">✍️ À toi de jouer</div>{m.group(1)}</div>',
                  h, flags=re.S)


def cases(h):
    h = re.sub(r"<li>\[ \]\s*", '<li class="case">', h)
    return re.sub(r"<ul>(\s*<li class=\"case\">)", r'<ul class="cases">\1', h)


def ouvertures(h, slug, meta):
    scenes = SCENES.get(slug, {}).get("chapitres", [])
    titres = []
    compteur = iter(range(10 ** 6))

    def remplacer(m):
        i = next(compteur)
        brut = m.group(1)
        mc = re.match(r"Chapitre (\d+) — (.*)", brut)
        label, titre = (f"Chapitre {mc.group(1)}", mc.group(2)) if mc else ("", brut)
        titres.append((label, titre))
        illus = scenes[i]() if i < len(scenes) else ""
        return (f'<section class="ouverture{"" if illus else " sans-illus"}">'
                + (f'<div class="ouv-illus">{illus}</div>' if illus else "")
                + (f'<div class="ouv-label">{label}</div>' if label else "")
                + f'<h2>{titre}</h2></section>')
    return re.sub(r"<h2>(.*?)</h2>", remplacer, h), titres


def construire(fichier):
    meta, corps = lire(fichier)
    slug = fichier.stem
    # Markdown exige une ligne vide avant une liste : on l'ajoute quand le
    # texte introduit directement la liste (« remplis : » puis « - … »).
    corps = re.sub(r"(?m)^([^\s>|#-].*[^\n])\n(?=(?:- |\d+\. ))", r"\1\n\n", corps)
    # Deux citations séparées par une ligne vide restent deux encadrés distincts.
    corps = re.sub(r"(?m)^(>.*)\n\n(?=>)", r"\1\n\n<div></div>\n\n", corps)
    # Dans une citation, chaque ligne reste une ligne (publication, listes à emoji).
    corps = re.sub(r"(?m)^(> ?\S.*)\n(?=> ?\S)", r"\1  \n", corps)
    h = markdown.markdown(corps, extensions=["tables", "sane_lists"])
    h = cases(exercices(encadres(h)))
    h, titres = ouvertures(h, slug, meta)
    c, f = meta["couleur"], meta["fonce"]
    badges = "".join(f"<span>{html.escape(b.strip())}</span>" for b in meta.get("badges", "").split("|") if b.strip())

    sommaire = "".join(
        f'<li><span class="som-num">{(l.split()[-1] if l else "★")}</span><span><small>{l or "&nbsp;"}</small>{t}</span></li>'
        for l, t in titres)

    variables = f":root {{ --c: {c}; --f: {f}; }}"
    couverture = f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>{html.escape(meta['titre'])}</title>
<style>{POLICES}{CSS_COMMUN}{variables}
@page {{ size: A5; margin: 0; }}
.couverture {{ width: 148mm; height: 210mm; background: var(--f); color: #fff; position: relative; overflow: hidden; display: flex; flex-direction: column; }}
.c-haut {{ padding: 13mm 12mm 0; position: relative; z-index: 2; }}
.marque {{ display: inline-block; font-size: 7.5pt; font-weight: 700; letter-spacing: .18em; text-transform: uppercase; background: rgba(255,255,255,.14); padding: 1.6mm 3.2mm; border-radius: 99px; }}
h1 {{ font-family: 'Fraunces', serif; font-weight: 900; font-size: 25pt; line-height: 1.08; margin: 6mm 0 3.5mm; }}
.sous {{ font-size: 9.5pt; line-height: 1.45; opacity: .92; max-width: 118mm; }}
.badges {{ display: flex; flex-wrap: wrap; gap: 2mm; margin-top: 5mm; }}
.badges span {{ background: #F0A830; color: #1F1A17; font-size: 7.4pt; font-weight: 800; padding: 1.5mm 3mm; border-radius: 99px; }}
.c-illus {{ flex: 1; display: flex; align-items: flex-end; margin-top: 2mm; }}
.c-illus svg {{ width: 100%; height: 100%; display: block; }}
.c-bas {{ position: absolute; left: 0; right: 0; bottom: 0; padding: 3mm 12mm; font-size: 7pt; background: rgba(0,0,0,.28); display: flex; justify-content: space-between; }}
</style></head><body><section class="couverture">
<div class="c-haut"><div class="marque">Le Grenier CI · Guide pratique</div>
<h1>{html.escape(meta['titre'])}</h1><div class="sous">{html.escape(meta['sous_titre'])}</div>
<div class="badges">{badges}</div></div>
<div class="c-illus">{SCENES[slug]['couverture']().replace('xMidYMid meet', 'xMidYMax slice')}</div>
<div class="c-bas"><span>{html.escape(meta['edition'])} · Côte d'Ivoire</span><span>Usage personnel · ne pas partager</span></div>
</section></body></html>"""

    corps_html = f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>{html.escape(meta['titre'])}</title>
<style>{POLICES}{CSS_COMMUN}{variables}
@page {{ size: A5; margin: 14mm 13mm 16mm; }}
body {{ font-size: 9pt; line-height: 1.6; }}
.sommaire h2 {{ font-family: 'Fraunces', serif; font-size: 20pt; color: var(--f); margin: 0 0 1mm; }}
.sommaire .intro {{ color: #736E64; margin-bottom: 3mm; }}
.sommaire ol {{ list-style: none; padding: 0; margin: 0; }}
.sommaire li {{ display: flex; align-items: center; gap: 3.5mm; padding: 1.5mm 0; border-bottom: 1px dashed #DDD9D0; font-weight: 600; font-size: 9.6pt; }}
.sommaire small {{ display: block; font-size: 7pt; color: var(--c); text-transform: uppercase; letter-spacing: .08em; font-weight: 800; }}
.som-num {{ flex: 0 0 7mm; height: 7mm; border-radius: 50%; background: var(--c); color: #fff; display: flex; align-items: center; justify-content: center; font-weight: 800; }}
.ouverture {{ page-break-before: always; margin-bottom: 5mm; }}
.ouv-illus svg {{ width: 100%; height: auto; display: block; border-radius: 4mm; }}
.ouv-label {{ display: inline-block; margin-top: 4mm; background: var(--c); color: #fff; font-size: 7.4pt; font-weight: 800; letter-spacing: .14em; text-transform: uppercase; padding: 1.2mm 3mm; border-radius: 99px; }}
.ouverture h2 {{ font-family: 'Fraunces', serif; font-weight: 900; font-size: 18pt; line-height: 1.15; color: var(--f); margin: 2.5mm 0 0; }}
.sans-illus {{ background: var(--f); color: #fff; border-radius: 4mm; padding: 7mm 6mm; }}
.sans-illus h2 {{ color: #fff; margin: 0; }}
h3 {{ font-size: 10.6pt; font-weight: 800; color: var(--f); margin: 5.5mm 0 1.8mm; break-after: avoid; page-break-after: avoid; }}
h3 + * {{ break-before: avoid; }}
p {{ margin: 0 0 2.8mm; }}
ul, ol {{ margin: 0 0 3mm; padding-left: 5mm; }}
li {{ margin-bottom: 1.1mm; }}
li::marker {{ color: var(--c); font-weight: 800; }}
strong {{ font-weight: 700; color: #111; }}
code {{ background: #F1EDE4; padding: .2mm 1.2mm; border-radius: 1mm; font-size: 8.4pt; }}
table {{ width: 100%; border-collapse: separate; border-spacing: 0; margin: 3mm 0 4.5mm; font-size: 8pt; page-break-inside: avoid; border: 1px solid #E4DED3; border-radius: 3mm; overflow: hidden; }}
th {{ background: var(--c); color: #fff; text-align: left; padding: 2mm; font-weight: 700; }}
td {{ padding: 2mm; border-top: 1px solid #EEE9E0; vertical-align: top; height: 7mm; }}
tr:nth-child(even) td {{ background: #FAF8F3; }}
ul.cases {{ list-style: none; padding-left: 0; }}
li.case {{ position: relative; padding-left: 7mm; margin-bottom: 1.8mm; }}
li.case::before {{ content: ''; position: absolute; left: 0; top: .6mm; width: 3.6mm; height: 3.6mm; border: 1.6px solid var(--c); border-radius: 1mm; background: #fff; }}
.encadre {{ display: flex; gap: 3mm; margin: 4mm 0; padding: 3mm 3.5mm; border-radius: 3mm; page-break-inside: avoid; }}
.encadre .ico {{ flex: 0 0 7mm; height: 7mm; border-radius: 50%; background: #fff; display: flex; align-items: center; justify-content: center; font-size: 10pt; }}
.encadre p:last-child {{ margin: 0; }}
.conseil {{ background: #E7F4EC; }} .alerte {{ background: #FDEBE6; }} .etoile {{ background: #FFF3D6; }}
blockquote {{ margin: 4mm 0; padding: 3mm 4mm; border-left: 3px solid #F0A830; background: #F7F4EE; border-radius: 0 3mm 3mm 0; font-style: italic; page-break-inside: avoid; }}
blockquote p:last-child {{ margin: 0; }}
.histoire {{ margin: 4.5mm 0; padding: 3.5mm 4mm 3mm 13mm; border-radius: 3mm; background: #FDF6E8; position: relative; page-break-inside: avoid; }}
.histoire::before {{ content: '📖'; position: absolute; left: 3.5mm; top: 3mm; font-size: 13pt; }}
.histoire p:last-child {{ margin: 0; }}
.etape {{ margin: 5mm 0; padding: 4mm; border-radius: 3mm; background: var(--f); color: #fff; page-break-inside: avoid; }}
.etape strong {{ color: #F0A830; }} .etape p {{ margin: 0; }}
.etape::before {{ content: '🚀'; font-size: 13pt; margin-right: 2mm; float: left; }}
.chat {{ margin: 4mm 0; border-radius: 3.5mm; overflow: hidden; background: #ECE5DD; page-break-inside: avoid; border: 1px solid #DDD5CA; }}
.chat-entete {{ background: #075E54; color: #fff; padding: 2mm 3mm; display: flex; gap: 2.5mm; align-items: center; font-size: 8pt; line-height: 1.25; }}
.chat-entete strong {{ color: #fff; }}
.chat-entete small {{ opacity: .8; font-size: 6.8pt; }}
.chat-avatar {{ width: 6.5mm; height: 6.5mm; border-radius: 50%; background: #F0A830; flex: 0 0 auto; }}
.chat-fil {{ padding: 3mm; display: flex; flex-direction: column; gap: 1.8mm;
  background-image: radial-gradient(rgba(0,0,0,.05) 1px, transparent 1px); background-size: 3mm 3mm; }}
.b {{ max-width: 84%; padding: 2mm 3mm; border-radius: 2.5mm; font-size: 8.4pt; line-height: 1.45; box-shadow: 0 .3mm .6mm rgba(0,0,0,.12); }}
.b-client {{ background: #fff; align-self: flex-start; border-top-left-radius: 0; }}
.b-vendeur {{ background: #DCF8C6; align-self: flex-end; border-top-right-radius: 0; }}
.b-heure {{ display: block; text-align: right; font-size: 6.5pt; color: #34B7F1; margin-top: .5mm; }}
.post {{ margin: 4mm 0; border: 1px solid #DADDE1; border-radius: 3mm; overflow: hidden; background: #fff; page-break-inside: avoid; }}
.post-entete {{ display: flex; gap: 2.5mm; align-items: center; padding: 2.5mm 3mm; font-size: 8pt; line-height: 1.25; }}
.post-entete small {{ color: #65676B; font-size: 6.8pt; }}
.post-avatar {{ width: 7mm; height: 7mm; border-radius: 50%; background: var(--c); flex: 0 0 auto; }}
.post-corps {{ padding: 0 3.5mm 2mm; font-size: 8.6pt; }}
.post-corps p {{ margin: 0 0 1.2mm; }}
.post-actions {{ display: flex; justify-content: space-around; border-top: 1px solid #E4E6EB; padding: 1.8mm 0; font-size: 7.6pt; color: #65676B; font-weight: 600; }}
.atoi {{ margin: 5mm 0; padding: 3.5mm 4mm; border: 1.8px dashed var(--c); border-radius: 3.5mm; background: #fff; page-break-inside: avoid; }}
.atoi-titre {{ display: inline-block; background: var(--c); color: #fff; font-weight: 800; font-size: 8.4pt; padding: 1mm 3mm; border-radius: 99px; margin-bottom: 2.5mm; }}
.atoi p:last-child, .atoi ul:last-child, .atoi table:last-child {{ margin-bottom: 0; }}
</style></head><body>
<section class="sommaire"><h2>Au programme</h2>
<div class="intro">Lis un chapitre par jour et coche les cases au fur et à mesure.</div><ol>{sommaire}</ol></section>
{h}
</body></html>"""
    DIST.mkdir(exist_ok=True)
    (DIST / f"{slug}-couverture.html").write_text(couverture, encoding="utf-8")
    (DIST / f"{slug}-corps.html").write_text(corps_html, encoding="utf-8")
    return slug, meta["titre"]


def assembler(slug):
    sortie = PdfWriter()
    for partie in ("couverture", "corps"):
        for page in PdfReader(DIST / f"{slug}-{partie}.pdf").pages:
            sortie.add_page(page)
    sortie.add_metadata({"/Title": slug, "/Author": "Le Grenier CI"})
    with open(DIST / f"{slug}.pdf", "wb") as f:
        sortie.write(f)
    for partie in ("couverture", "corps"):
        (DIST / f"{slug}-{partie}.pdf").unlink()
    print(f"PDF : dist/{slug}.pdf ({len(PdfReader(DIST / f'{slug}.pdf').pages)} pages)")


if __name__ == "__main__":
    guides = [construire(f) for f in sorted(SRC.glob("*.md"))]
    subprocess.run(["node", str(RACINE / "build-pdf.js")] + [s for s, _ in guides], check=True)
    for slug, _ in guides:
        assembler(slug)
