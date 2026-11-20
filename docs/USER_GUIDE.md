# Robot Console — guida completa

## Avvisi del modello nella dimostrazione — build46

In **Operatore → Connessione e riferimento** puoi togliere **Blocca interferenze modello · Operatore**, quindi confermare **Usa solo avvisi**. Serve a non bloccare sequenze e HOME su interferenze del modello approssimato. Controlla fisicamente il percorso: non è una verifica di assenza di collisioni reali. Limiti, velocità, STOP e controlli Studio MoveJ/MoveL rimangono attivi. Scelta valida solo per la connessione corrente; una nuova connessione riattiva il blocco. [Dettagli](CAMPI_E_SEQUENZE.md).


Manuale offline della versione locale 2.0.1, build 45. Il progetto è in sviluppo.

## 01 · Che cosa fa Robot Console

Robot Console è un’app macOS per comandare un braccio articolato, insegnare pose, ripeterle, osservare un modello 3D e integrare strumenti locali. Le quattro aree in alto sono **Operatore**, **Studio 3D e programmi**, **Diagnostica e ROS 2**, **Assistente**. La guida è consultabile senza Internet: cerca una parola, scegli un capitolo nell’indice oppure usa Capitolo precedente/successivo. Salva manuale esporta il testo completo nella lingua selezionata.

**Il robot DOC ha cinque gradi di libertà**, J1–J5. L’app espone sei canali per configurazioni future; J6 non aggiunge un sesto giunto al modello DOC. Il modello locale è EB-15 con pinza EBG-30, ricostruito da CAD; le quote del modello non dimostrano la calibrazione del robot montato.

Ci sono tre informazioni diverse da non confondere: il **target virtuale** del modello, gli **angoli comandati** calcolati dagli impulsi e la **posizione misurata** da eventuali sensori. Questa versione non dispone di feedback encoder integrato per correggere il moto. Un movimento disegnato bene o completato nel protocollo seriale non prova che il robot reale abbia raggiunto quel punto.

**Anteprima** usa un controllore simulato e non apre la porta seriale. **Robot USB** apre la porta scelta dopo conferma. Cambiare area di lavoro o nascondere un pannello non cambia questa modalità e non interrompe un movimento.

**MoveJ** è il piano articolare comune di Studio, pose e programmi: lo stesso piano si osserva in anteprima e, dopo conferma, si esegue con **Esegui MoveJ…**; anche **Esegui target visualizzato…** lo usa. Riproduci e i programmi a pose registrate collegano i target attivi direttamente; i programmi con istruzioni MoveJ/MoveL usano lo stesso piano in anteprima ed esecuzione (capitolo 12). **MoveL** porta la punta in linea retta con la deviazione misurata. Le collisioni usano geometrie semplificate; homing automatico, orientamenti cartesiani arbitrari a sei componenti e retroazione fisica non sono funzioni completate.


**La build45 cambia i percorsi e la scrittura dei numeri.** Le sequenze partono dalla posizione attuale e visitano solo i target delle pose attive, nell’ordine visibile, con transizioni articolari dirette e simultanee. Per impostazione predefinita restano sull’ultima posa. “Torna a HOME a fine sequenza” è facoltativo; “Vai a HOME…” pianifica un ritorno diretto e chiede conferma. I vecchi percorsi dei jog restano archiviati ma non vengono riprodotti da sequenza/posa/HOME. Prima di provare vecchie sequenze sul braccio controlla Anteprima sequenza. Serve un riferimento valido, senza dover essere a zero. Le modifiche virtuali da fermo mantengono il riferimento del controllore. STOP, reset, perdita USB, modifiche firmware e rilascio fisico richiedono ancora di ristabilirlo. Le pose nei programmi hanno ID stabili: cancellarne una produce un errore, senza sostituirla con la posa che prende il suo indice.

**Scrittura dei numeri:** puoi svuotare un campo, scrivere il segno e completare i decimali con virgola o punto. HOME del modello usa bozze di testo e conserva l’ultima vista valida finché il testo è incompleto; un errore non diventa zero. Applica/Salva convalidano il testo completo. Modificare HOME del modello, mapping, TCP o target da fermo non scollega la USB e non azzera il conteggio fisico. L’indicatore Riferimento HOME valido è distinto dalla posizione HOME.

Le procedure seguenti descrivono il comportamento della build45. `docs/CAMPI_E_SEQUENZE.md`, incluso nell’app, dettaglia migrazione e verifiche.

## 02 · Primo avvio e prova senza hardware

Apri **Robot Console** dalla cartella Applicazioni del Mac. L’avvio non connette automaticamente la Mega e non carica firmware. Il programma richiede il runtime Python configurato sul computer; Ollama, ROS 2 e Arduino CLI servono solo alle rispettive funzioni. Una copia dell’app non garantisce da sola che su un altro Mac siano presenti tutte le dipendenze.

Per imparare l’interfaccia senza muovere il robot:

1. In Operatore → Connessione e riferimento scegli **Anteprima** e premi **Avvia anteprima**.
2. Premi **Conferma HOME**: in questa modalità confermi soltanto uno zero virtuale.
3. Nei limiti scegli **±5°**, premi **Per tutti i giunti**, poi **Applica limiti**. Il preset compila i campi; non è applicato finché non premi il pulsante finale.
4. In Muovi e osserva imposta un passo di 1° e prova J1 + e −. Osserva angoli, eventi e modello. Se vuoi che il modello segua il conteggio, attiva **Segui comandi**.
5. Registra due pose con nomi diversi e prova Una volta. Verifica anche STOP; dopo un arresto devi ristabilire HOME.

Per provare il nuovo percorso, apri Studio, inserisci nel pannello MoveJ J1=5, J2=−5 e gli altri a zero. Scegli il ritorno iniziale se desiderato, pianifica e riproduci. Questo test anima soltanto il modello e non modifica il conteggio del controllore: è diverso dai jog del controllore virtuale.

Non serve scaricare un modello IA né avviare ROS per queste prove. Prima di passare al controllo fisico, rileggi connessione, HOME, ENABLE e firmware.

## 03 · Interfaccia, temi, lingua e pannelli

La barra superiore contiene **Eventi**, **Note**, **Guida**, **Lingua**, **Tema** e **STOP**. Puoi scegliere Italiano o English e tema Chiaro, Scuro o Sistema; Sistema segue l’aspetto di macOS. Il colore acceso identifica azioni e selezioni; un pulsante attenuato indica che mancano condizioni per usarlo.

**Eventi** apre o chiude la barra sinistra, con attività della sessione e chiusura. **Note** mostra gli appunti a destra. Trascina i separatori verticali per regolarne la larghezza; doppio clic ripristina la larghezza standard. Le scorciatoie sono ⌘B per Eventi e ⌥⌘B per Note. La parte centrale usa lo spazio disponibile anche con entrambe le barre chiuse.

I riquadri centrali possono essere regolati **solo in altezza** usando la maniglia inferiore. Adatta ripristina l’altezza naturale del contenuto. Le sezioni richiudibili si espandono cliccando il titolo. In un campo lungo, una griglia o un editor può esserci uno scorrimento interno separato dalla pagina principale.

Le preferenze visive restano su questo Mac. Non sono parametri del firmware e non cambiano i movimenti. I messaggi sopra la pagina spiegano errori o azioni mancanti: leggerli prima di ripetere un comando aiuta a capire quale condizione non è soddisfatta.

## 04 · Connessione USB e riconoscimento del firmware

Per il robot fisico scegli **Robot USB**, seleziona la porta della Mega, premi **Connetti Mega** e leggi la conferma. La connessione apre la seriale e può riavviare la scheda. Attendi il riconoscimento di identità, capacità e velocità prima di confermare HOME. Una spia accesa dimostra alimentazione della scheda, non il riconoscimento del protocollo.

La porta usata dal monitor seriale di Arduino o da un’altra app può essere occupata: chiudi quel monitor prima di connettere Robot Console. Usa una sola istanza del controllore per i dati personali. La copia Studio Preview usata per i collaudi software ha dati separati e blocca l’hardware.

Se compare **Mega senza risposta USB**, controlla la porta scelta, cavo dati, disponibilità della seriale e risultato del caricamento precedente. Attendi il tempo di avvio indicato dall’app. Non premere ripetutamente RESET o Carica solo perché manca una risposta: prima leggi i log e verifica che il firmware sia quello compatibile.

Il profilo prepara Mega 2560/RAMPS 1.4, A4988 e DM542 esterno su J2. L’editor offre alcune varianti di driver e J6 esterno: non rende automaticamente compatibile qualsiasi scheda o robot. La USB può alimentare la logica, ma non sostituisce le alimentazioni necessarie a motori e servo.

**Scollega controllo** chiude il collegamento quando il controllore è fermo. Prima di modificare configurazioni strutturali o lavorare sul firmware usa questa funzione. Dopo riconnessione, riavvio, arresto o perdita del riferimento non presumere che la posizione precedente sia ancora valida.

