"""Genera i marker ArUco e la board ChArUco da stampare in scala reale.

    python genera_marker.py                      # marker 0-3 da 50 mm + board ChArUco
    python genera_marker.py --ids 0 1 2 --lato-mm 80

Output in dati/stampa/:
  - marker_<id>.png: un marker con bordo bianco, comodo da mostrare sul telefono;
  - foglio_marker*.pdf/png e board_charuco.pdf/png: fogli A4 da stampare al 100%
    ("dimensioni effettive"), senza "adatta alla pagina".

Dopo la stampa MISURA col righello il lato del marker (bordo nero compreso) e il lato
di un quadrato della board, e scrivi i valori in config.yaml: contano le misure reali.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from comune import carica_config, crea_board, dizionario, percorso

A4_MM = (210, 297)  # larghezza, altezza in verticale
MARGINE_MM = 12


def mm_in_px(mm: float, dpi: int) -> int:
    return int(round(mm / 25.4 * dpi))


def salva(img: np.ndarray, base: Path, dpi: int) -> None:
    """Salva PNG e PDF con la risoluzione indicata, così la stampa al 100% è in scala."""
    pil = Image.fromarray(img)
    pil.save(base.with_suffix(".png"), dpi=(dpi, dpi))
    pil.save(base.with_suffix(".pdf"), "PDF", resolution=float(dpi))


def immagine_marker(diz: cv2.aruco.Dictionary, marker_id: int, lato_mm: float, dpi: int) -> tuple[np.ndarray, float]:
    """Marker con lato multiplo del numero di celle (bit interni + bordo nero), per bordi netti.
    Restituisce l'immagine e il lato effettivo in mm."""
    celle = diz.markerSize + 2
    lato_px = max(celle, round(mm_in_px(lato_mm, dpi) / celle) * celle)
    return cv2.aruco.generateImageMarker(diz, marker_id, lato_px), lato_px / dpi * 25.4


def scrivi(img: np.ndarray, testo: str, x: int, y: int, dpi: int) -> None:
    scala = dpi / 300
    cv2.putText(img, testo, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 1.0 * scala, 0, max(1, round(2 * scala)), cv2.LINE_AA)


def fogli_marker(cfg: dict, ids: list[int], lato_mm: float, dpi: int, uscita: Path) -> float:
    nome_diz = cfg["marker"]["dizionario"]
    diz = dizionario(nome_diz)
    w, h = mm_in_px(A4_MM[0], dpi), mm_in_px(A4_MM[1], dpi)
    margine, spazio = mm_in_px(MARGINE_MM, dpi), mm_in_px(20, dpi)  # lo spazio fa anche da bordo bianco

    lato_reale = lato_mm
    immagini = []
    for i in ids:
        img, lato_reale = immagine_marker(diz, i, lato_mm, dpi)
        immagini.append((i, img))
        bordo = img.shape[0] // (diz.markerSize + 2)  # una cella di bianco attorno
        cv2.imwrite(str(uscita / f"marker_{i}.png"),
                    cv2.copyMakeBorder(img, bordo, bordo, bordo, bordo, cv2.BORDER_CONSTANT, value=255))

    lato_px = immagini[0][1].shape[0]
    if lato_px > w - 2 * margine or lato_px > h - 2 * margine:
        raise SystemExit(f"Un marker da {lato_mm} mm non entra in un A4: riduci --lato-mm.")
    per_riga = (w - 2 * margine + spazio) // (lato_px + spazio)
    per_colonna = (h - 2 * margine + spazio) // (lato_px + spazio)
    per_foglio = per_riga * per_colonna

    for n_foglio, inizio in enumerate(range(0, len(immagini), per_foglio), start=1):
        foglio = np.full((h, w), 255, np.uint8)
        for k, (i, img) in enumerate(immagini[inizio:inizio + per_foglio]):
            x = margine + (k % per_riga) * (lato_px + spazio)
            y = margine + (k // per_riga) * (lato_px + spazio)
            foglio[y:y + lato_px, x:x + lato_px] = img
            scrivi(foglio, f"ID {i}", x, y + lato_px + mm_in_px(5, dpi), dpi)
        scrivi(foglio, f"{nome_diz} - lato {lato_reale:.1f} mm - stampa al 100%, poi misura",
               margine, h - mm_in_px(6, dpi), dpi)
        suffisso = "" if len(immagini) <= per_foglio else f"_{n_foglio}"
        salva(foglio, uscita / f"foglio_marker{suffisso}", dpi)
    return lato_reale


def foglio_board(cfg: dict, dpi: int, uscita: Path) -> float:
    c = cfg["charuco"]
    board = crea_board(cfg)
    quadrato_px = mm_in_px(c["lato_quadrato_m"] * 1000, dpi)
    bw, bh = c["quadrati_x"] * quadrato_px, c["quadrati_y"] * quadrato_px
    img = board.generateImage((bw, bh), marginSize=0)

    margine = mm_in_px(MARGINE_MM, dpi)
    for wm, hm in (A4_MM, A4_MM[::-1]):  # prima in verticale, poi in orizzontale
        w, h = mm_in_px(wm, dpi), mm_in_px(hm, dpi)
        if bw <= w - 2 * margine and bh <= h - 4 * margine:
            break
    else:
        raise SystemExit("La board non entra in un A4: riduci lato_quadrato_m o il numero di quadrati.")

    foglio = np.full((h, w), 255, np.uint8)
    x, y = (w - bw) // 2, (h - bh) // 2
    foglio[y:y + bh, x:x + bw] = img
    scrivi(foglio, f"ChArUco {c['quadrati_x']}x{c['quadrati_y']} {c['dizionario']} - quadrato "
                   f"{quadrato_px / dpi * 25.4:.1f} mm - marker {c['lato_marker_m'] * 1000:.1f} mm",
           margine, h - mm_in_px(6, dpi), dpi)
    salva(foglio, uscita / "board_charuco", dpi)
    return quadrato_px / dpi * 25.4


def main() -> None:
    cfg = carica_config()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ids", type=int, nargs="+", default=[0, 1, 2, 3], help="ID dei marker da generare")
    ap.add_argument("--lato-mm", type=float, default=cfg["marker"]["lato_m"] * 1000,
                    help="lato del marker in mm (default: valore in config.yaml)")
    ap.add_argument("--dpi", type=int, default=300)
    args = ap.parse_args()

    uscita = percorso(cfg, "stampa")
    uscita.mkdir(parents=True, exist_ok=True)
    lato = fogli_marker(cfg, args.ids, args.lato_mm, args.dpi, uscita)
    quadrato = foglio_board(cfg, args.dpi, uscita)

    print(f"File salvati in {uscita}")
    print(f"- marker {args.ids}: lato nominale {lato:.1f} mm")
    print(f"- board ChArUco: quadrato nominale {quadrato:.1f} mm")
    print("Stampa al 100% su carta opaca, incolla su un supporto rigido, poi misura e aggiorna "
          "marker.lato_m e charuco.lato_quadrato_m / lato_marker_m in config.yaml.")


if __name__ == "__main__":
    main()
