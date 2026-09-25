"""Construit les guides PDF de la boutique numérique.

Usage : python3 produits-numeriques/build.py
Entrée : produits-numeriques/src/*.md (en-tête titre/sous_titre/edition/couleur)
Sortie : produits-numeriques/dist/<slug>.html puis, via build-pdf.js,
         <slug>.pdf (A5) et <slug>-couverture.png
"""
import html
import pathlib
import re

import markdown

RACINE = pathlib.Path(__file__).parent
SRC = RACINE / "src"
DIST = RACINE / "dist"


def lire(fichier):
    texte = fichier.read_text(encoding="utf-8")
    entete, corps = re.match(r"^---\n(.*?)\n---\n(.*)$", texte, re.S).groups()
    meta = dict(ligne.split(": ", 1) for ligne in entete.splitlines())
    return meta, corps


def construire(fichier):
    meta, corps = lire(fichier)
    # Markdown exige une ligne vide avant une liste : on l'ajoute quand le
    # texte introduit directement la liste (« remplis : » puis « - … »).
    corps = re.sub(r"(?m)^([^\s>|#-].*[^\n])\n(?=(?:- |\d+\. ))", r"\1\n\n", corps)
    contenu = markdown.markdown(corps, extensions=["tables", "sane_lists"])
    titres = re.findall(r"<h2>(.*?)</h2>", contenu)
    contenu = re.sub(r"<h2>", '<h2 class="chapitre">', contenu)
    sommaire = "".join(f"<li>{t}</li>" for t in titres)
    couleur = meta["couleur"]
    page = f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<title>{html.escape(meta['titre'])}</title>
<style>
  @page {{ size: A5; margin: 16mm 14mm 18mm; }}
  @page :first {{ margin: 0; }}
  :root {{ --c: {couleur}; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: 'DejaVu Sans', 'Liberation Sans', Arial, sans-serif; font-size: 9.6pt; line-height: 1.55; color: #1A1916; margin: 0; }}
  .couverture {{ height: 210mm; width: 148mm; background: var(--c); color: #fff; padding: 22mm 16mm; display: flex; flex-direction: column; page-break-after: always; position: relative; overflow: hidden; }}
  .couverture::after {{ content: ''; position: absolute; right: -40mm; bottom: -40mm; width: 120mm; height: 120mm; border-radius: 50%; background: rgba(255,255,255,.08); }}
  .couverture .marque {{ font-size: 9pt; letter-spacing: .2em; text-transform: uppercase; opacity: .85; }}
  .couverture h1 {{ font-size: 25pt; line-height: 1.15; margin: 24mm 0 8mm; }}
  .couverture .sous {{ font-size: 11.5pt; line-height: 1.45; opacity: .92; }}
  .couverture .bas {{ margin-top: auto; font-size: 9pt; opacity: .85; position: relative; z-index: 1; }}
  .couverture .bande {{ width: 22mm; height: 3px; background: #F0A830; margin-top: 8mm; }}
  .sommaire {{ page-break-after: always; }}
  .sommaire h2 {{ font-size: 15pt; color: var(--c); border: 0; margin-top: 0; }}
  .sommaire ul {{ padding-left: 0; list-style: none; }}
  .sommaire li {{ margin: 2.2mm 0; font-size: 10.5pt; }}
  h2.chapitre {{ page-break-before: always; font-size: 15pt; color: var(--c); border-bottom: 2px solid var(--c); padding-bottom: 2mm; margin: 0 0 5mm; }}
  h3 {{ font-size: 11pt; color: var(--c); margin: 6mm 0 2mm; break-after: avoid; page-break-after: avoid; }}
  h3 + p, h3 + ul, h3 + ol, h3 + table {{ break-before: avoid; }}
  p {{ margin: 0 0 3mm; }}
  ul, ol {{ margin: 0 0 3mm; padding-left: 5.5mm; }}
  li {{ margin-bottom: 1.2mm; }}
  blockquote {{ margin: 4mm 0; padding: 3mm 4mm; background: #F4F2EE; border-left: 3px solid #F0A830; border-radius: 2mm; page-break-inside: avoid; }}
  blockquote p:last-child {{ margin-bottom: 0; }}
  table {{ width: 100%; border-collapse: collapse; margin: 3mm 0 5mm; font-size: 8.4pt; page-break-inside: avoid; }}
  th {{ background: var(--c); color: #fff; text-align: left; padding: 1.8mm 2mm; }}
  td {{ padding: 1.8mm 2mm; border-bottom: 1px solid #DDD9D0; vertical-align: top; }}
  tr:nth-child(even) td {{ background: #FAFAF7; }}
  strong {{ color: #111; }}
  code {{ background: #F4F2EE; padding: 0 1mm; border-radius: 1mm; font-size: 8.8pt; }}
</style></head><body>
<section class="couverture">
  <div class="marque">Le Grenier CI · Guides pratiques</div>
  <h1>{html.escape(meta['titre'])}</h1>
  <div class="sous">{html.escape(meta['sous_titre'])}</div>
  <div class="bande"></div>
  <div class="bas">{html.escape(meta['edition'])} · Usage personnel — merci de ne pas partager ce fichier.</div>
</section>
<section class="sommaire"><h2>Sommaire</h2><ul>{sommaire}</ul></section>
{contenu}
</body></html>"""
    DIST.mkdir(exist_ok=True)
    sortie = DIST / (fichier.stem + ".html")
    sortie.write_text(page, encoding="utf-8")
    print("HTML :", sortie.relative_to(RACINE))


if __name__ == "__main__":
    for f in sorted(SRC.glob("*.md")):
        construire(f)
