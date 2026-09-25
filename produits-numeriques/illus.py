"""Kit d'illustrations vectorielles (SVG) pour les guides Le Grenier CI.

Style : aplats, formes arrondies, personnages ivoiriens, palette par guide.
Chaque fonction renvoie un fragment SVG ; `scene()` l'emballe dans un <svg>.
"""
import itertools
import math

_ids = itertools.count(1)


def uid(prefixe):
    """Identifiant unique : plusieurs SVG cohabitent dans un même document."""
    return f"{prefixe}{next(_ids)}"

PEAUX = ["#5A3520", "#6E4226", "#8A5530", "#A36A3C"]
ENCRE = "#1F1A17"


def scene(contenu, w=600, h=400, fond=None, extra=""):
    fond_svg = f'<rect width="{w}" height="{h}" fill="{fond}"/>' if fond else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
            f'preserveAspectRatio="xMidYMid meet" {extra}>{fond_svg}{contenu}</svg>')


def g(contenu, x=0, y=0, s=1, r=0):
    rot = f" rotate({r})" if r else ""
    return f'<g transform="translate({x},{y}) scale({s}){rot}">{contenu}</g>'


# ── Décors ──────────────────────────────────────────────────────────────
def blob(cx, cy, r, couleur, seed=0, opacite=1):
    pts = []
    for i in range(8):
        a = i / 8 * 2 * math.pi
        k = 1 + 0.12 * math.sin(i * 2.3 + seed) + 0.08 * math.cos(i * 1.7 + seed * 2)
        pts.append((cx + r * k * math.cos(a), cy + r * k * math.sin(a)))
    m0 = ((pts[-1][0] + pts[0][0]) / 2, (pts[-1][1] + pts[0][1]) / 2)
    d = f"M{m0[0]:.1f},{m0[1]:.1f} "
    for i in range(8):
        p0, p1 = pts[i], pts[(i + 1) % 8]
        mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
        d += f"Q{p0[0]:.1f},{p0[1]:.1f} {mx:.1f},{my:.1f} "
    return f'<path d="{d}Z" fill="{couleur}" opacity="{opacite}"/>'


def wax(x, y, w, h, c1, c2, pas=34, id_=None):
    """Motif pagne wax (cercles concentriques + losanges) dans un rectangle."""
    id_ = id_ or uid("wax")
    motif = (f'<pattern id="{id_}" width="{pas}" height="{pas}" patternUnits="userSpaceOnUse">'
             f'<rect width="{pas}" height="{pas}" fill="{c1}"/>'
             f'<circle cx="{pas/2}" cy="{pas/2}" r="{pas*0.34}" fill="none" stroke="{c2}" stroke-width="{pas*0.07}"/>'
             f'<circle cx="{pas/2}" cy="{pas/2}" r="{pas*0.14}" fill="{c2}"/>'
             f'<path d="M0,0 L{pas*0.18},0 L0,{pas*0.18}Z M{pas},{pas} L{pas*0.82},{pas} L{pas},{pas*0.82}Z '
             f'M{pas},0 L{pas},{pas*0.18} L{pas*0.82},0Z M0,{pas} L0,{pas*0.82} L{pas*0.18},{pas}Z" fill="{c2}"/>'
             f'</pattern>')
    return f'<defs>{motif}</defs><rect x="{x}" y="{y}" width="{w}" height="{h}" fill="url(#{id_})"/>'


def points(x, y, cols, rows, couleur, pas=14, r=2.2):
    return "".join(f'<circle cx="{x+i*pas}" cy="{y+j*pas}" r="{r}" fill="{couleur}"/>'
                   for i in range(cols) for j in range(rows))


def etincelle(x, y, t, couleur):
    return (f'<path d="M{x},{y-t} Q{x+t*0.18},{y-t*0.18} {x+t},{y} Q{x+t*0.18},{y+t*0.18} {x},{y+t} '
            f'Q{x-t*0.18},{y+t*0.18} {x-t},{y} Q{x-t*0.18},{y-t*0.18} {x},{y-t}Z" fill="{couleur}"/>')


