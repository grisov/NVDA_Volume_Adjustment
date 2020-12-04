# NVDA Volume Adjustment (regulacja głośności)

* Autor: Oleksandr Gryshchenko
* Wersja: 1.2
* Pobierz [wersja stabilna][1]
* Pobierz [wersja rozwojowa][2]

Dostosowuje poziom głośności wszystkich urządzeń audio zainstalowanych w systemie i każdego uruchomionego programu oddzielnie za pomocą prostych skrótów klawiszowych.
Możesz zawsze zmienić domyślne skróty klawiszowe na preferowane w oknie dialogowym NVDA Zdarzenia wejścia.

## Funkcje
* regulowanie poziomu głośności wszystkich urządzeń audio w systemie;
* kontrola głośności oddzielnie dla każdego uruchomionego programu;
* szybkie przełączenie na maksymalny lub minimalny poziom głośności dowolnego źródła dźwięku;
* elastyczne ustawienia dla ogłaszania listy wykrytych urządzeń audio i uruchomionych programów;
* automatyczne przełączanie na bieżący program;
* możliwość ustawienia niestandardowego kroku zmiany głośności.
* szybkie przełączanie wyjścia na inne dostępne urządzenia audio.

## Przełączanie między źródłami dźwięku
Aby przejść do poprzedniego lub następnego źródła dźwięku, możesz użyć kombinacji klawiszy NVDA+Windows+ Strzałka w lewo lub w prawo. Lista składa się z dwóch części - systemowych urządzeń audio i uruchomionych sesji audio. Przełączanie odbywa się cyklicznie w koło podobnie jak w pierścieniu szybkich ustawień NVDA.
Za pomocą panelu ustawień dodatku możesz ukryć dowolne elementy na tej liście.
Przełączanie między sesjami audio może następować automatycznie po przełączeniu do okna odpowiedniego programu - tryb ten można włączyć w panelu ustawień dodatku.

Uwaga: lista sesji audio zmienia się dynamicznie i zależy od uruchomionych programów.

## Regulacja poziomu głośności
Po wybraniu źródła dźwięku można zmienić jego poziom głośności za pomocą następujących poleceń:
* zwiększenie głośności - NVDA+Windows+Strzałka w górę;
* zmniejszenie głośności - NVDA+Windows+Strzałka w dół;
* ustawienie maksymalnego poziomu głośności - NVDA+Windows+Home;
* ustawienie minimalnego poziomu głośności - NVDA+Windows+End;
* wyciszenie źródła dźwięku - NVDA+Windows+Strzałka w dół (gdy minimalny poziom głośności jest już ustawiony).

Uwaga: Domyślnie głośność zmienia się o jeden procent przy jednokrotnym naciśnięciu klawisza. Wartość tę można zmienić w panelu ustawień w zakresie od 1 do 20.

## Szybkie przełączanie między urządzeniami wyjściowymi audio
Aby przełączyć wyjście wszystkich dźwięków NVDA na następne dostępne urządzenie audio, po prostu naciśnij NVDA+Windows+PageUp.
Aby powrócić do poprzedniego urządzenia audio, użyj NVDA+Windows+PageDown.
Ponadto, aby szybko przełączyć wyjście audio NVDA na wybrane urządzenie audio, możesz użyć NVDA+Windows+ klawisze funkcyjne od F1.

## Panel ustawień dodatku
Poniższe opcje pozwalają elastycznie dostosować zachowanie aplikacji oraz listę zasobów audio, aby przełączać się między nimi.

### Krok do zmiany poziomu głośności
Minimalna wartość, o którą poziom głośności zostanie zmieniony po jednym naciśnięciu klawisza. Możesz ustawić wartość od 1 do 20 punktów.

### Automatyczne przełączanie sesji audio
Jeśli to pole wyboru jest zaznaczone, dodatek zostanie automatycznie przełączony do sesji dźwiękowej odpowiadającej programowi, na którym jest ustawiony fokus.
Na przykład, jeśli obecnie przeglądasz witrynę w przeglądarce Firefox, dodatek wykryje to i automatycznie przełączy się na sesję audio przeglądarki Firefox. Możesz natychmiast dostosować poziom głośności dla bieżącego procesu bez znajdowania go na liście.

### Ukryj sesje audio o takich samych nazwach
Czasami podczas uruchamiania niektórych programów otwieranych jest wiele sesji dźwiękowych o tych samych nazwach. Ta opcja pozwala ukryć takie sesje audio.

