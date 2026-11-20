> Aggiornamento build45: le pose registrate ora sono target con ID stabile, raggiunti direttamente dalla posizione attuale; nessun percorso storico viene riprodotto. I programmi a pose terminano sull’ultima istruzione senza HOME implicita. HOME manuale è un ritorno articolare diretto esplicito. Le descrizioni storiche dei percorsi insegnati sotto non prevalgono su queste regole. Vedere CAMPI_E_SEQUENZE.md.

# Programmi offline: MoveJ, MoveL, cicli, condizioni e variabili (fase 6)

Build 41 (istruzioni di movimento), build 42 (struttura e sensori) e build44 (funzioni). Il pannello Studio → **Programmi · istruzioni e anteprima** costruisce
programmi con istruzioni di movimento e li pianifica una sola volta. Anteprima 3D,
durata stimata, validazione ed esecuzione usano lo stesso piano.

## Istruzioni

| Tipo | Destinazione e opzioni | Diventa nel piano |
|---|---|---|
| MoveJ | `to`: `target` (+ `offset` mm nel riferimento del target, `orientation` `axis`/`position`), `home`, `pose` (`index`), `joints` (`angles`) · `speed` 10–100 % | un gruppo simultaneo; per un target, IK seminata con gli angoli dell'istruzione precedente, soluzione più vicina |
| MoveL | `to`: `target` (+ `offset`) o `point` (`frame`, `xyz` mm) · `orientation` `keep`/`free` · `tolerance` 0,05–5 mm · `speed` | i tratti di `movel.plan_line`, ognuno un gruppo simultaneo |
| Posa | `index` | MoveJ agli angoli della posa, pinza e pausa della posa |
| Uscita digitale (build43) | `kind: output`, `output`, `output_value` booleano, `timeout` 0,1–600s | stato simulato o richiesta esterna con conferma e timeout; durata massima nota |
| Pinza, Attesa, Nota | come prima | tappe del piano (pinza 1,5 s convenzionali) |
| Ripeti (vecchio) | `start`, `count`, non annidato | salto all'indietro; ogni ciclo parte da dove finisce il precedente |
| Ripeti N volte … Fine | `kind: loop`, `times` (espressione), `variable` facoltativo | ripetizione nota in pianificazione, contatore 0…N−1 |
| Se … Altrimenti … Fine | `kind: if`, `condition`; `else`, `end` | ramo deciso in pianificazione (solo variabili) o in esecuzione (sensori: entrambi i rami pianificati) |
| Variabile | `kind: set`, `variable`, `value` (espressione) | valore noto in pianificazione |
| Attesa sensore | `sensor`, `expected`, `timeout` | tappa `sensor`: attende il valore o si ferma al timeout |

`offset_expr` (tre stringhe, vuota = numero di `offset`) permette quote come `60 + strato*20`.

Un programma senza MoveJ/MoveL, strutture, variabili, uscite o funzioni abilitati resta un **programma a pose registrate** e
mantiene il comportamento precedente (percorsi insegnati, attese sensore, `run_program`).

## Linguaggio (`program_lang.py`)

Sintassi Python ristretta, analizzata con `ast` e valutata percorrendo solo nodi ammessi:
numeri, true/false, nomi (variabili o sensori), + - * / // %, confronti anche concatenati,
and/or/not. Niente chiamate, attributi, indici o import. Struttura bilanciata, al massimo
8 livelli; Altrimenti/Fine sono sempre attivi e seguono il loro Ripeti/Se.

## Rami verificati

L'interprete (`ProgramPlanner.segment`) segue i blocchi con il proprio stato: angoli, pinza,
variabili, contatori. Una condizione che legge sensori chiude il tratto di programma e apre
due stati; gli stati uguali (stessa istruzione, angoli, pinza, variabili, contatori) sono
pianificati una volta sola, quindi i rami che si ricongiungono non si moltiplicano. Ogni
tratto passa da `build_plan`. Limiti: 128 rami, 120 000 campioni. L'anteprima e le durate
seguono un percorso scelto per condizione (Vero/Falso nel pannello, altrimenti il valore
attuale del sensore); l'esecutore `movej_run.run_tree` legge la condizione e sceglie fra i due
seguiti già pianificati. Sul robot reale valgono solo dati non simulati con meno di 1 s.

## Velocità