## 05 · HOME: riferimento e ritorno

**Conferma HOME** dichiara che il braccio si trova nella posa iniziale scelta dall’operatore e azzera gli angoli del controllore. Non cerca un finecorsa e non sposta da solo il braccio in una posizione nota. Senza sensori di riferimento non è un homing automatico.

Sul robot la conferma può abilitare la tenuta dei motori. Predisponi il braccio nella posa di riferimento e sostieni gli assi che potrebbero cedere durante una variazione di tenuta. In Anteprima è soltanto uno zero virtuale.

**Vai a HOME…** pianifica un collegamento articolare diretto dalla posizione attuale agli angoli zero, mostra la traccia e chiede conferma. Non ripercorre i vecchi jog o le pose eliminate. Il ritorno conserva le velocità dei singoli giunti, controlla tutti gli assi prima di iniziare e lascia invariata la pinza. Non è una linea retta del TCP nello spazio.

Dopo STOP, errore, riavvio o rilascio di un giunto HOME può diventare non valida. In quel caso non cercare di recuperarla confermando senza guardare il braccio: occorre ristabilire fisicamente il riferimento. Il conteggio degli impulsi non rileva un asse spostato a mano o passi persi.

**HOME del modello…** è un’altra funzione: cambia l’allineamento della rappresentazione 3D. Non cambia HOME del controllore e non azzera gli angoli fisici. Vedi il capitolo su modello e TCP.

## 06 · Limiti dei giunti e predefiniti

I campi Minimo e Massimo definiscono l’intervallo comandabile di ogni canale in gradi rispetto alla HOME. All’inizio sono a zero e bloccano il moto. Gli intervalli devono includere lo zero e restare nel dominio software ammesso, da −360° a +360°; ciò non significa che il tuo robot possa percorrerlo tutto.

Puoi cancellare completamente un campo mentre lo riscrivi. Il valore vuoto è una modifica incompleta: il pulsante Applica richiede numeri validi. Usa il segno meno per il limite inferiore e verifica ogni asse prima di confermare.

Il menu **Predefinito** offre Bloccato 0°, ±5°, ±15°, ±30°, ±45°, ±90°, ±180° e ±360°. **Per tutti i giunti** copia il preset nei sei campi; il menu nella scheda di un giunto cambia solo quel giunto. **Applica limiti** invia e conferma l’insieme. Un preset non conosce finecorsa, cavi, carter o attrezzature.

**Riprendi ultimi** ripropone i valori salvati per quella modalità; devi comunque applicarli. Anteprima e Robot USB hanno memorie separate. Un numero visibile nel campo può essere soltanto una bozza: distinguilo dai limiti accettati dal controllore.

I limiti del controllore e quelli URDF sono distinti. Il nuovo MoveJ controlla entrambi, includendo segni e offset. Per un asse non utilizzato, mantieni un intervallo a zero o escludilo in modo coerente con la configurazione hardware.

## 07 · Muovi e osserva: passo, angoli e velocità

In modalità **Singolo**, − e + muovono il giunto della scheda dello spostamento relativo scelto. Il **passo** è un angolo per clic, non una velocità. Puoi usare i pulsanti rapidi da 1° a 360°, lo slider, il regolatore ±1° oppure scrivere un valore e premere **Imposta angolo**.

Esempio: posizione comandata J1=10°, passo=5°. Un clic su + chiede J1=15°; un clic su − riporta a 10°. Il comando viene rifiutato se oltrepassa i limiti applicati. I numeri degli angoli descrivono l’uscita configurata considerando microstepping e riduttore, non solo l’albero motore.

Ogni scheda ha la propria **velocità in °/s**. Trascina lo slider o scrivi il numero, poi premi **Invio o ✓**. Le due cifre decimali sono conservate. Il valore comune e **Applica a tutti** sostituiscono le sei velocità; non sovrascrivono i limiti angolari.

Le velocità individuali valgono per jog, gruppi, pose, programmi e ritorni gestiti dal controllore. Il massimo dipende dal profilo; nel profilo attuale l’app indica fino a 20°/s. Non viene garantito che ogni combinazione di riduzione e carico raggiunga quel valore: il budget impulsi può rallentare il movimento.

La velocità non regola la corrente del driver. A4988 e DM542 hanno regolazioni hardware della corrente; aumentando la frequenza dei passi cambiano coppia disponibile, perdite e condizioni di moto. Questa app non misura temperatura, corrente o margine di coppia.

Il menu **Tastiera** sceglie il giunto per ⌥← e ⌥→ nell’area Operatore. Evita di usarle mentre stai inserendo testo; il controllo resta subordinato a HOME, limiti e stato. **Canali aggiuntivi** espone J6 se non è associato al modello: non crea geometria.

## 08 · Movimenti simultanei: due o più giunti

Scegli **Simultaneo** nella stessa sezione Muovi e osserva. Inserisci uno spostamento relativo in ciascun giunto: per esempio J1=10°, J2=−5°, gli altri=0°. Uno zero lascia fermo il canale. Le velocità si impostano nelle stesse schede della modalità Singolo.

Applica ogni velocità modificata con Invio o ✓. Poi prepara il gruppo con **Muovi insieme…**, leggi il riepilogo di destinazioni, picchi e durata e conferma. Il firmware fisico deve dichiarare la capacità **MULTI_AXIS_V1**; un firmware vecchio può funzionare per il singolo senza supportare il gruppo.

I giunti condividono un avanzamento normalizzato con accelerazione: si muovono insieme ma ciascuno rispetta il proprio massimo. Se J1 percorre 10° e J2 5° nello stesso tratto, le loro velocità effettive sono proporzionali alle distanze. Non tutti viaggiano necessariamente al valore scritto nella propria scheda.

Il pianificatore limita anche la somma dei passi a **2000 impulsi/s**. È un limite software di progetto, non una misura certificata sul banco. Riduzioni e microstep elevati richiedono più impulsi per grado e possono allungare molto il tempo in uscita.

Modificare posizione, velocità, HOME, limiti, abilitazioni o configurazione dopo il riepilogo invalida il gruppo: preparalo di nuovo. **STOP Jn su un membro ferma l’intero gruppo**, non soltanto quel motore. Registrare una posa dopo un gruppo ne conserva la struttura; le pose vecchie non diventano simultanee automaticamente.

## 09 · STOP, spunte dei giunti e corrente

**STOP** in alto ed **Esc** interrompono il moto corrente e la sequenza; non sono un arresto di emergenza hardware certificato. Non isolano elettricamente l’alimentazione. Il firmware conserva la tenuta quando supportata e richiede di ristabilire HOME dopo l’interruzione.

**STOP Jn** ferma quel giunto se è il giunto attivo. In un gruppo simultaneo ferma l’intero gruppo se ne fa parte. Se Jn è già fermo e un altro asse si muove singolarmente, usa STOP globale per fermare quello in movimento.

Togliere la **spunta del giunto** lo esclude dai comandi e, con firmware compatibile e collegamento ENABLE presente, disabilita il driver. Per A4988 questo rilascia la corrente nelle bobine: un asse sotto carico può cadere. L’app chiede conferma del rilascio; sostienilo prima di confermare. La sequenza viene interrotta e HOME invalidata.

Nella configurazione attuale **J2 usa DM542 con ENA scollegato**. L’esclusione impedisce nuovi movimenti, ma non toglie corrente e non elimina la coppia di tenuta. La scheda lo indica. Nessuna impostazione software può aprire un filo non collegato. J6 fisico non configurato non pilota un pin.

Riattivare la spunta prepara l’asse; la tenuta viene riabilitata alla conferma HOME. La conferma mostrata dall’app è uno stato del firmware, non una misura elettrica. Un firmware precedente senza gestione ENABLE per asse non può offrire tutte queste azioni.

**Arresta anteprima / ■ MoveJ** ferma invece la sola animazione MoveJ. Non altera HOME né angoli comandati. Lo STOP globale rimane un comando del controllore e invalida il piano virtuale.

## 10 · Pinza e servo

**Apri pinza** e **Chiudi pinza** inviano i due comandi configurati nel firmware. Il collegamento predefinito del segnale servo è D11; alimentazione, massa comune e compatibilità del servo devono essere predisposte correttamente. La USB della Mega non è un’alimentazione di potenza per la pinza.

L’app mostra **l’ultima richiesta**, non un sensore di apertura o forza. Non misura se un oggetto è stato afferrato né interrompe automaticamente la chiusura quando lo tocca. La presa dipende da servo, tensione, cinematismo, attrito e limiti meccanici.

Nelle pose scegli **Apri**, **Chiudi** o **Mantieni**. Apri/Chiudi vengono applicati all’arrivo della posa; Mantieni non invia un nuovo comando. La riproduzione conserva queste azioni e la pausa. La pinza non viene riportata automaticamente a uno stato opposto durante il ritorno HOME.

