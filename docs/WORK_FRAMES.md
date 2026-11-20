# Riferimenti di lavoro e target — primo incremento

## Contratto

Il progetto Studio passa a `schema: 2`. Il robot, il TCP, il mapping, i programmi,
le pose articolari e la geometria EB-15/EBG-30 restano quelli già esistenti.

- `work_frames`: fino a 32 elementi `{id, name, parent: "base", xyz, rpy}`.
- `cartesian_targets`: fino a 256 elementi `{id, name, frame_id, xyz, rpy}`.
- `selected_target`: identificatore selezionato, oppure stringa vuota.
- `base` è un riferimento implicito immutabile: coincide con la radice URDF.
  Gli altri riferimenti sono tutti figli diretti della base; non ci sono cicli o
  gerarchie di riferimenti annidate in questo incremento.
- Coordinate persistite in **metri**, angoli in **radianti**. L'interfaccia usa mm
  e gradi. RPY sono rotazioni attorno agli assi fissi, `Rz(yaw) Ry(pitch) Rx(roll)`.
  `T_base_target = T_base_riferimento × T_riferimento_target`, riusando le funzioni
  di trasformazione URDF. Matrici e coordinate base sono derivate, mai affidate al JSON.
- ID stabili, nomi non vuoti e univoci per tipo. Eliminare un riferimento usato
  viene rifiutato: riassegnare o eliminare prima i suoi target. Cambiare riferimento
  a un target conserva i numeri locali inseriti e quindi può cambiare il punto base.

## Uso offline

In **Modello del braccio → Riferimenti di lavoro e target**, crea un riferimento
con posizione XYZ e rotazione RPY rispetto alla base, poi un target locale.
L'albero mostra base, riferimenti e target associati. Selezionare un target mostra
le sue coordinate nella base e lo evidenzia in 3D. La terna RGB rappresenta gli assi
X/Y/Z; un punto arancione è il target selezionato, gli altri sono ciano.

Esempio: riferimento `(100, 200, 0) mm`, yaw `90°`; target locale `(50, 0, 0) mm`.
Il target nella base è `(100, 250, 0) mm`. Traslare il riferimento aggiorna tutti
i target associati senza cambiarne le coordinate locali né muovere il robot.

Creazione, modifica ed eliminazione richiedono il controllo scollegato. Selezione
e visualizzazione non comandano alcun movimento. I target sono **metadati geometrici**:
questo incremento non aggiunge MoveJ, MoveL, esecuzione di target nominati o una nuova
IK. La loro orientazione viene conservata e visualizzata; l'IK esistente resta di
sola posizione. Nessuna nuova validazione di collisioni è attribuita a questi punti.

## Migrazione e conservazione

Progetti versione 1: riferimenti e target inizialmente vuoti, stessi TCP, calibrazione,
ostacoli, blocchi, giunti e preview. All'avvio, dopo una lettura valida, una copia
datata precede il salvataggio nel nuovo formato. Importare un archivio versione 1
lascia invariato il file originale e salva il progetto locale in versione 2.
Le autorizzazioni fisiche vengono sempre azzerate all'importazione, come prima.

Esportazione/importazione include i riferimenti e i target nel progetto ZIP corrente.
Una nuova importazione URDF azzera questi metadati legati alla base del modello;
l'aggiornamento automatico del modello DOC mantiene invece la scena esistente.
Le build precedenti a questa funzione non leggono progetti versione 2: per tornare
indietro utilizzare la copia dati della versione precedente.

Il nuovo modello contiene mesh ToolBox con licenza indicata CC BY-NC-ND: **nessuna
pubblicazione di questa build o delle mesh senza chiarimento e autorizzazione**.
Quote CAD e anteprima non sono calibrazione o collaudo fisico.
