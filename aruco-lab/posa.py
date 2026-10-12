"""Stima della posa e trasformazioni — DA COMPLETARE.

Ogni funzione contiene un TODO con suggerimenti. Finché non la implementi restituisce
None (o False) e l'app mostra a schermo quale funzione manca. Ordine consigliato:

  TODO 1  stima_posa            → assi sul marker e distanza
  TODO 2  errore_riproiezione   → quanto la posa "spiega" gli angoli osservati
  TODO 3  disegna_cubo          → primo oggetto virtuale ancorato al marker
  TODO 4  rapporto_ambiguita    → quando fidarsi della posa
  TODO 5  matrice_da_rvec_tvec, inversa → trasformazioni 4x4 e posa relativa (tasto m)
  TODO 6  angoli_eulero         → orientamento leggibile (roll, pitch, yaw)

Convenzioni: unità in metri; frame della camera OpenCV con x a destra, y in basso,
z in avanti; frame del marker con origine al centro, x a destra, y in alto, z uscente
dal marker verso la camera.
"""
from __future__ import annotations

import cv2  # noqa: F401  (servirà nei TODO)
import numpy as np


def punti_marker(lato: float) -> np.ndarray:
    """Angoli del marker nel suo sistema di riferimento, nello stesso ordine in cui
    li restituisce il detector: 0 alto-sinistra, 1 alto-destra, 2 basso-destra,
    3 basso-sinistra. È l'ordine richiesto da cv2.SOLVEPNP_IPPE_SQUARE."""
    s = lato / 2
    return np.array([[-s, s, 0], [s, s, 0], [s, -s, 0], [-s, -s, 0]], dtype=np.float32)


def stima_posa(angoli: np.ndarray, lato: float, K: np.ndarray, dist: np.ndarray):
    """Posa del marker nel frame della camera (T_camera_marker).

    angoli: array (4, 2) con i pixel degli angoli; lato: lato del marker in metri.
    Restituisce (rvec, tvec), ciascuno di forma (3, 1), oppure None se la stima fallisce.

    TODO 1: usa cv2.solvePnP con punti_marker(lato), angoli, K, dist e
            flags=cv2.SOLVEPNP_IPPE_SQUARE; se riesce restituisci (rvec, tvec).
    Verifica: gli assi disegnati dall'app restano "incollati" al marker e la distanza
    mostrata corrisponde a quella misurata col metro (con la camera calibrata).
    """
    return None


def errore_riproiezione(angoli: np.ndarray, rvec: np.ndarray, tvec: np.ndarray, lato: float,
                        K: np.ndarray, dist: np.ndarray) -> float | None:
    """Errore medio, in pixel, tra gli angoli osservati e quelli riproiettati con la posa.

    TODO 2: proietta punti_marker(lato) con cv2.projectPoints(punti, rvec, tvec, K, dist)
            e calcola la media delle distanze dagli angoli osservati (np.linalg.norm).
    Valori attesi: pochi decimi di pixel. Se è grande, la posa (o la calibrazione) è sbagliata.
    """
    return None


def disegna_cubo(img: np.ndarray, rvec: np.ndarray, tvec: np.ndarray, lato: float,
                 K: np.ndarray, dist: np.ndarray) -> bool:
    """Disegna un cubo di lato `lato` appoggiato sul marker. Restituisce True se disegnato.

    TODO 3: definisci gli 8 vertici (i 4 angoli di punti_marker più gli stessi spostati di
            +lato lungo z, che esce dal marker verso la camera), proiettali con
            cv2.projectPoints e collega con cv2.line la base, il coperchio e i 4 spigoli verticali.
    Verifica: muovendo il marker il cubo resta appoggiato sopra, senza "scivolare".
    È la stessa operazione che servirà per sovrapporre il modello 3D dell'aereo.
    """
    return False


def rapporto_ambiguita(angoli: np.ndarray, lato: float, K: np.ndarray, dist: np.ndarray) -> float | None:
    """Rapporto tra gli errori di riproiezione delle due pose possibili di un marker piano.

    TODO 4: chiama cv2.solvePnPGeneric con flags=cv2.SOLVEPNP_IPPE_SQUARE: restituisce
            (n, rvecs, tvecs, errori) con le due soluzioni ordinate dalla migliore.
            Restituisci errori[1][0] / errori[0][0] (attento alla divisione per zero).
    Interpretazione: vicino a 1 le due pose spiegano ugualmente bene l'immagine → posa
    ambigua, può "ribaltarsi". Prova con marker piccolo, lontano e visto quasi di fronte.
    """
    return None


def matrice_da_rvec_tvec(rvec: np.ndarray, tvec: np.ndarray) -> np.ndarray | None:
    """Matrice omogenea 4x4 [R | t; 0 0 0 1] a partire da rvec (Rodrigues) e tvec.

    TODO 5a: R, _ = cv2.Rodrigues(rvec); metti R nel blocco 3x3 e tvec nell'ultima colonna
             di una np.eye(4).
    """
    return None


def inversa(T: np.ndarray) -> np.ndarray | None:
    """Inversa di una trasformazione rigida 4x4, senza usare np.linalg.inv.

    TODO 5b: se T = [R | t], l'inversa è [Rᵀ | -Rᵀ·t].
    Verifica: inversa(T) @ T deve dare la matrice identità (np.allclose).
    Uso nell'app (tasto m): T_M1_M2 = inversa(T_C_M1) @ T_C_M2 deve restare costante
    muovendo la camera, se i due marker sono fermi l'uno rispetto all'altro.
    """
    return None


def angoli_eulero(R: np.ndarray) -> tuple[float, float, float] | None:
    """Angoli (roll, pitch, yaw) in gradi della rotazione R, convenzione Z-Y-X.

    TODO 6: con R = Rz(yaw)·Ry(pitch)·Rx(roll):
            pitch = -asin(R[2,0]); roll = atan2(R[2,1], R[2,2]); yaw = atan2(R[1,0], R[0,0]).
    Nota: con il marker di fronte alla camera vedrai roll ≈ ±180°, perché la z del marker
    punta verso la camera mentre quella della camera punta in avanti. È normale.
    """
    return None