Nel programma puoi aggiungere un blocco Pinza tra due pose. Nel nuovo piano MoveJ la pinza è soltanto visualizzata, con tempo convenzionale di 1,5 s: non è una previsione misurata del servo reale. Le regolazioni dei punti finali della pinza appartengono al firmware; non aumentare la presa spingendo oltre un arresto meccanico.

## 11 · Pose: registrare, modificare e ordinare

Per registrare una posa il controllore deve essere connesso, fermo e con riferimento valido: non deve essere a zero. Raggiungi la posizione, inserisci nome, pausa e azione pinza, poi premi ＋ Registra posa. Si salvano gli angoli finali con un ID stabile. I vecchi percorsi sono dati d’archivio e non vengono usati per raggiungere le pose.

La posa è relativa alla HOME della sessione e alla configurazione del robot. Una posa registrata in Anteprima non è automaticamente una posa fisica validata. Cambiare rapporti, zero, versi o montaggio può cambiare completamente il risultato reale.

**Modifica** apre nome, angoli, pausa, pinza e abilitazione. Salva modifiche conferma soltanto l’editing, non muove il robot. Cambiare direttamente gli angoli è diverso dal registrare un tragitto: l’app valida il nuovo percorso secondo le regole correnti, senza considerarlo provato fisicamente.

Usa **↑ / ↓** per riordinare e il cestino per eliminare. **Annulla ultima modifica pose** recupera l’ultima modifica disponibile della sequenza; non è una cronologia infinita. Le revisioni impediscono che una modifica vecchia sovrascriva silenziosamente una sequenza appena cambiata.

La spunta della posa la **esclude temporaneamente**: il target, la pausa e la pinza non aggiungono tappe. Le transizioni collegano soltanto le pose attive; possono attraversare geometricamente una zona, ma non riproducono i passaggi registrati della posa esclusa. Cancellare una posa referenziata da un programma produce un errore esplicito.

Apri **Ordine dei giunti…** e scegli **Un giunto alla volta**. Usa le frecce per cambiare l’ordine (ad esempio J2 → J1 → J4 → J6) e imposta la pausa dopo ciascun giunto, da 0 a 60 secondi. L’app attende la fine del movimento prima di contare la pausa. Se un giunto è già al suo angolo, lo salta. La pausa dopo l’ultimo giunto attivo è quella della posa. L’ordine viene salvato per tutta la sequenza, incluso l’eventuale HOME a fine ciclo. **Anteprima sequenza → Riproduci anteprima** mostra il tragitto e le pause. Nel modello DOC a cinque assi il movimento di J6 compare nel piano articolare, mentre la vista 3D mostra i soli giunti associati al modello.

**Una volta** parte dalla posizione attuale e si ferma sull’ultima posa attiva. **Ripeti** collega l’ultima alla prima del ciclo successivo. La spunta **Torna a HOME a fine sequenza** aggiunge un ritorno esplicito con l’ordine selezionato. **Pausa / Riprendi** sospende/prosegue; **Termina questo ciclo** completa il ciclo in corso. **Svuota** cancella la sequenza dopo conferma. Prima di avviare puoi usare **Anteprima sequenza**; avviare calcola comunque il piano e chiede conferma, con verifica delle modifiche successive.

Riordinare ora cambia l’ordine dei target e delle transizioni articolari dirette e simultanee. Le pose eliminate non rimangono come tappe nei percorsi delle altre. Controlla sempre la nuova anteprima prima di provare una sequenza registrata con le vecchie versioni.

## 12 · Programmi: istruzioni MoveJ e MoveL

In Studio → **Programmi · istruzioni e anteprima** scegli il tipo in **Istruzione**, compila la riga sotto e premi **Aggiungi istruzione**. Il nome è facoltativo: senza nome l’app ne propone uno («MoveJ → Pezzo +60 mm»). Le frecce cambiano l’ordine, il cestino elimina e la spunta salta l’istruzione senza cancellarla. Il programma è salvato nel progetto a ogni modifica ed esportato con **Esporta progetto…**.

**MoveJ** porta tutti i giunti insieme verso: un **target della scena** (con lo scostamento **Z sopra** in millimetri nel riferimento del target e la pinza allineata all’asse del target oppure **solo posizione**), la **HOME** (tutti i giunti a 0°), una **posa salvata** (i suoi angoli finali) o gli **angoli attuali** del controllore. Per un target l’app calcola la soluzione IK più vicina a dove finisce l’istruzione precedente. **MoveL** porta la punta in linea retta verso un target, con la pinza mantenuta o libera e una tolleranza da 0,1 a 2 mm. **Pinza**, **Attesa**, **Nota** e **Ripeti** completano il programma; **Posa registrata** diventa un MoveJ agli angoli della posa.

La **velocità** di MoveJ e MoveL è una percentuale (10–100%) delle velocità dei giunti impostate in Muovi e osserva, modificabile in ogni riga. Il firmware accetta almeno 1 °/s per asse: una percentuale più bassa resta a 1 °/s. Il budget impulsi può comunque limitare il movimento simultaneo; la durata della riga lo mostra.

**Pianifica programma** calcola l’intero programma: ogni istruzione parte da dove finisce la precedente, il percorso è controllato ogni grado contro limiti del controllore, limiti URDF, autocollisioni, ostacoli e piano di lavoro. Ogni riga mostra la sua durata, sotto compaiono durata stimata totale, tratti e, per ogni MoveL, lunghezza, tratti e deviazione massima. Se un’istruzione non è realizzabile la pianificazione si ferma lì: la riga è bordata di rosso e un riquadro indica istruzione, tratto, causa (per esempio «interferenza … piano di lavoro» o «irraggiungibile: fuori portata») e angoli. **Valida programma** fa la stessa pianificazione.

**Anteprima** anima il braccio 3D sul piano; **⏮ / ⏭** saltano all’istruzione precedente o successiva e la riga evidenziata con ▶ è quella che sta per essere eseguita; il cursore permette di guardare qualsiasi istante. Qualunque modifica a istruzioni, target, velocità, limiti o modello rende il piano scaduto: ripianifica.

**Esegui programma…** esegue esattamente il piano mostrato, dopo conferma: stessi tratti, stesse velocità, stesso ordine. Prima di ogni tratto il controllore ricalcola il profilo e si ferma senza inviare impulsi se differisce dal piano. **Passo passo…** esegue la prima istruzione e poi si ferma prima di ogni altra: **Istruzione successiva** prosegue di una, **Continua fino alla fine** completa il resto, STOP interrompe. Durante l’esecuzione la riga attiva mostra ⚡ (o ⏸ in attesa). A fine programma compare la durata misurata accanto a quella stimata (le pause del passo passo non sono contate). Se il programma termina in HOME, il percorso di ritorno viene azzerato; altrimenti Vai a HOME pianifica un ritorno diretto su richiesta. Nessuna ripresa automatica dopo un errore.

Sul robot reale i programmi con target o MoveL richiedono la corrispondenza fisica del modello dichiarata, e le pose usate devono essere registrate sul robot reale.

**Ripeti N volte … Fine** ripete le istruzioni interne; il numero può essere un’espressione e il **contatore** facoltativo (per esempio `strato`) vale 0, 1, 2… a ogni giro. **Se (condizione) … Altrimenti … Fine** sceglie fra due gruppi di istruzioni. **Variabile** assegna un valore (`passo = 20`, `n = n + 1`). Ripeti e Se si possono annidare fino a 8 livelli; le istruzioni interne sono rientrate. Una nuova istruzione va dopo la riga selezionata (clic sulla riga): subito dopo «Ripeti» o «Se» finisce al loro interno. Eliminando un Ripeti o un Se si tolgono anche la sua Fine e l’Altrimenti, le istruzioni interne restano; disattivandolo si salta tutto il blocco.

Le **espressioni** usano numeri, variabili, i nomi dei sensori definiti in Diagnostica, + - * / // %, confronti (== != < <= > >=) e and, or, not; niente altro viene eseguito. «Z sopra» di MoveJ e MoveL accetta anche un’espressione, per esempio `60 + strato*20` per impilare. Variabili, numero di ripetizioni e quote sono noti già in pianificazione; **i sensori si leggono solo nelle condizioni Se e nelle attese**.

**Attesa sensore** aspetta che l’ingresso abbia il valore indicato, al massimo per il timeout; poi il programma si ferma. Nella stima della durata conta zero secondi. Una **condizione Se sui sensori** non si può conoscere prima: la pianificazione verifica **entrambi i rami** a ogni condizione, ripetizioni comprese, e fonde i rami che tornano nello stesso stato (stessa posizione, pinza e variabili). Il riquadro mostra i rami verificati; per ogni condizione scegli **Vero/Falso** per l’anteprima e le durate. In esecuzione la condizione è letta in quel momento e il programma prosegue sul ramo corrispondente, sempre già verificato; le condizioni lette compaiono sotto il piano e nel registro. Un problema in un ramo non mostrato viene comunque segnalato, con il ramo («ramo: Se al blocco 4 vero»). Oltre 128 rami la pianificazione si ferma: riduci le condizioni dentro i cicli che cambiano variabili diverse.

