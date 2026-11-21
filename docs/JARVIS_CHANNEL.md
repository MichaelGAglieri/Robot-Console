# Canale locale JARVIS — 9 novembre 2026

Integrazione separata dall’API HTTP Python: `jarvis_channel.py`, avviata e chiusa
con il bridge nativo. Socket Unix privato in `DOC Regia/jarvis/control.sock`.

Comandi ammessi: stato, abilitazione USB/HOME su richiesta, jog relativo/assoluto,
sequenza singola delle pose abilitate, STOP, STOP ed esci. Nessun upload firmware,
comando shell o modifica limiti. Usa il controller e le verifiche esistenti.
La HOME resta una dichiarazione dell’operatore e abilita la tenuta dei motori.

Il canale serve processi dello stesso utente locale: cartella 0700, socket 0600,
sessione, scadenza, identificativi monouso ed epoca STOP. Nessuna porta TCP.
L’API pubblica `local_api.py` mantiene il proprio contratto originale.

Il lato client (assistente vocale AL-76, ex JARVIS) è mantenuto nel repository
[AL-76_ex-JARVIS](https://github.com/MichaelGAglieri/AL-76_ex-JARVIS).
Per scegliere una porta fra più schede collegate si può impostare la variabile
d'ambiente `ROBOT_CONSOLE_PORT`.

Test specifici: `test_jarvis_channel.py`. Eseguirli con dati temporanei e
`DOC_REGIA_NO_HARDWARE=1`. Nessun test effettuato sul robot fisico.
