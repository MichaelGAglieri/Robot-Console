# API Python e adattatori I/O — build43

L’API è locale, autenticata e facoltativa. Il client `robot_console_client.py` usa soltanto
la libreria standard di Python3. Non apre porte seriali e non configura il robot.
Il token dell’API e i permessi sono di sessione: non entrano nei progetti esportati.

## Abilitazione dall’app

In **Diagnostica e ROS2 → API Python · programmi e I/O**, premi **Avvia API locale**.
Copia l’indirizzo `http://127.0.0.1:PORTA` e il token. L’API parte con entrambi i permessi
spenti. Abilita **Consenti pianificazione dei programmi da API** per inviare programmi;
abilita anche **Consenti esecuzione da script in Anteprima** per eseguirli simulati.

Sul robot reale una richiesta di esecuzione crea sempre un banner nell’app: nome,
identificativo piano, durata stimata e rami verificati. Apri Studio, controlla il piano,
poi **Approva ed esegui** oppure **Rifiuta richiesta**. L’approvazione non è esposta su
HTTP e vale una volta sola, per quel piano, contesto, modalità e generazione STOP.
Scade dopo 60 s; la presenza dello script va mantenuta anche durante l’attesa.
Non sono presenti endpoint USB, firmware, HOME, limiti o movimento diretto dei giunti.
La HOME e le condizioni iniziali vanno predisposte dall’operatore nell’app.

## Client Python

```python
from robot_console_client import RobotConsole

robot = RobotConsole('http://127.0.0.1:PORTA', token)
blocks = [
    {'kind': 'movej', 'name': 'Punto A', 'to': 'joints',
     'angles': [5, 0, 0, 0, 0, 0], 'speed': 50},
    {'kind': 'wait', 'name': 'Attesa', 'seconds': 0.3},
    {'kind': 'movej', 'name': 'Rientro', 'to': 'home'},
]
plan = robot.plan(blocks, scenario={})
print(plan['duration'], plan['duration_min'], plan['duration_max'])
run = robot.execute(plan, name='Esempio Python')
result = robot.wait(run, timeout=120, progress=lambda s: print(s['status']))
```

L’esempio mostra il formato: gli angoli non sono una traiettoria fisica consigliata.
I blocchi sono quelli di Studio, descritti in `PROGRAMMI.md`. In aggiunta:

```json
{"kind":"output","name":"Segnale deposito","output":"lampada","output_value":true,"timeout":2}
```

Definisci prima `lampada` nella sezione Diagnostica. L’API non crea ingressi/uscite o target
automaticamente. `plan()` sostituisce le istruzioni del progetto attivo e le rende visibili
nel pannello. Non modifica modello, limiti, calibrazione o collegamento hardware.

`scenario` associa l’indice del blocco Se, come stringa, a `true`/`false`: sceglie solo il
ramo mostrato in anteprima. Tutti i rami sono verificati; durante l’esecuzione decide il
sensore attuale. La risposta contiene tappe, albero dei rami, campioni per la vista,
`id`, `context` e `fingerprint`. L’esecuzione richiede l’id e l’impronta del piano letto;
non rigenera un percorso nascosto. Le tappe passano da `Studio.validate_blocks`,
`MoveJPreview.prepare(source='program')` e `MoveJPreview.execute`, come il pannello.
Le righe firmware `~multi`, compresi profili di velocità e ordine, sono le stesse.

`duration` è la stima del ramo visualizzato, escludendo le attese sensore/uscita.
`duration_min` e `duration_max` sono i limiti temporali sull’albero, con i timeout I/O nel
massimo. Pause passo passo, latenza e risposte reali non sono deterministiche; il massimo
non è una garanzia temporale del robot. Una conferma I/O può arrivare subito.

## Stato, annullamento e passo passo

`execute()` restituisce un id di esecuzione distinto da quello del piano:
`awaiting_operator`, `running`, poi `completed`, `stopped`, `failed`, `rejected` o `expired`.
`run()` legge stato e avanzamento: blocco attivo, tratto, decisioni sensore, durate misurate. `measured_seconds` somma le durate delle tappe confrontabili (escluse attese sensore e pause dell’operatore), come il pannello; non è il tempo totale a muro di un programma con sensori.
Il risultato finale rimane associato al suo programma anche se la GUI pianifica altro.

`wait()` invia heartbeat ogni 0,2 s. Se lo script sparisce per 3 s, la console chiede STOP
senza ripresa automatica. `wait()` richiede STOP anche al timeout o con Ctrl-C.
Per un proprio ciclo di controllo chiama `heartbeat(run)` almeno ogni secondo.
Con `execute(plan, step=True)`, usa `step(run)` o `continue_program(run)` mantenendo
l’heartbeat. `stop()` funziona anche con il permesso programmi revocato, finché l’API
è avviata. Anche STOP nell’app interrompe lo stesso esecutore. Ferma API o revoca dei
permessi arresta il programma avviato dall’API; non riavvia niente automaticamente.

STOP è software: interrompere gli impulsi non dimostra rilascio della coppia o arresto
meccanico certificato. Lo script non mantiene l’heartbeat dell’interfaccia macOS: i due
controlli restano separati.

## Contratto degli adattatori

1. Definisci nell’app i nomi degli ingressi e delle uscite (massimo 64 per categoria).
2. Registra una sessione con nome, liste `inputs`/`outputs` e `simulated` esplicito
   (predefinito `true`). Un nome I/O ha un solo proprietario attivo.
3. La risposta contiene `id` e `adapter_token` segreto. Il token API comune autentica
   il servizio; il token adattatore identifica il proprietario di letture e conferme.
