"""Controllo automatico delle funzioni di posa.py, senza webcam.

    python controlla_posa.py

Genera immagini sintetiche di un marker con posa nota, esegue le tue funzioni e
confronta i risultati con i valori veri. Per ogni TODO stampa OK, ERRATO o DA FARE.
"""
from __future__ import annotations

import math

import cv2
import numpy as np

import posa

W, H = 1280, 720
K = np.array([[800.0, 0, W / 2], [0, 800.0, H / 2], [0, 0, 1]])
DIST = np.zeros(5)
LATO = 0.05
DIZ = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)


def rendi_marker(rvec: np.ndarray, tvec: np.ndarray, marker_id: int = 7) -> np.ndarray:
    """Immagine del marker vista da una camera con calibrazione K e posa (rvec, tvec)."""
    lato_px = 600
    marker = cv2.aruco.generateImageMarker(DIZ, marker_id, lato_px)
    # pixel del marker -> metri nel piano del marker (origine al centro, y in alto)
    A = np.array([[LATO / lato_px, 0, -LATO / 2], [0, -LATO / lato_px, LATO / 2], [0, 0, 1]])
    R, _ = cv2.Rodrigues(rvec)
    omografia = K @ np.column_stack([R[:, 0], R[:, 1], tvec.ravel()]) @ A
    return cv2.warpPerspective(marker, omografia, (W, H), flags=cv2.INTER_LINEAR, borderValue=255)


def rileva(img: np.ndarray) -> np.ndarray:
    p = cv2.aruco.DetectorParameters()
    p.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    angoli, ids, _ = cv2.aruco.ArucoDetector(DIZ, p).detectMarkers(img)
    if ids is None:
        raise RuntimeError("marker sintetico non rilevato: problema nel test, non nel tuo codice")
    return angoli[0].reshape(4, 2)


def angolo_tra(R1: np.ndarray, R2: np.ndarray) -> float:
    c = (np.trace(R1.T @ R2) - 1) / 2
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


def rpy_in_R(roll: float, pitch: float, yaw: float) -> np.ndarray:
    r, p, y = np.radians([roll, pitch, yaw])
    Rx = np.array([[1, 0, 0], [0, math.cos(r), -math.sin(r)], [0, math.sin(r), math.cos(r)]])
    Ry = np.array([[math.cos(p), 0, math.sin(p)], [0, 1, 0], [-math.sin(p), 0, math.cos(p)]])
    Rz = np.array([[math.cos(y), -math.sin(y), 0], [math.sin(y), math.cos(y), 0], [0, 0, 1]])
    return Rz @ Ry @ Rx


# Posa di riferimento: marker a 40 cm, di fronte alla camera e un po' inclinato.
RVEC = np.array([[math.pi * 0.9], [0.15], [0.05]])
TVEC = np.array([[0.03], [-0.02], [0.40]])


def controlla_stima_posa(angoli):
    stima = posa.stima_posa(angoli, LATO, K, DIST)
    if stima is None:
        return None, "DA FARE"
    rvec, tvec = (np.asarray(v, dtype=np.float64).reshape(3, 1) for v in stima)
    errore_t = np.linalg.norm(tvec - TVEC) * 1000
    errore_r = angolo_tra(cv2.Rodrigues(rvec)[0], cv2.Rodrigues(RVEC)[0])
    esito = f"posizione {errore_t:.1f} mm, rotazione {errore_r:.2f}°"
    if errore_t > 5 or errore_r > 2:
        return None, f"ERRATO ({esito}): controlla l'ordine dei punti e il flag SOLVEPNP_IPPE_SQUARE"
    return (rvec, tvec), f"OK ({esito})"


def controlla_errore_riproiezione(angoli):
    err = posa.errore_riproiezione(angoli, RVEC, TVEC, LATO, K, DIST)
    if err is None:
        return "DA FARE"
    proiettati, _ = cv2.projectPoints(posa.punti_marker(LATO), RVEC, TVEC, K, DIST)
    atteso = float(np.linalg.norm(proiettati.reshape(4, 2) - angoli, axis=1).mean())
    if abs(float(err) - atteso) > 1e-3:
        return f"ERRATO (ottenuto {float(err):.4f} px, atteso {atteso:.4f} px)"
    sbagliato = posa.errore_riproiezione(angoli, RVEC, TVEC + [[0.01], [0], [0]], LATO, K, DIST)
    return f"OK ({atteso:.3f} px con la posa vera, {float(sbagliato):.1f} px spostandola di 1 cm)"


