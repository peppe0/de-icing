"""Laboratorio ArUco con la webcam: rilevamento, posa, registrazione.

    python app.py

Tasti (h mostra/nasconde la legenda a schermo):
  d  debug: soglie adattive, candidati scartati (rosso), ordine degli angoli
  t  finestra con gli slider dei parametri del detector
  p  posa: assi, distanza, posizione, errore di riproiezione, angoli
  c  cubo virtuale appoggiato sul marker
  a  rapporto di ambiguità della posa
  m  posa relativa tra i due marker con ID più basso
  r  avvia/ferma la registrazione su CSV (dati/registrazioni)
  s  screenshot (dati/screenshot)
  q  esci (anche ESC)
"""
from __future__ import annotations

import csv
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

import posa
from comune import apri_camera, carica_calibrazione, carica_config, crea_detector, parametri_detector, percorso

VERDE, ROSSO, GIALLO, BIANCO, BLU = (0, 200, 0), (0, 0, 255), (0, 220, 255), (255, 255, 255), (255, 140, 0)
FONT = cv2.FONT_HERSHEY_SIMPLEX
FINESTRA, FINESTRA_SOGLIE, FINESTRA_PARAMETRI = "aruco-lab", "soglie adattive", "parametri detector"

# Soglie indicative per colorare il rapporto di ambiguità: verificale con i tuoi esperimenti.
AMBIGUITA_ROSSO, AMBIGUITA_GIALLO = 1.5, 3.0

COLONNE_CSV = ["t_s", "id", "tx_m", "ty_m", "tz_m", "rx", "ry", "rz",
               "distanza_m", "errore_px", "rapporto_ambiguita"]

# Slider dei parametri del detector: (nome, attributo, scala, minimo, massimo)
SLIDER = [
    ("finestra min", "adaptiveThreshWinSizeMin", 1, 3, 50),
    ("finestra max", "adaptiveThreshWinSizeMax", 1, 3, 100),
    ("finestra passo", "adaptiveThreshWinSizeStep", 1, 1, 50),
    ("costante soglia", "adaptiveThreshConstant", 1, 0, 30),
    ("perimetro min x1000", "minMarkerPerimeterRate", 1000, 1, 500),
    ("correzione errori x100", "errorCorrectionRate", 100, 0, 100),
]


@dataclass
class Stato:
    debug: bool = False
    parametri: bool = False
    posa: bool = True
    cubo: bool = False
    ambiguita: bool = False
    relativa: bool = False
    legenda: bool = True


@dataclass
class Contesto:
    detector: cv2.aruco.ArucoDetector
    parametri: cv2.aruco.DetectorParameters
    K: np.ndarray
    dist: np.ndarray
    calibrata: bool
    lato: float


@dataclass
class Risultato:
    vis: np.ndarray
    soglie: np.ndarray | None = None
    righe: list[dict] = field(default_factory=list)  # righe per il CSV
    todo: set[tuple[str, str]] = field(default_factory=set)  # (numero TODO, funzione) ancora da fare
    info: list[str] = field(default_factory=list)  # righe extra per l'HUD


class Registratore:
    def __init__(self, cartella: Path):
        cartella.mkdir(parents=True, exist_ok=True)
        self.file = cartella / f"reg_{datetime.now():%Y%m%d_%H%M%S}.csv"
        self._f = open(self.file, "w", newline="", encoding="utf-8")
        self._w = csv.DictWriter(self._f, fieldnames=COLONNE_CSV)
        self._w.writeheader()
        self.righe = 0

    def scrivi(self, righe: list[dict]) -> None:
        self._w.writerows(righe)
        self.righe += len(righe)

    def chiudi(self) -> None:
        self._f.close()


def testo(img: np.ndarray, s: str, org: tuple[int, int], colore=BIANCO, scala: float = 0.55) -> None:
    """Testo su un riquadro scuro, leggibile su qualsiasi sfondo."""
    (w, h), base = cv2.getTextSize(s, FONT, scala, 1)
    x, y = org
    cv2.rectangle(img, (x - 3, y - h - 4), (x + w + 3, y + base + 2), (30, 30, 30), -1)
    cv2.putText(img, s, org, FONT, scala, colore, 1, cv2.LINE_AA)


