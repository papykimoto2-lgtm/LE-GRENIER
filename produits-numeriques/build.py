"""Construit les guides PDF illustrés de la boutique numérique.

Usage : python3 produits-numeriques/build.py
Entrée : produits-numeriques/src/guide-*.md et livre-*.md (en-tête : titre,
         sous_titre, edition, couleur, fonce, badges « a | b | c » ; options :
         marque, sommaire_titre, sommaire_intro, style: recit)
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
  ## Partie I — …  /  ## Prologue — …  /  ## Épilogue — …  (récits)
"""
import html
import pathlib
import re
import subprocess
import sys

import json

import markdown
from PIL import Image
from pypdf import PdfReader, PdfWriter

RACINE = pathlib.Path(__file__).parent
SRC = RACINE / "src"
DIST = RACINE / "dist"
PHOTOS_BRUTES = RACINE / "photos-brutes"
PHOTOS = RACINE / "photos"
# Signature de la préface (à confirmer par l'auteur).
AUTEUR = "Cyrille KESSIE · Fondateur de SANIX AFRICA Technologies et de Le Grenier CI"
sys.path.insert(0, str(RACINE))
from scenes import SCENES  # noqa: E402


def photo(ident, w, h, fy=0.5, fx=0.5, zoom=1.0):
    """Recadre une photo au format w×h autour du point (fx, fy) ; renvoie son chemin relatif à dist/."""
    PHOTOS.mkdir(exist_ok=True)
    sortie = PHOTOS / f"{ident}-{w}x{h}-{fx}-{fy}-{zoom}.jpg"
    if not sortie.exists():
        img = Image.open(PHOTOS_BRUTES / f"{ident}.jpg").convert("RGB")
        iw, ih = img.size
        ratio = w / h
        cw, ch = (iw, iw / ratio) if iw / ih < ratio else (ih * ratio, ih)
        cw, ch = cw / zoom, ch / zoom
        x0 = min(max(fx * iw - cw / 2, 0), iw - cw)
        y0 = min(max(fy * ih - ch / 2, 0), ih - ch)
        img.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize((w, h), Image.LANCZOS).save(sortie, quality=86)
    return f"../photos/{sortie.name}"


def credits_photos(idents):
    tous = json.loads((PHOTOS_BRUTES / "credits.json").read_text(encoding="utf-8"))
    return ", ".join(sorted({tous[i]["auteur"] for i in idents if i in tous}))


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


# Récit (style: recit) : texte justifié, lettrine, chapitres sobres, pages de partie.
CSS_RECIT = """
body { font-size: 9.4pt; line-height: 1.68; }
p { text-align: justify; hyphens: auto; }
.sommaire li { padding: .7mm 0; font-size: 8.8pt; }
.sommaire li.som-partie { margin-top: 2mm; border-bottom: 2px solid var(--c); }
.sommaire li.som-partie .som-num { background: var(--f); }
.sans-illus { background: none; color: inherit; border-radius: 0; padding: 14mm 0 2mm; border-bottom: 2px solid #F0A830; }
.sans-illus h2 { color: var(--f); font-size: 20pt; }
.ouverture + p { font-family: 'Fraunces', serif; font-weight: 700; font-size: 13pt; line-height: 1.35; color: var(--c); text-align: left; }
.sommaire li { break-inside: avoid; }
.ouverture + p strong { color: inherit; }
.pf-texte { font-size: 8.8pt; }
.partie { page-break-before: always; page-break-after: always; height: 178mm; display: flex; flex-direction: column;
  background: var(--f); color: #fff; border-radius: 4mm; overflow: hidden; }
.partie-photo { width: 100%; height: 100mm; object-fit: cover; display: block; }
.partie-texte { flex: 1; display: flex; flex-direction: column; justify-content: center; padding: 0 9mm; }
.partie .ouv-label { background: #F0A830; color: #1F1A17; align-self: flex-start; }
.partie h2 { font-family: 'Fraunces', serif; font-weight: 900; font-size: 26pt; line-height: 1.05; margin: 3mm 0 0; color: #fff; }
blockquote { font-style: normal; }
.citation-forte { font-family: 'Fraunces', serif; font-weight: 700; font-size: 12pt; line-height: 1.4; color: var(--f);
  text-align: center; margin: 6mm 4mm; padding: 4mm 0; border-top: 1px solid #F0A830; border-bottom: 1px solid #F0A830; }
"""