def controlla_disegna_cubo():
    img = np.zeros((H, W, 3), np.uint8)
    if not posa.disegna_cubo(img, RVEC, TVEC, LATO, K, DIST):
        return "DA FARE"
    s = LATO / 2
    vertici = np.array([[x, y, z] for z in (0, LATO) for x, y in ((-s, s), (s, s), (s, -s), (-s, -s))], np.float32)
    proiettati, _ = cv2.projectPoints(vertici, RVEC, TVEC, K, DIST)
    disegnato = img.max(axis=2) > 0
    mancanti = [i for i, (x, y) in enumerate(proiettati.reshape(-1, 2))
                if not disegnato[max(0, int(y) - 3):int(y) + 4, max(0, int(x) - 3):int(x) + 4].any()]
    if mancanti:
        return (f"ERRATO: nessuna linea vicino ai vertici {mancanti} "
                "(il coperchio va a z = +lato, verso la camera)")
    return "OK"


def controlla_ambiguita():
    risultati = []
    for nome, rvec, tvec in (("frontale vicino", RVEC, TVEC),
                             ("piccolo e lontano", np.array([[math.pi], [0.02], [0.0]]), np.array([[0.0], [0.0], [1.6]]))):
        angoli = rileva(rendi_marker(rvec, tvec))
        rapporto = posa.rapporto_ambiguita(angoli, LATO, K, DIST)
        if rapporto is None:
            return "DA FARE"
        _, _, _, errori = cv2.solvePnPGeneric(posa.punti_marker(LATO), angoli, K, DIST,
                                              flags=cv2.SOLVEPNP_IPPE_SQUARE)
        atteso = float(errori[1][0] / max(errori[0][0], 1e-12))
        if not math.isclose(float(rapporto), atteso, rel_tol=1e-3):
            return f"ERRATO ({nome}: ottenuto {float(rapporto):.3f}, atteso {atteso:.3f})"
        risultati.append(f"{nome} {atteso:.1f}")
    return "OK (" + ", ".join(risultati) + ")"


def controlla_matrice():
    T = posa.matrice_da_rvec_tvec(RVEC, TVEC)
    if T is None:
        return None, "DA FARE"
    T = np.asarray(T, dtype=np.float64)
    if T.shape != (4, 4):
        return None, f"ERRATO: forma {T.shape}, attesa (4, 4)"
    ok = (np.allclose(T[:3, :3], cv2.Rodrigues(RVEC)[0]) and np.allclose(T[:3, 3], TVEC.ravel())
          and np.allclose(T[3], [0, 0, 0, 1]))
    return (T, "OK") if ok else (None, "ERRATO: R, t o l'ultima riga [0 0 0 1] non tornano")


def controlla_inversa(T):
    if T is None:
        T = np.eye(4)
        T[:3, :3], T[:3, 3] = cv2.Rodrigues(RVEC)[0], TVEC.ravel()
    T_inv = posa.inversa(T)
    if T_inv is None:
        return "DA FARE"
    if not np.allclose(np.asarray(T_inv) @ T, np.eye(4)):
        return "ERRATO: inversa(T) @ T non è l'identità"
    return "OK"


def controlla_eulero():
    attesi = (10.0, -20.0, 30.0)
    rpy = posa.angoli_eulero(rpy_in_R(*attesi))
    if rpy is None:
        return "DA FARE"
    if not np.allclose(rpy, attesi, atol=1e-6):
        return f"ERRATO (ottenuto {np.round(rpy, 3).tolist()}, atteso {list(attesi)})"
    return "OK"


def main() -> None:
    angoli = rileva(rendi_marker(RVEC, TVEC))
    controlli = [
        ("TODO 1  stima_posa", lambda: controlla_stima_posa(angoli)[1]),
        ("TODO 2  errore_riproiezione", lambda: controlla_errore_riproiezione(angoli)),
        ("TODO 3  disegna_cubo", controlla_disegna_cubo),
        ("TODO 4  rapporto_ambiguita", controlla_ambiguita),
        ("TODO 5a matrice_da_rvec_tvec", lambda: controlla_matrice()[1]),
        ("TODO 5b inversa", lambda: controlla_inversa(controlla_matrice()[0])),
        ("TODO 6  angoli_eulero", controlla_eulero),
    ]
    for nome, controllo in controlli:
        try:
            esito = controllo()
        except Exception as e:  # mostra l'errore e passa al controllo successivo
            esito = f"ERRORE: {type(e).__name__}: {e}"
        print(f"{nome:<32}{esito}")


if __name__ == "__main__":
    main()