def soleil(x, y, r, couleur):
    rayons = "".join(
        f'<line x1="{x+math.cos(a)*(r+8):.1f}" y1="{y+math.sin(a)*(r+8):.1f}" '
        f'x2="{x+math.cos(a)*(r+20):.1f}" y2="{y+math.sin(a)*(r+20):.1f}" stroke="{couleur}" stroke-width="5" stroke-linecap="round"/>'
        for a in [i * math.pi / 4 for i in range(8)])
    return f'<circle cx="{x}" cy="{y}" r="{r}" fill="{couleur}"/>{rayons}'


def plante(x, y, s=1, pot="#C8643B", feuille="#2E8B57"):
    return g(f'''
      <path d="M0,0 C-30,-40 -40,-80 -8,-110 C-5,-70 0,-40 0,0Z" fill="{feuille}"/>
      <path d="M0,0 C30,-30 55,-60 40,-100 C20,-70 5,-40 0,0Z" fill="{feuille}" opacity=".85"/>
      <path d="M0,0 C-10,-50 5,-90 22,-125 C25,-80 15,-40 0,0Z" fill="{feuille}" opacity=".7"/>
      <path d="M-26,0 L26,0 L20,40 L-20,40Z" fill="{pot}"/>
      <rect x="-30" y="-6" width="60" height="10" rx="4" fill="{pot}"/>''', x, y, s)


# ── Objets ──────────────────────────────────────────────────────────────
def telephone(x, y, w=120, h=220, ecran="", coque=ENCRE, r=0, fond_ecran="#ECE5DD"):
    """Téléphone ; `ecran` est dessiné dans un repère (0,0)-(w-14,h-34)."""
    iw, ih = w - 14, h - 34
    cid = uid("ecr")
    return g(f'''
      <rect x="0" y="0" width="{w}" height="{h}" rx="{w*0.14}" fill="{coque}"/>
      <rect x="7" y="18" width="{iw}" height="{ih}" rx="6" fill="{fond_ecran}"/>
      <rect x="{w/2-14}" y="7" width="28" height="5" rx="2.5" fill="#444"/>
      <clipPath id="{cid}"><rect x="0" y="0" width="{iw}" height="{ih}" rx="6"/></clipPath>
      <g clip-path="url(#{cid})" transform="translate(7,18)">{ecran}</g>''', x, y, 1, r)


def ecran_chat(iw, ih, bulles, entete="#075E54", nom="Ma Boutique"):
    """bulles : liste de (cote 'g'/'d', nb_lignes, texte optionnel court)."""
    out = f'<rect width="{iw}" height="26" fill="{entete}"/><circle cx="14" cy="13" r="8" fill="#F0A830"/>'
    out += f'<text x="27" y="17" font-size="9" font-family="Arial" font-weight="700" fill="#fff">{nom}</text>'
    yy = 36
    for cote, n, txt in bulles:
        bw = iw * 0.68
        bx = 6 if cote == "g" else iw - bw - 6
        bh = 10 + n * 8
        coul = "#fff" if cote == "g" else "#DCF8C6"
        out += f'<rect x="{bx}" y="{yy}" width="{bw}" height="{bh}" rx="6" fill="{coul}"/>'
        if txt:
            out += f'<text x="{bx+6}" y="{yy+13}" font-size="7.5" font-family="Arial" font-weight="700" fill="#075E54">{txt}</text>'
            n -= 1
            base = yy + 20
        else:
            base = yy + 9
        for i in range(n):
            lw = bw - 14 - (18 if i == n - 1 else 0)
            out += f'<rect x="{bx+6}" y="{base+i*8}" width="{lw}" height="3.5" rx="1.7" fill="#9AA5A1"/>'
        yy += bh + 7
    return out


