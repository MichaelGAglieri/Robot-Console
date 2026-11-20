# Collisioni e validazione del programma (fase 5, build 38)

## Geometria semplificata (`collision.py`)

Per ogni link con geometria visuale (mesh STL/OBJ, box, cilindri, sfere) l'app ricava
fino a **quattro capsule**: i vertici vengono divisi in fette lungo l'asse principale e
ogni fetta riceve una capsula con raggio pari al 95° percentile della distanza
dall'asse. Le fette evitano che gli alloggiamenti dei giunti gonfino l'intero link.
I link senza geometria mantengono il controllo precedente (segmento tra le origini dei
giunti, raggio 25 mm). Funziona per il DOC e per qualsiasi braccio importato da URDF.

Coppie escluse automaticamente: parti dello stesso corpo rigido, link collegati da un
giunto, dita della stessa pinza e coppie di link già entro 15 mm nella posa di
riferimento (vicine per costruzione: la loro interazione è affidata ai limiti dei
giunti).

## Controlli

- **Autocollisione** tra link, **ostacoli** (box dell'ambiente) e **piano di lavoro**
  z = 0 (tavolo, attivabile), con margine di sicurezza (predefinito 10 mm).
- Usati ovunque: anteprima, IK e jog, MoveJ e MoveL (campioni a 1°), target dello Studio.

Sul DOC, muovendo un giunto per volta dalla posa verticale: J2 arriva a circa ±89°
(braccio orizzontale vicino al tavolo), J3 a ±135° (pinza sul tavolo), J4 a ±100°
(pinza sull'avambraccio); J1 libero; J5 tocca il margine a circa ±132° per
l'approssimazione del corpo asimmetrico della pinza (risultato prudente).

## Validazione del programma (`validation.py`)

**Valida programma** e **Valida sequenza** simulano i percorsi insegnati come li esegue
il controllore: prefisso comune conservato, tratti a ritroso, tratti della posa
successiva e ritorno a HOME. Ogni unità (giunto singolo o gruppo simultaneo) è
campionata a 1° e controllata contro limiti applicati, limiti URDF calibrati e
collisioni. Il rapporto indica tappa, problema e angoli (un messaggio per tappa e tipo).

**Riproduci** ed **Esegui programma** fanno la stessa verifica prima di partire: in
Anteprima o con il modello dichiarato conforme al robot, un problema blocca l'avvio;
sul robot reale con modello non dichiarato conforme il problema viene registrato
negli eventi ma non blocca (il modello potrebbe non corrispondere al braccio).

## Limiti

Capsule e campionamento sono approssimazioni: parti sottili o asimmetriche possono
risultare più grandi (prudenza) o, in punti tra due campioni, sfuggire. Nessun test sul
braccio reale: le prove fisiche restano l'ultimo passo (il DOC non ha sensori).

## Revisione build 39: pinza e cicli

I blocchi pinza sono valutati nell’ordine effettivo del programma, inclusi programmi
di sola pinza; lo stato risultante è usato nei tratti e nel ritorno successivi.
L’avvio Ripeti controlla anche un secondo ciclo con lo stato finale del primo. Il
comando Valida sequenza separato controlla un ciclo. Le azioni servo verificano
la configurazione finale richiesta, non un volume continuo spazzato dalle dita.
