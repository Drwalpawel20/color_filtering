# Color Filters App

Aplikacja desktopowa do przetwarzania i analizy obrazów, wykonana w Pythonie z wykorzystaniem **Tkinter** oraz **Pillow**. Program umożliwia nakładanie filtrów, modyfikowanie parametrów kolorów, dodawanie szumów oraz analizę obrazu w różnych przestrzeniach barw.

Aplikacja posiada graficzny interfejs użytkownika z obsługą języka polskiego i angielskiego oraz jasnego i ciemnego motywu.

## Funkcje

### Obsługa obrazów

* otwieranie obrazów:

  * PNG
  * JPG/JPEG
  * BMP
  * TIFF
* wyświetlanie obrazu oryginalnego i przetworzonego obok siebie,
* zamiana miejscami obrazu oryginalnego i przetworzonego,
* resetowanie wszystkich zmian do pierwotnego obrazu,
* zapis przetworzonego obrazu jako PNG lub JPEG,
* automatyczne zapamiętywanie ostatnio otwartego obrazu.

### Korekcja kolorów

Aplikacja umożliwia niezależną regulację kanałów RGB:

* Red (R),
* Green (G),
* Blue (B).

Dostępne są również:

* przesunięcie odcienia (`Hue`) w zakresie `-180°` – `180°`,
* regulacja nasycenia,
* efekt sepia,
* equalizacja histogramu dla poszczególnych kanałów,
* rozmycie Gaussa,
* wyostrzenie obrazu.

Wartości parametrów mogą być regulowane za pomocą interaktywnych suwaków.

### Szumy

Program umożliwia dodawanie dwóch rodzajów szumu:

#### Szum Gaussowski

Parametr określa odchylenie standardowe dodawanego szumu.

#### Szum Salt & Pepper

Dodawane są losowe:

* czarne piksele — `pepper`,
* białe piksele — `salt`.

Intensywność szumu określana jest procentowo.

### Filtry

#### Filtr medianowy

Filtr medianowy jest stosowany niezależnie dla kanałów RGB.

Parametr `radius` określa rozmiar kernela:

```text
kernel = (2 × radius + 1) × (2 × radius + 1)
```

Przykładowo:

```text
radius = 1 → 3×3
radius = 2 → 5×5
radius = 3 → 7×7
```

#### Filtr dolnoprzepustowy LPF

Implementacja wykorzystuje rozmycie Gaussa dla poszczególnych kanałów RGB.

Parametr określa promień rozmycia w pikselach.

#### Wektorowa mediana

Program zawiera implementację wektorowego filtru medianowego dla obrazu RGB.

Filtr analizuje sąsiedztwo piksela i wybiera wektor RGB znajdujący się najbliżej średniego wektora kolorów w analizowanym oknie.

Rozmiar okna jest określany na podstawie promienia:

```text
radius = 1 → 3×3
radius = 2 → 5×5
radius = 3 → 7×7
```

Jeżeli dostępny jest **NumPy**, wykorzystywana jest przyspieszona implementacja bazująca na tablicach NumPy oraz obrazach całkowych.

### Przestrzenie barw

Aplikacja obsługuje analizę obrazu w czterech przestrzeniach barw:

* **RGB**
* **HSV**
* **HSI**
* **CIELAB**

Użytkownik może wybrać przestrzeń barw z listy rozwijanej.

### Wizualizacja kanałów

Program umożliwia porównanie kanałów obrazu przed i po zastosowaniu filtrów.

Dostępne są dwa tryby wizualizacji.

#### Wizualizacja kolorowa

Dla wybranej przestrzeni barw wyświetlane są poszczególne kanały obrazu:

```text
Kanał → oryginał → po filtrze
```

Dla RGB są to:

```text
R
G
B
```

Dla HSV:

```text
H
S
V
```

Dla HSI:

```text
H
S
I
```

Dla CIELAB:

```text
L
a
b
```

#### Wizualizacja w skali szarości

Każdy kanał jest dodatkowo przedstawiany jako obraz w odcieniach szarości.

Pozwala to łatwiej obserwować rozkład wartości poszczególnych składowych.

## Interfejs użytkownika

Interfejs został zaprojektowany w Tkinterze i składa się z kilku głównych elementów:

```text
┌──────────────────────────────────────────────────────────────┐
│                     Pasek filtrów                           │
├────────────────┬─────────────────────────────────────────────┤
│                │                                             │
│  Panel         │              Oryginalny obraz               │
│  sterowania    │                    ⇄                        │
│                │              Przetworzony obraz             │
│                │                                             │
│                │                                             │
└────────────────┴─────────────────────────────────────────────┘
```

### Panel sterowania

Panel po lewej stronie zawiera:

