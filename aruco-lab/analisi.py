"""Analisi di una registrazione CSV dell'app — DA COMPLETARE.

    python analisi.py                                       # ultima registrazione
    python analisi.py dati/registrazioni/reg_X.csv --distanza-reale 0.50

  TODO 7  jitter              → quanto "trema" la posa con il marker fermo
  TODO 8  confronto_distanza  → errore rispetto alla distanza misurata col metro
  TODO 9  grafici             → distanza e posizione nel tempo, salvati in PNG

Per l'esperimento: marker fermo (appoggiato, non in mano), camera ferma, 10-20 s di
registrazione per ogni distanza (es. 0.5, 1 e 2 m), misurando la distanza dalla lente
al centro del marker.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np

from comune import carica_config, percorso


def carica(file: Path) -> dict[int, dict[str, np.ndarray]]:
    """Legge il CSV e raggruppa le colonne per ID del marker: dati[id]["tz_m"] è un array.
    I valori mancanti (funzioni ancora da implementare) diventano NaN."""
    colonne: dict[int, dict[str, list[float]]] = {}
    with open(file, newline="", encoding="utf-8") as f:
        for riga in csv.DictReader(f):
            serie = colonne.setdefault(int(riga["id"]), {})
            for chiave, valore in riga.items():
                if chiave != "id":
                    serie.setdefault(chiave, []).append(float(valore) if valore != "" else np.nan)
    return {i: {k: np.array(v) for k, v in s.items()} for i, s in colonne.items()}


def jitter(serie: dict[str, np.ndarray]) -> dict[str, float] | None:
    """TODO 7: deviazione standard (np.std) di tx_m, ty_m, tz_m e distanza_m, in millimetri.
    Restituisci un dizionario, ad esempio {"tx_mm": ..., "ty_mm": ..., "tz_mm": ..., "distanza_mm": ...}.
    Domande da porti: quale asse trema di più? Come cresce il jitter con la distanza?"""
    return None


def confronto_distanza(serie: dict[str, np.ndarray], distanza_reale: float) -> dict[str, float] | None:
    """TODO 8: confronta la distanza stimata (colonna distanza_m) con quella misurata.
    Restituisci ad esempio {"media_m": ..., "errore_mm": media - reale, "errore_pct": ...}.
    Ripeti con e senza calibrazione: quanto cambia l'errore?"""
    return None


def grafici(dati: dict[int, dict[str, np.ndarray]], file_png: Path) -> bool:
    """TODO 9: con matplotlib (import matplotlib.pyplot as plt) disegna, per ogni marker,
    distanza_m e tz_m in funzione di t_s; se ti è utile aggiungi un secondo grafico con
    errore_px. Salva con plt.savefig(file_png), poi plt.show(), e restituisci True."""
    return False


def main() -> None:
    cfg = carica_config()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", nargs="?", type=Path, help="CSV da analizzare (default: il più recente)")
    ap.add_argument("--distanza-reale", type=float, help="distanza misurata col metro, in metri")
    args = ap.parse_args()

    file = args.file
    if file is None:
        registrazioni = sorted(percorso(cfg, "registrazioni").glob("reg_*.csv"))
        if not registrazioni:
            raise SystemExit("Nessuna registrazione trovata: nell'app premi r per avviarla e fermarla.")
        file = registrazioni[-1]

    dati = carica(file)
    if not dati:
        raise SystemExit(f"{file.name} non contiene pose: hai completato stima_posa (TODO 1)?")
    print(f"File: {file}")
    for marker_id, serie in sorted(dati.items()):
        n = len(serie["t_s"])
        durata = serie["t_s"][-1] - serie["t_s"][0] if n > 1 else 0.0
        print(f"\nMarker {marker_id}: {n} campioni in {durata:.1f} s"
              + (f" (circa {(n - 1) / durata:.0f} Hz)" if durata > 0 else ""))

        j = jitter(serie)
        print("  jitter: " + ("TODO 7" if j is None else ", ".join(f"{k} {v:.2f}" for k, v in j.items())))
        if args.distanza_reale is not None:
            c = confronto_distanza(serie, args.distanza_reale)
            print("  distanza: " + ("TODO 8" if c is None else ", ".join(f"{k} {v:.3f}" for k, v in c.items())))

    file_png = file.with_suffix(".png")
    print("\ngrafici: " + (f"salvati in {file_png}" if grafici(dati, file_png) else "TODO 9"))


if __name__ == "__main__":
    main()