def mosaico_soglie(gray: np.ndarray, p: cv2.aruco.DetectorParameters, larghezza_max: int) -> np.ndarray:
    """Le immagini binarie su cui lavora il detector: una per ogni dimensione della finestra
    di soglia adattiva, da adaptiveThreshWinSizeMin a Max con passo Step. I marker devono
    apparire come quadrati bianchi ben chiusi in almeno una di queste."""
    finestre = list(range(p.adaptiveThreshWinSizeMin, p.adaptiveThreshWinSizeMax + 1,
                          max(1, p.adaptiveThreshWinSizeStep)))
    if len(finestre) > 6:  # troppe da mostrare: ne tengo 6 equidistanti
        finestre = [finestre[i] for i in np.linspace(0, len(finestre) - 1, 6).round().astype(int)]
    scala = min(1.0, larghezza_max / (len(finestre) * gray.shape[1]))
    tasselli = []
    for f in finestre:
        f = max(3, f | 1)  # come nel detector: finestra dispari e almeno 3
        b = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV,
                                  f, p.adaptiveThreshConstant)
        b = cv2.cvtColor(cv2.resize(b, None, fx=scala, fy=scala, interpolation=cv2.INTER_AREA),
                         cv2.COLOR_GRAY2BGR)
        testo(b, f"finestra {f} px", (8, 22), VERDE)
        tasselli.append(b)
    return cv2.hconcat(tasselli)


def elabora_frame(frame: np.ndarray, stato: Stato, ctx: Contesto, t: float = 0.0) -> Risultato:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    angoli, ids, scartati = ctx.detector.detectMarkers(gray)
    r = Risultato(vis=frame.copy())

    if stato.debug:
        r.soglie = mosaico_soglie(gray, ctx.parametri, 1600)
        if scartati:
            cv2.aruco.drawDetectedMarkers(r.vis, scartati, borderColor=ROSSO)
    if ids is None:
        return r
    cv2.aruco.drawDetectedMarkers(r.vis, angoli, ids, borderColor=VERDE)
    if stato.debug:
        for c in angoli:
            for k, (x, y) in enumerate(c.reshape(4, 2)):
                testo(r.vis, str(k), (int(x) + 4, int(y) - 4), BLU, 0.6)
    if not stato.posa:
        return r

    pose: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    for c, marker_id in sorted(zip(angoli, ids.ravel()), key=lambda x: x[1]):
        marker_id = int(marker_id)
        c = c.reshape(4, 2)
        stima = posa.stima_posa(c, ctx.lato, ctx.K, ctx.dist)
        if stima is None:
            r.todo.add(("1", "stima_posa"))
            continue
        rvec, tvec = stima
        pose[marker_id] = (rvec, tvec)
        cv2.drawFrameAxes(r.vis, ctx.K, ctx.dist, rvec, tvec, ctx.lato / 2)

        t_cm = tvec.ravel() * 100
        etichette = [(f"id {marker_id}: {np.linalg.norm(t_cm):.1f} cm", BIANCO),
                     (f"x {t_cm[0]:.1f}  y {t_cm[1]:.1f}  z {t_cm[2]:.1f}", BIANCO)]

        err = posa.errore_riproiezione(c, rvec, tvec, ctx.lato, ctx.K, ctx.dist)
        if err is None:
            r.todo.add(("2", "errore_riproiezione"))
        else:
            etichette.append((f"err {err:.2f} px", BIANCO))

        if stato.cubo and not posa.disegna_cubo(r.vis, rvec, tvec, ctx.lato, ctx.K, ctx.dist):
            r.todo.add(("3", "disegna_cubo"))

        rapporto = posa.rapporto_ambiguita(c, ctx.lato, ctx.K, ctx.dist)
        if rapporto is None:
            r.todo.add(("4", "rapporto_ambiguita"))
        elif stato.ambiguita:
            colore = ROSSO if rapporto < AMBIGUITA_ROSSO else GIALLO if rapporto < AMBIGUITA_GIALLO else VERDE
            etichette.append((f"ambiguita {rapporto:.1f}", colore))

        T = posa.matrice_da_rvec_tvec(rvec, tvec)
        if T is None:
            r.todo.add(("5a", "matrice_da_rvec_tvec"))
        else:
            eulero = posa.angoli_eulero(T[:3, :3])
            if eulero is None:
                r.todo.add(("6", "angoli_eulero"))
            else:
                etichette.append(("roll {:.0f}  pitch {:.0f}  yaw {:.0f}".format(*eulero), BIANCO))

        x0, y0 = int(c[:, 0].min()), int(c[:, 1].max()) + 22
        for i, (s, colore) in enumerate(etichette):
            testo(r.vis, s, (x0, y0 + 21 * i), colore, 0.5)

        r.righe.append({
            "t_s": round(t, 4), "id": marker_id,
            "tx_m": float(tvec[0, 0]), "ty_m": float(tvec[1, 0]), "tz_m": float(tvec[2, 0]),
            "rx": float(rvec[0, 0]), "ry": float(rvec[1, 0]), "rz": float(rvec[2, 0]),
            "distanza_m": float(np.linalg.norm(tvec)),
            "errore_px": "" if err is None else round(float(err), 4),
            "rapporto_ambiguita": "" if rapporto is None else round(float(rapporto), 4),
        })

    if stato.relativa:
        posa_relativa(pose, r)
    return r


