"""Scènes illustrées des guides : couvertures et ouvertures de chapitre.

`SCENES[slug]` = {"couverture": svg, "chapitres": [svg par titre ## dans l'ordre]}.
Les graphiques des chapitres chiffrés reprennent exactement les montants du texte.
"""
import math

from illus import (PEAUX, ENCRE, scene, g, blob, wax, points, etincelle, soleil, plante,
                   telephone, ecran_chat, ecran_catalogue, sac, etiquette, pieces, billet,
                   colis, bouclier, bulle, lignes_texte, calendrier, graphique, appareil_photo,
                   loupe, moto, etal, personne)

W, H = 600, 280  # bannière de chapitre


def texte(x, y, t, taille=16, couleur=ENCRE, poids=800, ancre="start"):
    return (f'<text x="{x}" y="{y}" font-family="DejaVu Sans, Arial" font-size="{taille}" font-weight="{poids}" '
            f'fill="{couleur}" text-anchor="{ancre}">{t}</text>')


def fond_banniere(c1, c2, seed=0, motif_id="wb"):
    return (f'<rect width="{W}" height="{H}" rx="22" fill="{c1}"/>'
            + blob(470, 150, 150, c2, seed, .9) + blob(90, 60, 70, c2, seed + 2, .5)
            + points(24, 200, 5, 4, "#ffffff", 13, 2).replace('fill="#ffffff"', 'fill="#ffffff" opacity=".35"'))


def bulle_txt(x, y, w, t, couleur="#fff", queue="g", taille=15, coul_txt=ENCRE):
    return bulle(x, y, w, 36, couleur, queue, texte(w / 2, 24, t, taille, coul_txt, 800, "middle"))


# ════════════════════════════════════════════════════════════════════════
#  GUIDE 1 — Vendre sur WhatsApp et Facebook (vert / or)
# ════════════════════════════════════════════════════════════════════════
V1, V2, OR, CORAIL, CREME = "#0D5C35", "#1A7A48", "#F0A830", "#E4572E", "#FDF6E8"


def g1_couverture():
    c = blob(300, 330, 250, OR, 3, .95) + blob(470, 160, 90, V2, 1, .9)
    c += points(40, 60, 6, 5, "#ffffff", 16, 2.4).replace('fill="#ffffff"', 'fill="#ffffff" opacity=".3"')
    c += telephone(330, 90, 170, 310, ecran_chat(156, 276, [
        ("g", 2, "Bonjour, la robe est dispo ?"), ("d", 2, "Oui ! 12 000 F 😊"),
        ("g", 1, None), ("d", 3, "Livraison demain 10h"), ("g", 2, "Je prends 2 ! 🎉")], nom="Awa Mode"), ENCRE, 6)
    c += personne(190, 520, 1.45, PEAUX[1], CORAIL, ENCRE, "foulard", "#7C3A8A", "telephone")
    c += sac(470, 470, 1.1, "#7C3A8A") + sac(530, 500, .8, CORAIL)
    c += etiquette(60, 330, 1.2, CREME, "12 000") + pieces(90, 520, 5, 1.2)
    c += bulle_txt(40, 200, 110, "Prix ?", "#fff", "d") + bulle_txt(470, 50, 100, "+1 vente", "#DCF8C6", "g")
    c += etincelle(560, 250, 16, "#fff") + etincelle(30, 150, 11, OR) + etincelle(320, 60, 12, "#fff")
    return scene(c, 600, 540)


def g1_intro():
    c = fond_banniere(V1, V2, 1)
    c += personne(170, 270, .8, PEAUX[2], OR, ENCRE, "tresses", pose="bras_leves")
    c += telephone(330, 40, 110, 200, ecran_chat(96, 166, [("g", 2, "Ta boutique"), ("d", 2, "dans ta poche"), ("g", 2, None)]), ENCRE, 8)
    c += etincelle(90, 60, 16, OR) + etincelle(520, 70, 12, "#fff") + pieces(520, 250, 4, .9) + sac(470, 250, .7, CORAIL)
    return scene(c, W, H)


def g1_choisir():
    c = fond_banniere(V1, V2, 2)
    c += etal(330, 200, .9)
    c += personne(90, 275, .72, PEAUX[0], "#1A5FBF", ENCRE, "court", pose="repos")
    c += loupe(490, 90, 1.2, OR) + etiquette(210, 70, 1, OR, "Top")
    c += etincelle(560, 200, 12, "#fff")
    return scene(c, W, H)