`speed` è la percentuale delle velocità dei giunti di Muovi e osserva
(`Controller.group_plan(..., scale)`), con il minimo di 1 °/s accettato dalla Mega
(`~multi` richiede 1–20 °/s in centesimi). Il budget di 2000 impulsi/s resta valido:
per questo un MoveL breve a 50 % può durare quasi come a 100 %.

## Stesso piano, nessuna differenza nascosta

- `program_plan.ProgramPlanner` trasforma le istruzioni in tappe; `movej_preview.build_plan`
  le campiona ogni grado (limiti, URDF, autocollisioni, ostacoli, piano di lavoro).
- Il contesto del piano include istruzioni, scena (riferimenti e target), velocità, limiti,
  modello, calibrazione e posizione comandata: qualunque modifica lo rende scaduto.
- `movej_run.run_plan` esegue le tappe del piano. Prima di ogni gruppo il controllore
  ricalcola il profilo con la stessa velocità: se velocità richieste o durata differiscono
  dal piano, si ferma senza inviare impulsi.
- Un errore di pianificazione indica l'istruzione e il tratto (`Blocco N · nome · tratto k/n`),
  con causa e angoli; **Valida programma** usa la stessa pianificazione.

## Passo passo

`studio_program_execute` con `step=true`: la prima istruzione parte subito, poi il worker
si ferma prima di ogni nuova istruzione finché arriva `studio_program_step`;
`studio_program_continue` prosegue senza fermarsi. STOP interrompe anche durante l'attesa.
Le pause dell'operatore non entrano nella durata misurata.

## Fine programma e HOME

Se il programma termina con tutti i giunti a 0° il percorso di ritorno viene azzerato
(nulla da ripercorrere). Altrimenti HOME ripercorre all'indietro i gruppi eseguiti, che
sono già stati controllati.

## Robot reale

Programmi con target o MoveL richiedono la corrispondenza fisica dichiarata del modello;
le pose usate devono essere registrate sul robot reale. Nessuna prova sul braccio fisico
in questa build (il braccio non ha sensori: le prove fisiche restano per ultime).

## Verifiche build 42

- 9 test in `test_program_logic.py`: espressioni senza accesso a Python, struttura, cicli
  annidati con contatore e impilamento, rami fusi (7 per tre cicli), problema in un ramo non
  mostrato, limite dei rami, esecuzione con Mega simulata che segue il sensore (righe `~multi`
  identiche ai tratti dei rami scelti), rifiuto dei dati simulati sul robot reale, timeout.
- Codice incluso nell'app, programma con 2 cicli e condizione sul sensore: 5 rami, 561
  campioni; pila corretta (80 e 60 mm); 89,45 s misurati contro 87,91 s stimati.

## Verifiche build 41

- 10 test in `test_program.py`: compito presa e deposito (MoveJ sopra il pezzo, MoveL giù,
  chiudi, MoveL su, MoveJ sopra il deposito, MoveL giù, apri, MoveL su, HOME), velocità,
  problemi localizzati, salvataggio, Ripeti, passo passo, STOP in attesa, durata in Anteprima.
  L'esecuzione con Mega simulata confronta le righe `~multi` inviate con le tappe del piano.
- Preview isolata: stesso compito pianificato (56,9 s), eseguito passo passo e in continuo
  (57,3 s misurati contro 56,9 s stimati), problema localizzato su un MoveL dentro il tavolo.

## API Python e I/O (build43)

L’API pianifica ed esegue con questo stesso motore e le stesse tappe; vedere `PYTHON_API.md` e capitolo24 della guida. La presenza di un’uscita digitale rende il programma offline anche senza movimenti. In questo modo nessuna uscita può essere saltata dal vecchio esecutore a pose. Pianificare non applica le uscite.

## Funzioni e sottoprogrammi (build44)

`function` / `end` definisce il corpo; `call` passa argomenti e opzionalmente assegna un risultato; `return` rientra subito nel chiamante. Variabili locali, fino a 8 livelli di richiamo, ricorsione rifiutata e rami sensore tutti verificati. Il planner include la pila delle chiamate nella chiave di stato; ogni tappa conserva `call_path` per distinguere richiami e iterazioni nel passo passo. `program_functions.py` contiene firme e frame, senza I/O. Editor, API, salvataggio e piano comune condividono gli stessi blocchi. Procedura, formato, limiti e compatibilità: [SOTTOPROGRAMMI.md](SOTTOPROGRAMMI.md). Esempio: `examples/python_subprograms.py`.