def ecran_catalogue(iw, ih, couleurs):
    out = f'<rect width="{iw}" height="26" fill="#075E54"/>'
    out += '<text x="8" y="17" font-size="9" font-family="Arial" font-weight="700" fill="#fff">Catalogue</text>'
    cw = (iw - 18) / 2
    for i, c in enumerate(couleurs[:6]):
        cx = 6 + (i % 2) * (cw + 6)
        cy = 34 + (i // 2) * (cw + 22)
        out += f'<rect x="{cx}" y="{cy}" width="{cw}" height="{cw}" rx="5" fill="{c}"/>'
        out += f'<rect x="{cx}" y="{cy+cw+4}" width="{cw*0.8}" height="4" rx="2" fill="#555"/>'
        out += f'<rect x="{cx}" y="{cy+cw+11}" width="{cw*0.45}" height="4" rx="2" fill="#1A7A48"/>'
    return out


def sac(x, y, s=1, couleur="#E4572E", anse="#1F1A17"):
    return g(f'''<path d="M-22,-30 C-22,-58 22,-58 22,-30" fill="none" stroke="{anse}" stroke-width="5"/>
      <path d="M-40,-32 L40,-32 L46,30 L-46,30Z" fill="{couleur}"/>
      <rect x="-40" y="-32" width="80" height="8" fill="#000" opacity=".12"/>''', x, y, s)


def etiquette(x, y, s=1, couleur="#F0A830", texte=""):
    t = (f'<text x="24" y="5" font-size="15" font-family="Arial" font-weight="800" fill="{ENCRE}" '
         f'text-anchor="middle">{texte}</text>') if texte else ""
    return g(f'''<path d="M0,0 L14,-16 L62,-16 L62,16 L14,16Z" fill="{couleur}"/>
      <circle cx="12" cy="0" r="4" fill="#fff"/>{t}''', x, y, s, -12)


def pieces(x, y, n=4, s=1, couleur="#F0A830"):
    out = ""
    for i in range(n):
        out += f'<ellipse cx="0" cy="{-i*9}" rx="26" ry="8" fill="#C98A1B"/>'
        out += f'<ellipse cx="0" cy="{-i*9-4}" rx="26" ry="8" fill="{couleur}"/>'
    out += f'<text x="0" y="{-(n-1)*9-1}" font-size="10" font-family="Arial" font-weight="800" fill="#8A5A0B" text-anchor="middle">F</text>'
    return g(out, x, y, s)


def billet(x, y, s=1, r=0, couleur="#7CC49A"):
    return g(f'''<rect x="-40" y="-20" width="80" height="40" rx="4" fill="{couleur}"/>
      <rect x="-34" y="-14" width="68" height="28" rx="3" fill="none" stroke="#fff" stroke-width="2" opacity=".7"/>
      <circle cx="0" cy="0" r="9" fill="#fff" opacity=".75"/>
      <text x="0" y="4" font-size="10" font-family="Arial" font-weight="800" fill="#1F6B45" text-anchor="middle">F</text>''', x, y, s, r)


def colis(x, y, s=1, couleur="#D9A066"):
    return g(f'''<rect x="-35" y="-30" width="70" height="60" rx="4" fill="{couleur}"/>
      <rect x="-35" y="-30" width="70" height="14" fill="#000" opacity=".1"/>
      <rect x="-6" y="-30" width="12" height="60" fill="#fff" opacity=".45"/>''', x, y, s)


def bouclier(x, y, s=1, couleur="#1A7A48"):
    return g(f'''<path d="M0,-40 L34,-28 C34,8 20,30 0,42 C-20,30 -34,8 -34,-28Z" fill="{couleur}"/>
      <path d="M-14,0 L-3,12 L17,-12" fill="none" stroke="#fff" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>''', x, y, s)


def bulle(x, y, w, h, couleur="#fff", queue="g", contenu=""):
    qx = 14 if queue == "g" else w - 14
    return g(f'''<rect x="0" y="0" width="{w}" height="{h}" rx="{min(16,h/2)}" fill="{couleur}"/>
      <path d="M{qx-8},{h-2} L{qx - (10 if queue=='g' else -10)},{h+14} L{qx+8},{h-2}Z" fill="{couleur}"/>{contenu}''', x, y)


def lignes_texte(x, y, w, n, couleur="#9AA5A1", pas=11, ep=5):
    return "".join(f'<rect x="{x}" y="{y+i*pas}" width="{w - (w*0.3 if i == n-1 else 0)}" height="{ep}" rx="{ep/2}" fill="{couleur}"/>' for i in range(n))


def calendrier(x, y, s=1, couleur="#E4572E", coches=18):
    out = f'<rect x="0" y="0" width="150" height="140" rx="10" fill="#fff"/>'
    out += f'<rect x="0" y="0" width="150" height="32" rx="10" fill="{couleur}"/><rect x="0" y="20" width="150" height="12" fill="{couleur}"/>'
    out += f'<circle cx="35" cy="0" r="6" fill="{ENCRE}"/><circle cx="115" cy="0" r="6" fill="{ENCRE}"/>'
    out += '<text x="75" y="22" font-size="13" font-family="Arial" font-weight="800" fill="#fff" text-anchor="middle">30 JOURS</text>'
    for i in range(30):
        cx, cy = 14 + (i % 6) * 24, 44 + (i // 6) * 19
        if i < coches:
            out += f'<path d="M{cx-4},{cy+2} L{cx},{cy+6} L{cx+7},{cy-3}" fill="none" stroke="#1A7A48" stroke-width="3" stroke-linecap="round"/>'
        else:
            out += f'<rect x="{cx-5}" y="{cy-4}" width="11" height="11" rx="2" fill="#E8E3DA"/>'
    return g(out, x, y, s)


def graphique(x, y, valeurs, s=1, couleur="#1A7A48", fleche="#F0A830"):
    out = ""
    mx = max(valeurs)
    for i, v in enumerate(valeurs):
        h = v / mx * 120
        out += f'<rect x="{i*34}" y="{-h}" width="24" height="{h}" rx="4" fill="{couleur}" opacity="{0.45+0.55*i/len(valeurs)}"/>'
    n = len(valeurs)
    out += f'<path d="M-6,-20 C{n*10},-40 {n*20},-90 {n*34-4},-138" fill="none" stroke="{fleche}" stroke-width="6" stroke-linecap="round"/>'
    out += f'<path d="M{n*34-22},-136 L{n*34-2},-142 L{n*34-8},-122Z" fill="{fleche}"/>'
    return g(out, x, y, s)


def appareil_photo(x, y, s=1):
    return g(f'''<rect x="-40" y="-26" width="80" height="54" rx="8" fill="{ENCRE}"/>
      <rect x="-18" y="-36" width="30" height="14" rx="4" fill="{ENCRE}"/>
      <circle cx="0" cy="2" r="18" fill="#555"/><circle cx="0" cy="2" r="11" fill="#8FD3C1"/>
      <circle cx="4" cy="-2" r="4" fill="#fff" opacity=".8"/>''', x, y, s)


def loupe(x, y, s=1, couleur=ENCRE):
    return g(f'''<circle cx="0" cy="0" r="26" fill="#fff" opacity=".35" stroke="{couleur}" stroke-width="8"/>
      <line x1="19" y1="19" x2="46" y2="46" stroke="{couleur}" stroke-width="11" stroke-linecap="round"/>''', x, y, s)


def moto(x, y, s=1, couleur="#E4572E"):
    return g(f'''<circle cx="-55" cy="0" r="24" fill="{ENCRE}"/><circle cx="-55" cy="0" r="10" fill="#bbb"/>
      <circle cx="60" cy="0" r="24" fill="{ENCRE}"/><circle cx="60" cy="0" r="10" fill="#bbb"/>
      <path d="M-60,-20 L-10,-20 L20,-44 L55,-44 L70,-6 L-40,-6Z" fill="{couleur}"/>
      <path d="M40,-44 L52,-74" stroke="{ENCRE}" stroke-width="6" stroke-linecap="round"/>
      <path d="M44,-76 L64,-76" stroke="{ENCRE}" stroke-width="6" stroke-linecap="round"/>
      <rect x="-80" y="-66" width="46" height="40" rx="4" fill="#D9A066"/>
      <rect x="-60" y="-66" width="8" height="40" fill="#fff" opacity=".45"/>''', x, y, s)


def etal(x, y, s=1, c1="#E4572E", c2="#FDF6E8", produits=("#F0A830", "#1A7A48", "#7C3A8A", "#E4572E")):
    bandes = "".join(f'<path d="M{-150+i*50},-150 L{-100+i*50},-150 L{-100+i*50},-120 Q{-125+i*50},-100 {-150+i*50},-120Z" fill="{c1 if i%2==0 else c2}"/>' for i in range(6))
    prods = "".join(f'<rect x="{-130+i*65}" y="{-40}" width="46" height="36" rx="6" fill="{c}"/>' for i, c in enumerate(produits))
    return g(f'''<rect x="-146" y="-120" width="8" height="160" fill="#8A5A2B"/><rect x="138" y="-120" width="8" height="160" fill="#8A5A2B"/>
      {bandes}<rect x="-155" y="0" width="310" height="44" rx="4" fill="#A86B34"/><rect x="-155" y="0" width="310" height="10" fill="#000" opacity=".12"/>
      {prods}''', x, y, s)


# ── Personnages ─────────────────────────────────────────────────────────
def personne(x, y, s=1, peau=PEAUX[1], haut="#1A7A48", bas="#1F1A17", tete="foulard",
             coiffe="#F0A830", pose="telephone", motif=None, lunettes=False, sourire=True):
    """Personnage debout, pieds en (0,0), environ 300 unités de haut."""
    tissu = f'url(#{motif})' if motif else haut
    jambes = (f'<path d="M-24,-130 L-6,-130 L-10,-8 L-26,-8Z" fill="{bas}"/>'
              f'<path d="M6,-130 L24,-130 L26,-8 L10,-8Z" fill="{bas}"/>'
              f'<ellipse cx="-19" cy="-4" rx="15" ry="7" fill="{ENCRE}"/><ellipse cx="19" cy="-4" rx="15" ry="7" fill="{ENCRE}"/>')
    corps = f'<path d="M-36,-228 Q0,-242 36,-228 L42,-122 Q0,-110 -42,-122Z" fill="{tissu}"/>'
    cou = f'<rect x="-8" y="-246" width="16" height="22" rx="6" fill="{peau}"/>'
    visage = f'<ellipse cx="0" cy="-270" rx="27" ry="30" fill="{peau}"/>'
    yeux = ('<circle cx="-9" cy="-272" r="3" fill="#1F1A17"/><circle cx="9" cy="-272" r="3" fill="#1F1A17"/>')
    if lunettes:
        yeux += ('<circle cx="-9" cy="-272" r="8" fill="none" stroke="#1F1A17" stroke-width="2.5"/>'
                 '<circle cx="9" cy="-272" r="8" fill="none" stroke="#1F1A17" stroke-width="2.5"/>'
                 '<line x1="-1" y1="-272" x2="1" y2="-272" stroke="#1F1A17" stroke-width="2.5"/>')
    bouche = ('<path d="M-9,-256 Q0,-248 9,-256" fill="none" stroke="#1F1A17" stroke-width="2.5" stroke-linecap="round"/>'
              if sourire else '<line x1="-6" y1="-254" x2="6" y2="-254" stroke="#1F1A17" stroke-width="2.5" stroke-linecap="round"/>')
    if tete == "foulard":
        cheveux = (f'<path d="M-30,-282 C-38,-322 36,-330 32,-284 C44,-300 30,-338 0,-334 C-34,-338 -46,-300 -30,-282Z" fill="{coiffe}"/>'
                   f'<path d="M22,-322 C44,-338 58,-318 40,-300 C50,-318 34,-326 22,-316Z" fill="{coiffe}"/>'
                   f'<path d="M-30,-290 Q0,-300 30,-290" stroke="#000" stroke-opacity=".15" stroke-width="3" fill="none"/>')
    elif tete == "afro":
        cheveux = f'<circle cx="0" cy="-286" r="36" fill="#1F1A17"/><ellipse cx="0" cy="-266" rx="27" ry="24" fill="{peau}"/>'
        visage = ""
    elif tete == "tresses":
        cheveux = (f'<path d="M-28,-280 C-30,-316 30,-316 28,-280 C22,-298 -22,-298 -28,-280Z" fill="#1F1A17"/>'
                   + "".join(f'<path d="M{-26+i*10},-292 L{-30+i*12},-228" stroke="#1F1A17" stroke-width="5" stroke-linecap="round"/>' for i in (0, 5)))
    elif tete == "casquette":
        cheveux = (f'<path d="M-28,-282 C-30,-312 30,-312 28,-282Z" fill="{coiffe}"/>'
                   f'<path d="M20,-286 L54,-282 L22,-276Z" fill="{coiffe}"/>')
    else:  # court
        cheveux = '<path d="M-27,-278 C-30,-306 30,-306 27,-278 C20,-292 -20,-292 -27,-278Z" fill="#1F1A17"/>'

    if pose == "telephone":
        bras = (f'<path d="M-36,-222 Q-54,-170 -34,-150 L-22,-162 Q-34,-176 -24,-210Z" fill="{tissu}"/>'
                f'<path d="M34,-222 Q58,-180 30,-178 L22,-190 Q34,-192 24,-212Z" fill="{tissu}"/>'
                f'<circle cx="24" cy="-184" r="9" fill="{peau}"/>'
                f'<rect x="10" y="-222" width="26" height="44" rx="5" fill="{ENCRE}" transform="rotate(-12,23,-200)"/>'
                f'<rect x="14" y="-216" width="18" height="30" rx="2" fill="#8FD3C1" transform="rotate(-12,23,-200)"/>'
                f'<circle cx="-30" cy="-150" r="9" fill="{peau}"/>')
    elif pose == "bras_leves":
        bras = (f'<path d="M-34,-222 Q-70,-250 -62,-300 L-48,-298 Q-52,-260 -24,-236Z" fill="{tissu}"/>'
                f'<path d="M34,-222 Q70,-250 62,-300 L48,-298 Q52,-260 24,-236Z" fill="{tissu}"/>'
                f'<circle cx="-56" cy="-304" r="10" fill="{peau}"/><circle cx="56" cy="-304" r="10" fill="{peau}"/>')
    elif pose == "carton":
        bras = (f'<path d="M-36,-222 Q-50,-180 -20,-170 L-16,-184 Q-32,-190 -26,-212Z" fill="{tissu}"/>'
                f'<path d="M36,-222 Q50,-180 20,-170 L16,-184 Q32,-190 26,-212Z" fill="{tissu}"/>'
                f'<rect x="-40" y="-200" width="80" height="62" rx="4" fill="#D9A066"/>'
                f'<rect x="-6" y="-200" width="12" height="62" fill="#fff" opacity=".45"/>'
                f'<circle cx="-30" cy="-176" r="9" fill="{peau}"/><circle cx="30" cy="-176" r="9" fill="{peau}"/>')
    elif pose == "montre":
        bras = (f'<path d="M-36,-222 Q-54,-170 -34,-150 L-22,-162 Q-34,-176 -24,-210Z" fill="{tissu}"/>'
                f'<path d="M34,-222 Q70,-214 92,-236 L84,-248 Q64,-230 26,-238Z" fill="{tissu}"/>'
                f'<circle cx="92" cy="-246" r="10" fill="{peau}"/><circle cx="-30" cy="-150" r="9" fill="{peau}"/>')
    else:  # repos
        bras = (f'<path d="M-36,-222 Q-54,-170 -38,-140 L-26,-146 Q-36,-176 -24,-210Z" fill="{tissu}"/>'
                f'<path d="M36,-222 Q54,-170 38,-140 L26,-146 Q36,-176 24,-210Z" fill="{tissu}"/>'
                f'<circle cx="-33" cy="-138" r="9" fill="{peau}"/><circle cx="33" cy="-138" r="9" fill="{peau}"/>')
    return g(jambes + corps + cou + visage + cheveux + yeux + bouche + bras, x, y, s)
