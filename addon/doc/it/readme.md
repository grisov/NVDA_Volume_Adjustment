# NVDA Volume Adjustment

* Autore: Oleksandr Gryshchenko
* Versione: 1.3
* Compatibilitа con  NVDA: 2019.3 o successive
* Download [versione stabile][1]

Regola il livello del volume di tutti i dispositivi audio installati nel sistema e di ciascun programma in esecuzione separatamente utilizzando semplici scorciatoie da tastiera.
Puoi sempre modificare le scorciatoie da tastiera predefinite con quelle che preferisci tramite la finestra di dialogo Gesti di immissione di NVDA.

## Caratteristiche
* regolare il livello del volume di tutti i dispositivi audio nel sistema;
* controllo del volume per ogni programma in esecuzione separatamente;
* la possibilitа di regolare il volume di ciascun canale del dispositivo audio selezionato o impostare il valore medio per tutti i canali;
* passare rapidamente al livello di volume massimo o minimo di qualsiasi sorgente audio o del canale selezionato;
* due modalitа di muting della sorgente sonora: spegnimento completo o diminuzione del volume in percentuale;
* la possibilitа di ripristinare il livello del volume di tutte le sorgenti audio disattivate disponibili allo spegnimento di NVDA;
* impostazioni flessibili per l'annuncio dell'elenco dei dispositivi audio rilevati e dei programmi in esecuzione;
* passaggio automatico al programma in primo piano;
* la possibilitа di impostare un passaggio di modifica del volume personalizzato;
* commutazione rapida dell'uscita su altri dispositivi audio disponibili.

## Passa da una sorgente audio all'altra
Per passare alla sorgente audio precedente o successiva puoi utilizzare le combinazioni di tasti freccia sinistra o destra+NVDA+Windows+. L'elenco и composto da due parti: dispositivi audio di sistema e sessioni audio in esecuzione. La commutazione avviene ciclicamente  come per le  impostazioni di NVDA.
Dalle impostazioni del componente aggiuntivo puoi nascondere qualsiasi elemento in questo elenco.
Il passaggio tra le sessioni audio puт avvenire automaticamente quando si passa alla finestra del programma corrispondente: questa modalitа puт essere abilitata nel pannello delle impostazioni del componente aggiuntivo.

Nota: l'elenco delle sessioni audio cambia dinamicamente e dipende dai programmi in esecuzione.

## Regola il livello del volume
Una volta selezionata la sorgente sonora, и possibile modificarne il livello del volume utilizzando i seguenti comandi:

* aumentare il volume - NVDA+Windows+Freccia su;
* diminuire il volume - NVDA+Windows+Freccia giщ;
* impostare il livello massimo del volume - NVDA+Windows+Home (attenzione, questa azione puт danneggiare l'udito);
* impostare il livello minimo del volume - NVDA+Windows+Fine;
* disattiva la sorgente audio - NVDA+Windows+Freccia giщ (quando и giа impostato il livello minimo del volume);
* disattivare il volume o ripristinare il volume della sorgente audio precedentemente silenziata - NVDA+Windows+Escape, la modalitа mute puт essere selezionata nel pannello delle impostazioni del componente aggiuntivo.

Nota: per impostazione predefinita, il volume cambia dell'uno percento per ogni pressione di un tasto. Questo valore puт essere modificato dalle  impostazioni di NVDA nell'intervallo da 1 a 20.

## Regola il volume del canale selezionato
Per la sorgente sonora selezionata и inoltre disponibile la regolazione del volume dei suoi singoli canali:

* passare tra tutti i canali disponibili della sorgente audio selezionata - NVDA+Shift+Windows+ freccia destra o sinistra;
* aumentare o diminuire il livello del volume del canale selezionato - NVDA+Shift+Windows+ frecce su o giщ;
* imposta il livello di volume massimo o minimo del canale selezionato - NVDA+Maiusc+Windows+ Home o Fine;
* imposta il livello del volume medio per tutti i canali: NVDA+Shift+Windows+Escape.

Nota: il controllo del volume del canale и attualmente disponibile solo per i dispositivi audio.

## Passaggio rapido tra dispositivi di uscita audio
Per commutare l'uscita di tutti i suoni NVDA sul successivo dispositivo audio disponibile, premi semplicemente NVDA+Windows+PaginaSu.
E per tornare al dispositivo audio precedente, usa NVDA+Windows+PageDown.
Inoltre, per commutare rapidamente l'uscita audio di NVDA sul dispositivo audio selezionato, puoi utilizzare i tasti funzione NVDA+Windows+ da F1, F2, F3 ed eccetera...

Nota: le funzioni di commutazione separate vengono create per tutti i dispositivi audio in uscita rilevati nel sistema. Tutte queste funzionalitа sono visualizzate nella finestra di dialogo "Gesti di immissione", in cui и possibile assegnare comandi di attivazione a ciascuno dei dispositivi rilevati.

## Impostazioni del componente aggiuntivo
Le seguenti opzioni consentono di regolare in modo flessibile il comportamento del componente aggiuntivo e l'elenco delle risorse audio per passare da uno all'altro.

### Annuncia lo stato della sorgente sonora durante la commutazione
Se questa casella di controllo и selezionata, durante il passaggio tra le sorgenti audio o tra i canali, verrа annunciato il loro stato attuale, ovvero il livello del volume o l'indicatore di silenziamento.

### Passaggio per modificare il livello del volume
Il valore minimo a cui verrа modificato il livello del volume premendo un tasto. И possibile impostare un valore da 1 a 20 punti.

### Modifica il volume dell'applicazione corrente
Se questa casella di controllo и selezionata, il componente aggiuntivo passerа automaticamente alla sessione audio che corrisponde al programma in primo piano.
Ad esempio, se stai attualmente navigando in un sito Web in Firefox, il componente aggiuntivo lo rileverа. Passerа automaticamente alla sessione audio di Firefox e puoi regolare immediatamente il livello del volume per il processo corrente senza trovarlo nell'elenco.

### Nascondi sessioni audio con gli stessi nomi
A volte, quando vengono eseguiti alcuni programmi, vengono aperte piщ sessioni audio con gli stessi nomi. Questa opzione consente di nascondere tali sessioni audio.

### Nascondi processi
In questo elenco di caselle di controllo и possibile contrassegnare i processi che si desidera nascondere dall'elenco principale. Questi possono essere, ad esempio, programmi di servizio.
Il pulsante "Aggiorna" viene utilizzato per aggiornare l'elenco di tutti i processi in esecuzione e le sessioni audio disponibili. Tutti gli elementi selezionati rimangono contrassegnati.
Pulsante "Azzera": deseleziona tutti gli elementi selezionati e rimuove gli elementi obsoleti.

### Controlla tutti i dispositivi audio disponibili
Abilita le funzionalitа avanzate dell'add-on, ovvero la possibilitа di regolare il volume in input di tutti i dispositivi audio rilevati nel sistema.
Per ragioni sconosciute, questa funzione causa errori su alcuni sistemi, quindi и contrassegnata come sperimentale.

### Nascondi dispositivi audio
Se non utilizzi uno o piщ dispositivi audio e non vuoi che siano presenti quando passi da una sorgente audio all'altra, puoi rimuoverli facilmente dall'elenco principale semplicemente selezionandoli nel pannello delle impostazioni.
Il pulsante "Aggiorna" viene utilizzato per eseguire la scansione di tutti i dispositivi audio sul sistema e visualizzare le informazioni aggiornate. Tutti gli elementi selezionati rimangono contrassegnati.
Pulsante "Azzera": deseleziona tutti gli elementi selezionati e rimuove gli elementi obsoleti.

### Disattiva il volume
La funzione di disattivazione del volume puт funzionare in due modalitа:

1. Spegnere completamente la sorgente audio. Per abilitare questa modalitа, и necessario selezionare l'opzione appropriata nell'elenco di selezione della modalitа di muting.
2. Diminuire il livello del volume del valore percentuale che puт essere regolato con il dispositivo di scorrimento nel pannello delle impostazioni del componente aggiuntivo.

Nota: и possibile ripristinare il livello del volume per tutte le sorgenti audio disattivate disponibili allo spegnimento di NVDA. Poichй l'elenco delle sessioni audio cambia in modo dinamico, il volume verrа ripristinato solo per i programmi attualmente disponibili che riproducono l'audio.

### Utilizzo delle scorciatoie da tastiera predefinite
Se non prevedi di utilizzare tutte le funzionalitа del componente aggiuntivo. Nel pannello delle impostazioni, puoi disabilitare le combinazioni di tasti predefinite per tutte le funzioni disponibili. Quindi puoi assegnare le tue scorciatoie da tastiera attraverso la finestra di dialogo "Gesti di immissione..." standard di NVDA solo per quelle funzioni che ti interessano.

## Contributi
Siamo molto grati a tutti coloro che hanno compiuto lo sforzo di sviluppare, tradurre e mantenere questo componente aggiuntivo:

* Dang Manh Cuong - traduzione vietnamita;
* Cagri Dogan - traduzione in turco e test di pre-release;
* Christianlm - traduzione italiana;
* Cary Rowen - traduzione cinese semplificata, molte buone idee e test di pre-release;
* Stefan Banita - traduzione polacca;
* Wafiqtaher - traduzione araba.

## Problemi conosciuti
In alcuni sistemi, la funzione di scansione di tutti i dispositivi audio disponibili causa errori per motivi sconosciuti. Questo и un problema noto con il modulo PyCaw di terze parti che non и stato ancora risolto.

## Change log

### Versione 1.3
* aggiunto un insieme di funzioni per controllare il livello del volume di ogni canale dei dispositivi audio;
* aggiunta la possibilitа di informare sullo stato della sorgente sonora o del canale quando si passa da uno all'altro;
* nella finestra di dialogo "Gesti di immissione" viene visualizzata una funzione di commutazione separata per ciascun dispositivo audio di uscita rilevato nel sistema;
* Aggiunta funzionalitа per disattivare completamente o parzialmente temporaneamente la sorgente audio selezionata;
* aggiunta la possibilitа di ripristinare il livello del volume per tutte le sorgenti audio disattivate disponibili allo spegnimento di NVDA;
* i parametri mute sono stati aggiunti al pannello delle impostazioni;
* aggiunto un avviso su possibili danni all'udito quando si utilizza la funzione per impostare il livello massimo del volume;
* il codice sorgente и notevolmente ottimizzato e ha aggiunto suggerimenti di tipo MyPy;
* l'add-on и adattato per supportare le versioni Python 3.7 e 3.8;
* modulo di terze parti aggiornato ** psutil **;
* traduzioni aggiornate in cinese e ucraino.

### Versione 1.2
* Aggiunte scorciatoie da tastiera separate per passare rapidamente al dispositivo di uscita audio selezionato;
* aggiunta la possibilitа di disabilitare i gesti utilizzati nell'add-on per impostazione predefinita.

### Versione 1.1
* corretto bug di duplicazione delle sessioni audio per un processo in esecuzione;
* risolto il metodo di rilevamento della sessione audio corrente;
* migliorato il metodo per determinare il nome del processo corrente;
* sovrascrivere il dispositivo di output predefinito in un altro modo se il primo tentativo non и andato a buon fine;
* pannello delle impostazioni dei componenti aggiuntivi migliorato;
* Aggiunta la possibilitа di cambiare rapidamente l'uscita su un altro dispositivo audio disponibile.

### Versione 1.0: caratteristiche di implementazione
* questo add-on si basa sulle funzionalitа avanzate dell'add-on NVDA Unmute, che sono state rimosse dall'add-on originale a causa dell'incoerenza con il suo compito principale;
* aggiunta la possibilitа di regolare il livello del volume di tutti i dispositivi audio rilevati nel sistema;
* Aggiunte scorciatoie da tastiera per impostare rapidamente i livelli di volume massimo e minimo per la sorgente audio selezionata;
* Aggiunto pannello delle impostazioni del componente aggiuntivo.

## Alterazione del codice sorgente del componente aggiuntivo
Puoi clonare questo repository per apportare modifiche a NVDA Volume Adjustment.

### Dipendenze di terze parti
Questi possono essere installati con pip:

- markdown
- scons
- python-gettext

### Per impacchettare il componente aggiuntivo per la distribuzione
1. Aprire una riga di comando, passare alla radice di questo repository
2. Eseguire il comando **scons**. L'add-on creato, se non ci sono stati errori, viene posizionato nella directory corrente.

[1]: https://github.com/grisov/NVDA_Volume_Adjustment/releases/download/latest/volumeAdjustment-1.3.2.nvda-addon
