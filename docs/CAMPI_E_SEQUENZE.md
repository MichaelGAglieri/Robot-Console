# Campi, pose e riferimento — build45 / build46

Questa versione corregge un problema del percorso delle pose: nelle precedenti ogni posa portava con sé il percorso completo dei jog usati per raggiungerla. Eliminare o escludere una riga non eliminava quei passaggi dai percorsi di altre pose. Anche il ritorno HOME li ripercorreva. Il formato storico rimane nell’archivio, ma non guida più questi movimenti.

## Sequenza visibile

La sequenza ora collega **la posizione attuale → le sole pose attive, nell’ordine visualizzato → l’ultima posa** con transizioni articolari dirette. Gli assi si muovono insieme con le velocità di Muovi e osserva, accelerazioni e budget impulsi esistenti. Non è una linea retta del TCP nello spazio. Una transizione può incrociare geometricamente un punto precedente, ma non contiene tappe nascoste prese da pose eliminate o dai vecchi jog.

- **Anteprima sequenza** mostra il percorso 3D prima di muovere.
- **Una volta / Ripeti** pianificano prima della conferma; una modifica a pose, velocità o stato rende la conferma scaduta.
- Il riferimento del controllore deve essere valido, ma il braccio non deve essere a zero per partire.
- Per impostazione predefinita resta sull’ultima posa. **Torna a HOME a fine sequenza** aggiunge un ritorno diretto esplicito. Ripeti collega l’ultima posa alla prima del ciclo successivo, senza un HOME intermedio non richiesto.
- **Vai a HOME…** pianifica e chiede conferma del collegamento diretto a zero. Non riavvolge i movimenti storici. Il controllo geometrico viene eseguito prima della partenza, anche se il modello non è dichiarato conforme; un controllo fallito blocca queste sequenze e il ritorno.
- Le istruzioni Posa nei programmi mantengono un identificativo stabile: riordinare non cambia il bersaglio; eliminare la posa produce un errore da correggere, senza usare quella che ha ereditato il suo indice.

I vecchi programmi solo a pose partono dalla posizione attuale e terminano dove finiscono le istruzioni; aggiungi un MoveJ HOME esplicito se necessario. Le definizioni dei sottoprogrammi e le relative regole della build44 restano supportate.

**Il percorso è cambiato rispetto alle versioni precedenti.** Rivedi la nuova anteprima delle tue sequenze prima di provarle sul braccio. Le capsule, il modello e il conteggio impulsi non certificano la traiettoria fisica: non c’è retroazione encoder integrata. Nessun collaudo reale è stato eseguito durante questo aggiornamento.

## Riferimento valido e posizione HOME

Il vecchio indicatore `home` significa **riferimento valido**, non «robot fisicamente a zero». Quando è valido l’app mostra **Riferimento HOME valido**; puoi registrare, modificare e avviare dalla posizione attuale.

Da fermo, HOME del modello, offset/mapping del modello, TCP, riferimenti di lavoro, target, ostacoli, limiti e metadati delle pose non azzerano gli angoli né richiedono una nuova connessione. Le modifiche geometriche rendono scaduti i piani e possono richiedere una nuova dichiarazione di corrispondenza fisica del modello, disponibile da fermo senza scollegare.

STOP, perdita USB, reset/caricamento firmware, variazione del profilo impulsi o rilascio elettrico dei motori possono rendere il conteggio incerto: in questi casi il riferimento va ristabilito. Il nuovo pulsante **Imposta riferimento HOME…** azzera il conteggio dopo conferma fisica; è diverso da **Vai a HOME…**, che muove il robot. Modificare URDF o firmware strutturali richiede ancora una sessione scollegata. Queste protezioni non vengono aggirate.

## Scrittura dei numeri

Audit dei 58 punti di codice che creano campi TextField: tutti usano bozze di testo. I campi numerici non vengono più legati direttamente a un numero con formattazione o clamp durante la scrittura. Puoi selezionare tutto, cancellare, scrivere il segno e completare i decimali; virgola e punto sono accettati, anche il meno tipografico `−`. Un campo vuoto o un segno incompleto non diventa zero.

In HOME del modello la vista conserva l’ultimo valore valido mentre il testo è incompleto, segnala l’errore e impedisce il salvataggio finché i campi non sono corretti. Nessun valore fuori limite viene corretto silenziosamente mentre scrivi. Il campo ROS usa testo con validazione finale del dominio; le velocità in modifica non vengono sovrascritte da un aggiornamento del controllore. Riprendi ultimi limiti gestisce correttamente cinque o sei canali.

Imposta/Applica/Salva convalidano il contenuto completo. I valori non validi producono un messaggio, senza usare un numero di ripiego. Se scrivi una quota nel programma e vuoi un’espressione, usa la sintassi supportata dei sottoprogrammi; non sono comandi Python liberi.

Le scorciatoie dei jog non inviano movimenti mentre stai scrivendo in un campo o in una finestra modale. Annulla/Esc nella finestra HOME del modello chiude la modifica virtuale; il pulsante STOP conserva il comportamento di arresto e fuori dalle finestre modali Esc rimane la scorciatoia STOP.

## Migrazione e recupero

L’installer conserva la penultima app e i dati personali. Al primo caricamento di pose senza ID, viene salvato `sequenza-prima-id.json` prima di assegnare identificativi persistenti. I vecchi percorsi restano dati d’archivio. La migrazione non connette la scheda e non trasmette comandi.


## Interferenze del modello durante una dimostrazione — build46

In **Operatore → Connessione e riferimento**, la spunta **Blocca interferenze modello · Operatore** è attiva per impostazione predefinita. Se il modello approssimato segnala per esempio `link_3 / link_5`, la pianificazione può fermare anche HOME: il nome MoveJ indica il motore comune di interpolazione dei giunti, senza implicare che si stia usando un programma Studio o una retta MoveL.

Da fermo puoi togliere la spunta e confermare **Usa solo avvisi**. Il rilevamento delle interferenze 3D rimane visibile, ma non blocca sequenze, pose e HOME dell’Operatore. Verifica personalmente il percorso reale: non è stato stabilito che l’interferenza sia un falso positivo. Le collisioni fisiche non scompaiono disattivando il blocco software.

Rimangono bloccanti i limiti applicati, i limiti URDF calibrati, i giunti esclusi o non disponibili, il riferimento e lo stato della comunicazione. Velocità, accelerazioni, budget impulsi e STOP non cambiano. Studio MoveJ/MoveL e i programmi pianificati mantengono i controlli precedenti. I comandi manuali singoli/simultanei continuano ad avere il comportamento preesistente, senza verifica geometrica del modello.

La scelta richiede conferma, viene segnalata in arancione e nel registro, non si può modificare durante un movimento, invalida i piani e le conferme precedenti e **si azzera alla prossima connessione**. Non viene salvata in progetti né importata da file. Per ripristinare subito il blocco, rimetti la spunta. Firmware e modello non sono stati modificati.
