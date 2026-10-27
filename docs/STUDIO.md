# Robot Console Studio 2.0

Versione 2.0 in sviluppo per macOS Apple Silicon. Il robot DOC di riferimento è **5 DOF**;
la console gestisce **sei canali**, con J6 opzionale. Nessuna connessione USB, importazione
URDF o attivazione di Ollama avviene all'avvio.

La tendina **Lingua** permette di scegliere Italiano oppure English. La scelta è salvata e
non riconnette la Mega, non azzera HOME e non modifica pose o firmware. Nuove risposte e
dettatura seguono la lingua scelta; note storiche, codice, output firmware e log esterni
conservano la lingua originale. La dettatura inglese richiede il supporto locale di macOS.

## Aree di lavoro

- **Operatore**: connessione/HOME, firmware, modello, limiti, movimenti e pose.
- **Studio 3D e programmi**: modello ingrandito, configurazione URDF, target virtuali,
  blocchi e anteprima del percorso registrato.
- **Diagnostica e ROS 2**: registrazione CSV, ingressi sensore, osservatore ROS,
  strumenti opzionali, API e telecamera locale.
- **Assistente**: conversazione, voce e memoria locale. Nessuna autorità di movimento.

## Prima prova senza robot

1. Operatore → **Avvia anteprima** → **Conferma HOME**.
2. Scegli ±5° → **Per tutti i giunti** → **Applica limiti**.
3. Prova J1 e J6 con 1°. La vista accanto ai comandi segue una stima animata.
4. La casella J6 esclude i suoi comandi. Una sequenza o un ritorno HOME che lo
   richiedono vengono rifiutati prima di iniziare; riabilitalo per rientrare.
5. Registra due pose e la richiesta della pinza, torna HOME e riproduci.

I test automatici e l'anteprima non dimostrano movimento, coppia o precisione fisici.
Il conteggio impulsi non rileva perdita di passi. STOP ferma gli impulsi e invalida HOME;
**non rilascia la coppia di un DM542 con ENA non gestito**.

## Firmware: microstepping, riduttori ed editor

Scollega il controllo prima di modificare i sorgenti o la configurazione.
In **Firmware · parametri ed editor**, apri **Microstepping, riduttori e sorgenti**.

- Passi/giro: passi interi del motore, ad esempio 200 per 1,8°.
- Microstep ×: 8 indica 1/8. Deve corrispondere ai **jumper/DIP fisici**.
- Riduzione :1: giri del motore per giro dell'uscita, ad esempio 38,4.
- Inverti: cambia il verso del canale nel firmware generato.

`impulsi/grado = passi × microstep × riduzione / 360`.
La velocità ammessa viene limitata tra 1 e 20°/s e dal budget configurato di
4000 impulsi/s per asse. Non costituisce una prova di velocità sostenibile sotto carico.
Corrente, dissipazione e tensioni restano proprietà del driver e del montaggio.

1. Modifica i parametri e premi **Genera e salva dai parametri…**.
2. Oppure scegli un file `.ino`, `.h` o `.cpp` e modifica il testo nell'editor.
3. Premi **Salva sorgente**. La versione precedente viene conservata nelle revisioni.
4. **Verifica compilazione** usa i file salvati; una modifica non salvata non viene compilata.
5. Se vuoi aggiornare la scheda, seleziona la Mega nella sezione firmware e premi
   **Carica sulla Mega…**. Richiede la conferma, compila, ricontrolla l'identità della
   porta e verifica la scrittura. Nessun movimento viene avviato al termine.
6. Riconnetti e ristabilisci HOME. Un profilo generato diverso da quello ricevuto
   blocca i movimenti. Il firmware legacy Regia 2/4 resta accettato per il solo profilo
   originale a cinque assi, con il relativo limite di velocità.