### Ukryj procesy
Na tej liście pól wyboru możesz zaznaczyć procesy, które chcesz ukryć na głównej liście. Mogą to być na przykład programy usługowe.
Przycisk "Odśwież" służy do aktualizacji listy wszystkich uruchomionych procesów i dostępnych sesji audio. Wszystkie zaznaczone elementy pozostają zaznaczone.
Przycisk "Wyczyść" - odznacza wszystkie zaznaczone elementy i usuwa przestarzałe elementy.

### Kontroluj wszystkie dostępne urządzenia audio
Udostępnia zaawansowane funkcje dodatku, a mianowicie możliwość regulacji głośności wszystkich urządzeń audio wykrytych w systemie.
Z nieznanych przyczyn ta funkcja powoduje błędy w niektórych systemach, dlatego jest oznaczona jako eksperymentalna.

### Ukryj urządzenia audio
Jeśli nie używasz jednego lub więcej urządzeń audio i nie chcesz, aby były obecne podczas przełączania się między źródłami dźwięku, możesz łatwo usunąć je z głównej listy, po prostu zaznaczając je w panelu ustawień.
Przycisk "Odśwież" służy do skanowania wszystkich urządzeń audio w systemie i wyświetlania zaktualizowanych informacji. Wszystkie zaznaczone elementy pozostają oznaczone.
Przycisk "Wyczyść" - odznacza wszystkie zaznaczone elementy i usuwa przestarzałe elementy.

### Użyj domyślnych skrótów klawiszowych
Jeśli nie planujesz korzystać ze wszystkich funkcji dodatku. W panelu ustawień możesz wyłączyć domyślne kombinacje klawiszy dla wszystkich dostępnych funkcji. Następnie możesz przypisać własne skróty klawiszowe za pośrednictwem standardowego okna dialogowego NVDA "Zdarzenia Wejścia..." tylko dla tych funkcji, które Cię interesują.

## Wkład
Jesteśmy bardzo wdzięczni wszystkim, którzy dołożyli starań, aby opracować, przetłumaczyć i utrzymać ten dodatek:
* Dang Manh Cuong - wietnamskie tłumaczenie;
* Cagri Dogan - tureckie tłumaczenie;
* Christianlm - włoskie tłumaczenie;
* Cary Rowen - tłumaczenie na chiński uproszczony;
* Stefan Banita - polskie tłumaczenie.

## Lista zmian

### Wersja 1.2
* dodano oddzielne skróty klawiszowe do szybkiego przełączania na wybrane urządzenie wyjściowe audio;
* Dodano możliwość wyłączenia wszystkich domyślnych skrótów klawiszowych używanych w dodatku.

### Wersja 1.1
* naprawiony błąd powielania sesji audio związanych z jednym uruchomionym procesem;
* naprawiono metodę wykrywania bieżącej sesji audio;
* poprawiono metodę określania nazwy bieżącego procesu;
* nadpisywanie domyślnego urządzenia wyjściowego w inny sposób, jeśli pierwsza próba się nie powiodła;
* ulepszony panel ustawień dodatku;
* dodana możliwość szybkiego przełączania wyjścia na inne dostępne urządzenie audio.

### Wersja 1.0: Zaimplementowano funkcje
* Ten dodatek jest oparty na zaawansowanych funkcjach dodatku NVDA Unmute, które zostały usunięte z oryginalnego dodatku z powodu niespójności z jego głównym zadaniem.
* Dodano możliwość regulacji poziomu głośności wszystkich urządzeń audio wykrytych w systemie.
* Dodano skróty klawiszowe, aby szybko ustawić maksymalny i minimalny poziom głośności dla wybranego źródła dźwięku.
* Dodano panel ustawień dodatku.

## Zmiany w NVDA Volume Adjustment
Możesz sklonować to repozytorium, aby wprowadzić zmiany w NVDA Volume Adjustment.

### Zewnętrzne zależności
Można je zainstalować za pomocą pip:
- markdown
- scons
- python-gettext

### Aby spakować dodatek do dystrybucji:
1. Otwórz wiersz poleceń, przejdź do katalogu głównego tego repozytorium
2. Uruchom polecenie **scons**. Utworzony dodatek, jeśli nie było błędów, jest umieszczony w bieżącym katalogu.

[1]: https://github.com/grisov/NVDA_Volume_Adjustment/releases/download/v1.2/volumeAdjustment-1.2.nvda-addon
[2]: https://github.com/grisov/NVDA_Volume_Adjustment/releases/download/v1.2/volumeAdjustment-1.2.nvda-addon
