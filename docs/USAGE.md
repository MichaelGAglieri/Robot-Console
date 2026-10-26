> Per le funzioni della build locale 2.0 (URDF, J6, editor firmware, programmi e ROS) leggi [STUDIO.md](STUDIO.md).

# Uso di Robot Console

## Tema dell’interfaccia

Nel selettore **Tema**, in alto, scegli **Chiara**, **Scura** oppure **Sistema**. Sistema segue automaticamente l’aspetto di macOS, anche se cambia mentre l’app è aperta. La scelta si applica anche all’editor delle pose e alle finestre di dialogo, viene salvata sul Mac ed è disponibile anche nel menu **Aspetto → Tema**. Al primo avvio è selezionato Sistema.

## Anteprima

Avvia Anteprima, conferma HOME virtuale e applica i limiti. Gli angoli visualizzati sono virtuali. Usa la velocità in gradi al secondo e lo spostamento per clic per muovere i giunti, poi registra una posa.

Ogni posa conserva i cinque angoli, il percorso da HOME, il nome, la pausa e la richiesta della pinza. Ultimo comando usa la richiesta pinza fatta dall’app; Apri e Chiudi sono espliciti; Mantieni non invia comandi.

## Modificare e organizzare

Modifica apre nome, angoli assoluti rispetto a HOME, pausa, pinza e abilitazione. I campi accettano punto e virgola decimale; salva per confermare. Il salvataggio non muove il robot. Gli angoli nuovi estendono il percorso originale con correzioni in ordine J1–J5; non sono traiettorie già provate e richiedono verifica prima dell’uso fisico.

Le frecce spostano una posa prima o dopo; il cestino elimina solo quella posa. Annulla ultima modifica recupera l’ultima modifica della sessione. L’interruttore esclude temporaneamente una posa, mantenendola salvata: niente sosta né comando pinza per quella tappa. Il percorso di altre pose può comunque attraversarne la posizione. Se tutte sono escluse, non si avvia la sequenza.

Per riprodurre torna prima a HOME. Il riordino usa i percorsi registrati a ritroso fino al tratto comune e poi verso la posa successiva; può passare da HOME. Il ritorno mantiene lo stato della pinza. Pausa sospende l’avanzamento della sequenza; STOP interrompe il controllo e invalida il riferimento. Termina al prossimo HOME conclude il ciclo in corso.

## USB e firmware

L’app parte scollegata. Caricare il firmware è un’operazione separata, con conferma, e richiede il controllo USB scollegato. Chiudi altri monitor seriali. La Mega richiede un intervallo silenzioso di avvio prima dell’identificazione; attendi riconoscimento e conferma velocità.

La sezione firmware usa Arduino CLI, core arduino:avr 1.8.8 e AccelStepper 1.64. La preparazione delle dipendenze richiede Internet una volta; tool e librerie non sono incorporati nel download dell’app. Il firmware Regia 4 abilita 1–20°/s; Regia 2 resta riconosciuto fino a 10°/s.

Conferma HOME solo dopo avere posizionato il braccio nel riferimento fisico scelto. Applica limiti compatibili con il montaggio. Le conferme seriali contano impulsi comandati: non verificano che il motore non abbia perso passi. Per chiudere usa HOME e chiudi e verifica il ritorno visivamente; STOP ed esci interrompe gli impulsi senza certificare l’isolamento di potenza.

## IA e dati locali

**Leggi risposta** pronuncia il contenuto dell’ultima risposta dell’assistente. L’intestazione `[Ollama locale · nome del modello]` rimane visibile nella chat e viene esclusa dalla lettura vocale per tutti i modelli, anche nelle risposte già salvate.

Ollama è opzionale: l’app rileva il servizio e i modelli locali, può avviarlo e caricare il modello scelto. Non scarica automaticamente pesi. Ferma IA scarica il modello selezionato dalla memoria; un servizio Ollama già avviato da altre applicazioni può restare attivo. La chat non dispone di comandi di movimento.

Dettatura italiana: richiede i permessi macOS e supporto al riconoscimento sul dispositivo; non ripiega automaticamente su un servizio remoto. Il ROS observer richiede il checkout DOC e Pixi, senza avviare un controller motorio ROS.

I dati dell’app restano nella cartella storica `~/Library/Application Support/DOC Regia`: sequenze, limiti, conversazioni e impostazioni. Non caricarli su GitHub. L’app non riconnette il robot automaticamente al successivo avvio.