def posa_relativa(pose: dict[int, tuple[np.ndarray, np.ndarray]], r: Risultato) -> None:
    """T_M1_M2 = inversa(T_C_M1) @ T_C_M2 per i due marker con ID più basso."""
    if len(pose) < 2:
        r.info.append("posa relativa: servono almeno 2 marker con la posa stimata")
        return
    (id1, (rv1, tv1)), (id2, (rv2, tv2)) = sorted(pose.items())[:2]
    T1, T2 = posa.matrice_da_rvec_tvec(rv1, tv1), posa.matrice_da_rvec_tvec(rv2, tv2)
    if T1 is None or T2 is None:
        r.todo.add(("5a", "matrice_da_rvec_tvec"))
        return
    T1_inv = posa.inversa(T1)
    if T1_inv is None:
        r.todo.add(("5b", "inversa"))
        return
    T12 = T1_inv @ T2
    t = T12[:3, 3] * 100
    riga = f"T_{id1}_{id2}: t = ({t[0]:.1f}, {t[1]:.1f}, {t[2]:.1f}) cm  |t| = {np.linalg.norm(t):.1f} cm"
    eulero = posa.angoli_eulero(T12[:3, :3])
    if eulero is not None:
        riga += "  rpy = ({:.0f}, {:.0f}, {:.0f})".format(*eulero)
    r.info.append(riga)


def disegna_hud(img: np.ndarray, stato: Stato, ctx: Contesto, fps: float,
                reg: Registratore | None, r: Risultato) -> None:
    righe = [(f"{fps:4.1f} fps   " + ("camera calibrata" if ctx.calibrata
              else "camera NON calibrata: K approssimata, distanze indicative"),
              VERDE if ctx.calibrata else GIALLO)]
    if reg:
        righe.append((f"REC {reg.file.name}  ({reg.righe} righe)", ROSSO))
    righe += [(s, BIANCO) for s in r.info]
    if r.todo:
        mancanti = ", ".join(f"{nome} (TODO {num})" for num, nome in sorted(r.todo))
        righe.append((f"Da completare in posa.py: {mancanti}", GIALLO))
    if stato.legenda:
        on = lambda v: "ON" if v else "off"  # noqa: E731
        righe += [
            (f"d debug [{on(stato.debug)}]   t parametri [{on(stato.parametri)}]   p posa [{on(stato.posa)}]", BIANCO),
            (f"c cubo [{on(stato.cubo)}]   a ambiguita [{on(stato.ambiguita)}]   m relativa [{on(stato.relativa)}]", BIANCO),
            ("r registra   s screenshot   h legenda   q esci", BIANCO),
        ]
    for i, (s, colore) in enumerate(righe):
        testo(img, s, (10, 26 + 26 * i), colore, 0.6)