def g1_whatsapp():
    c = fond_banniere(V1, V2, 3)
    c += telephone(210, 30, 120, 225, ecran_catalogue(106, 191, [CORAIL, OR, "#7C3A8A", "#1A5FBF", V2, "#D9A066"]), ENCRE, -6)
    c += telephone(360, 40, 120, 225, ecran_chat(106, 191, [("g", 2, "Bienvenue 👋"), ("d", 2, None), ("g", 3, "Catalogue ➜")], nom="Awa Mode"), ENCRE, 6)
    c += personne(100, 275, .75, PEAUX[3], CORAIL, ENCRE, "foulard", OR, "telephone")
    c += bulle_txt(470, 190, 110, "Répond. rapide", "#fff", "g", 12)
    return scene(c, W, H)


def g1_photos():
    c = fond_banniere(V1, V2, 4)
    fen = ('<rect x="0" y="0" width="150" height="170" rx="8" fill="#BFE6F2"/>'
           '<rect x="72" y="0" width="6" height="170" fill="#fff"/><rect x="0" y="82" width="150" height="6" fill="#fff"/>'
           '<rect x="-8" y="-8" width="166" height="186" rx="12" fill="none" stroke="#fff" stroke-width="10"/>')
    c += g(fen, 60, 55) + soleil(95, 80, 18, OR)
    robe = (f'<path d="M0,-10 L0,10" stroke="{ENCRE}" stroke-width="4"/><path d="M-30,10 L30,10" stroke="{ENCRE}" stroke-width="4"/>'
            f'<path d="M-22,12 L22,12 L28,50 L48,150 L-48,150 L-28,50Z" fill="{CORAIL}"/>'
            + "".join(f'<circle cx="{-30+i*15}" cy="{80+(i%2)*28}" r="6" fill="{OR}"/>' for i in range(5)))
    c += g(robe, 300, 70)
    c += telephone(420, 70, 100, 175, '<rect width="86" height="141" fill="#F7F3EA"/>'
                   f'<path d="M30,30 L56,30 L60,50 L70,110 L16,110 L26,50Z" fill="{CORAIL}"/>'
                   '<circle cx="43" cy="128" r="8" fill="#fff" stroke="#999" stroke-width="2"/>', ENCRE, 10)
    c += etincelle(540, 60, 14, "#fff") + etincelle(250, 230, 10, OR)
    return scene(c, W, H)


def g1_facebook():
    c = fond_banniere(V1, V2, 5)
    noeuds = [(300, 140, 44, OR), (160, 80, 26, "#fff"), (440, 70, 26, "#fff"), (140, 210, 26, "#fff"),
              (460, 215, 26, "#fff"), (230, 40, 18, CORAIL), (380, 245, 18, CORAIL), (530, 140, 20, "#8FD3C1"), (70, 140, 20, "#8FD3C1")]
    c += "".join(f'<line x1="300" y1="140" x2="{x}" y2="{y}" stroke="#fff" stroke-opacity=".45" stroke-width="3"/>' for x, y, _, _ in noeuds[1:])
    for i, (x, y, r, col) in enumerate(noeuds):
        c += f'<circle cx="{x}" cy="{y}" r="{r}" fill="{col}"/>'
        c += f'<circle cx="{x}" cy="{y - r*0.22}" r="{r*0.32}" fill="{PEAUX[i % 4]}"/>'
        c += f'<path d="M{x - r*0.55},{y + r*0.6} Q{x},{y + r*0.02} {x + r*0.55},{y + r*0.6}Z" fill="{PEAUX[i % 4]}"/>'
    c += bulle_txt(340, 20, 120, "Prix ? 🔥", "#fff", "g", 14) + bulle_txt(60, 238, 130, "Je veux !", "#DCF8C6", "d", 14)
    return scene(c, W, H)


def g1_vente():
    c = fond_banniere(V1, V2, 6)
    c += personne(95, 275, .72, PEAUX[1], "#7C3A8A", ENCRE, "foulard", CORAIL, "telephone")
    c += personne(510, 275, .72, PEAUX[3], "#1A5FBF", ENCRE, "court", pose="telephone")
    c += bulle_txt(170, 30, 190, "Bonjour ! 12 000 F 😊", "#fff", "g", 14)
    c += bulle_txt(250, 85, 170, "Taille M svp", "#DCF8C6", "d", 14)
    c += bulle_txt(170, 140, 200, "Je vous la réserve ?", "#fff", "g", 14)
    c += bulle_txt(270, 195, 130, "Oui ! ✅", "#DCF8C6", "d", 15)
    return scene(c, W, H)