* otwieranie obrazu,
* zapis wyniku,
* reset,
* wybór przestrzeni barw,
* wizualizację kanałów,
* balans RGB,
* Hue,
* Saturation,
* Sepia,
* equalizację histogramu,
* Blur,
* Sharpen,
* tryb pełnoekranowy.

Panel posiada pionowy pasek przewijania.

### Górny pasek

Górny pasek zawiera ustawienia:

* szumu Gaussowskiego,
* szumu Salt & Pepper,
* filtru medianowego,
* filtru LPF,
* wektorowej mediany.

Pasek posiada również poziome przewijanie, dzięki czemu wszystkie opcje mogą być dostępne przy mniejszej szerokości okna.

## Automatyczna aktualizacja podglądu

Zmiana wartości większości parametrów powoduje automatyczną aktualizację podglądu.

Wykorzystywany jest mechanizm `debounce`, dzięki któremu kolejne zmiany suwaka nie powodują niepotrzebnego wykonywania operacji dla każdej pojedynczej zmiany wartości.

Dla bardziej wymagających operacji, takich jak:

* filtr medianowy,
* LPF,
* wektorowa mediana,

wykorzystywane są wątki działające w tle, aby nie blokować interfejsu użytkownika.

## Wielojęzyczność

Aplikacja obsługuje dwa języki:

* 🇵🇱 Polski
* 🇬🇧 English

Język można zmienić z poziomu menu aplikacji.

Wybrany język jest zapisywany w pliku konfiguracyjnym.

## Motywy

Dostępne są dwa motywy interfejsu:

* jasny,
* ciemny.

Aktualny motyw jest zapisywany automatycznie i przywracany przy kolejnym uruchomieniu aplikacji.

## Zapisywanie ustawień

Aplikacja wykorzystuje plik:

```text
color_filters_settings.json
```

Przechowywane są w nim m.in.:

```json
{
    "language": "pl",
    "theme": "dark",
    "last_image": null
}
```

Dzięki temu aplikacja może zachować wybrane ustawienia pomiędzy uruchomieniami.

## Struktura katalogów

Po uruchomieniu aplikacja automatycznie tworzy katalogi:

```text
projekt/
│
├── main.py
├── color_filters_settings.json
│
├── obrazy/
│   └── ...
│
└── wyniki/
    └── ...
```

### `obrazy/`

Domyślny katalog przeznaczony na obrazy wejściowe.

### `wyniki/`

Domyślny katalog przeznaczony na zapisane obrazy wynikowe.

### `color_filters_settings.json`

Plik zawierający ustawienia aplikacji.

## Wymagania

Projekt wymaga:

* Python 3.10+
* Tkinter
* Pillow
* NumPy

Dodatkowo funkcjonalność CIELAB wykorzystuje **OpenCV (`cv2`)**.

## Instalacja

Zainstaluj wymagane biblioteki:

```bash
pip install pillow numpy opencv-python
```

Tkinter jest zazwyczaj dostępny razem z Pythonem.

Następnie uruchom aplikację:

```bash
python main.py
```

Jeżeli plik posiada inną nazwę, należy użyć odpowiedniej nazwy pliku:

```bash
python nazwa_pliku.py
```

## Technologie

Projekt wykorzystuje:

| Technologia | Zastosowanie                                 |
| ----------- | -------------------------------------------- |
| Python      | język programowania                          |
| Tkinter     | graficzny interfejs użytkownika              |
| Pillow      | obsługa i przetwarzanie obrazów              |
| NumPy       | operacje numeryczne i przyspieszenie filtrów |
| OpenCV      | konwersja do przestrzeni CIELAB              |
| JSON        | zapisywanie ustawień                         |
| threading   | wykonywanie cięższych operacji w tle         |

## Przetwarzanie obrazu

Aplikacja rozdziela przetwarzanie na dwa poziomy:

### Podgląd

Do szybkiego podglądu wykorzystywana jest pomniejszona wersja obrazu.

Pozwala to na płynniejszą zmianę parametrów za pomocą suwaków.

### Wynik końcowy

Przy zapisie obrazu filtry są wykonywane ponownie na pełnym obrazie wejściowym, dzięki czemu zapisany plik zachowuje oryginalną rozdzielczość.

## Obsługa DPI

Aplikacja zawiera obsługę skalowania DPI systemu Windows:

```python
ctypes.windll.shcore.SetProcessDpiAwareness(1)
```

Dodatkowo skalowanie Tkintera jest dostosowywane do rozdzielczości ekranu.

## Tryb pełnoekranowy

Tryb pełnoekranowy można przełączyć:

* przyciskiem **Pełny ekran**,
* klawiszem `F11`.

Ponowne naciśnięcie `F11` przywraca standardowy widok okna.

## Licencja

Projekt został przygotowany jako aplikacja edukacyjna do przetwarzania i analizy obrazów.
