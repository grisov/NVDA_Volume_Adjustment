# NVDA Volume Adjustment (regulacja głośności)

* Autor: Oleksandr Gryshchenko
* Wersja: 1.0
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

## Panel ustawień dodatku
Poniższe opcje pozwalają elastycznie dostosować zachowanie aplikacji oraz listę zasobów audio, aby przełączać się między nimi.

### Krok do zmiany poziomu głośności
Minimalna wartość, o którą poziom głośności zostanie zmieniony po jednym naciśnięciu klawisza. Możesz ustawić wartość od 1 do 20 punktów.

### Automatyczne przełączanie sesji audio
Jeśli to pole wyboru jest zaznaczone, dodatek zostanie automatycznie przełączony do sesji dźwiękowej odpowiadającej programowi, na którym jest ustawiony fokus.
Na przykład, jeśli obecnie przeglądasz witrynę w przeglądarce Firefox, dodatek wykryje to i automatycznie przełączy się na sesję audio przeglądarki Firefox. Możesz natychmiast dostosować poziom głośności dla bieżącego procesu bez znajdowania go na liście.

### Ukryj urządzenia audio
Jeśli nie używasz jednego lub więcej urządzeń audio i nie chcesz, aby były obecne podczas przełączania się między źródłami dźwięku, możesz łatwo usunąć je z głównej listy, po prostu zaznaczając je w panelu ustawień.
Przycisk "Aktualizuj" służy do skanowania wszystkich urządzeń audio w systemie i wyświetlania zaktualizowanych informacji. Wszystkie zaznaczone elementy pozostają oznaczone.
Przycisk "Wyczyść" - odznacza wszystkie zaznaczone elementy i usuwa przestarzałe elementy.

### Ukryj procesy
Na tej liście pól wyboru możesz zaznaczyć procesy, które chcesz ukryć na głównej liście. Mogą to być na przykład programy usługowe.
Przycisk "Aktualizuj" służy do aktualizacji listy wszystkich uruchomionych procesów i dostępnych sesji audio. Wszystkie zaznaczone elementy pozostają zaznaczone.
Przycisk "Wyczyść" - odznacza wszystkie zaznaczone elementy i usuwa przestarzałe elementy.

## Wkład
Jesteśmy bardzo wdzięczni wszystkim, którzy dołożyli starań, aby opracować, przetłumaczyć i utrzymać ten dodatek:
* Dang Manh Cuong - wietnamskie tłumaczenie;
* Cagri Dogan - tureckie tłumaczenie;
* Christianlm - włoskie tłumaczenie;
* Cary Rowen - tłumaczenie na chiński uproszczony;
* Stefan Banita - polskie tłumaczenie.

## Lista zmian

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

[1]: https://github.com/grisov/NVDA_Volume_Adjustment/releases/download/v1.0/volumeAdjustment-1.0.nvda-addon
[2]: https://github.com/grisov/NVDA_Volume_Adjustment/releases/download/v1.0/volumeAdjustment-1.0.nvda-addon