def g1_paiement():
    c = fond_banniere(V1, V2, 7)
    ecr = ('<rect width="126" height="206" fill="#fff"/><rect width="126" height="30" fill="#1DC3F0"/>'
           + texte(63, 20, "Mobile Money", 11, "#fff", 800, "middle")
           + '<circle cx="63" cy="80" r="26" fill="#1A7A48"/>'
           '<path d="M50,80 L60,90 L78,70" fill="none" stroke="#fff" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>'
           + texte(63, 130, "Paiement reçu", 11, ENCRE, 800, "middle") + texte(63, 156, "12 000 F", 19, "#1A7A48", 900, "middle")
           + lignes_texte(20, 172, 86, 2, "#DDD"))
    c += telephone(240, 25, 140, 240, ecr, ENCRE, 0)
    c += bouclier(470, 120, 1.4, OR) + pieces(120, 250, 6, 1.1) + billet(120, 110, 1.1, -12) + billet(150, 150, 1, 8, "#9FD8B4")
    c += etincelle(540, 230, 12, "#fff")
    return scene(c, W, H)


def g1_livraison():
    c = fond_banniere(V1, V2, 8)
    c += '<rect x="20" y="236" width="560" height="10" rx="5" fill="#fff" opacity=".25"/>'
    c += moto(200, 230, 1.1, CORAIL) + personne(460, 275, .75, PEAUX[2], OR, ENCRE, "tresses", pose="carton")
    c += "".join(etincelle(330 + i * 30, 50, 11, OR) for i in range(5))
    c += bulle_txt(300, 80, 150, "Merci ! ⭐⭐⭐⭐⭐", "#fff", "d", 13)
    return scene(c, W, H)


def g1_plan():
    c = fond_banniere(V1, V2, 9)
    c += calendrier(80, 60, 1.2, CORAIL, 20) + graphique(330, 245, [2, 3, 5, 7, 10], .95, "#fff", OR)
    c += personne(520, 275, .7, PEAUX[0], OR, ENCRE, "afro", pose="bras_leves")
    return scene(c, W, H)


def g1_grenier():
    c = fond_banniere(V1, V2, 10)
    c += telephone(250, 25, 130, 235, ecran_catalogue(116, 201, [OR, CORAIL, "#7C3A8A", "#1A5FBF", V2, "#D9A066"]), ENCRE, 0)
    c += etiquette(410, 80, 1.1, OR, "Boost") + bouclier(470, 200, 1, "#fff")
    c += personne(120, 275, .72, PEAUX[1], CORAIL, ENCRE, "foulard", "#1A5FBF", "bras_leves")
    return scene(c, W, H)


# ════════════════════════════════════════════════════════════════════════
#  GUIDE 2 — Lancer sa boutique avec 50 000 F (violet / or)
# ════════════════════════════════════════════════════════════════════════
P1, P2 = "#5B2466", "#7C3A8A"


def g2_couverture():
    c = blob(300, 330, 250, OR, 5, .95) + blob(120, 150, 90, P2, 2, .9)
    c += points(420, 40, 6, 5, "#ffffff", 16, 2.4).replace('fill="#ffffff"', 'fill="#ffffff" opacity=".3"')
    # escalier de croissance 50k → 137k (montants du chapitre 8)
    marches = [(50, "50 000"), (70, "70 000"), (98, "98 000"), (137, "137 000")]
    for i, (v, lib) in enumerate(marches):
        h = v * 2.2
        x = 300 + i * 70
        c += f'<rect x="{x}" y="{500-h}" width="58" height="{h}" rx="8" fill="{P2 if i < 3 else "#fff"}" opacity="{0.55+0.15*i}"/>'
        c += texte(x + 29, 490 - h, lib, 12, "#fff", 800, "middle")
    c += personne(170, 520, 1.45, PEAUX[2], "#1A7A48", ENCRE, "court", pose="bras_leves", lunettes=True)
    c += plante(555, 505, .75, CORAIL, "#1A7A48") + pieces(300, 520, 6, 1.2) + colis(480, 505, .7) + sac(90, 510, .9, CORAIL)
    c += etincelle(520, 80, 16, "#fff") + etincelle(40, 60, 12, OR)
    return scene(c, 600, 540)


