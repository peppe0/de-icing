"""Funzioni condivise: configurazione, camera, detector, board ChArUco e calibrazione."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import yaml

CARTELLA = Path(__file__).resolve().parent


def carica_config(percorso: str | Path | None = None) -> dict:
    percorso = Path(percorso) if percorso else CARTELLA / "config.yaml"
    with open(percorso, encoding="utf-8") as f:
        return yaml.safe_load(f)


def percorso(cfg: dict, chiave: str) -> Path:
    """Percorso di una voce della sezione `file` della config, relativo ad aruco-lab/."""
    p = Path(cfg["file"][chiave])
    return p if p.is_absolute() else CARTELLA / p


def dizionario(nome: str) -> cv2.aruco.Dictionary:
    if not nome.startswith("DICT_") or not hasattr(cv2.aruco, nome):
        raise ValueError(f"Dizionario ArUco sconosciuto: {nome} (esempi: DICT_4X4_50, DICT_5X5_100)")
    return cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, nome))


def parametri_detector() -> cv2.aruco.DetectorParameters:
    p = cv2.aruco.DetectorParameters()
    # Raffinamento sub-pixel degli angoli: migliora molto la stabilità della posa.
    p.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    return p


def crea_detector(cfg: dict, parametri: cv2.aruco.DetectorParameters | None = None) -> cv2.aruco.ArucoDetector:
    return cv2.aruco.ArucoDetector(dizionario(cfg["marker"]["dizionario"]),
                                   parametri if parametri is not None else parametri_detector())


def crea_board(cfg: dict) -> cv2.aruco.CharucoBoard:
    c = cfg["charuco"]
    return cv2.aruco.CharucoBoard((c["quadrati_x"], c["quadrati_y"]),
                                  c["lato_quadrato_m"], c["lato_marker_m"], dizionario(c["dizionario"]))


def apri_camera(cfg: dict) -> cv2.VideoCapture:
    c = cfg["camera"]
    cap = cv2.VideoCapture(c["indice"])
    if not cap.isOpened():
        raise RuntimeError(
            f"Impossibile aprire la camera {c['indice']}.\n"
            "- Su Mac, la prima volta il sistema chiede il permesso e OpenCV non aspetta la risposta: "
            "consenti e rilancia il comando.\n"
            "- Se non compare nessuna richiesta: Impostazioni di Sistema → Privacy e sicurezza → Fotocamera, "
            "abilita l'app da cui lanci il comando (Terminale, iTerm o VS Code), chiudila con Cmd+Q e riaprila.\n"
            "- Prova un altro indice in config.yaml (camera.indice).")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, c["larghezza"])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, c["altezza"])
    if not c.get("autofocus", True):
        cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)  # non tutte le webcam (né tutti i sistemi) lo supportano
    ok, frame = cap.read()
    if not ok:
        raise RuntimeError("La camera si è aperta ma non restituisce immagini.")
    h, w = frame.shape[:2]
    if (w, h) != (c["larghezza"], c["altezza"]):
        print(f"Attenzione: la camera lavora a {w}x{h} invece di {c['larghezza']}x{c['altezza']}. "
              "Calibra e lavora sempre alla stessa risoluzione.")
    return cap


def salva_calibrazione(file: Path, K: np.ndarray, dist: np.ndarray, dimensione: tuple[int, int],
                       rms: float, n_immagini: int) -> None:
    file.parent.mkdir(parents=True, exist_ok=True)
    fs = cv2.FileStorage(str(file), cv2.FILE_STORAGE_WRITE)
    fs.write("K", K)
    fs.write("dist", dist)
    fs.write("larghezza", int(dimensione[0]))
    fs.write("altezza", int(dimensione[1]))
    fs.write("rms_px", float(rms))
    fs.write("n_immagini", int(n_immagini))
    fs.write("data", datetime.now().isoformat(timespec="seconds"))
    fs.release()


def carica_calibrazione(cfg: dict, dimensione: tuple[int, int]) -> tuple[np.ndarray, np.ndarray, bool]:
    """Restituisce (K, dist, calibrata). Se manca una calibrazione valida per questa
    risoluzione, usa una K approssimata (focale ≈ larghezza, cioè FOV orizzontale ≈ 53°)."""
    file = percorso(cfg, "calibrazione")
    if file.exists():
        fs = cv2.FileStorage(str(file), cv2.FILE_STORAGE_READ)
        K, dist = fs.getNode("K").mat(), fs.getNode("dist").mat()
        w, h = int(fs.getNode("larghezza").real()), int(fs.getNode("altezza").real())
        fs.release()
        if (w, h) == tuple(dimensione):
            return K, dist, True
        print(f"Calibrazione ignorata: è stata fatta a {w}x{h}, la camera ora lavora a "
              f"{dimensione[0]}x{dimensione[1]}.")
    w, h = dimensione
    K = np.array([[w, 0, w / 2], [0, w, h / 2], [0, 0, 1]], dtype=np.float64)
    return K, np.zeros(5), False
