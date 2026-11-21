# MoveL — retta del TCP (fase 4, build 36)

MoveL porta la punta in linea retta dalla posizione **comandata** a un punto nella base
o in un riferimento di lavoro. Non introduce un nuovo esecutore: produce un normale
piano MoveJ (sorgente `movel`) con anteprima, campionamento degli ostacoli, conferma,
STOP e ritorno a HOME come gli altri piani.

## Calcolo (`movel.py`)

1. La retta è campionata ogni 1 mm (massimo 2 m). Ogni punto è risolto con l'IK a
   priorità di `ik5.py`, partendo dalla soluzione del punto precedente: la soluzione
   resta sullo stesso ramo. Con «Mantieni» l'asse e la rotazione della pinza restano
   quelli iniziali quando i cinque assi lo permettono; lo scarto massimo viene riportato.
2. Limiti: URDF calibrati **e** limiti applicati al controllore. Un punto non risolto
   (sopra 0,1 mm) ferma il piano con la distanza dall'inizio e il motivo; un salto
   superiore a 6° per millimetro indica singolarità o cambio di configurazione.
3. I punti vengono uniti in tratti: per ogni tratto si cerca il punto più lontano
   (raddoppio e bisezione) tale che il moto **eseguito dal backend** — interpolazione
   lineare dei giunti tra angoli arrotondati a 0,01°, campionata ogni 0,25° — resti
   entro la tolleranza dalla retta. Massimo 64 tratti.
4. Risultato: punti di passaggio, deviazione massima, errore all'arrivo, scarti di
   orientamento, avviso di singolarità.

Esempi sul modello DOC con la pinza verso il basso: 100 mm in 5 tratti (tolleranza
0,5 mm), 8 tratti a 0,1 mm, 3 tratti a 2 mm; arrivo entro 0,02 mm; calcolo in circa 0,1 s.

## Tempi e capacità della Mega

Ogni tratto è un `~multi` con accelerazione e frenata proprie e attesa del DONE: il
braccio si ferma brevemente tra i tratti (nessun movimento continuo multi-tratto nel
firmware attuale). La durata stimata somma i profili dei gruppi; l'esecutore misura la
durata reale di ogni tratto (`exec_measured`, mostrata nel pannello), che sul robot
include ACK/DONE e latenza USB. Le prime prove sul braccio serviranno a misurare questo
margine; un movimento continuo richiederebbe un firmware con coda di tratti.

## Limiti

La deviazione è verificata sui campioni del modello CAD, non misurata sul braccio,
e non costituisce un limite continuo matematico fra i campioni. Le collisioni
usano le capsule e le esclusioni documentate in `COLLISIONI.md`. Nessuna orientazione a sei
componenti arbitraria: con cinque assi la pinza si inclina solo nel piano del braccio.

## Verifiche

`test_movel.py`: deviazione ricontrollata in modo indipendente ricampionando i tratti
a 0,05°, effetto della tolleranza, tratto irraggiungibile localizzato (portata e limiti),
scarto di orientamento con 5 assi, piano MoveL in un riferimento di lavoro con limiti
del controllore e requisiti sul robot reale, esecuzione con il protocollo Mega simulato
(un `~multi` per tratto, arrivo sulla retta, tempi misurati).

## Revisione build 39

Anche il tratto minimo deve rispettare la tolleranza dopo la quantizzazione a 0,01°.
Se non è rappresentabile il piano viene rifiutato con distanza e tolleranza; non viene
accettato un segmento fuori soglia. La verifica include l’inizio del segmento e
conserva il passo massimo di 0,25° anche per ampie rotazioni.