4. Invia heartbeat con intervallo inferiore a1s (il client lo fa ogni 0,2 s).
   Dopo1s la sessione scade e non si riattiva: registrane una nuova.
5. Le letture hanno timestamp assegnato dalla console. I dati di adattatore scadono
   dopo 1 s anche in Anteprima. Sul robot reale sono accettati solo campioni dichiarati
   non simulati, con campione e heartbeat entrambi recenti.

```python
from robot_console_client import Adapter

with Adapter(robot, 'Sensore esterno', inputs=['presente'], simulated=False) as io:
    # Integra qui la lettura del dispositivo reale:
    valore = leggi_dispositivo()
    io.publish('presente', valore)
```

`simulated=False` è una dichiarazione dell’adattatore, non un’attestazione hardware della
console. Non usarla per dati generati. `POST /v1/sensors` senza sessione rimane compatibile,
ma i suoi valori sono sempre marcati simulati e non valgono sul robot reale.
I pulsanti Simula dell’app mantengono il loro valore in Anteprima. Dati di sessione,
lease, richieste e valori delle uscite non sono persistiti; si salvano solo le definizioni.

### Uscite con conferma

In Anteprima l’istruzione imposta soltanto uno stato simulato locale. Sul robot la console
pubblica una richiesta con id univoco, nome, valore, proprietario e timeout. L’adattatore
la legge con `requests()`, applica l’uscita al proprio dispositivo e solo dopo risponde
con `acknowledge(request, actual_value, success=True)`.

```python
with Adapter(robot, 'I/O esterno', outputs=['lampada'], simulated=False) as io:
    while True:
        for richiesta in io.requests():
            applica_uscita_reale(richiesta['name'], richiesta['value'])
            confermato = leggi_stato_uscita()
            io.acknowledge(richiesta, confermato)
        # Il thread interno mantiene l’heartbeat; prevedi pausa e uscita nel tuo adattatore.
```

Le funzioni del dispositivo sono intenzionalmente lasciate all’integratore. La console
non modifica pin della Mega. Una conferma falsa, valore diverso, sessione sbagliata,
heartbeat perso o timeout interrompe il programma. Gli ACK sono monouso; dopo STOP o
scadenza non fanno proseguire il programma. Una condizione con dato inutilizzabile si
interrompe subito; un’attesa sensore continua fino al proprio timeout, senza considerare
il vecchio dato valido. La perdita dell’adattatore durante un’attesa uscita la interrompe.

L’adattatore deve rifiutare richieste scadute, verificare i propri interblocchi e gestire
il valore dell’uscita alla perdita di collegamento. Un comando già applicato fuori dal
Mac non può essere annullato retroattivamente da STOP; non sono implementati reset
fisico delle uscite o un circuito di sicurezza. Gli I/O non sono indicati per attuazioni
pericolose senza una progettazione hardware separata.

## Endpoint

Ogni richiesta: `Authorization: Bearer TOKEN`. Corpo JSON oggetto, massimo 256 KiB;
Host locale corretto; niente CORS o richieste con Origin. Client senza proxy o redirect.

| Metodo | Percorso | Uso |
|---|---|---|
| GET | `/v1/health`, `/v1/state` | disponibilità, permessi, stato |
| POST | `/v1/program/plan` | `blocks`, `scenario` → stesso piano di Studio |
| GET | `/v1/plan` | piano completo e rami verificati |
| POST | `/v1/program/execute` | `id` piano, `fingerprint`, `name`, `step` |
| GET | `/v1/runs/ID` | esito e avanzamento |
| POST | `/v1/program/heartbeat` | `id` esecuzione |
| POST | `/v1/program/step`, `/v1/program/continue` | `id` esecuzione |
| POST | `/v1/stop` | STOP condiviso, corpo `{}` |
| GET | `/v1/io` | definizioni, valori, adattatori, richieste recenti |
| POST | `/v1/adapters` | registra sessione (`name`, `inputs`, `outputs`, `simulated`) |
| POST | `/v1/adapters/ID/heartbeat`, `/disconnect` | `adapter_token` |
| POST | `/v1/sensors` | `name`, `value`, `adapter_id`, `adapter_token` |
| GET | `/v1/adapters/ID/requests` | header `X-Adapter-Token` oltre al Bearer |
| POST | `/v1/io/ack` | `request_id`, `adapter_id`, `adapter_token`, `value`, `success` |

403 non viene recuperato automaticamente; richiesta errata o piano scaduto restituisce
400 con `error` e, se presente, `problem` localizzato al blocco. Endpoint assente:404.
Esecuzione accettata/attesa operatore:202. Rileggi l’errore prima di ripianificare;
nessun retry automatico di esecuzioni o ACK.

## Esempi e verifica

`examples/python_pick_and_place.py` usa i target già presenti `Pezzo` e `Deposito` e
costruisce lo stesso compito del pannello: sopra il pezzo, discesa, presa, risalita,
deposito, rilascio e HOME. Senza `--execute` pianifica soltanto. `--output lampada`
aggiunge il segnale finale, se definito. Il token è letto da `ROBOT_CONSOLE_TOKEN` o con
prompt nascosto, evitando la cronologia dei comandi.

```sh
PYTHONPATH=. python3 examples/python_pick_and_place.py --url http://127.0.0.1:PORTA
PYTHONPATH=. python3 examples/python_pick_and_place.py --url http://127.0.0.1:PORTA --execute
```

`examples/python_simulated_sensor.py` pubblica un ingresso esplicitamente simulato.
Non costituisce un driver hardware. I test confrontano piani GUI/API e ogni riga `~multi`
con una Mega simulata; coprono permessi, conferma, STOP, rami, freschezza, lease e ACK.
Nessun collaudo sul braccio, sensore reale o uscita fisica è stato eseguito in questa fase.