# ── Transformations du HTML produit par Markdown ────────────────────────
CHAT_TITRE = ("Modèle à copier", "adapte le nom et les prix")


def _bulles(contenu):
    out = []
    for p in re.findall(r"<p>(.*?)</p>", contenu, re.S):
        p = p.strip()
        if p.startswith("🙋"):
            out.append(f'<div class="b b-client">{p[1:].strip()}</div>')
        elif p.startswith("💬"):
            out.append(f'<div class="b b-vendeur">{p[1:].strip()}<span class="b-heure">✓✓</span></div>')
    return ('<div class="chat"><div class="chat-entete"><span class="chat-avatar"></span>'
            f'<span><strong>{CHAT_TITRE[0]}</strong><br><small>{CHAT_TITRE[1]}</small></span></div>'
            f'<div class="chat-fil">{"".join(out)}</div></div>')


def encadres(h):
    def remplacer(m):
        contenu = m.group(1).strip()
        premier = re.sub(r"<[^>]+>", "", contenu)[:40].strip()
        if premier.startswith(("💬", "🙋")):
            return _bulles(contenu)
        if premier.startswith("❝"):
            return f'<div class="citation-forte">{contenu.replace("❝", "", 1)}</div>'
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
    # Récit : les photos sont rattachées à une étiquette (« Partie I »…).
    par_label = SCENES.get(slug, {}).get("par_label", {})
    titres = []
    compteur = iter(range(10 ** 6))

    def remplacer(m):
        i = next(compteur)
        brut = m.group(1)
        mc = re.match(r"(Chapitre \d+|Partie [IVX]+|Prologue|Épilogue|Annexe) — (.*)", brut)
        label, titre = (mc.group(1), mc.group(2)) if mc else ("", brut)
        titres.append((label, titre))
        sc = par_label.get(label) if par_label else (scenes[i] if i < len(scenes) else None)
        if label.startswith("Partie"):
            photo_partie = f'<img class="partie-photo" src="{photo(sc[1], 1000, 900, sc[2])}" alt="">' if sc else ""
            return (f'<section class="partie">{photo_partie}<div class="partie-texte">'
                    f'<div class="ouv-label">{label}</div><h2>{titre}</h2></div></section>')
        if isinstance(sc, tuple):
            illus = f'<img class="ouv-photo" src="{photo(sc[1], 1500, 700, sc[2])}" alt="">'
        else:
            illus = sc() if sc else ""
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
    global CHAT_TITRE
    CHAT_TITRE = tuple(meta.get("bulles", "Modèle à copier | adapte le nom et les prix").split(" | "))
    # Récit : un retour à la ligne dans le texte reste un retour à la ligne (phrases courtes, rythme).
    extensions = ["tables", "sane_lists"] + (["nl2br"] if meta.get("style") == "recit" else [])
    h = markdown.markdown(corps, extensions=extensions)
    h = re.sub(r"⟦(.*?)⟧", r'<mark class="acompleter">\1</mark>', h)
    h = cases(exercices(encadres(h)))
    h, titres = ouvertures(h, slug, meta)
    c, f = meta["couleur"], meta["fonce"]
    badges = "".join(f"<span>{html.escape(b.strip())}</span>" for b in meta.get("badges", "").split("|") if b.strip())

    def ligne_sommaire(l, t):
        classe = ' class="som-partie"' if l.startswith("Partie") else ""
        num = l.split()[-1] if l.startswith(("Chapitre", "Partie")) else "★"
        return f'<li{classe}><span class="som-num">{num}</span><span><small>{l or "&nbsp;"}</small>{t}</span></li>'
    sommaire = "".join(ligne_sommaire(l, t) for l, t in titres)

    variables = f":root {{ --c: {c}; --f: {f}; }}"
    cp = SCENES[slug].get("couverture_photo")
    if cp:
        fond_couverture = (f'<img class="c-photo" src="{photo(cp[0], 1480, 2100, cp[2], cp[1])}" alt="">'
                           '<div class="c-degrade"></div>')
    else:
        fond_couverture = f"<div class=\"c-illus\">{SCENES[slug]['couverture']().replace('xMidYMid meet', 'xMidYMax slice')}</div>"
    # Titre court (style best-seller) : très grand, la seconde partie en or.
    titre_classe, titre_html = "", html.escape(meta["titre"])
    if len(meta["titre"]) <= 28:
        titre_classe = ' class="grand"'
        if ", " in meta["titre"]:
            a, b = meta["titre"].split(", ", 1)
            titre_html = f'{html.escape(a)},<br><span class="or">{html.escape(b)}</span>'
    # Portrait de l'auteur en couverture : le titre passe en bas pour dégager le visage.
    css_bas = ("""
.couverture { justify-content: flex-end !important; }
.c-haut { padding: 0 12mm 21mm !important; }
.c-degrade { background: linear-gradient(0deg, var(--f) 0%, color-mix(in srgb, var(--f) 90%, transparent) 30%, transparent 55%) !important; }
""" if SCENES[slug].get("titre_en_bas") else "")
    idents = ([sc[1] for sc in SCENES[slug].get("chapitres", []) if isinstance(sc, tuple)]
              + [sc[1] for sc in SCENES[slug].get("par_label", {}).values()] + ([cp[0]] if cp else []))
    marque = html.escape(meta.get("marque", "Le Grenier CI · Guide pratique"))
    css_recit = CSS_RECIT if meta.get("style") == "recit" else ""
    fichier_preface = SRC / f"preface-{slug}.md"
    if not fichier_preface.exists():
        fichier_preface = SRC / "preface.md"
    preface_md = fichier_preface.read_text(encoding="utf-8").replace("{titre}", meta["titre"])
    preface = ""
    if (PHOTOS_BRUTES / "auteur.jpg").exists():
        preface = (f'<section class="preface"><div class="pf-label">Préface</div><h2>Le mot de l\'auteur</h2>'
                   f'<div class="pf-grille"><img class="pf-photo" src="{photo("auteur", 800, 1000, 0.5, 0.72, 1.45)}" alt="">'
                   f'<div class="pf-texte">{markdown.markdown(preface_md)}'
                   f'<div class="pf-signature">{html.escape(AUTEUR)}</div></div></div></section>')
    couverture = f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>{html.escape(meta['titre'])}</title>