Il generatore aggiorna costanti riconoscibili, conservando le altre modifiche. Se hai
rimosso tali costanti, esporta il codice prima di ripristinare. Modifiche libere a pin,
protocollo, identificazione o watchdog richiedono revisione tecnica: il fatto che
compilino non dimostra che siano corrette. Usa il pannello dei parametri per mantenere
coerenti la conversione degli angoli e l'identificazione del profilo. Le costanti motore
diverse dal profilo vengono segnalate e bloccano il controllo finché non le riallinei.

### J6

La RAMPS offre solo X/Y/Z/E0/E1. J6 è **abilitato logicamente** e funziona in Anteprima;
lo puoi escludere dalla casella nei controlli. Il firmware standard non attiva pin J6.
Per usarlo fisicamente serve un driver esterno: abilita **J6 fisico**, imposta STEP/DIR
su pin liberi consentiti e genera/carica il profilo. Per DM542 ENA resta non gestito.
La console richiede sia il profilo attivo sia l'annuncio `CAPS 6` del firmware.
Non è stato effettuato alcun collaudo fisico del sesto asse.

Le pose e i limiti salvati a cinque canali vengono estesi con J6 a zero.

## Modelli, calibrazione e progetti

Il modello predefinito è il DOC a **cinque assi della presentazione e di Webots**,
una versione illustrativa derivata dall’UR3e con pinza radiale. Non è il CAD fisico EB-15.
Le dita sono elementi visivi e non consumano J6. Gli offset HOME iniziali sono quelli
nominali della presentazione: verifica la calibrazione prima dell’uso fisico.
**Carica DOC 5 DOF** ripristina questo modello a controllo scollegato.

Trascina sul modello per ruotare attorno al braccio. Rotella e pizzico regolano lo zoom;
i pulsanti ↺/↻ ruotano di 15°. **Adatta vista** ricentra e inquadra tutte le mesh.


**Importa URDF…** accetta URDF locali già espansi. Xacro non viene eseguito, né vengono
scaricate risorse. Box, sfere, cilindri, STL/OBJ/DAE locali e joint mimic sono supportati.
Le mesh devono restare nel pacchetto vicino all'URDF; le risorse mancanti diventano
segnaposto. I materiali senza texture vengono conservati; riferimenti esterni vengono
rimossi/rifiutati. Esempi: `examples/arm-five.urdf` e `arm-six.urdf`.

Sono ammessi bracci con 1–16 giunti indipendenti. Multi-braccio e umanoidi non sono
supportati; i sei canali hardware restano il limite del backend corrente. Un modello
importato parte **senza mapping hardware**. Importare un URDF non configura driver o pin.

Espandi **Giunti, mapping hardware e TCP**, associa esplicitamente i giunti ai canali,
imposta segno e offset, scegli il link e il TCP in mm. Il segno/offset trasformano la
coordinata comandata nella coordinata URDF; non costituiscono un homing misurato.
La conferma fisica è una dichiarazione dell'operatore e viene rimossa importando un progetto.
I giunti prismatici sono solo visuali, non comandabili con questo firmware rotativo.

Gli slider e i target numerici modificano il modello. **Esegui target visualizzato…**
richiede conferma, limiti validi e mapping verificato per il robot reale. Esegue un asse
alla volta; non introduce traiettorie fisiche coordinate. L'IK è solo di posizione, non
impone l'orientamento e aggiorna esclusivamente l'anteprima.

Gli ostacoli sono box in metri: `[{"name":"tavolo","center":[0,0,-0.1],"size":[1,1,0.1]}]`.
Il controllo usa segmenti tra origini dei link, margine 25 mm e campionamento del percorso
sequenziale del target Studio. Non verifica mesh complete, autocollisione, inerzie o tutte
le traiettorie delle pose insegnate. Non è una funzione di sicurezza certificata.

**Esporta progetto…** crea uno ZIP con URDF, mesh, configurazione, sensori dichiarati e
blocchi e sequenza delle pose. Non include conversazioni, credenziali o autorizzazioni hardware.
Importare sostituisce la sequenza locale dopo validazione; l’ultima modifica può essere annullata.
I blocchi posa la richiamano per indice: verifica i riferimenti dopo eliminazione o riordino.
Il profilo firmware non viene applicato automaticamente e i percorsi importati richiedono
verifica con il robot, il mapping e i limiti del banco di destinazione. I dati si trovano in `~/Library/Application Support/DOC Regia/`.

