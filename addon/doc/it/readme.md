# NVDA Unmute

* Authore: Oleksandr Gryshchenko
* Versione: 1.3
* [versione stabile][1]
* [versione in sviluppo][2]

Questo componente aggiuntivo controlla lo stato del sistema audio di Windows all'avvio di NVDA. Se l'audio dovesse essere disattivato, il componente aggiuntivo lo attiva forzatamente.

Il componente aggiuntivo controlla anche lo stato del sintetizzatore vocale. In caso di problemi con la sua inizializzazione, si tenta di avviare il sintetizzatore, specificato nelle impostazioni di NVDA.

Una caratteristica aggiuntiva è la possibilità di regolare il volume del dispositivo audio principale e di ogni singola applicazione.

## impostazioni del componente aggiuntivo

Le seguenti opzioni sono disponibili nella finestra di dialogo delle impostazioni del componente aggiuntivo:

1. Il primo cursore d'avanzamento nella finestra di dialogo delle impostazioni del componente aggiuntivo consente di specificare il livello del volume di Windows, che verrà eseguito all'avvio di NVDA Se il suono era precedentemente disattivato o era troppo basso.
2. Aumenta il volume se è  inferiore a: questo cursore d'avanzamento consente di regolare il livello di sensibilità del componente aggiuntivo. Se il livello del volume scende al di sotto del valore specificato, il volume verrà aumentato al successivo avvio di NVDA. In caso contrario, se il livello del volume è superiore al valore specificato, al riavvio di NVDA, il suo livello non cambierà. Naturalmente, se il volume è stato precedentemente disattivato, al riavvio il componente aggiuntivo lo attiverà comunque.
3. La successiva casella di controllo consente di abilitare la reinizializzazione del driver del sintetizzatore vocale. Questa procedura verrà avviata solo se all'avvio di NVDA viene rilevato che il driver del sintetizzatore vocale non è stato inizializzato.
4. In questo campo è possibile specificare il numero di tentativi per reinizializzare il driver del sintetizzatore vocale. I tentativi vengono eseguiti ciclicamente con un intervallo di 1 secondo. Il valore 0 significa che i tentativi verranno eseguiti  fino a quando l'operazione non sarà completata con successo.
5. La casella di controllo successiva attiva o disattiva la riproduzione del suono di avvio quando l'operazione è riuscita.

## Regola il volume

Questo componente aggiuntivo consente di regolare il volume del dispositivo audio principale di Windows e per ogni programma attualmente in esecuzione.

Per fare questo utilizza le scorciatoie da tastiera NVDA + Windows + tasti freccia.

Utilizzare le frecce sinistra e destra per selezionare un dispositivo o un'applicazione. Quindi utilizzare le frecce su e giù per regolare il livello del volume della sorgente audio selezionata.

Se si riduce il volume a zero per un determinato programma e si preme nuovamente la freccia in basso, questa sorgente sonora verrà disattivata.

> Nota: l'elenco delle sorgenti audio cambia dinamicamente e dipende dai programmi attualmente in esecuzione.

## Change log

### Version 1.3
* added the ability to control the volume of the main audio device and separately for each running program;
* updated translation into Vietnamese (thanks to Dang Manh Cuong);
* updated Ukrainian translation;
* updated ReadMe.

### Version 1.2
* switched to using the **Core Audio Windows API** instead of **Windows Sound Manager**;
* added startup sound playback when audio is successfully turned on by add-on.

### Version 1.1
* added add-on settings dialog;
* updated Ukrainian translation.

### Version 1.0.1
* Performs repeated attempts to enabling the synth driver in case of its failed initialization;
* Vietnamese translation added by Dang Manh Cuong;
* Ukrainian translation added.

### Version 1.0. Features of implementation
The add-on uses a third-party module Windows Sound Manager.

## Altering NVDA Unmute
You may clone this repo to make alteration to NVDA Unmute.

### Third Party dependencies
These can be installed with pip:
- markdown
- scons
- python-gettext

### To package the add-on for distribution:
1. Open a command line, change to the root of this repo
2. Run the **scons** command. The created add-on, if there were no errors, is placed in the current directory.

[1]: 
[2]: 
