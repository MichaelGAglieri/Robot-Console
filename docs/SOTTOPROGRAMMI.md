# Funzioni e sottoprogrammi — build44

Una funzione è una sequenza nominata da riutilizzare passando valori diversi: ad esempio `prendi(quota)` e `deposita(quota)`. Usa il pianificatore offline esistente: non apre porte USB, non cambia firmware, non crea un esecutore alternativo. Il progetto resta work in progress; i collaudi di questa build sono software e simulati.

## Dall’interfaccia

1. Apri **Studio 3D e programmi → Programmi · istruzioni e anteprima**. In **Istruzione** scegli **Funzione**. Scrivi `prendi` nel nome tecnico e `quota` nei parametri, poi **Aggiungi istruzione**. I nomi tecnici accettano lettere ASCII, cifre e `_`, iniziando con lettera o `_`, senza spazi; non usare nomi di sensori per i parametri. Il nome descrittivo è libero.
2. La definizione viene aggiunta in fondo al livello principale, con **Fine funzione**. Seleziona la riga Funzione e inserisci il corpo fra inizio e fine, selezionando via via la riga dopo cui inserire. Puoi usare MoveJ, MoveL, pinza, pose, attese, I/O, cicli, condizioni e altri richiami. Nel campo **Z sopra · mm** puoi scrivere `quota` invece di un numero.
3. Seleziona **Fine funzione** (o una riga del programma principale) e scegli **Richiama funzione**. Seleziona `prendi`, assegna `60` a `quota` e aggiungi. La definizione da sola non muove nulla: viene saltata dal programma principale. Il richiamo esegue il corpo e poi rientra all’istruzione successiva.
4. Aggiungi un altro richiamo con `quota = 40`, oppure crea `deposita(quota)`. Il pulsante con la matita modifica firma o richiamo; cambiare il nome tecnico aggiorna i riferimenti dei richiami, mentre un cambio di parametri richiede di correggerne i valori. Il cestino della definizione elimina **anche tutto il corpo**; i richiami rimasti diventano errori di pianificazione.
5. **Pianifica programma**, osserva l’anteprima e usa **Passo passo…** in Anteprima. La prima istruzione eseguibile parte subito; le successive attendono **Istruzione successiva**. Il richiamo viene espanso: i movimenti interni non diventano un’unica azione opaca. L’indicazione mostra richiamo, funzione e istruzione del corpo. Uno STOP annulla il piano e richiede di ristabilire HOME; non riprende automaticamente.

Gli schemi dei corpi possono essere spostati con le frecce purché rimangano strutturalmente validi; una modifica non bilanciata è rifiutata. Non eliminare l’intestazione per trasformare il corpo in programma principale. Come ogni modifica di istruzioni, cambiare una funzione rende il piano precedente scaduto.

## Parametri, variabili locali e risultati

Ogni richiamo deve passare esattamente i parametri della firma. I valori sono numeri o espressioni calcolate nell’ambiente del chiamante, ad esempio `60 + strato*20`. Il corpo riceve soltanto questi parametri e le proprie variabili locali. Non legge implicitamente le variabili del chiamante e non le cambia al rientro. Gli angoli, la pinza e gli I/O modificati dalle istruzioni eseguibili, invece, restano nello stato raggiunto: il rientro non torna alla posizione iniziale.

**Restituisci** esce subito dalla funzione, anche da cicli e condizioni annidati. Il valore è facoltativo. In **Richiama funzione → Variabile risultato (facoltativa)** puoi scrivere un nome da assegnare nel chiamante. Se chiedi un risultato, tutti i percorsi raggiungibili della funzione devono restituirlo; arrivare a Fine funzione senza valore è un errore.

Esempio senza movimenti:

```text
Funzione doppio(x)
    Restituisci x * 2
Fine funzione
Richiama doppio(x = 30) → altezza
```

Ora `altezza` vale 60 nel chiamante e può essere usata nella quota di un target o in un’espressione. Non esistono tipi stringa, oggetti, import o codice Python arbitrario. In questo incremento i parametri sono numerici/booleani; gli ID dei target, delle pose e degli I/O rimangono riferimenti fissi nel corpo.

## Sensori e verifica

Un sensore si legge in **Se** o **Attesa sensore**, anche dentro una funzione. Non può diventare un argomento o un risultato numerico perché il percorso deve essere pianificabile. Tutti i rami sensore vengono verificati, con ambiente locale e punto di rientro separati per ogni richiamo. L’anteprima sceglie Vero/Falso per istruzione condizionale: se la stessa condizione viene richiamata più volte, la scelta vale per tutte le occorrenze visualizzate. In esecuzione il sensore viene riletto a ogni occorrenza.

Un errore indica **Richiamo N → funzione / Blocco M**, includendo il ramo sensore quando disponibile. La velocità delle istruzioni resta la percentuale delle velocità per giunto di Muovi e osserva. Il piano, inclusi i movimenti interni dei sottoprogrammi, passa dagli stessi controlli geometrici e dallo stesso esecutore, con approvazione nativa per l’API sul robot reale.

Limiti del linguaggio: 200 blocchi totali, 32 definizioni, 8 parametri per funzione, 8 chiamate annidate, ricorsione diretta/indiretta rifiutata nei percorsi raggiungibili. Restano i limiti del pianificatore (128 rami, 120000 campioni complessivi, 800 tratti di moto e 2000 istruzioni per segmento). Il vecchio Ripeti con salto all’indietro non è combinabile con funzioni: usa **Ripeti N volte … Fine**.

## Formato salvato e Python

```json
[
  {"kind":"function","name":"Doppio","function":"doppio","parameters":["x"]},
  {"kind":"return","name":"Risultato","value":"x*2"},
  {"kind":"end","name":"Fine funzione"},
  {"kind":"call","name":"Calcola","function":"doppio","arguments":{"x":"30"},"result":"quota"},
  {"kind":"note","name":"Calcolo completato"}
]
```

Il progetto ed **Esporta progetto…** conservano firma, corpo, argomenti e risultato. Le versioni precedenti alla build44 non conoscono queste istruzioni: conserva una copia del vecchio progetto prima di modificarlo. Il normale installer conserva i dati personali prima dell’aggiornamento e la penultima app.

`examples/python_subprograms.py` contiene presa e deposito con MoveJ, MoveL, pinza e HOME, sullo stesso formato dell’editor. Crea i target `Pezzo` e `Deposito` nella scena, avvia l’API in Diagnostica, abilita esplicitamente i permessi, poi:

```sh
PYTHONPATH=. python3 examples/python_subprograms.py --url http://127.0.0.1:PORTA
```

Il token viene chiesto senza eco oppure letto da `ROBOT_CONSOLE_TOKEN`. Senza `--execute` pianifica soltanto. In Anteprima puoi abilitare esplicitamente l’esecuzione demo. Sul robot reale è necessaria la conferma del piano nell’app; lo script non connette la Mega, non imposta HOME, non modifica i limiti e non approva sé stesso. I target dell’esempio richiedono quote e ambiente coerenti: un esempio riuscito in simulazione non certifica il robot fisico.
