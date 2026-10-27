# Movimenti simultanei e conferma vocale — Robot Console 2.0.1

## Uso

In **Muovi e osserva**, scegli **Simultaneo** e inserisci gli spostamenti relativi direttamente nelle schede J1–J6. Le caselle e gli slider della velocità sono gli stessi usati in modalità **Singolo**; **Applica a tutti** imposta un massimo comune. Premi Invio o ✓ per applicare una velocità digitata. Finché ci sono velocità modificate da confermare, il pulsante del gruppo resta bloccato. Il riepilogo mostra i picchi previsti per giunto e il tempo totale.
Per esempio J1 `10`, J2 `-5`, altri `0`. **Muovi insieme…** mostra il riepilogo.
Zero lascia fermo il giunto. Il firmware del robot deve annunciare `MULTI_AXIS_V1`;
il firmware precedente continua a funzionare per i movimenti singoli.

Ogni velocità individuale è un massimo: il gruppo usa un profilo normalizzato comune
con accelerazione, riducendo le velocità per rispettare ciascun asse e il budget
complessivo di 2000 impulsi/s. È un limite prudenziale di progetto, non una frequenza
misurata sul banco. La corrente rimane quella regolata sui driver; più motori in moto
richiedono di verificare anche alimentazione, dissipazione e carichi.

**Registra posa** conserva i gruppi appena eseguiti. Riproduzione, ritorno HOME e
programmi mantengono i gruppi. Le pose precedenti restano sequenziali: non vengono
convertite automaticamente in percorsi diversi. I target del pannello Studio
continuano a usare il percorso sequenziale esistente.

Lo STOP di qualsiasi membro del gruppo interrompe **tutto il gruppo** e invalida
HOME. I driver conservano la tenuta. J2/DM542 ha ancora ENA non collegato: non viene
promesso il rilascio della corrente. Nessuna coda di movimenti viene inviata alla Mega.

## Voce: comando, riepilogo, conferma

Apri **Comandi vocali del robot**, poi premi **Parla al robot** una volta.
La dettatura usa il riconoscimento locale Apple nella lingua dell’app, richiede i
permessi Microfono/Riconoscimento vocale e non coinvolge Ollama o la chat IA.

- «Muovi J2 di 45 gradi»: aggiunge 45° alla posizione comandata.
- «Muovi J3 di meno 20 gradi»: sottrae 20°.
- «Muovi J1 a 45 gradi, J2 a 30 e J3 a meno 10»: target assoluti, gruppo simultaneo.
- «Avvia posa 1»: raggiunge la prima posa conservando il percorso insegnato, compresa
  l’eventuale azione pinza e la pausa; resta sulla posa invece di avviare tutta la sequenza.

Dopo 1,5 secondi senza nuove parole l’app valida la frase e legge la domanda con
posizioni finali e spostamenti. **Aspetta che finisca di parlare**, poi di’
**«sì, confermo»** oppure **«annulla»**. In inglese: “move J2 by 45 degrees”,
“move J1 to 45 and J2 to 30”, “start pose 1”, “yes confirm” / “cancel”.
Numeri non riconosciuti o frasi ambigue vengono rifiutati: non vengono indovinati.

Il microfono di conferma si avvia solo dopo la sintesi vocale, con una nuova sessione.
Non viene usato il testo del riepilogo come conferma. Il consenso è monouso, scade
30 secondi dopo la preparazione e viene rifiutato se cambiano HOME, posizione,
modalità, limiti, velocità, maschera, revisione pose o identità firmware.
Un errore di trascrizione resta possibile: ascolta sempre tutto il riepilogo.

**Ascolta il prossimo comando a movimento concluso** permette di continuare a voce:
l’ascolto riparte solo a movimento terminato e con HOME ancora valida. Dopo STOP,
errore o annullamento non riparte. Venti secondi senza comando terminano l’ascolto.
Durante il moto usa **STOP/Esc**; la voce non è un arresto di emergenza.

## Firmware e ripristino

Scollega il controllo nell’app. In Firmware usa **Aggiorna comandi giunti…**:
salva una revisione completa, conserva rapporti, microstep e pin e sostituisce il
sorgente principale. Rivedi eventuali modifiche manuali prima di compilarlo.
**Verifica compilazione** e **Carica sulla Mega…** restano azioni esplicite separate.
Installare l’app non carica firmware né collega la scheda.

