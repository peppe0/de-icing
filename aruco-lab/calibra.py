"""Calibrazione della camera con la board ChArUco.

    python calibra.py cattura    # acquisisci immagini della board (SPAZIO salva, q termina)
    python calibra.py calcola    # calcola K e distorsione dalle immagini salvate
    python calibra.py verifica   # confronta dal vivo immagine originale e corretta

Consigli per la cattura: 20-30 immagini, board ferma (niente mosso), inclinata in modi
diversi (anche 30-45°), a distanze diverse e in tutte le zone dell'immagine, bordi e
angoli compresi. I puntini grigi mostrano le zone già coperte.
"""
from __future__ import annotations

import argparse
import math

import cv2
import numpy as np

from comune import apri_camera, carica_calibrazione, carica_config, crea_board, percorso, salva_calibrazione

MIN_ANGOLI_CATTURA = 12  # angoli ChArUco minimi per salvare un'immagine
MIN_ANGOLI_CALCOLO = 6   # angoli minimi perché un'immagine entri nella calibrazione
MIN_IMMAGINI = 10


def cattura(cfg: dict) -> int:
    board = crea_board(cfg)
    detector = cv2.aruco.CharucoDetector(board)
    cartella = percorso(cfg, "immagini_calibrazione")
    cartella.mkdir(parents=True, exist_ok=True)
    salvate = len(list(cartella.glob("*.png")))
    copertura: list[np.ndarray] = []  # angoli delle immagini salvate, per vedere le zone coperte
    messaggio = ""

    cap = apri_camera(cfg)
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        angoli, ids, _, _ = detector.detectBoard(frame)
        n = 0 if ids is None else len(ids)
        vis = frame.copy()
        for p in copertura:
            cv2.circle(vis, (int(p[0]), int(p[1])), 2, (160, 160, 160), -1)
        if n:
            # reshape: OpenCV 5 restituisce gli angoli come (N, 2), la funzione di disegno vuole (N, 1, 2)
            cv2.aruco.drawDetectedCornersCharuco(vis, angoli.reshape(-1, 1, 2), ids.reshape(-1, 1), (0, 255, 0))
        colore = (0, 200, 0) if n >= MIN_ANGOLI_CATTURA else (0, 0, 255)
        cv2.putText(vis, f"angoli: {n}   salvate: {salvate}   SPAZIO salva, q termina",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, colore, 2)
        if messaggio:
            cv2.putText(vis, messaggio, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2)
        cv2.imshow("calibrazione - cattura", vis)

        tasto = cv2.waitKey(1) & 0xFF
        if tasto in (ord("q"), 27):
            break
        if tasto == ord(" "):
            if n >= MIN_ANGOLI_CATTURA:
                salvate += 1
                cv2.imwrite(str(cartella / f"img_{salvate:03d}.png"), frame)  # l'immagine originale, senza disegni
                copertura.extend(angoli.reshape(-1, 2))
                messaggio = f"salvata img_{salvate:03d}.png"
            else:
                messaggio = f"servono almeno {MIN_ANGOLI_CATTURA} angoli visibili"
    cap.release()
    cv2.destroyAllWindows()
    return salvate