def g2_intro():
    c = fond_banniere(P1, P2, 1)
    c += pieces(160, 240, 6, 1.4) + billet(250, 200, 1.2, -10) + billet(270, 230, 1.1, 6, "#9FD8B4")
    c += texte(210, 70, "50 000 F", 40, "#fff", 900, "middle")
    c += plante(440, 250, .95, CORAIL, "#1A7A48") + etincelle(520, 60, 14, OR) + etincelle(360, 50, 10, "#fff")
    return scene(c, W, H)


def g2_mental():
    c = fond_banniere(P1, P2, 2)
    c += bouclier(170, 140, 2.2, OR) + pieces(170, 245, 3, .9)
    c += personne(440, 275, .75, PEAUX[1], OR, ENCRE, "foulard", "#1A7A48", "montre")
    c += texte(170, 40, "Capital sacré", 18, "#fff", 800, "middle")
    return scene(c, W, H)


def g2_produit():
    c = fond_banniere(P1, P2, 3)
    c += etal(300, 205, .85, CORAIL, CREME, (OR, "#1A7A48", "#1A5FBF", CORAIL))
    c += loupe(500, 80, 1.1, OR) + etiquette(80, 60, 1, OR, "-30%") + etiquette(90, 150, 1, "#fff", "x10")
    return scene(c, W, H)


def g2_repartition():
    """Anneau : répartition exacte des 50 000 F (chapitre 3)."""
    parts = [(35000, "Stock", OR), (3000, "Emballage", "#8FD3C1"), (5000, "Visibilité", CORAIL),
             (4000, "Transport", "#fff"), (3000, "Réserve", "#1A7A48")]
    cx, cy, r = 170, 140, 92
    c = fond_banniere(P1, P2, 4)
    a0 = -math.pi / 2
    for v, lib, col in parts:
        a1 = a0 + v / 50000 * 2 * math.pi
        grand = 1 if a1 - a0 > math.pi else 0
        x0, y0 = cx + r * math.cos(a0), cy + r * math.sin(a0)
        x1, y1 = cx + r * math.cos(a1), cy + r * math.sin(a1)
        c += f'<path d="M{x0:.1f},{y0:.1f} A{r},{r} 0 {grand} 1 {x1:.1f},{y1:.1f}" fill="none" stroke="{col}" stroke-width="44"/>'
        a0 = a1
    c += texte(cx, cy - 2, "50 000 F", 20, "#fff", 900, "middle") + texte(cx, cy + 20, "ton capital", 12, "#fff", 600, "middle")
    for i, (v, lib, col) in enumerate(parts):
        y = 58 + i * 40
        c += f'<rect x="330" y="{y-16}" width="22" height="22" rx="6" fill="{col}"/>'
        c += texte(362, y, lib, 16, "#fff", 700) + texte(560, y, f"{v:,} F".replace(",", " "), 16, "#fff", 800, "end")
    return scene(c, W, H)


def g2_prix():
    """Barre empilée : coût de revient d'un sac + marge = 5 500 F (chapitre 4)."""
    parts = [(3000, "Achat", "#fff"), (100, "Transport", "#8FD3C1"), (150, "Emballage", "#8FD3C1"),
             (200, "Pub", CORAIL), (2050, "Ta marge", OR)]
    c = fond_banniere(P1, P2, 5)
    x = 40
    for v, lib, col in parts:
        w = v / 5500 * 520
        c += f'<rect x="{x:.1f}" y="120" width="{w:.1f}" height="60" fill="{col}"/>'
        if w > 60:
            c += texte(x + w / 2, 156, lib, 15, P1, 800, "middle")
        x += w
    c += '<rect x="40" y="120" width="520" height="60" rx="10" fill="none" stroke="#fff" stroke-width="4"/>'
    c += texte(40, 90, "Coût de revient : 3 450 F", 17, "#fff", 800) + texte(560, 90, "+ marge 2 050 F", 17, OR, 800, "end")
    c += texte(300, 230, "Prix de vente : 5 500 F", 26, "#fff", 900, "middle")
    c += etiquette(500, 30, .9, OR, "5 500")
    return scene(c, W, H)


def g2_boutique():
    c = fond_banniere(P1, P2, 6)
    c += telephone(200, 25, 125, 235, ecran_catalogue(111, 201, [OR, CORAIL, "#1A5FBF", "#1A7A48", P2, "#D9A066"]), ENCRE, -6)
    c += telephone(340, 35, 125, 235, ecran_chat(111, 201, [("g", 2, "Sacs Chic 👜"), ("d", 2, None), ("g", 2, None)], nom="Sacs Chic"), ENCRE, 6)
    c += etiquette(70, 80, 1, OR, "0 F") + etincelle(520, 80, 14, "#fff") + sac(520, 240, .8, CORAIL)
    return scene(c, W, H)


