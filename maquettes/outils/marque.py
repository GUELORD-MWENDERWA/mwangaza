"""Marque Mwangaza : fichiers du logo (SVG) et livre de marque (PDF).

Depuis backend/ (fontTools et WeasyPrint viennent de l'environnement du serveur) :
  uv run python ../maquettes/outils/marque.py logo    # SVG dans maquettes/assets/logo/
  uv run python ../maquettes/outils/marque.py livre   # docs/marque/livre-de-marque.pdf
PNG du logo, à partir des SVG, depuis la racine : node maquettes/outils/captures.mjs --logo

Le logotype est le mot « mwangaza » en Poppins SemiBold (licence OFL), approche de -0,035 em
et crénage de la police, converti en tracés : les fichiers ne dépendent d'aucune police
installée. Proportions de la piste retenue (maquettes/marque/marque.html) : symbole de 1,2 em,
espace de 0,26 em, symbole centré sur la ligne du mot, soleil de 0,19 em au-dessus du
premier m du logotype seul.
"""

import sys
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[2]
LOGO = ROOT / "maquettes" / "assets" / "logo"
FONT = ROOT / "maquettes" / "assets" / "fonts" / "poppins-latin-600-normal.woff2"

BLEU, SOLEIL, ARDOISE, CRAIE = "#1A2F80", "#FFA81E", "#111418", "#FFFFFF"

# Symbole sur une grille de 64 : carré arrondi, m tracé d'un trait de 8 (contour exact), soleil.
TUILE = "M18 0H46A18 18 0 0 1 64 18V46A18 18 0 0 1 46 64H18A18 18 0 0 1 0 46V18A18 18 0 0 1 18 0Z"
M = (
    "M10 54V34A13 13 0 0 1 32 24.62A13 13 0 0 1 54 34V54H46V34"
    "A5 5 0 0 0 36 34V54H28V34A5 5 0 0 0 18 34V54Z"
)
SOL = "M26.5 14.5A5.5 5.5 0 1 0 37.5 14.5A5.5 5.5 0 1 0 26.5 14.5Z"

EM = 100  # unités du fichier pour 1 em du logotype
SYMBOLE_EM, ESPACE_EM, APPROCHE_EM, POINT_EM = 1.2, 0.26, -0.035, 0.19


def num(x: float) -> str:
    s = f"{x:.2f}".rstrip("0").rstrip(".")
    return "0" if s == "-0" else s


def crenage(font: TTFont):
    """Crénage (unités de la police) d'une paire de glyphes, selon la fonction « kern » de GPOS."""
    gpos = font["GPOS"].table
    index = set()
    for rec in gpos.FeatureList.FeatureRecord:
        if rec.FeatureTag == "kern":
            index.update(rec.Feature.LookupListIndex)
    tables = []
    for i in sorted(index):
        lookup = gpos.LookupList.Lookup[i]
        for st in lookup.SubTable:
            if lookup.LookupType == 9:
                st = st.ExtSubTable
            if getattr(st, "LookupType", 2) == 2:
                tables.append(st)

    def paire(gauche: str, droite: str) -> int:
        for st in tables:
            couverts = st.Coverage.glyphs
            if gauche not in couverts:
                continue
            if st.Format == 1:
                for rec in st.PairSet[couverts.index(gauche)].PairValueRecord:
                    if rec.SecondGlyph == droite:
                        return getattr(rec.Value1, "XAdvance", 0) or 0
                continue
            c1 = st.ClassDef1.classDefs.get(gauche, 0)
            c2 = st.ClassDef2.classDefs.get(droite, 0)
            return getattr(st.Class1Record[c1].Class2Record[c2].Value1, "XAdvance", 0) or 0
        return 0

    return paire


def mot(x0: float):
    """Tracé du mot « mwangaza » (ligne de base en y = 0), ses limites et le centre du premier m."""
    font = TTFont(FONT)
    upm = font["head"].unitsPerEm
    s = EM / upm
    cmap, glyphes = font.getBestCmap(), font.getGlyphSet()
    paire = crenage(font)
    hhea = font["hhea"]
    # Boîte de ligne de 1 em (line-height: 1) : son centre, au-dessus de la ligne de base.
    centre = (hhea.ascent - (hhea.ascent - hhea.descent - upm) / 2 - upm / 2) * s
    pen = SVGPathPen(glyphes, ntos=num)
    x, gauche, prec, bornes, m1 = x0, None, None, [], None
    for c in "mwangaza":
        g = cmap[ord(c)]
        if prec:
            x += paire(prec, g) * s
        glyphes[g].draw(TransformPen(pen, (s, 0, 0, -s, x, 0)))
        bp = BoundsPen(glyphes)
        glyphes[g].draw(bp)
        xmin, ymin, xmax, ymax = bp.bounds
        bornes.append((x + xmin * s, -ymax * s, x + xmax * s, -ymin * s))
        if m1 is None:
            m1 = x + (xmin + xmax) / 2 * s
        gauche = gauche if gauche is not None else x + xmin * s
        x += glyphes[g].width * s + APPROCHE_EM * EM
        prec = g
    haut = min(b[1] for b in bornes)
    bas = max(b[3] for b in bornes)
    droite = max(b[2] for b in bornes)
    return pen.getCommands(), (gauche, haut, droite, bas), m1, centre