In Anteprima basta un valore simulato (Diagnostica → Simula 0/1). Sul **robot reale** contano solo dati non simulati e aggiornati nell’ultimo secondo, inviati da un adattatore (API locale); altrimenti il programma si ferma con l’indicazione del sensore. Il vecchio blocco Ripeti «dal primo blocco» resta per i programmi semplici; con Ripeti N volte o Se usa la struttura … Fine.

Un programma **senza** istruzioni MoveJ/MoveL, strutture, variabili, uscite o funzioni abilitate resta un **programma a pose registrate**: le pose sono raggiunte direttamente dagli angoli correnti, i sensori hanno un timeout e il programma termina sull’ultima istruzione. Non richiede di partire da zero e non aggiunge HOME implicite. L’Editor delle istruzioni JSON salva l’elenco completo; i riferimenti alle pose sono legati a ID persistenti, oltre all’indice di visualizzazione.

### Funzioni riutilizzabili e sottoprogrammi (build44)

In **Istruzione → Funzione** scrivi il nome tecnico (es. `prendi`) e i parametri separati da virgole (es. `quota`). Aggiungi: la definizione e Fine funzione vanno in fondo al livello principale. Seleziona il suo inizio e inserisci le istruzioni del corpo fra queste due righe. Nel campo Z sopra puoi usare `quota` come espressione. La definizione viene saltata nel programma principale: esegue il corpo soltanto **Richiama funzione**, con un valore per ogni parametro, per esempio `quota = 60`.

Per richiamarla dal programma principale seleziona Fine funzione o una riga principale, scegli **Richiama funzione**, seleziona il nome e compila gli argomenti. Ripeti il richiamo con valori diversi. La matita modifica firma o richiamo; rinominare aggiorna i riferimenti, cambiare i parametri richiede di correggere gli argomenti. Eliminare una funzione elimina anche il corpo: i richiami rimasti vanno corretti. Un piano già calcolato scade dopo una modifica.

Le variabili sono **locali**: la funzione vede solo i parametri e le variabili create nel corpo. Al rientro si ripristina l’ambiente del chiamante, mentre posizione, pinza e I/O restano nello stato raggiunto. **Restituisci** termina subito la funzione anche dentro cicli/condizioni; può fornire un numero o un’espressione. Per usarlo assegna una **Variabile risultato** nel richiamo. Se chiedi un risultato ogni percorso raggiungibile deve restituire un valore; Fine funzione senza valore viene rifiutato. Esempio: `doppio(x)` → `Restituisci x*2`; richiamala con `x=30` e risultato `quota`, che varrà 60.

Sono ammessi 32 sottoprogrammi, 8 parametri ciascuno e 8 livelli di richiamo; la ricorsione viene rifiutata. I parametri sono numerici/booleani: target, pose e I/O restano riferimenti fissi nel corpo. I sensori si leggono nelle condizioni o attese, mai negli argomenti o valori restituiti. Tutti i rami vengono pianificati mantenendo ambiente e rientro separati per ogni richiamo. Usa Ripeti N volte … Fine; il vecchio Ripeti con salto non è combinabile con le funzioni.

Pianifica, osserva e prova **Passo passo…** in Anteprima. L’indicazione attiva mostra richiamo → funzione → istruzione interna; si ferma fra istruzioni interne e fra richiami distinti, mentre i tratti di uno stesso MoveL proseguono insieme. La prima istruzione parte subito. STOP annulla senza ripresa automatica. Le velocità, i limiti e i controlli geometrici sono quelli del piano comune; non occorre modificare il firmware per usare i sottoprogrammi.

Salvataggio ed esportazione progetto conservano tutto; le app prima della build44 non riconoscono queste nuove istruzioni. Una procedura completa e il formato JSON sono in `docs/SOTTOPROGRAMMI.md`, inclusa nell’app. L’esempio Python `examples/python_subprograms.py` pianifica presa e deposito con due funzioni; esegue soltanto con `--execute`, i permessi espliciti e, sul robot reale, l’approvazione nell’app.

## 13 · Vista 3D e significato delle visualizzazioni

Scorri con **due dita** sul trackpad o trascina nel riquadro per **orbitare** attorno al braccio in entrambe le direzioni. **Maiusc + due dita** (oppure Maiusc + trascinamento o tasto destro) trasla l’inquadratura. Il **pizzico** sul trackpad e la rotella del mouse regolano lo zoom. La rotazione si ferma quando sollevi le dita; ↺ e ↻ ruotano la camera a piccoli passi. Le viste 3D, Fronte, Lato e Alto cambiano solo l’inquadratura. **Adatta vista** comprende robot, riferimenti e target; con un piano MoveJ valido comprende anche i suoi campioni TCP.

**Segui comandi** mostra l’animazione stimata dal controllore. Disattivandolo puoi preparare un target virtuale con i campi dei giunti o IK. Il modello evidenziato e l’eventuale sagoma del conteggio reale aiutano a confrontarli; non sono immagini o misure del braccio fisico.

I piccoli marcatori indicano i giunti indipendenti, non flange fisse o dita della pinza. La traccia arancione è il TCP del nuovo piano MoveJ; i punti recenti visualizzano una scia del modello. Le terne rosso/verde/blu rappresentano gli assi X/Y/Z dei riferimenti e dei target. Le coordinate TCP sotto la vista sono in millimetri.

Ostacoli e messaggi di interferenza derivano da capsule ricavate dai link: autocollisioni fra le coppie controllate, box e piano di lavoro. Alcune coppie vicine per costruzione sono escluse. Il controllo è approssimato, non copre ogni dettaglio delle mesh, cavi o oggetti afferrati; la grafica non certifica la sicurezza.

## 14 · URDF, giunti, mapping e modello DOC

A controllo scollegato, apri **Modello del braccio → Giunti, mapping hardware e TCP**. **Importa URDF…** richiede un file URDF già espanso; Xacro deve essere convertito prima. Mantieni le mesh e le risorse del pacchetto accanto al file nei percorsi previsti. Un avviso di mesh mancante significa che una parte può essere rappresentata da un segnaposto.

Per ogni giunto indipendente, **Motore** associa il giunto a J1–J6 oppure Solo modello. **Verso** applica il segno e **offset** allinea lo zero geometrico. Applica mapping salva la configurazione; non ricabla i pin e non cambia i parametri del driver. Evita di associare due giunti indipendenti allo stesso canale.

I limiti URDF descrivono il modello. I giunti rotativi sono presentati in gradi nell’interfaccia e usano radianti internamente; i prismatici richiedono unità coerenti. L’esecuzione fisica di giunti prismatici non è implementata da questo controllore articolare. Il nuovo MoveJ richiede giunti rotativi e mapping univoco per gli assi mossi.

La spunta del giunto lo esclude dall’anteprima/controllo associato. Se il canale è fisico può attivare la procedura di rilascio ENABLE descritta nel capitolo STOP: non è soltanto un interruttore grafico.

**Carica DOC 5 DOF** ripristina il modello di riferimento con cinque giunti indipendenti. J6 può comparire tra i canali aggiuntivi senza essere un giunto del DOC. **Ho verificato fisicamente modello, mapping, versi e offset** è una dichiarazione dell’operatore richiesta ai flussi Studio fisici; non esegue una misura.

**Salva progetto** conserva la configurazione corrente. **Esporta progetto…** produce un archivio con modello, risorse e dati di progetto previsti; **Apri progetto…** lo importa e azzera l’autorizzazione fisica. Le note operatore e il diario IA non sono inclusi. Il dettaglio delle licenze delle risorse rimane nei relativi avvisi: l’importazione non concede diritti di redistribuzione.

## 15 · HOME del modello e TCP

Con controllo scollegato premi **HOME del modello…** vicino alla vista 3D. La finestra mostra il modello a zero comandato e permette di regolare gli offset visivamente con slider e numeri. Puoi orbitare e adattare la vista mentre allinei il modello alla posa fisica scelta.

**Annulla** scarta la prova. **Salva HOME del modello** conserva una revisione precedente del progetto, applica gli offset e richiede una nuova verifica della calibrazione per i target Studio fisici. Non muove motori, non modifica firmware e non cambia HOME o posizioni del controllore.

Il risultato è un **allineamento a vista**; precisione di TCP, lunghezze reali, giochi e versi richiedono misure. Se il conteggio del controllore era diverso da zero, il modello può restare sul target della nuova HOME: Segui comandi torna a visualizzare il conteggio corrente.

Il **TCP** è il punto utensile rispetto al Link utensile scelto. I campi X/Y/Z sono in millimetri e vengono applicati con **Salva TCP**. Per esempio Z=50 mm aggiunge 50 mm lungo l’asse locale Z del link selezionato. Non è una traslazione fissa lungo Z della stanza: ruota insieme al link.

Cambiare TCP modifica coordinate, tracce e problema IK. Non cambia la meccanica o il conteggio degli impulsi. In questa versione c’è un utensile/TCP corrente, non un catalogo completo di utensili intercambiabili.