I gruppi aggiungono un identificatore agli elementi del percorso, senza alterare
angoli o pose esistenti. L’importazione/esportazione corrente lo conserva.
Le vecchie build non conoscono il significato dei gruppi: per tornare alla build 26
ripristina anche i dati precedenti, evitando di riprodurre con quella build le nuove
pose simultanee. Nessuna modifica automatica dei progetti salvati al semplice avvio.

## Verifiche e limiti

Test automatici: comando multiplo atomico; limiti; asse disabilitato e J6 assente;
budget e profilo normalizzato; ACK/DONE di gruppo; STOP; watchdog; percorso inverso;
serializzazione dei gruppi; grammatica italiana/inglese; conferma monouso, negativa,
scaduta e invalidata da modifiche; conservazione delle funzionalità precedenti.
Il test C++ esegue il vero parser firmware con GPIO e motori simulati. I tre profili
AVR compilano (standard, rapporti/microstep diversi, J6 esterno).

Da collaudare sul banco, solo per iniziativa dell’operatore: frequenza e jitter STEP,
scarto temporale tra assi, impulso minimo e setup DIR, STOP/watchdog sotto carico,
assenza di passi persi, traiettoria e carichi. AccelStepper viene servito in un loop
cooperativo: il profilo comune non prova una sincronizzazione fisica perfetta.
La visualizzazione mostra una stima del profilo, non encoder. Nessun controllo
collisioni completo su questi percorsi. La catena acustica microfono–voce–conferma
richiede una prova locale in Anteprima, compresi rumore, accento e permessi macOS.

## Conservazione delle versioni

Per gli aggiornamenti locali usa `zsh native/install_local.command` dopo la build,
con Robot Console chiusa. Rimangono la versione installata e la penultima in
`build/local-history/`; le precedenti vengono spostate nel Cestino dopo la verifica
della nuova app. I backup dei dati restano separati e non vengono eliminati.

## Build 28: regolazione omogenea delle velocità

Il preventivo legge direttamente le velocità applicate in Muovi e osserva, include
accelerazione e budget impulsi e non invia comandi al firmware. Modificare velocità
o stato dopo il riepilogo impedisce l’avvio finché non viene riesaminato. Anche i
gruppi richiesti a voce e le pose registrate usano la stessa regolazione dei giunti.
Il firmware MULTI_AXIS_V1 è invariato rispetto alla build 27.

## Disposizione delle barre laterali

**Eventi** mostra/nasconde a sinistra Attività del robot: fino a 300 eventi recenti
della sessione, con ora e modalità, scorrimento automatico disattivabile e comando
HOME/chiusura in basso. Il diario persistente esistente resta distinto da questa
finestra sulla sessione. **Note** apre gli appunti personali a destra. I separatori
regolano le larghezze; entrambe le barre si possono chiudere per liberare il centro.
Il menu Vista offre le stesse opzioni: ⌘B per gli eventi, ⌥⌘B per le note. Le scelte
restano salvate e nascondere una barra non ferma né modifica i movimenti.

## Vista 3D e HOME del modello

Il riquadro 3D occupa lo spazio accanto alla griglia dei giunti, con larghezza
flessibile e altezza pari ai controlli. In **HOME del modello…**, a controllo
scollegato, regola gli slider o i valori numerici e osserva la posa a zero comandato.
Puoi orbitare, cambiare vista e adattare l’inquadratura. Le prove nella finestra non
modificano il progetto: **Annulla** le scarta. **Salva HOME del modello** conserva
una copia del progetto precedente in `studio/home-revisions/`, applica gli offset
al modello e richiede una nuova verifica del mapping per i target fisici Studio.
Non invia comandi, non cambia firmware, HOME o angoli del controllore. È un
allineamento a vista, non una calibrazione misurata. Se il conteggio precedente non
era a zero, il modello mostra la nuova HOME come target virtuale; attiva Segui comandi
quando vuoi tornare a visualizzare il conteggio attuale.

Il modello DOC fornito contiene esattamente cinque giunti indipendenti, J1–J5.
I comandi mostrano i canali associati al modello; Canali aggiuntivi rende accessibile
J6 senza aggiungere geometria o un sesto grado di libertà al DOC. I marcatori 3D
identificano solo i giunti indipendenti, non flange fisse o dita della pinza.
