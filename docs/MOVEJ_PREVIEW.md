# MoveJ — piano comune, anteprima ed esecuzione

Stato locale aggiornato alla build 39. Il DOC mantiene cinque assi e il TCP configurato;
J6 richiede un giunto associato e l’hardware appropriato.

## Pianificare e osservare

Il pannello MoveJ accetta angoli assoluti, giunti Studio, una posa, un programma
supportato oppure una retta MoveL (vedi `MOVEL.md`). Ogni tratto articolare usa il
calcolo dei gruppi simultanei: massimi individuali, accelerazione normalizzata e
budget complessivo di 2000 impulsi/s. MoveJ interpola gli angoli: il TCP generalmente
segue una curva. Durata e picchi sono stime software, non misure del robot.

Pianificazione, cursore e Riproduci anteprima modificano solo il modello, anche con
il robot collegato ma fermo. Non cambiano posizioni comandate, HOME o percorsi.
L’arresto locale ferma l’animazione; STOP generale e modifiche di stato/configurazione
invalidano il piano. Nessuna ripresa automatica; piani eseguiti sono monouso.

Sono verificati limiti applicati, limiti URDF calibrati, mapping, assi esclusi e
interferenze lungo campioni a massimo 1° per giunto. Le collisioni usano capsule,
esclusioni e margini descritti in `COLLISIONI.md`, senza garanzia geometrica continua.
64 tratti, 200 istruzioni, 4096 campioni, un’ora stimata; attese sensore rifiutate.
La pinza in anteprima usa una durata convenzionale di 1,5 s; non è un tempo misurato.

## Eseguire lo stesso piano

`movej_run.py` esegue il piano mostrato dopo conferma esplicita
(`studio_movej_execute`, id corrente). Richiede controllore connesso, HOME valida,
stato fermo, contesto immutato e posizione uguale all’inizio del piano. Sul robot:
firmware MULTI_AXIS_V1; corrispondenza fisica dichiarata per Giunti Studio/MoveL;
pose provenienti dalla modalità robot.

Ogni tratto passa da `Controller.move_group`: una riga `~multi` validata, con attesa
di MULTI ACK e MULTI DONE, timeout e controllo di generation. STOP, USB persa,
interfaccia assente, ERROR o HALTED interrompono senza ripresa. Prima e dopo il tratto
il conteggio deve coincidere col piano. Pinza usa servo; le pause e note mantengono
l’ordine. Pausa trattiene tra i tratti. Il tempo misurato include attese software e,
in modalità robot, latenza ACK/DONE: non è una misura encoder.

I gruppi completati entrano nel percorso registrato, perciò HOME torna lungo di essi.
L’opzione ritorno aggiunge un tratto del piano: è animato in anteprima oppure eseguito
con Esegui MoveJ nella modalità scelta. Il firmware frena tra i tratti; non c’è blending.

Esegui target visualizzato usa il piano comune; solo firmware senza MULTI_AXIS_V1
mantiene il ripiego sequenziale. Una volta, Ripeti ed Esegui programma conservano
invece i percorsi insegnati: non sono riscritti come nuovi segmenti diretti. Per
eseguire un programma supportato su segmenti diretti seleziona Programma nel pannello
MoveJ. I piani temporanei non vengono salvati nel progetto.

## Verifiche e limiti

`test_movej_preview.py`, `test_movej_execution.py` e `test_movel.py` verificano profili,
limiti, invalidazione, monouso, ritorni, pinza/pause, STOP, ACK/DONE simulati, perdita
USB ed ERROR. Sono prove software: nessuna validazione di carico, passi persi,
jitter STEP, posizione fisica o sicurezza certificata. Non provato sul braccio reale.