## 16 · Riferimenti di lavoro e target locali

Apri l’omonima sezione nel modello a controllo scollegato. La **Base robot** è implicita e non eliminabile. Un **riferimento di lavoro** è un’origine con orientamento rispetto alla base; un **target** è un punto orientato espresso in quel riferimento.

Scegli Riferimento, premi Nuovo, assegna un nome, compila XYZ in mm e Roll/Pitch/Yaw in gradi, poi Salva riferimento. I riferimenti di questa versione sono figli diretti della base, senza annidamento. Le rotazioni seguono la convenzione Rz(yaw) · Ry(pitch) · Rx(roll).

Scegli Target, premi Nuovo, seleziona il riferimento, inserisci nome e posa locale e salva. L’albero e i marcatori 3D mostrano il risultato; i dati in base consentono di controllare la trasformazione. Se sposti il riferimento, il target mantiene le coordinate locali e cambia posizione nel mondo.

Esempio: riferimento X=100, Y=200, Z=0 mm e yaw=90°; target locale X=50, Y=0, Z=0 mm. Il target in base è X=100, Y=250, Z=0 mm. Portando il riferimento a X=150 ottieni X=150, Y=250, Z=0 mm. Questo è un cambiamento geometrico, non un comando motore.

Per modificare seleziona l’elemento nell’albero, aggiorna i campi e salva. Per eliminare un riferimento devi prima eliminare o riassegnare i target che lo usano; la base resta immutabile. La scena viene conservata nel progetto schema 2, con backup prima della migrazione dei vecchi progetti.

L’orientamento dei target viene salvato e disegnato; dalla build 34 **Calcola IK sul target** può usarlo (capitolo 18). I target nominati non diventano automaticamente un movimento. Il modello a cinque assi non può in generale soddisfare ogni posa arbitraria a sei componenti: la console misura e mostra lo scarto.

## 17 · MoveJ e MoveL: pianificare, osservare ed eseguire

**MoveJ** significa interpolare i giunti nello stesso tratto temporale. La traiettoria del TCP è in generale curva: non è MoveL, cioè una retta cartesiana. Pianificazione, cursore e riproduzione dell’anteprima sono calcoli puri, anche con il robot collegato, a controllore fermo: non cambiano angoli comandati, HOME, percorso, pose o pinza. Muove il controllore soltanto **Esegui MoveJ…**, descritto in fondo al capitolo.

Scegli la sorgente: **Angoli assoluti** usa i sei valori finali in gradi; **Giunti Studio** usa il target virtuale attuale; **Posa salvata** usa angoli finali, pinza e pausa della posa; **Programma** legge pose abilitate, pinza, attese, note e ripetizioni supportate. Non riutilizza automaticamente le traiettorie insegnate: costruisce segmenti MoveJ diretti e lascia invariati i dati originali.

Esempio: se J1 comandato è 10°, inserire J1=15° chiede un tratto di +5°. **Usa angoli attuali** riempie i campi con il conteggio del controllore; non copia la posa geometrica modificata a mano. Per quella scegli Giunti Studio. Gli assi non mappati, come J6 del DOC, devono restare fermi.

Prima applica i limiti in Operatore nella modalità Anteprima e le velocità desiderate in Muovi e osserva. Puoi usare il controllore virtuale con HOME per impostarli; la sola pianificazione non richiede che il robot reale sia connesso. **Includi ritorno al punto iniziale** aggiunge un segmento inverso diretto, anch’esso verificato; il ritorno muove il controllore soltanto quando confermi Esegui MoveJ, secondo la modalità selezionata.

Premi **Pianifica MoveJ**. Il riepilogo mostra durata stimata, numero campioni, tratti e velocità di picco per giunto. Usa lo stesso profilo dei gruppi simultanei: massimi individuali, accelerazione e budget di 2000 impulsi/s. Le durate sono stime; per la pinza si usa un’attesa convenzionale di 1,5 s.

**Riproduci anteprima / ▶ MoveJ** anima il modello dall’inizio. **Arresta anteprima / ■ MoveJ** ferma soltanto l’animazione nel punto corrente. Il cursore temporale permette di ispezionare altri istanti e ferma la riproduzione mentre lo muovi. Adatta vista include la traccia arancione. **Cancella piano** rimuove il preventivo senza cambiare pose o programmi.

Il piano controlla limiti applicati, limiti URDF calibrati, assi esclusi, mapping e punti intermedi contro gli ostacoli esistenti. Campiona con passo massimo di 1° per giunto: non verifica collisioni complete delle mesh o tra campioni. Sono ammessi fino a 64 tratti, 200 istruzioni, 4096 campioni e un’ora stimata; le attese sensore vengono rifiutate. Se nemmeno il tratto minimo arrotondato rispetta la tolleranza MoveL, il piano viene rifiutato: la tolleranza non viene allargata automaticamente.

Una modifica di stato, velocità, limiti, modello o programma rende il piano scaduto. Ripianifica; non viene riattivato automaticamente ripristinando vecchi numeri. Il piano è temporaneo e non viene salvato nel progetto.

**Esegui MoveJ…** (dalla build 35) esegue **esattamente il piano mostrato**, dopo una conferma che riporta modalità, tratti e durata. Servono HOME confermata, controllore fermo e un piano non scaduto. Ogni tratto diventa un movimento simultaneo del controllore: stessi limiti, assi esclusi, velocità e budget di impulsi; sul robot reale l’app invia una sola riga `~multi` per tratto e attende MULTI ACK e MULTI DONE dalla Mega prima del tratto successivo. Pinza e pause seguono il piano; **Pausa** trattiene l’esecuzione tra un tratto e l’altro. I tratti completati entrano nel percorso registrato, quindi **HOME** torna indietro lungo di essi.

**STOP**, perdita della USB, assenza dell’interfaccia, timeout del DONE o un errore del firmware interrompono subito: il conteggio resta all’ultimo tratto completato, HOME va ristabilita e **non c’è ripresa automatica**. Un piano già eseguito o interrotto non si riavvia: ripianifica. Sul robot reale, la sorgente Giunti Studio richiede la conferma della corrispondenza fisica del modello, e le pose devono essere state registrate sul robot reale, non in Anteprima. I programmi con attese sensore restano sul motore programmi esistente. Riproduci, Una volta e i programmi a pose registrate collegano direttamente i target attivi; i programmi con istruzioni MoveJ/MoveL si eseguono dal pannello Programmi (capitolo 12).

**Retta MoveL** (build 36) è una sorgente del pannello MoveJ: la punta va **in linea retta** dalla posizione comandata a un punto, nella base o in un riferimento di lavoro. Scegli la pinza — **Mantieni** (asse e rotazione restano quelli di partenza, quando i cinque assi lo permettono) o **Libera** — e la **tolleranza** (0,1–2 mm). **Usa punto attuale** e **Usa target salvato** riempiono i campi. La console risolve l’IK ogni millimetro, partendo ogni volta dalla soluzione precedente, e poi unisce i punti nei pochi movimenti simultanei che restano entro la tolleranza: il controllore esegue ogni tratto interpolando i giunti, con angoli arrotondati a 0,01°, e la deviazione viene misurata proprio su quel percorso. Il riepilogo indica lunghezza, tratti, **deviazione massima dalla retta**, errore all’arrivo e lo scarto di orientamento. Se una parte della retta non è raggiungibile, il piano viene rifiutato indicando **a quanti millimetri dall’inizio** e perché: fuori portata, limiti dei giunti (anche quelli applicati al controllore), giunti esclusi, oppure una singolarità o un cambio di configurazione. Il resto è il normale MoveJ: anteprima, controllo degli ostacoli, **Esegui MoveJ…**, STOP e HOME. Il backend esegue un gruppo alla volta, quindi tra un tratto e l’altro il braccio si ferma brevemente; dopo l’esecuzione il pannello mostra la **durata misurata** di ogni tratto rispetto alla stima, utile per conoscere i tempi reali della Mega. Sul robot reale MoveL richiede la conferma della corrispondenza fisica del modello.

## 18 · IK, jog cartesiano e ostacoli

Il pannello **IK e jog cartesiano · anteprima**, sotto il braccio 3D dello Studio, mostra X/Y/Z della punta in mm e la direzione della pinza nel riferimento scelto (base robot o un riferimento di lavoro). Tutto ciò che fai qui cambia **solo il modello virtuale**: nessun comando ai motori.

**Jog cartesiano.** Scegli passo (0,5–25 mm) e premi −X/+X, −Y/+Y, −Z/+Z. Con **Utensile** gli assi seguono la pinza: +Z avanza nella direzione delle dita. **Mantieni direzione utensile** conserva l’orientamento della pinza mentre la punta trasla. Rx/Ry/Rz ruotano la pinza attorno alla punta di 1, 5 o 15°. Ogni passo parte dalla posa attuale e cerca la soluzione più vicina; viene **rifiutato**, lasciando l’anteprima com’era, se il punto è fuori portata o oltre i limiti, se un giunto dovrebbe ruotare più di 15° in un passo (singolarità o cambio di configurazione) oppure se la rotazione richiesta non è realizzabile.

