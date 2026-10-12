# aruco-lab

Applicazione per sperimentare con i marker ArUco usando la webcam del PC: rilevamento,
calibrazione della camera, stima della posa e analisi della precisione. È il primo passo
verso la registrazione dell'aereo nel progetto AR per il de-icing.

## Installazione

Serve Python 3.9 o successivo.

```bash
cd aruco-lab
python3 -m venv .venv
source .venv/bin/activate        # su Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Serve `opencv-python`, la versione con interfaccia grafica. Se hai installato anche
`opencv-contrib-python` o `opencv-python-headless`, disinstallali: più pacchetti OpenCV
nello stesso ambiente vanno in conflitto. Il codice funziona con OpenCV 4.8+ e 5.x.

## Flusso di lavoro

1. **Genera e stampa i marker**: `python genera_marker.py` crea in `dati/stampa/` i fogli
   A4 dei marker e della board ChArUco. Stampali al 100% ("dimensioni effettive"), incollali
   su un supporto rigido, **misura col righello** e scrivi le misure reali in `config.yaml`.
2. **Calibra la camera**: `python calibra.py cattura`. Salva 20-30 immagini della board
   (SPAZIO) e premi q: la calibrazione viene calcolata e salvata in `dati/calibrazione.yaml`.
   Controlla il risultato con `python calibra.py verifica`.
3. **Completa `posa.py`**: un TODO alla volta. Dopo ognuno esegui `python controlla_posa.py`,
   che verifica il tuo codice su immagini sintetiche, senza webcam.
4. **Usa l'app**: `python app.py`.
5. **Registra e analizza**: nell'app premi r per avviare e fermare la registrazione, poi
   `python analisi.py --distanza-reale 0.50` (dopo aver completato i TODO di `analisi.py`).

## Tasti dell'app

| Tasto | Funzione |
|---|---|
| `d` | debug: soglie adattive, candidati scartati (in rosso), ordine degli angoli |
| `t` | slider dei parametri del detector |
| `p` | posa: assi, distanza, posizione, errore di riproiezione, angoli |
| `c` | cubo virtuale appoggiato sul marker |
| `a` | rapporto di ambiguità della posa |
| `m` | posa relativa tra i due marker con ID più basso |
| `r` | avvia/ferma la registrazione su CSV |
| `s` | screenshot |
| `h` | mostra/nasconde la legenda |
| `q` / `ESC` | esci |

## Cosa è pronto e cosa devi completare

| File | Stato |
|---|---|
| `config.yaml` | pronto: aggiorna le misure dopo la stampa |
| `comune.py` | pronto: configurazione, camera, detector, board, file di calibrazione |
| `genera_marker.py` | pronto |
| `calibra.py` | pronto |
| `app.py` | pronto: chiama le funzioni di `posa.py` e indica a schermo quelle mancanti |
| `controlla_posa.py` | pronto: autoverifica dei TODO di `posa.py` |
| **`posa.py`** | **da completare: TODO 1-6** |
| **`analisi.py`** | **da completare: TODO 7-9** |

### I TODO, in ordine

| TODO | Funzione | Cosa impari |
|---|---|---|
| 1 | `stima_posa` | PnP: dagli angoli in pixel alla posa del marker |
| 2 | `errore_riproiezione` | come si misura la bontà di una posa |
| 3 | `disegna_cubo` | proiettare un oggetto 3D: è ciò che servirà per il modello dell'aereo |
| 4 | `rapporto_ambiguita` | perché un marker piccolo o lontano può "ribaltarsi" |
| 5a, 5b | `matrice_da_rvec_tvec`, `inversa` | trasformazioni 4×4 e composizione dei frame |
| 6 | `angoli_eulero` | leggere un orientamento |
| 7 | `jitter` | quanto trema la posa a marker fermo |
| 8 | `confronto_distanza` | accuratezza rispetto al metro |
| 9 | `grafici` | presentare i risultati |

## Esperimenti suggeriti

1. **Distanza**: marker a 0.5, 1 e 2 m, misurando dalla lente al centro del marker.
   Confronta l'errore con e senza calibrazione.
2. **Jitter**: a ogni distanza, 10-20 s con marker e camera fermi. Quale asse trema di più?
3. **Angolo**: ruota il marker da 0° a 70°. Come cambiano errore di riproiezione e ambiguità?
   Nota che il marker visto quasi di fronte e da lontano è il caso più ambiguo.
4. **Parametri del detector** (tasto `t` insieme a `d`): cosa succede alzando o abbassando
   la costante della soglia? Con quale perimetro minimo vedi marker più piccoli?
5. **Posa relativa** (tasto `m`): due marker su un cartoncino a distanza nota. La distanza
   calcolata resta costante muovendo la camera? Quanto vale l'errore?

I grafici di questi esperimenti sono già materiale per il capitolo sperimentale della tesi.

## Convenzioni

- Unità in metri, angoli in gradi.
- Frame della camera (OpenCV): x a destra, y in basso, z in avanti.
- Frame del marker: origine al centro, x a destra, y in alto, z uscente dal marker verso la
  camera. Per questo, con il marker di fronte, il roll vale circa ±180°.
- `rvec, tvec` restituiti da `stima_posa` descrivono `T_camera_marker`: la posa del marker
  nel frame della camera.

## Problemi comuni

- **La camera non si apre**: su Mac dai il permesso al Terminale o a VS Code in Impostazioni
  di Sistema → Privacy e sicurezza → Fotocamera. Se si apre la camera sbagliata (per esempio
  l'iPhone con Continuity Camera), cambia `camera.indice` in `config.yaml`.
- **Il marker non viene rilevato**: serve un bordo bianco attorno al marker; il dizionario in
  `config.yaml` deve essere lo stesso usato per generarlo; evita riflessi; se è piccolo nell'immagine,
  abbassa il perimetro minimo con gli slider.
- **Distanze sbagliate**: controlla `marker.lato_m` (lato reale, bordo nero compreso), che la
  camera sia calibrata e che la risoluzione sia la stessa della calibrazione.
- **Assi che saltano o si ribaltano**: è l'ambiguità della posa (TODO 4). Avvicinati o usa un
  marker più grande.
- **Tutorial online che non funzionano**: molti usano l'API vecchia
  (`estimatePoseSingleMarkers`, `aruco.detectMarkers`), rimossa in OpenCV 5.