def g2_clients():
    c = fond_banniere(P1, P2, 7)
    for i in range(20):
        x, y = 70 + (i % 10) * 50, 130 + (i // 10) * 110
        c += personne(x, y, .3, PEAUX[i % 4], [OR, CORAIL, "#8FD3C1", "#fff", "#1A7A48"][i % 5], ENCRE,
                      ["foulard", "court", "tresses", "afro", "casquette"][i % 5], [P2, OR, CORAIL][i % 3], "repos")
    c += texte(560, 40, "20 premiers clients", 18, "#fff", 800, "end")
    return scene(c, W, H)


def g2_caisse():
    c = fond_banniere(P1, P2, 8)
    cahier = (f'<rect x="0" y="0" width="230" height="190" rx="10" fill="#fff"/>'
              f'<rect x="0" y="0" width="230" height="30" rx="10" fill="{OR}"/><rect x="0" y="18" width="230" height="12" fill="{OR}"/>'
              + texte(115, 21, "Cahier de caisse", 14, ENCRE, 800, "middle")
              + "".join(f'<line x1="14" y1="{52+i*22}" x2="216" y2="{52+i*22}" stroke="#E0DAD0" stroke-width="2"/>' for i in range(6))
              + "".join(texte(20, 48 + i * 22, t, 11, c, 700) for i, (t, c) in enumerate([
                  ("+ 5 500 F  vente sac", "#1A7A48"), ("+ 5 500 F  vente sac", "#1A7A48"), ("− 1 000 F  transport", CORAIL),
                  ("+ 11 000 F  2 sacs", "#1A7A48"), ("− 2 000 F  boost", CORAIL)]))
              + texte(216, 180, "Solde : 19 000 F", 13, P1, 900, "end"))
    c += g(cahier, 60, 50) + pieces(400, 240, 6, 1.1) + billet(480, 120, 1.2, -10) + billet(470, 170, 1.1, 8, "#9FD8B4")
    return scene(c, W, H)


def g2_grandir():
    c = fond_banniere(P1, P2, 9)
    c += graphique(70, 250, [50, 70, 98, 137], 1.3, "#fff", OR)
    for i, v in enumerate(["50k", "70k", "98k", "137k"]):
        c += texte(70 + i * 44 + 16, 272, v, 12, "#fff", 800, "middle")
    c += personne(430, 275, .8, PEAUX[3], OR, ENCRE, "casquette", CORAIL, "carton") + colis(530, 250, .7) + colis(530, 205, .6)
    return scene(c, W, H)


def g2_plan():
    c = fond_banniere(P1, P2, 10)
    c += calendrier(70, 60, 1.2, OR, 25).replace("30 JOURS", "60 JOURS")
    c += personne(360, 275, .75, PEAUX[2], "#1A7A48", ENCRE, "foulard", OR, "bras_leves")
    c += plante(510, 250, .9, CORAIL, "#8FD3C1") + etincelle(460, 60, 14, OR)
    return scene(c, W, H)


# Chaque ouverture de chapitre est soit une scène dessinée (fonction), soit une
# photo réelle Pexels : ("photo", identifiant, point d'intérêt vertical 0→1).
# Les pages chiffrées (graphiques, paiement, calendrier) restent dessinées.
SCENES = {
    "guide-vendre-whatsapp-facebook": {
        "couverture": g1_couverture,
        "couverture_photo": ("30677594", 0.5, 0.35),
        "chapitres": [("photo", "6612222", 0.42), ("photo", "36943009", 0.5), ("photo", "27398372", 0.45),
                      ("photo", "8154650", 0.55), ("photo", "17722443", 0.35), g1_vente,
                      g1_paiement, ("photo", "34635135", 0.62), ("photo", "7191994", 0.5), ("photo", "7362929", 0.45)],
    },
    "guide-boutique-50000": {
        "couverture": g2_couverture,
        "couverture_photo": ("30840030", 0.62, 0.4),
        "chapitres": [g2_intro, ("photo", "19834923", 0.35), ("photo", "33490144", 0.3), g2_repartition, g2_prix,
                      ("photo", "16779591", 0.3), g2_clients, ("photo", "7491011", 0.5), ("photo", "7552575", 0.4), g2_plan],
    },
}