<style>{POLICES}{CSS_COMMUN}{variables}{css_bas}
@page {{ size: A5; margin: 0; }}
.couverture {{ width: 148mm; height: 210mm; background: var(--f); color: #fff; position: relative; overflow: hidden; display: flex; flex-direction: column; }}
.c-haut {{ padding: 13mm 12mm 0; position: relative; z-index: 2; }}
.marque {{ display: inline-block; font-size: 7.5pt; font-weight: 700; letter-spacing: .18em; text-transform: uppercase; background: rgba(255,255,255,.14); padding: 1.6mm 3.2mm; border-radius: 99px; }}
h1 {{ font-family: 'Fraunces', serif; font-weight: 900; font-size: 25pt; line-height: 1.08; margin: 6mm 0 3.5mm; }}
h1.grand {{ font-size: 40pt; line-height: 1; margin: 5mm 0 4mm; }}
h1 .or {{ color: #F0A830; }}
.sous {{ font-size: 9.5pt; line-height: 1.45; opacity: .92; max-width: 118mm; }}
.badges {{ display: flex; flex-wrap: wrap; gap: 2mm; margin-top: 5mm; }}
.badges span {{ background: #F0A830; color: #1F1A17; font-size: 7.4pt; font-weight: 800; padding: 1.5mm 3mm; border-radius: 99px; }}
.c-illus {{ flex: 1; display: flex; align-items: flex-end; margin-top: 2mm; }}
.c-illus svg {{ width: 100%; height: 100%; display: block; }}
.c-photo {{ position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; z-index: 0; }}
.c-degrade {{ position: absolute; inset: 0; z-index: 1; background: linear-gradient(180deg, var(--f) 0%, color-mix(in srgb, var(--f) 88%, transparent) 30%, transparent 58%, transparent 80%, rgba(0,0,0,.55) 100%); }}
.c-bas {{ z-index: 2; position: absolute; left: 0; right: 0; bottom: 0; padding: 3mm 12mm; font-size: 7pt; background: rgba(0,0,0,.28); display: flex; justify-content: space-between; }}
</style></head><body><section class="couverture">
<div class="c-haut"><div class="marque">{marque}</div>
<h1{titre_classe}>{titre_html}</h1><div class="sous">{html.escape(meta['sous_titre'])}</div>
<div class="badges">{badges}</div></div>
{fond_couverture}
<div class="c-bas"><span>{html.escape(meta['edition'])} · Côte d'Ivoire</span><span>Usage personnel · ne pas partager</span></div>
</section></body></html>"""

    corps_html = f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>{html.escape(meta['titre'])}</title>
<style>{POLICES}{CSS_COMMUN}{variables}
@page {{ size: A5; margin: 14mm 13mm 16mm; }}
body {{ font-size: 9pt; line-height: 1.6; }}
.sommaire h2 {{ font-family: 'Fraunces', serif; font-size: 20pt; color: var(--f); margin: 0 0 1mm; }}
.sommaire .intro {{ color: #736E64; margin-bottom: 3mm; }}
.sommaire ol {{ list-style: none; padding: 0; margin: 0; }}
.sommaire li {{ display: flex; align-items: center; gap: 3.5mm; padding: 1.1mm 0; border-bottom: 1px dashed #DDD9D0; font-weight: 600; font-size: 9.6pt; }}
.sommaire small {{ display: block; font-size: 7pt; color: var(--c); text-transform: uppercase; letter-spacing: .08em; font-weight: 800; }}
.som-num {{ flex: 0 0 7mm; height: 7mm; border-radius: 50%; background: var(--c); color: #fff; display: flex; align-items: center; justify-content: center; font-weight: 800; }}
.ouverture {{ page-break-before: always; margin-bottom: 5mm; }}
.ouv-illus svg {{ width: 100%; height: auto; display: block; border-radius: 4mm; }}
.ouv-photo {{ width: 100%; height: auto; aspect-ratio: 1500 / 700; object-fit: cover; display: block; border-radius: 4mm; }}
.preface {{ page-break-after: always; }}
.pf-label {{ display: inline-block; background: var(--c); color: #fff; font-size: 7.4pt; font-weight: 800; letter-spacing: .14em; text-transform: uppercase; padding: 1.2mm 3mm; border-radius: 99px; }}
.preface h2 {{ font-family: 'Fraunces', serif; font-weight: 900; font-size: 19pt; color: var(--f); margin: 2.5mm 0 4mm; }}
.pf-photo {{ float: right; width: 46mm; height: 57.5mm; object-fit: cover; border-radius: 3mm; margin: 0 0 3mm 4mm; box-shadow: 0 1mm 3mm rgba(0,0,0,.18); }}
.pf-texte {{ font-size: 9.2pt; }}
.pf-signature {{ margin-top: 4mm; padding-top: 2.5mm; border-top: 2px solid var(--c); font-family: 'Fraunces', serif; font-weight: 700; color: var(--f); font-size: 10pt; clear: both; }}
mark.acompleter {{ background: #FFE58A; color: #6B4A00; font-weight: 700; padding: .3mm 1.5mm; border-radius: 1mm; }}
.credits {{ margin-top: 8mm; font-size: 7pt; color: #8A857B; border-top: 1px solid #E4DED3; padding-top: 2mm; }}
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
{css_recit}
</style></head><body>
{preface}
<section class="sommaire"><h2>{html.escape(meta.get("sommaire_titre", "Au programme"))}</h2>
<div class="intro">{html.escape(meta.get("sommaire_intro", "Lis un chapitre par jour et coche les cases au fur et à mesure."))}</div><ol>{sommaire}</ol></section>
{h}
<div class="credits">Photos : {html.escape(credits_photos(idents))} (Pexels, licence Pexels). Illustrations : Le Grenier CI.</div>
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
    # « python3 build.py livre » ne reconstruit que les fichiers dont le nom contient « livre ».
    filtre = sys.argv[1] if len(sys.argv) > 1 else ""
    guides = [construire(f) for f in sorted(SRC.glob("guide-*.md")) + sorted(SRC.glob("livre-*.md")) if filtre in f.stem]
    subprocess.run(["node", str(RACINE / "build-pdf.js")] + [s for s, _ in guides], check=True)
    for slug, _ in guides:
        assembler(slug)