**Perché alcune rotazioni vengono rifiutate.** Il DOC ha cinque assi: J1 orienta il piano del braccio, J2–J4 lavorano in quel piano, J5 ruota la pinza attorno al proprio asse. La pinza può quindi inclinarsi solo nel piano del braccio e ruotare su sé stessa; un’inclinazione laterale richiederebbe un sesto asse. Con la pinza verso il basso, per esempio, Rz (rotazione della pinza) funziona, mentre un’inclinazione laterale viene rifiutata con lo scarto in gradi. Traslando con la direzione mantenuta, se l’orientamento non è conservabile il passo viene applicato e lo scarto mostrato.

**IK verso un punto.** Inserisci X/Y/Z in mm nel riferimento scelto, scegli la pinza — **Libera** (solo posizione), **Verso −Z del riferimento** (perpendicolare al piano, verso il basso nella base) o **Mantieni attuale** — e premi **Calcola IK**. La posizione ha sempre la priorità; l’orientamento viene raggiunto quando i cinque assi lo permettono, altrimenti la console indica lo scarto.

**IK sul target salvato.** Scegli un target dei Riferimenti di lavoro e un orientamento: **Solo posizione**, **Posizione e asse Z** o **Asse Z e rotazione**. Nei target l’asse Z è la direzione della pinza (uscente dalla flangia) e l’asse X la sua rotazione: per una presa dall’alto usa roll 180°.

**Configurazioni.** Lo stesso punto si raggiunge spesso in più modi, per esempio **Braccio in avanti · gomito +** oppure **Braccio all’indietro · gomito −**. La console elenca le soluzioni (angoli, variazione massima, scarto), applica la più vicina alla posa attuale e con **Usa** puoi sceglierne un’altra. Se il punto non è raggiungibile ne indica il motivo — fuori portata (con distanza e portata stimata), limiti dei giunti o giunti esclusi — e lascia l’anteprima invariata. L’avviso di singolarità compare quando alcune direzioni richiederebbero grandi rotazioni, per esempio a braccio tutto verticale.

I calcoli usano le quote del modello e la calibrazione dello Studio (segni, offset, TCP), non misure del braccio. Un risultato in anteprima non va interpretato come un ordine da eseguire comunque.

Il calcolo aggiorna il modello virtuale. **Esegui target visualizzato…** è un’azione separata, con conferma, HOME, limiti, mapping e verifica fisica richiesti. Dalla build 35 pianifica ed esegue il MoveJ comune (capitolo 17): tutti i giunti insieme, con il percorso campionato contro gli ostacoli; solo con un firmware senza movimenti simultanei procede un giunto alla volta. Non aggiunge una traiettoria rettilinea o evitamento automatico degli ostacoli.

L’editor Ostacoli contiene una lista JSON. Ogni oggetto ha name, center e size in metri; per esempio `[{"name":"tavolo","center":[0.4,0,0.1],"size":[0.2,0.3,0.1]}]`. Il centro è nella base, size sono dimensioni complete, non semidimensioni. **Applica ostacoli** valida e salva la lista.

Il controllo usa capsule ricavate dalle mesh dei link, autocollisioni, ostacoli e piano di lavoro z=0. Valida sequenza controlla le transizioni dirette fra target attivi dalla posizione attuale, con HOME solo se selezionato; Riproduci esegue la stessa verifica e rifiuta i problemi prima di muovere. Valida programma usa il piano del programma. La geometria semplificata non descrive cavi, pezzo afferrato o ogni dettaglio; nessuna interferenza rilevata non certifica il percorso fisico.

La validazione segue i blocchi pinza nell’ordine del programma, anche nei programmi di sola pinza, e conserva lo stato delle dita nei percorsi successivi e nel ritorno. Prima di Ripeti controlla anche il secondo ciclo con lo stato finale della pinza; i cicli successivi ripetono quello stesso schema. La pinza è verificata nella geometria finale richiesta, non durante una scansione continua della corsa del servo. Valida sequenza da solo esamina un ciclo; l’avvio Ripeti aggiunge automaticamente il controllo del secondo.

## 19 · Firmware: driver, microstep e riduttori

L’editor opera su una **copia locale dei sorgenti**, non direttamente sulla memoria della Mega. A controllo scollegato apri **Firmware · parametri ed editor → Microstepping, riduttori e sorgenti**. Rileggi profilo ripristina nei campi i parametri salvati.

Per ogni asse imposti driver disponibile, passi motore/giro, microstepping, riduzione e inversione. Un motore da 1,8° usa 200 passi/giro. **Microstep 8 significa 1/8**; il rapporto 38,4 significa 38,4 giri motore per un giro in uscita. La conversione è passi/giro × microstep × riduzione / 360 impulsi per grado.

I valori devono coincidere con jumper A4988/DRV8825, DIP DM542 e riduttore reali. Cambiare il numero nell’app **non cambia elettricamente i jumper o i DIP**. Un valore incoerente causa angoli e velocità fisiche diversi da quelli mostrati. Corrente, tensione e dissipazione restano regolazioni hardware.

La RAMPS ha cinque slot motore. **J6 fisico** richiede un driver esterno e pin compatibili; non usa uno slot che non esiste. L’editor mostra i pin ammessi e segnala −1 come non collegato. Nel profilo attuale il DM542 non usa ENA; non assegnare pin a caso o già utilizzati da accessori.

**Genera e salva dai parametri…** conserva una revisione e aggiorna il firmware locale con il profilo. **Aggiorna comandi giunti…**, se proposto, sostituisce il file principale con quello incluso e rigenera i parametri preservando il profilo: eventuali modifiche manuali vanno recuperate e riesaminate dalla revisione.

Seleziona un file, usa **Rileggi file**, modifica il testo e **Salva sorgente**. Salvare non compila e non programma la scheda. Le modifiche libere possono rompere identificazione, watchdog, limiti e pin; dopo una modifica controlla compilazione e log. **Ripristina firmware originale…** conserva una revisione della versione corrente. **Esporta sorgenti…** salva un archivio; Apri cartella sorgenti apre i file locali.

L’identità del profilo permette di confrontare parametri preparati e firmware riconosciuto. Non prova che i selettori fisici siano corretti. Una nuova build dell’app non aggiorna automaticamente il firmware montato sul robot.

## 20 · Compilare e caricare il firmware dall’app

Servono **Arduino CLI**, core Arduino AVR e libreria AccelStepper. L’IDE Arduino non è necessario. La sezione Firmware mostra strumento, disponibilità, schede e log; il link ufficiale permette di installare la CLI se manca. **Prepara dipendenze…** richiede conferma e può usare Internet per scaricare i componenti necessari.

Per verificare soltanto il sorgente premi **Verifica compilazione**: crea il programma, ma non apre la porta per caricarlo sulla scheda. Un esito positivo non prova compatibilità del cablaggio o movimenti fisici.

Per il caricamento: scollega il controllo, prepara la Mega con sola USB e alimentazioni degli attuatori escluse, aggiorna le porte, scegli la Mega corretta e premi **Carica sulla Mega…**. Leggi e conferma l’azione. Non avviare simultaneamente Arduino IDE o un altro monitor sulla stessa porta.

Attendi il risultato del log. Non interrompere alimentazione o USB durante la scrittura. Il pulsante Annulla è disponibile nelle fasi annullabili, non durante la scrittura non interrompibile. Al termine l’app resta scollegata; riconnetti esplicitamente e attendi il riconoscimento prima di ristabilire HOME.

Se la compilazione fallisce, correggi il primo errore significativo nel log. Se il caricamento fallisce, controlla porta e disponibilità della scheda. Un firmware caricato ma non riconosciuto richiede diagnosi del protocollo e dei parametri, non movimenti di prova alla cieca.

## 21 · Comandi vocali del robot e conferma

Questa funzione si trova in **Muovi e osserva → Comandi vocali del robot** ed è distinta dalla dettatura della chat IA. Usa riconoscimento vocale locale Apple nella lingua dell’app e richiede i permessi Microfono e Riconoscimento vocale. Ollama non interpreta questi comandi motore.

Premi **Parla al robot**, poi pronuncia una frase chiara. «Muovi J2 di 5 gradi» indica uno spostamento relativo. «Muovi J2 a 5 gradi» indica una destinazione assoluta. «Muovi J1 a 5 gradi, J2 a 3 e J3 a meno 2» prepara un gruppo. «Avvia posa 1» richiama la prima posa con il percorso insegnato, pinza e pausa e resta sulla posa.

Dopo circa 1,5 secondi di silenzio l’app valida la frase e legge il riepilogo di destinazioni e spostamenti. **Aspetta che finisca**, poi rispondi **«sì, confermo»** oppure **«annulla»**. Il microfono di conferma parte in una nuova sessione dopo la voce sintetizzata; la lettura dell’app non è una conferma.