def svg(vb, corps: str) -> str:
    x, y, w, h = vb
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{num(x)} {num(y)} {num(w)} {num(h)}" '
        f'width="{num(w)}" height="{num(h)}" role="img" aria-label="Mwangaza">'
        f"<title>Mwangaza</title>{corps}</svg>\n"
    )


def symbole(tuile: str, trait: str, soleil: str) -> str:
    if tuile == "mono":  # une seule encre : m et soleil évidés
        return f'<path fill="{trait}" fill-rule="evenodd" d="{TUILE}{M}{SOL}"/>'
    return (
        f'<path fill="{tuile}" d="{TUILE}"/><path fill="{trait}" d="{M}"/>'
        f'<path fill="{soleil}" d="{SOL}"/>'
    )


def logo() -> None:
    versions = {  # nom : (tuile, m, soleil, mot, point)
        "": (BLEU, CRAIE, SOLEIL, BLEU, SOLEIL),
        "-inverse": (CRAIE, BLEU, SOLEIL, CRAIE, SOLEIL),
        "-mono": ("mono", ARDOISE, None, ARDOISE, ARDOISE),
    }
    x_mot = (SYMBOLE_EM + ESPACE_EM) * EM
    d_lock, (_, h1, droite, b1), _, centre = mot(x_mot)
    taille = SYMBOLE_EM * EM
    haut = -centre - taille / 2
    # Le descendant du g dépasse un peu sous le symbole.
    y0, y1 = min(haut, h1), max(haut + taille, b1)
    d_seul, (g2, h2, d2, b2), m1, centre = mot(0)
    r = POINT_EM * EM / 2
    cy = -(centre + EM / 2) - 0.02 * EM + r  # point à 0,02 em au-dessus de la boîte de ligne
    for suffixe, (tuile, trait, soleil, encre, point) in versions.items():
        k = taille / 64
        sym = symbole(tuile, trait, soleil)
        corps = f'<g transform="translate(0 {num(haut)}) scale({k:g})">{sym}</g>'
        corps += f'<path fill="{encre}" d="{d_lock}"/>'
        (LOGO / f"mwangaza-logo{suffixe}.svg").write_text(svg((0, y0, droite, y1 - y0), corps))
        (LOGO / f"mwangaza-symbole{suffixe}.svg").write_text(svg((0, 0, 64, 64), sym))
        corps = f'<path fill="{encre}" d="{d_seul}"/>'
        corps += f'<circle fill="{point}" cx="{num(m1)}" cy="{num(cy)}" r="{num(r)}"/>'
        haut2 = min(h2, cy - r)
        vb = (g2, haut2, d2 - g2, b2 - haut2)
        (LOGO / f"mwangaza-logotype{suffixe}.svg").write_text(svg(vb, corps))
    # Icônes installées : carré plein cadre, que le système arrondit lui-même. Android
    # (« maskable ») : m et soleil réduits dans le cercle sûr (80 % du côté) ; iPhone : tels quels.
    plein = f'<path fill="{BLEU}" d="M0 0H64V64H0Z"/>'
    dessin = f'<path fill="{CRAIE}" d="{M}"/><path fill="{SOLEIL}" d="{SOL}"/>'
    reduit = f'<g transform="translate(32 32) scale(.8) translate(-32 -31.5)">{dessin}</g>'
    (LOGO / "mwangaza-icone-maskable.svg").write_text(svg((0, 0, 64, 64), plein + reduit))
    (LOGO / "mwangaza-icone-apple.svg").write_text(svg((0, 0, 64, 64), plein + dessin))
    print("SVG écrits dans", LOGO.relative_to(ROOT))


def livre() -> None:
    from weasyprint import HTML

    src = ROOT / "docs" / "marque" / "livre-de-marque.html"
    out = src.with_suffix(".pdf")
    HTML(filename=str(src)).write_pdf(out)
    print(out.relative_to(ROOT), f"{out.stat().st_size // 1024} Ko")


if __name__ == "__main__":
    {"logo": logo, "livre": livre}[sys.argv[1] if len(sys.argv) > 1 else "logo"]()