def apri_slider(p: cv2.aruco.DetectorParameters) -> None:
    cv2.namedWindow(FINESTRA_PARAMETRI, cv2.WINDOW_NORMAL)
    for nome, attributo, scala, _, massimo in SLIDER:
        cv2.createTrackbar(nome, FINESTRA_PARAMETRI, int(round(getattr(p, attributo) * scala)), massimo,
                           lambda _v: None)


def leggi_slider(p: cv2.aruco.DetectorParameters) -> bool:
    """Aggiorna i parametri dagli slider. Restituisce True se qualcosa è cambiato."""
    cambiato = False
    for nome, attributo, scala, minimo, _ in SLIDER:
        valore = max(minimo, cv2.getTrackbarPos(nome, FINESTRA_PARAMETRI)) / scala
        if attributo == "adaptiveThreshWinSizeMax":
            valore = max(valore, p.adaptiveThreshWinSizeMin)
        valore = type(getattr(p, attributo))(valore)
        if getattr(p, attributo) != valore:
            setattr(p, attributo, valore)
            cambiato = True
    return cambiato


def main() -> None:
    cfg = carica_config()
    cap = apri_camera(cfg)
    ok, frame = cap.read()
    h, w = frame.shape[:2]
    K, dist, calibrata = carica_calibrazione(cfg, (w, h))
    if not calibrata:
        print("Camera non calibrata: le distanze sono solo indicative. Esegui 'python calibra.py cattura'.")
    parametri = parametri_detector()
    ctx = Contesto(crea_detector(cfg, parametri), parametri, K, dist, calibrata, cfg["marker"]["lato_m"])
    stato = Stato()
    reg: Registratore | None = None
    soglie_aperte = False
    t0 = t_prec = time.monotonic()
    fps = 0.0

    while ok:
        ora = time.monotonic()
        dt = max(ora - t_prec, 1e-6)
        fps = 1 / dt if fps == 0 else 0.9 * fps + 0.1 / dt
        t_prec = ora

        if stato.parametri and leggi_slider(ctx.parametri):
            ctx.detector.setDetectorParameters(ctx.parametri)
        r = elabora_frame(frame, stato, ctx, ora - t0)
        if reg:
            reg.scrivi(r.righe)
        disegna_hud(r.vis, stato, ctx, fps, reg, r)
        cv2.imshow(FINESTRA, r.vis)
        if r.soglie is not None:
            cv2.imshow(FINESTRA_SOGLIE, r.soglie)
            soglie_aperte = True
        elif soglie_aperte:
            cv2.destroyWindow(FINESTRA_SOGLIE)
            soglie_aperte = False

        tasto = cv2.waitKey(1) & 0xFF
        if tasto in (ord("q"), 27) or cv2.getWindowProperty(FINESTRA, cv2.WND_PROP_VISIBLE) < 1:
            break
        elif tasto == ord("d"):
            stato.debug = not stato.debug
        elif tasto == ord("t"):
            stato.parametri = not stato.parametri
            if stato.parametri:
                apri_slider(ctx.parametri)
            else:
                cv2.destroyWindow(FINESTRA_PARAMETRI)
        elif tasto == ord("p"):
            stato.posa = not stato.posa
        elif tasto == ord("c"):
            stato.cubo = not stato.cubo
        elif tasto == ord("a"):
            stato.ambiguita = not stato.ambiguita
        elif tasto == ord("m"):
            stato.relativa = not stato.relativa
        elif tasto == ord("h"):
            stato.legenda = not stato.legenda
        elif tasto == ord("r"):
            if reg:
                reg.chiudi()
                print(f"Registrazione salvata: {reg.file} ({reg.righe} righe)")
                reg = None
            else:
                reg = Registratore(percorso(cfg, "registrazioni"))
        elif tasto == ord("s"):
            cartella = percorso(cfg, "screenshot")
            cartella.mkdir(parents=True, exist_ok=True)
            file = cartella / f"screenshot_{datetime.now():%Y%m%d_%H%M%S}.png"
            cv2.imwrite(str(file), r.vis)
            print(f"Screenshot salvato: {file}")
        ok, frame = cap.read()

    if reg:
        reg.chiudi()
        print(f"Registrazione salvata: {reg.file} ({reg.righe} righe)")
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