In inglese: “move J2 by 5 degrees”, “move J2 to 5 degrees”, “start pose 1”, “yes confirm” e “cancel”. Una frase ambigua o un numero non compreso vengono rifiutati; ascolta comunque l’intero riepilogo perché la trascrizione può essere sbagliata.

La conferma è monouso e scade dopo 30 secondi. Cambiamenti a HOME, posizione, modalità, limiti, velocità, assi, pose o firmware la invalidano. **Annulla ascolto** chiude la sessione. La spunta **Ascolta il prossimo comando a movimento concluso** riapre l’ascolto dopo un comando concluso correttamente; dopo errore, STOP o annullamento non riparte. Circa 20 secondi senza comando terminano l’ascolto.

Durante un moto usa i pulsanti STOP o Esc. Rumore, permessi e riconoscimento vocale possono introdurre ritardi: la voce non è un arresto di emergenza. Prova prima questa catena in Anteprima, con angoli piccoli e senza hardware.

## 22 · Diagnostica, grafici e sensori

In Diagnostica e ROS 2, **Registra sessione** acquisisce periodicamente posizioni comandate, modalità, stato e pinza. L’app mantiene fino a 18000 campioni della sessione e mostra i recenti nel grafico. **Esporta CSV…** salva i dati raccolti. Registrazione e posa sono cose diverse: il CSV non diventa automaticamente un programma.

L’etichetta Origine distingue **virtuale** da **impulsi comandati · senza encoder**. Le linee del grafico mostrano quel conteggio, non il movimento misurato. Un motore bloccato o un riduttore che slitta può non essere riconosciuto.

Per aggiungere un ingresso inserisci nome, tipo e **Definisci sensore**. Sono previsti digital, distance, force, encoder e temperature come categorie di dati. Definire un nome non installa un sensore, non seleziona un pin della Mega e non crea un controllo in retroazione.

In Anteprima **Simula 0 / Simula 1** forniscono dati di prova marcati simulati. Per un ingresso reale serve un adattatore che invii valori aggiornati con l’origine corretta; i tempi di freschezza sono mostrati. Un dato mancante o vecchio non deve essere interpretato come una lettura attuale. Le attese programma reali non accettano dati sintetici.

I sensori esterni possono usare l’API locale per ingressi già definiti. Il controllo motori resta a impulsi: aggiungere dati encoder a questa tabella non realizza automaticamente anelli di posizione, homing, anticollisione o arresto di sicurezza.

## 23 · ROS 2, RViz, Webots e Gazebo

La console usa un **progetto ROS/Pixi già predisposto**; non installa l’intero ecosistema da sola. Seleziona la cartella e il dominio ROS, poi **Collega ROS 2**. Il dominio predefinito è 42 e deve coincidere con quello degli strumenti che vuoi osservare. Il collegamento è locale.

Il pannello mostra stato dell’osservatore, heartbeat, nodi e tempo dall’ultimo dato dei topic del laboratorio. **Scollega** ferma il collegamento avviato dall’app. Un heartbeat recente prova che l’osservatore comunica; non prova un movimento fisico.

La console pubblica stato e visualizzazione: `/doc_regia/stato`, `/robot_console/joint_states`, `/robot_console/robot_description` e TF con prefisso `robot_console/`. In Anteprima i dati sono virtuali, in Robot USB sono stime dagli impulsi. **Non riceve comandi motore via ROS**: non c’è un secondo controllore hardware che possa contendere la seriale.

Apri **Strumenti opzionali e integrazioni**, premi Rileva strumenti nel progetto e avvia soltanto quelli disponibili. **RViz 2** visualizza il modello della console; scegli frame/topic appropriati. **Webots** apre il laboratorio separato, inizialmente in pausa. **Gazebo** apre una scena di esempio, non un modello dinamico calibrato del DOC.

**Registrazione rosbag** avvia la raccolta dei topic previsti dall’integrazione. Per fermare un processo usa Ferma; l’app gestisce i processi che ha avviato, non qualsiasi istanza già aperta. I log rimangono locali.

Masse, inerzie, ros2_control, MoveIt, controllo dinamico e trasferimento simulazione-robot richiedono sviluppi e prove separati. La disponibilità di un pulsante per avviare uno strumento non equivale alla presenza di tutte queste integrazioni.

## 24 · API Python, programmi e adattatori I/O

In **Diagnostica e ROS2 → API Python · programmi e I/O**, premi **Avvia API locale** e copia indirizzo e token della sessione. Il servizio ascolta soltanto su **127.0.0.1**, con porta casuale. Ogni richiesta usa `Authorization: Bearer TOKEN`; token e permessi si azzerano a ogni avvio API e non entrano nei progetti.

Per inviare istruzioni abilita **Consenti pianificazione dei programmi da API**. Per l’esecuzione simulata abilita anche **Consenti esecuzione da script in Anteprima**. Il client Python3 `robot_console_client.py` usa solo la libreria standard. `plan(blocks, scenario)` accetta gli stessi blocchi di Studio, sostituisce le istruzioni del progetto e restituisce lo stesso piano verificato con durata, tappe, rami e problemi localizzati. `execute(plan)` richiede id e impronta esatti: non crea un percorso diverso. Nessun endpoint può collegare USB, caricare firmware, confermare HOME o modificare limiti.

Sul **robot reale ogni esecuzione da script richiede conferma nell’app**. Il banner mostra nome, piano, durata e rami: controllali in Studio, poi Approva ed esegui oppure Rifiuta richiesta. La conferma è monouso e scade dopo 60 s; cambi di piano, modalità o stato la invalidano. Anche durante l’attesa lo script deve mantenere il proprio heartbeat.

`wait(run)` segue l’avanzamento e rinnova l’heartbeat ogni 0,2 s. Script assente per 3 s: STOP senza ripresa automatica. Timeout dello script e Ctrl-C chiedono STOP. STOP nell’app e `stop()` dello script interrompono lo stesso esecutore; Ferma API o revoca dei permessi arresta il programma API. In passo passo usa `step(run)` o `continue_program(run)` mantenendo l’heartbeat. Le durate misurate sono software: non misurano la posizione del robot.

In Diagnostica definisci ingressi e **Uscite digitali e adattatori**. Un blocco **Uscita digitale** sceglie nome, valore 0/1 e timeout. In Anteprima cambia uno stato simulato. Sul robot la console pubblica una richiesta a un adattatore esterno; il programma prosegue solo dopo la conferma del valore richiesto entro il timeout. Nessun pin della Mega è modificato. Pianificazione e anteprima non comandano le uscite. La durata mostrata esclude le attese I/O; il client espone anche il massimo comprendente i timeout.

Un adattatore registra nomi, origine `simulated` e una sessione con token proprio. Heartbeat e campioni devono arrivare entro 1 s; dopo scadenza serve una nuova sessione. Dati non registrati sono sempre simulati. Sul robot reale servono origine dichiarata non simulata e campione recente: la dichiarazione dell’adattatore non è una certificazione della misura. Una condizione con dato inutilizzabile interrompe il programma; un’attesa sensore aspetta fino al timeout. Uscite senza adattatore, ACK errato o perdita del collegamento interrompono il programma. ACK scaduti o arrivati dopo STOP non riavviano niente. Un’uscita già applicata dal dispositivo esterno non viene annullata retroattivamente da STOP.

Endpoint principali: `GET /v1/health`, `/v1/state`, `/v1/plan`, `/v1/runs/ID`; `POST /v1/program/plan`, `/execute`, `/heartbeat`, `/step`, `/continue`; `POST /v1/stop`. I sensori usano `/v1/sensors`, gli adattatori `/v1/adapters`, le conferme `/v1/io/ack`. Il contratto completo è in **PYTHON_API.md**, incluso nell’app, con esempi e limiti. `examples/python_pick_and_place.py` pianifica soltanto salvo `--execute`; richiede i target Pezzo e Deposito già creati. Nessun esempio imposta automaticamente hardware, HOME o limiti.

## 25 · Telecamera, immagini e QR

In **Visione · telecamera locale** scegli un dispositivo, aggiorna l’elenco se necessario e premi **Avvia video**. La prima volta macOS chiede il permesso Telecamera. Se negato, abilitalo nelle impostazioni Privacy di macOS prima di riprovare.

La sezione Video, fotogrammi e codici mostra il flusso locale. **Salva fotogramma…** crea un PNG nella posizione scelta. **Rileva QR** legge i codici visibili nel fotogramma corrente e mostra il testo; non esegue quel testo come comando.

**Ferma video** arresta la sessione e libera il dispositivo; anche l’uscita dalla sezione della telecamera ne ferma l’acquisizione. Una fotocamera esterna deve essere riconosciuta dal sistema. Il video non viene inviato automaticamente a Ollama, a un servizio cloud o a ROS.

Non sono ancora disponibili calibrazione ottica, stima 3D degli oggetti, AprilTag, inseguimento o presa automatica. Per trasformare pixel in coordinate robot servono modelli, calibrazione camera/base e un flusso di validazione aggiuntivo.