## Programmi e sensori

Aggiungi blocchi posa, pinza, attesa, sensore, ripeti o nota. Possono essere esclusi,
riordinati, eliminati o modificati con l'editor JSON. I cicli sono limitati e non annidati;
l'esecuzione parte da HOME, verifica i percorsi e rientra lungo i tratti registrati.
Un errore o STOP non riprende automaticamente. Una posa esclusa resta esclusa anche nei
programmi. L'anteprima a scorrimento mostra il percorso insegnato, inclusi i ritorni.

Definisci gli ingressi in Diagnostica. I valori simulati sono marcati e non soddisfano
attese di sensori sul robot reale. Gli adattatori esterni devono aggiornare il valore
almeno una volta al secondo. Non usare questa interfaccia come arresto di emergenza.
Encoder, prossimità, forze, temperature, telecamere e LiDAR richiedono hardware/adattatori
appropriati; questa versione non integra retroazione motore o percezione 3D completa.

Attiva **Registra sessione** per CSV di posizioni comandate, modalità, pinza e stato.
La finestra conserva fino a 18000 campioni; i grafici recenti non sono misure encoder.
La telecamera si avvia solo esplicitamente, richiede permesso macOS e può salvare un PNG
oppure leggere QR. I QR rimangono dati mostrati e non diventano comandi.

## ROS 2 e strumenti

Seleziona un progetto Pixi con ambiente già preparato. La console non installa ROS.
**Collega ROS 2** avvia un osservatore sul dominio scelto, con discovery solo locale.
Mostra heartbeat, nodi e freschezza dei quattro topic `/laboratorio/*`.
Pubblica `/doc_regia/stato`, `/robot_console/joint_states`,
`/robot_console/robot_description` e `/tf` con prefisso `robot_console/`.
Non riceve comandi hardware via ROS. In Anteprima pubblica dati virtuali; sul robot
pubblica stime dagli impulsi, non misure reali.

RViz apre il modello della console; Webots apre il laboratorio separato in pausa.
Gazebo apre **una scena di esempio**, non il gemello fisico del DOC. La registrazione
rosbag conserva i topic elencati nel codice. Si possono fermare solo i processi avviati
dall'app. Masse, inerzie, ros2_control, MoveIt, collisioni complete, AprilTag e pianificazione
coordinata rimangono sviluppi successivi: non vengono presentati come già disponibili.

## API locale opzionale

**Avvia API locale** crea una porta casuale su 127.0.0.1. Copia il token della sessione.
Ogni richiesta deve avere `Authorization: Bearer TOKEN`.

- `GET /v1/state`: stato, modello e sensori.
- `GET /v1/health`: disponibilità.
- `POST /v1/sensors`: `{"name":"contatto_pinza","value":1}` per un ingresso già definito.

Non esistono endpoint per movimento, USB o firmware. Il token non è salvato o incluso
nei progetti. `Ferma API` chiude il servizio.

## Distribuzione Apple