def calcola(cfg: dict) -> None:
    board = crea_board(cfg)
    detector = cv2.aruco.CharucoDetector(board)
    cartella = percorso(cfg, "immagini_calibrazione")
    file_immagini = sorted(cartella.glob("*.png"))

    punti_3d, punti_2d, nomi = [], [], []
    dimensione = None
    for f in file_immagini:
        img = cv2.imread(str(f))
        if dimensione is None:
            dimensione = (img.shape[1], img.shape[0])
        elif (img.shape[1], img.shape[0]) != dimensione:
            print(f"  {f.name}: risoluzione diversa dalle altre, scartata")
            continue
        angoli, ids, _, _ = detector.detectBoard(img)
        if ids is None or len(ids) < MIN_ANGOLI_CALCOLO:
            print(f"  {f.name}: board non trovata o troppo pochi angoli, scartata")
            continue
        obj, imgp = board.matchImagePoints(angoli, ids)
        punti_3d.append(obj)
        punti_2d.append(imgp)
        nomi.append(f.name)

    if len(punti_3d) < MIN_IMMAGINI:
        raise SystemExit(f"Immagini valide: {len(punti_3d)}. Ne servono almeno {MIN_IMMAGINI}: "
                         "usa 'python calibra.py cattura'.")

    rms, K, dist, _, _, _, _, errori = cv2.calibrateCameraExtended(punti_3d, punti_2d, dimensione, None, None)
    errori = errori.ravel()

    w, _ = dimensione
    fov_x = math.degrees(2 * math.atan(w / (2 * K[0, 0])))
    print(f"\nImmagini usate: {len(punti_3d)} su {len(file_immagini)}  —  risoluzione {dimensione[0]}x{dimensione[1]}")
    print(f"Errore di riproiezione RMS: {rms:.3f} px  "
          f"({'ottimo' if rms < 0.5 else 'accettabile' if rms < 1 else 'da rifare'})")
    print(f"fx = {K[0, 0]:.1f}  fy = {K[1, 1]:.1f}  cx = {K[0, 2]:.1f}  cy = {K[1, 2]:.1f}  (FOV orizzontale ≈ {fov_x:.1f}°)")
    print(f"distorsione [k1 k2 p1 p2 k3] = {np.round(dist.ravel(), 4)}")

    soglia = max(2 * float(np.median(errori)), 0.5)  # sotto 0.5 px un'immagine va comunque bene
    peggiori = [(n, e) for n, e in zip(nomi, errori) if e > soglia]
    if peggiori:
        print("\nImmagini con errore molto sopra la mediana (forse mosse o sfocate: valuta di eliminarle e ricalcolare):")
        for n, e in sorted(peggiori, key=lambda x: -x[1]):
            print(f"  {n}: {e:.2f} px")

    file = percorso(cfg, "calibrazione")
    salva_calibrazione(file, K, dist, dimensione, rms, len(punti_3d))
    print(f"\nCalibrazione salvata in {file}")


def verifica(cfg: dict) -> None:
    cap = apri_camera(cfg)
    ok, frame = cap.read()
    h, w = frame.shape[:2]
    K, dist, calibrata = carica_calibrazione(cfg, (w, h))
    if not calibrata:
        raise SystemExit("Nessuna calibrazione valida: esegui prima 'cattura' e 'calcola'.")
    # alpha=0: l'immagine corretta contiene solo pixel validi (niente bordi neri)
    K_nuova, _ = cv2.getOptimalNewCameraMatrix(K, dist, (w, h), 0)
    mappa_x, mappa_y = cv2.initUndistortRectifyMap(K, dist, None, K_nuova, (w, h), cv2.CV_32FC1)
    print("Guarda linee dritte vicino ai bordi (stipiti, scaffali): nell'immagine corretta devono restare dritte. q per uscire.")
    while ok:
        corretta = cv2.remap(frame, mappa_x, mappa_y, cv2.INTER_LINEAR)
        for img, testo in ((frame, "originale"), (corretta, "corretta")):
            cv2.putText(img, testo, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
        affiancate = np.hstack([frame, corretta])
        scala = min(1.0, 1600 / affiancate.shape[1])
        cv2.imshow("calibrazione - verifica", cv2.resize(affiancate, None, fx=scala, fy=scala))
        if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
            break
        ok, frame = cap.read()
    cap.release()
    cv2.destroyAllWindows()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("azione", choices=["cattura", "calcola", "verifica"])
    args = ap.parse_args()
    cfg = carica_config()

    if args.azione == "cattura":
        if cattura(cfg) >= MIN_IMMAGINI:
            calcola(cfg)
        else:
            print(f"Servono almeno {MIN_IMMAGINI} immagini per calcolare la calibrazione.")
    elif args.azione == "calcola":
        calcola(cfg)
    else:
        verifica(cfg)


if __name__ == "__main__":
    main()