## 26 · Assistente, memoria e Ollama offline

L’Assistente consulta stato e diario locale; **non esegue movimenti**. Puoi chiedere «Qual è lo stato?», «Quali pose ho salvato?» oppure «Cosa è successo?». Con **Ricorda: …** memorizzi esplicitamente una nota nel diario IA, diverso dalle Note operatore laterali.

Scrivi una domanda e premi **Invia**. **Parla** detta testo nella casella; Ferma dettatura termina il microfono. La dettatura non è un ordine al robot e non equivale alla conferma vocale dei movimenti. **Leggi risposta** legge l’ultima risposta dell’assistente; le etichette tecniche del modello Ollama sono escluse dalla lettura. **Silenzio** ferma la voce sintetizzata.

La spunta **Conversazione libera · IA offline con Ollama** abilita il modello locale. Il pannello distingue installazione rilevata, servizio avviato, modello selezionato e modelli caricati in memoria. **Aggiorna** rilegge lo stato; **Avvia e carica modello** prepara quello scelto. Anche inviare una domanda con IA attiva può avviare il servizio e caricare il modello.

L’app usa modelli già presenti sul Mac e non li scarica automaticamente. Se Ollama manca, usa il link ufficiale; se non ci sono modelli, installane uno con gli strumenti di Ollama e aggiorna l’elenco. Il primo download richiede Internet; con runtime e modello disponibili puoi usare il percorso locale offline.

**Ferma IA e libera memoria** disabilita la conversazione libera e scarica dalla memoria il modello selezionato, lasciandolo su disco. Se il servizio era stato aperto da questa app viene fermato; se era già usato da altri programmi può restare attivo. Il comando attende che risposta o caricamento siano terminati. Su Apple Silicon la memoria è condivisa: le dimensioni su disco non sono una misura diretta della RAM occupata.

**Diario persistente** mostra gli ultimi eventi dal database locale. La memoria conserva richieste e risultati software, non crea una misura del robot. Un modello linguistico può dare risposte inesatte: le autorizzazioni ai movimenti restano nei controlli deterministici, non nella chat.

## 27 · Eventi, note, progetti e copie dei dati

**Attività del robot** conserva fino a 300 eventi recenti della sessione con ora e modalità. Segui ultimi eventi abilita lo scorrimento automatico. Nascondere la barra non cancella gli eventi e non ferma il robot. Il diario IA persistente è distinto da questa finestra recente.

**Note operatore** è un taccuino personale salvato automaticamente su questo Mac. Non viene incluso nei progetti esportati e non viene inviato automaticamente alla chat. Non confonderlo con Ricorda dell’assistente, che crea una voce nel suo diario.

I dati applicativi personali risiedono in `~/Library/Application Support/DOC Regia`; il progetto Studio include modello, mapping, offset, TCP, scena e blocchi. La sequenza del controllore e gli altri dati previsti dall’export seguono il formato corrente. Per spostare lavoro usa Esporta progetto e controlla il risultato su una copia prima di importarlo su un’altra configurazione.

Le revisioni di firmware e HOME e i backup precedenti alle migrazioni sono separati dalla copia dell’app. Il gestore locale conserva app attuale e penultima; le vecchie copie gestite sono recuperabili dal Cestino. I backup dei dati personali non vengono eliminati con le vecchie app.

Tornare a una build precedente può richiedere anche dati compatibili: schema 2 dei riferimenti e percorsi simultanei potrebbero non essere letti correttamente da build vecchie. Conserva i backup prima di un ripristino; non sostituire soltanto l’eseguibile presumendo compatibilità completa.

## 28 · Fine sessione e chiusura

Per finire un test, attendi il controllore fermo e controlla stato, angoli e ambiente. **HOME e chiudi l’app** nella barra sinistra propone il ritorno disponibile; se una sequenza è attiva puoi completare il ciclo e arrivare HOME. L’app chiede infine di **verificare visivamente HOME**, perché il completamento deriva dal conteggio e non da un sensore.

**STOP ed esci** è una scelta diversa: interrompe senza garantire il ritorno alla posa iniziale. Se la posizione è incerta, non confermare una HOME solo per eliminare l’avviso. Una chiusura forzata del sistema non può completare ordinatamente un tragitto.

L’arresto watchdog protegge da comunicazione assente secondo il firmware; non è una garanzia assoluta contro guasti elettrici, caduta di un asse o cablaggio errato. Il DM542 con ENA scollegato può mantenere coppia anche dopo la chiusura. Il programma non sostituisce la procedura di spegnimento dell’impianto.

Prima di caricare un firmware o modificare il cablaggio chiudi il controllo e predisponi il banco. L’aggiornamento dell’app non deve essere fatto mentre il robot è in moto o una porta è usata da una sessione attiva.

## 29 · Problemi frequenti e percorso di diagnosi

**I pulsanti + e − sono disabilitati:** verifica modalità, connessione, riconoscimento firmware, conferma velocità, HOME, limiti applicati e spunta del giunto. USB sola permette il riconoscimento della Mega ma non alimenta gli attuatori. In Anteprima puoi provare senza alimentazioni reali.

**Applica le velocità prima di muovere il gruppo:** c’è una bozza non confermata. Premi Invio o ✓ in ogni velocità modificata. Se cambi altri dati dopo il riepilogo, prepara nuovamente il gruppo. Il valore applicato ha due decimali; non serve cambiare numero solo per confermarlo.

**Firmware HALTED o watchdog:** il firmware ha arrestato il moto o non ha ricevuto la comunicazione prevista. Leggi il log, verifica che nessun altro programma contenda la seriale e ristabilisci il riferimento dopo aver risolto la causa. Non disattivare il watchdog come scorciatoia e non inviare una coda di comandi per sbloccare il robot.

**MoveJ scaduto:** sono cambiati dati rispetto al piano. Premi Pianifica MoveJ dopo aver verificato angoli, limiti e velocità. **Fuori limiti URDF calibrati:** controlla target, verso e offset del modello oltre ai limiti del controllore. **Asse non associato:** il canale richiesto non ha un giunto nel modello, per esempio J6 sul DOC. **Interferenza MoveJ:** modifica target o ambiente virtuale e controlla il tratto indicato.

**Un programma non parte:** verifica HOME, modalità delle pose, pose abilitate, blocchi validi e sensori richiesti aggiornati. Un sensore simulato non vale come ingresso reale. **Il modello non segue:** attiva Segui comandi e controlla mapping; un target virtuale o un cursore MoveJ possono mostrare una posizione diversa dal conteggio senza muovere il robot.

**Movimenti fisici errati nonostante la grafica corretta:** controlla con procedura di banco microstep/DIP, riduzione, versi, accoppiamento, alimentazioni e calibrazione. Non dedurre la causa dal solo modello e non compensare automaticamente un guasto aumentando angoli o corrente.

**IA o ROS non disponibili:** queste sono integrazioni opzionali. Controlla runtime/progetto, modello locale, stato del servizio e log; il controllo manuale in Anteprima non dipende dal loro avvio. **Microfono o camera negati:** correggi il permesso nelle impostazioni Privacy del sistema, poi riprova esplicitamente.

## 30 · Glossario e limiti attuali

**Giunto / joint:** grado di movimento del modello. **Canale Jn:** uscita logica del controllore, associata tramite mapping. **DOF:** grado di libertà indipendente; le dita accoppiate della pinza non trasformano DOC in un braccio a sei assi.

**Posa:** configurazione insegnata di giunti, pausa, pinza e percorso. **Target:** destinazione geometrica o articolare; non è automaticamente una posa provata. **TCP:** punto utensile. **Riferimento:** sistema di coordinate in cui esprimi un target.

**FK:** dagli angoli calcola la geometria e il TCP. **IK:** cerca gli angoli per un target: posizione, poi direzione e rotazione della pinza quando i cinque assi lo permettono. **MoveJ:** interpola gli angoli, TCP generalmente curvo. **MoveL:** percorso TCP rettilineo, diviso in movimenti simultanei entro una tolleranza misurata (capitolo 17).

**ACK:** firmware ha riconosciuto il comando. **DONE:** il software ha concluso gli impulsi previsti. Nessuno dei due è una misura encoder. **Watchdog:** arresto del firmware se la comunicazione attesa manca. **ENABLE:** abilitazione del driver quando cablata; distinta da alimentazione generale.

Il progetto è work in progress. Sensori di posizione, encoder, telecamere, prossimità, LiDAR, collisioni complete, pianificazione avanzata e altri backend richiedono incrementi verificati. La build locale ha firma ad hoc; firma Developer ID e notarizzazione Apple non sono state completate e richiedono l’iscrizione dell’autore.

La guida descrive ciò che questa build offre e i suoi limiti; non certifica sicurezza elettrica, capacità di carico o precisione del tuo montaggio. Usa le prove in Anteprima per imparare il flusso, poi una procedura di collaudo fisico coerente con il tuo hardware.