L'app locale è firmata ad hoc, non notarizzata. Identità e copyright dell'autore sono
nel bundle e nei sorgenti. Il flusso `native/notarize.command` è preparato ma richiede
un certificato Developer ID e un profilo Portachiavi dell'autore; non è stato eseguito.
Riferimento: [procedura Apple](https://developer.apple.com/documentation/security/customizing-the-notarization-workflow).
Python 3 e gli strumenti opzionali restano dipendenze esterne. Nessun servizio cloud è
necessario per le funzioni locali; Ollama usa un modello già presente sul Mac.

## Velocità per giunto, STOP e note locali

In **Muovi e osserva**, ogni scheda J1–J6 ha una velocità in °/s: usa lo slider
oppure scrivi il numero e premi Invio o ✓. Le velocità sono salvate su questo Mac
ed entrano in funzione al movimento successivo, anche nei programmi e nel ritorno
HOME. I singoli jog e i target Studio conservano il percorso sequenziale; la build 27 aggiunge gruppi simultanei espliciti. Il limite resta quello del
profilo, fino a 20°/s: non aumenta automaticamente la corrente del driver.
**Applica a tutti** sostituisce le sei velocità con il valore comune.

**STOP Jn** arresta gli impulsi del giunto indicato, se è quello attivo, conserva
la tenuta e interrompe la sequenza. Se quel giunto è già fermo, non arresta un
altro asse. Lo STOP globale/Esc rimane disponibile per interrompere il movimento
corrente. Dopo un arresto HOME deve essere ristabilita; nessuna ripresa automatica.
Nei gruppi simultanei STOP Jn arresta tutto il gruppo se Jn ne fa parte.
Sono comandi software, non un arresto di emergenza hardware certificato.

Togliere la spunta a un giunto lo esclude dai comandi e, con il nuovo firmware,
disattiva il suo ENABLE quando è collegato. Gli A4988 di J1, J3, J4 e J5 rilasciano
la corrente alle bobine: **sostieni un asse sotto carico prima di confermare**.
L'esclusione interrompe la sequenza e invalida HOME. La scheda del giunto mostra
la conferma ricevuta dal firmware, non una misura elettrica. Riattivare la spunta
prepara il giunto: la corrente viene riabilitata solo confermando HOME.

**J2/DM542 ha ENA scollegato nel cablaggio attuale.** L'esclusione ne impedisce i
movimenti, ma non interrompe la corrente e può rimanere la coppia di tenuta.
L'app lo indica esplicitamente. J6 non configurato non pilota alcun pin.

I firmware precedenti continuano a supportare movimento, velocità e STOP, ma
non possono gestire ENABLE per giunto. Senza hardware alimentato, scollega il
controllo e usa **Aggiorna comandi giunti…** nell'editor per preparare il nuovo
sorgente: salva una revisione e conserva il profilo, compresi microstep, riduzioni,
versi e pin. Il file principale viene sostituito; le modifiche manuali restano
nella revisione. La compilazione e il successivo caricamento sono azioni esplicite
dell'operatore. L'aggiornamento dell'app da solo non programma la Mega.

Il pulsante **Note** mostra/nasconde il pannello laterale, la cui larghezza è
regolabile trascinando il separatore. Gli appunti sono salvati automaticamente
nelle preferenze locali dell'app; non sono inclusi nei progetti esportati né
inviati all'assistente IA. Le prove della versione sono eseguite in anteprima,
con seriale simulata e compilazione del firmware, senza movimento fisico.

## Build 27: simultaneo e voce

Consulta [la guida dei movimenti simultanei e vocali](MULTI_VOICE.md).

## Build 29: spazio centrale e tema chiaro

I pannelli centrali seguono la larghezza disponibile quando apri, chiudi o ridimensioni
le barre laterali. I controlli vanno su più righe negli spazi stretti; nei moduli
avanzati molto larghi lo scorrimento resta locale al pannello. Le altezze manuali
non creano più vuoti quando il contenuto si riduce. Il tema chiaro usa lo stesso
verde acceso del tema scuro, bordi dei pulsanti interni e continui, testi secondari
più scuri e didascalie leggermente più grandi. Nessuna modifica al firmware o ai
parametri di movimento.

La griglia dei limiti occupa solo l’altezza del contenuto e distribuisce i sei canali
su una, due o tre righe secondo la larghezza. I selettori nativi (tema, modalità,
porta e predefiniti) usano testo scuro leggibile in modalità chiara.

## Build 30: conferma velocità dei giunti

Le velocità applicate mantengono due decimali e la conferma con Invio o ✓ aggiorna
sempre lo stato del campo, anche se il valore non cambia. I movimenti simultanei
successivi non richiedono di confermare nuovamente velocità già applicate. Una
modifica ancora non confermata continua a bloccare il gruppo. Nessuna modifica
al firmware, alle accelerazioni o al calcolo dei movimenti.
