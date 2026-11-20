# IK a cinque assi e jog cartesiano — primo incremento, solo anteprima

Fase 3 della roadmap. Il pannello **IK e jog cartesiano · anteprima** dello Studio
calcola gli angoli dei giunti da un punto o da un piccolo spostamento della punta.
Cambia soltanto il modello virtuale: nessun comando ai motori, nessun firmware e
nessun nuovo percorso di esecuzione. Per muovere il braccio resta il comando
esistente **Esegui target visualizzato…**, con conferma e verifica del mapping.

## Convenzioni

- Coordinate in metri nella base del robot (in mm nell'interfaccia). Gli angoli dei
  giunti sono quelli del controllore; l'angolo URDF è `q·segno + offset` della
  calibrazione dello Studio.
- Utensile: link e offset TCP configurati nello Studio. Asse **Z** della pinza =
  direzione uscente dalla flangia; asse **X** = riferimento per la rotazione della pinza.
- Nei target salvati la stessa convenzione vale per gli assi del target: roll 180°
  indica una presa dall'alto.

## Calcolo

`ik5.py` (geometria pura) costruisce la catena dalla base al link utensile, con
giunti mimic, giunti esclusi e limiti convertiti nelle coordinate del controllore.
Lo Jacobiano è analitico. Il risolutore usa priorità con proiezione nel nullo:

1. posizione del TCP;
2. asse della pinza (2 gradi di libertà);
3. rotazione attorno all'asse.

Uno smorzamento rende stabile il passo vicino alle singolarità; il proiettore resta
esatto, così un orientamento impossibile non sposta la posizione. Se serve, un
passaggio finale corregge soltanto la posizione. Il calcolo itera fino a 1 µm e
accetta la soluzione sotto 0,1 mm.

**Configurazioni.** L'IK parte dalla posa attuale e da otto pose iniziali (base verso
il punto o rovesciata, gomito ±). Tiene le soluzioni distinte che raggiungono la
posizione con l'orientamento migliore disponibile e sceglie la più vicina alla posa
attuale; le altre sono selezionabili con **Usa**. Le etichette indicano se il braccio
è in avanti o all'indietro rispetto a J1 e il segno del terzo giunto (gomito).

**Irraggiungibile.** Nessuna anteprima applicata. Motivo: fuori portata (distanza dal
secondo giunto oltre la somma dei segmenti fino al TCP, circa 601 mm sul DOC), limiti
dei giunti, giunti esclusi, oppure nessuna soluzione con la distanza minima trovata.

**Singolarità.** Avviso quando il minimo valore singolare dello Jacobiano di posizione
scende sotto 0,02 m/rad, per esempio a braccio verticale.

## Jog

Un passo parte sempre dalla posa attuale (continuità). Traslazioni fino a 50 mm e
rotazioni fino a 30° attorno alla punta, nella base, in un riferimento di lavoro o
nell'utensile. Il passo è rifiutato se la posizione non si raggiunge, se un giunto
dovrebbe ruotare più di 15° (o del doppio della rotazione richiesta) oppure se una
rotazione richiesta lascia uno scarto superiore a 0,5°. In traslazione con direzione
mantenuta lo scarto viene mostrato ma il passo è applicato.

## Limiti del DOC a cinque assi

J1 orienta il piano del braccio, J2–J4 lavorano nel piano, J5 ruota la pinza sul
proprio asse. La pinza può inclinarsi solo nel piano del braccio: una posa a sei
componenti arbitraria in generale non è realizzabile e la console lo dichiara.

## Verifiche

`test_ik5.py`: FK confrontata con l'URDF e con le quote EB-15 indipendenti (le stesse
del laboratorio Webots), Jacobiano contro differenze finite, andata e ritorno con
calibrazione, configurazioni e continuità, portata/limiti/giunti esclusi, direzione
laterale impossibile, jog esatto e rifiuti, integrazione Studio senza alcuna chiamata
al controllore. Le quote vengono dal CAD, non da misure del braccio montato.

## Non incluso

MoveL, esecuzione fisica dei passi di jog, collisioni sulle mesh, gamepad, catalogo
di utensili. La calibrazione misurata resta una verifica separata.
