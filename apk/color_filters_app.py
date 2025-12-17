# -*- coding: utf-8 -*-
"""
Color Filters App — wersja z:
- dwoma obrazami obok siebie (oryginał / po filtrze),
- paskiem przewijania panelu po lewej stronie,
- górnym paskiem zadań: przestrzeń barw, szumy, filtry, wizualizacja kanałów
  + poziomy pasek przewijania (scroll) dla górnego paska
  + suwaki i opisy kerneli/okien dla mediany, LPF i wektorowej mediany.
"""
import math
import os
import sys
import json
import ctypes
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import tkinter.font as tkfont

# Pillow
try:
    from PIL import Image, ImageTk, ImageOps, ImageEnhance, ImageFilter, ImageCms
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", "pillow"])
    from PIL import Image, ImageTk, ImageOps, ImageEnhance, ImageFilter, ImageCms

# Try to import numpy for faster vector median; optional
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except Exception:
    NUMPY_AVAILABLE = False

# DPI awareness (Windows)
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

# --- CONFIG ---
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGES_DIR = os.path.join(BASE_DIR, "obrazy")
RESULTS_DIR = os.path.join(BASE_DIR, "wyniki")
SETTINGS_FILE = os.path.join(BASE_DIR, "color_filters_settings.json")
os.makedirs(IMAGES_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)

PREVIEW_MAX_SIZE = (800, 600)
DEBOUNCE_MS = 200

def get_dynamic_preview_size(img):
    w, h = img.size
    aspect = w / h

    # zdjęcia poziome (szerokie)
    if aspect > 1.2:
        return (900, 600)   # Twoje 600×400 dla poziomych

    # zdjęcia pionowe / kwadratowe
    return PREVIEW_MAX_SIZE

default_settings = {"language": "pl", "theme": "dark", "last_image": None}
try:
    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
        settings = json.load(f)
except Exception:
    settings = default_settings.copy()

translations = {
    "pl": {
        "open": "Otwórz obraz...",
        "save": "Zapisz wynik...",
        "reset": "Resetuj do oryginału",
        "no_image": "Brak obrazu. Otwórz plik.",
        "color_balance": "Balans kolorów (R/G/B)",
        "hue": "Przesunięcie odcienia (hue)",
        "saturation": "Nasycenie",
        "sepia": "Sepia (0..1)",
        "equalize": "Equalizacja (histogram)",
        "blur": "Rozmycie (radius)",
        "sharpen": "Wyostrzenie (1=oryginał)",
        "fullscreen": "Pełny ekran",
        "color_space": "Przestrzeń barw",
        "median_filter": "Filtr medianowy",
        "apply_median": "Zastosuj medianę",
        "lpf_filter": "Filtr dolnoprzepustowy (Gaussian)",
        "apply_lpf": "Zastosuj LPF",
        "visualize_channels": "Wizualizuj kanały",
        "visualize_channels_gray": "Wizualizuj kanały (szarość)",

        "original": "Oryginalny",
        "filtered": "Po filtrze",
        "vector_median": "Filtr wektorowej mediany",
        "apply_vector_median": "Zastosuj wektorową medianę",
        "vector_running": "Wektorowa mediana: przetwarzanie...",
        "vector_done": "Zastosuj wektorową medianę",
        "language": "Język",
        "polish": "Polski",
        "english": "Angielski",
        "theme": "Motyw",
        "light": "Jasny",
        "dark": "Ciemny",
        "hint": "Zmiany stosują się automatycznie.",
        "reset": "Resetuj do oryginału",
        "commit": "Ustaw wynik jako nowy oryginał",
        "Szum_Gauss": "Szum Gaussowski (std)",
        "Szum_SaltPepper": "Szum Pieprz i Sól (%)",


    },
    "en": {
        "open": "Open image...",
        "save": "Save result...",
        "reset": "Reset to original",
        "no_image": "No image loaded. Open a file.",
        "color_balance": "Color balance (R/G/B)",
        "hue": "Hue shift (degrees)",
        "saturation": "Saturation",
        "sepia": "Sepia (0..1)",
        "equalize": "Equalize (histogram)",
        "blur": "Blur radius",
        "sharpen": "Sharpen (1=original)",
        "fullscreen": "Fullscreen",
        "color_space": "Color space",
        "median_filter": "Median filter",
        "apply_median": "Apply median",
        "lpf_filter": "Low-pass filter (Gaussian)",
        "apply_lpf": "Apply LPF",
        "visualize_channels": "Visualize channels",
        "visualize_channels_gray": "Visualize channels (grayscale)",

        "original": "Original",
        "filtered": "Filtered",
        "vector_median": "Vector median filter",
        "apply_vector_median": "Apply vector median",
        "vector_running": "Vector median: processing...",
        "vector_done": "Apply vector median",
        "language": "Language",
        "polish": "Polish",
        "english": "English",
        "theme": "Theme",
        "light": "Light",
        "dark": "Dark",
        "hint": "Changes are applied automatically.",
        "reset": "Reset to original",
        "commit": "Use result as new original",
        "Szum_Gauss": "Gaussian noise (std)",
        "Szum_SaltPepper": "Salt & Pepper noise (%)",


    },
}

current_language = settings.get("language", "pl")
current_theme = settings.get("theme", "dark")


def t(key):
    return translations.get(current_language, translations["pl"]).get(key, key)


# --- IMAGE HELPERS & FILTERS ---
def ensure_rgb(img):
    return img.convert("RGB") if img.mode != "RGB" else img


def make_preview_source(img):
    if img is None:
        return None

    max_size = get_dynamic_preview_size(img)

    pv = img.copy()
    pv.thumbnail(max_size, Image.LANCZOS)
    return pv


def make_preview(img, max_size=(400, 400)):
    pv = img.copy()
    pv.thumbnail(max_size, Image.LANCZOS)
    return pv


def adjust_color_balance(img, r_mul=1.0, g_mul=1.0, b_mul=1.0):
    img = ensure_rgb(img)
    r, g, b = img.split()
    r = r.point(lambda x: min(255, int(x * r_mul)))
    g = g.point(lambda x: min(255, int(x * g_mul)))
    b = b.point(lambda x: min(255, int(x * b_mul)))
    return Image.merge("RGB", (r, g, b))


def adjust_saturation(img, factor=1.0):
    return ImageEnhance.Color(img).enhance(factor)


def hue_shift(img, shift_deg=0):
    hsv = img.convert("HSV")
    h, s, v = hsv.split()
    shift = int(shift_deg * 255 / 360)
    h = h.point(lambda x: (x + shift) % 256)
    return Image.merge("HSV", (h, s, v)).convert("RGB")


def fast_sepia(img, intensity=1.0):
    gray = ImageOps.grayscale(img)
    sep = ImageOps.colorize(gray, "#704214", "#F0E0C0")
    return Image.blend(img, sep, intensity)


def sepia(img, intensity=0.8):
    img = ensure_rgb(img)
    width, height = img.size
    px = img.load()
    out = Image.new("RGB", img.size)
    out_px = out.load()
    for y in range(height):
        for x in range(width):
            r, g, b = px[x, y]
            tr = int(0.393 * r + 0.769 * g + 0.189 * b)
            tg = int(0.349 * r + 0.686 * g + 0.168 * b)
            tb = int(0.272 * r + 0.534 * g + 0.131 * b)
            out_px[x, y] = (
                min(255, int(tr * intensity + r * (1 - intensity))),
                min(255, int(tg * intensity + g * (1 - intensity))),
                min(255, int(tb * intensity + b * (1 - intensity))),
            )
    return out


def equalize_per_channel(img):
    r, g, b = img.split()
    return Image.merge("RGB", (ImageOps.equalize(r), ImageOps.equalize(g), ImageOps.equalize(b)))


def apply_blur(img, radius=2):
    return img.filter(ImageFilter.GaussianBlur(radius))


def apply_sharpen(img, factor=1.0):
    return ImageEnhance.Sharpness(img).enhance(factor)


def apply_median_per_channel(img, radius=1):
    img = ensure_rgb(img)
    r, g, b = img.split()
    size = max(1, int(radius) * 2 + 1)
    r2 = r.filter(ImageFilter.MedianFilter(size=size))
    g2 = g.filter(ImageFilter.MedianFilter(size=size))
    b2 = b.filter(ImageFilter.MedianFilter(size=size))
    return Image.merge("RGB", (r2, g2, b2))


def apply_gaussian_per_channel(img, radius=1):
    img = ensure_rgb(img)
    r, g, b = img.split()
    return Image.merge(
        "RGB",
        (
            r.filter(ImageFilter.GaussianBlur(radius)),
            g.filter(ImageFilter.GaussianBlur(radius)),
            b.filter(ImageFilter.GaussianBlur(radius)),
        ),
    )

def swap_images():
    global orig_image, working_image, orig_preview

    if orig_image is None or working_image is None:
        return

    # zamiana obrazów
    orig_image, working_image = working_image, orig_image

    # odśwież preview
    orig_preview = make_preview_source(orig_image)
    show_images(orig_image, working_image)


# --- SZUMY ---
import numpy as np  # zgodne z wcześniejszym NUMPY_AVAILABLE


def add_gaussian_noise(image, std=25):
    """Dodaje kolorowy szum Gaussowski do obrazu RGB."""
    np_img = np.array(image).astype(np.float32)
    noise = np.random.normal(0, std, np_img.shape)
    noisy_img = np.clip(np_img + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(noisy_img)


def add_salt_and_pepper_noise(image, amount):
    img = image.convert("RGB")
    np_img = np.array(img)
    noisy_img = np_img.copy()

    h, w, c = noisy_img.shape

    num_pixels = int(amount * h * w)

    # --- PIEPRZ (czarne piksele) ---
    y_coords = np.random.randint(0, h, num_pixels)
    x_coords = np.random.randint(0, w, num_pixels)
    noisy_img[y_coords, x_coords] = [0, 0, 0]

    # --- SÓL (białe piksele) ---
    y_coords = np.random.randint(0, h, num_pixels)
    x_coords = np.random.randint(0, w, num_pixels)
    noisy_img[y_coords, x_coords] = [255, 255, 255]

    return Image.fromarray(noisy_img)


# --- Accelerated approximate vector median ---
if NUMPY_AVAILABLE:

    def _integral_image_channel(channel_arr):
        """Compute integral image (summed-area table) for a 2D numpy array."""
        return np.cumsum(np.cumsum(channel_arr, axis=0), axis=1)

    def _window_sum_from_integral(ii, x0, y0, x1, y1):
        res = ii[y1, x1]
        if x0 > 0:
            res -= ii[y1, x0 - 1]
        if y0 > 0:
            res -= ii[y0 - 1, x1]
        if x0 > 0 and y0 > 0:
            res += ii[y0 - 1, x0 - 1]
        return res

    def vector_median_filter_fast(img, radius=1):
        img = ensure_rgb(img)
        w, h = img.size
        if w * h == 0:
            return img.copy()

        arr = np.asarray(img, dtype=np.float32)
        ii_r = _integral_image_channel(arr[:, :, 0])
        ii_g = _integral_image_channel(arr[:, :, 1])
        ii_b = _integral_image_channel(arr[:, :, 2])

        out = np.empty_like(arr, dtype=np.uint8)

        for y in range(h):
            y0 = max(0, y - radius)
            y1 = min(h - 1, y + radius)
            for x in range(w):
                x0 = max(0, x - radius)
                x1 = min(w - 1, x + radius)
                area = (y1 - y0 + 1) * (x1 - x0 + 1)

                mean_r = _window_sum_from_integral(ii_r, x0, y0, x1, y1) / area
                mean_g = _window_sum_from_integral(ii_g, x0, y0, x1, y1) / area
                mean_b = _window_sum_from_integral(ii_b, x0, y0, x1, y1) / area
                mean = np.array([mean_r, mean_g, mean_b], dtype=np.float32)

                patch = arr[y0 : y1 + 1, x0 : x1 + 1, :].reshape(-1, 3)
                dif = patch - mean
                d2 = (dif * dif).sum(axis=1)
                idx = int(np.argmin(d2))
                out[y, x, :] = np.clip(patch[idx, :], 0, 255).astype(np.uint8)

        return Image.fromarray(out, mode="RGB")

else:

    def vector_median_filter_fast(img, radius=1):
        img = ensure_rgb(img)
        w, h = img.size
        px = img.load()
        out = Image.new("RGB", img.size)
        out_px = out.load()
        for y in range(h):
            for x in range(w):
                x0 = max(0, x - radius)
                x1 = min(w - 1, x + radius)
                y0 = max(0, y - radius)
                y1 = min(h - 1, y + radius)
                sr = sg = sb = 0.0
                neigh = []
                cnt = 0
                for yy in range(y0, y1 + 1):
                    for xx in range(x0, x1 + 1):
                        r, g, b = px[xx, yy]
                        neigh.append((r, g, b))
                        sr += r
                        sg += g
                        sb += b
                        cnt += 1
                if cnt == 0:
                    out_px[x, y] = px[x, y]
                    continue
                mean = (sr / cnt, sg / cnt, sb / cnt)
                best = neigh[0]
                best_d = (
                    (best[0] - mean[0]) ** 2
                    + (best[1] - mean[1]) ** 2
                    + (best[2] - mean[2]) ** 2
                )
                for cand in neigh[1:]:
                    d = (
                        (cand[0] - mean[0]) ** 2
                        + (cand[1] - mean[1]) ** 2
                        + (cand[2] - mean[2]) ** 2
                    )
                    if d < best_d:
                        best_d = d
                        best = cand
                out_px[x, y] = best
        return out


def vector_median_filter(img, radius=1):
    return vector_median_filter_fast(img, radius=int(radius))


def apply_vector_median_to(img, radius=1):
    return vector_median_filter(img, radius=int(radius))


# HSI helpers
def rgb_to_hsi(img):
    img = ensure_rgb(img)
    w, h = img.size
    pixels = img.load()
    H = Image.new("F", img.size)
    S = Image.new("F", img.size)
    I = Image.new("F", img.size)
    Hpx, Spx, Ipx = H.load(), S.load(), I.load()
    for y in range(h):
        for x in range(w):
            r, g, b = [v / 255.0 for v in pixels[x, y]]
            num = 0.5 * ((r - g) + (r - b))
            den = math.sqrt((r - g) ** 2 + (r - b) * (g - b)) + 1e-8
            theta = math.acos(max(-1, min(1, num / den))) if den > 0 else 0.0
            h_angle = theta if b <= g else (2 * math.pi - theta)
            Hpx[x, y] = h_angle / (2 * math.pi)
            min_rgb = min(r, g, b)
            Ipx[x, y] = (r + g + b) / 3
            Spx[x, y] = 0 if Ipx[x, y] == 0 else 1 - min_rgb / Ipx[x, y]
    HL, SL, IL = Image.new("L", img.size), Image.new("L", img.size), Image.new("L", img.size)
    for src, dst in ((H, HL), (S, SL), (I, IL)):
        sp = src.load()
        dp = dst.load()
        for y in range(h):
            for x in range(w):
                dp[x, y] = int(max(0, min(255, sp[x, y] * 255)))
    return HL, SL, IL


# CIELAB via ImageCms
def rgb_to_lab(img):
    try:
        srgb_p = ImageCms.createProfile("sRGB")
        lab_p = ImageCms.createProfile("LAB")
        transform = ImageCms.buildTransformFromOpenProfiles(
            srgb_p, lab_p, "RGB", "LAB"
        )
        return ImageCms.applyTransform(img.convert("RGB"), transform)
    except Exception:
        return img.convert("RGB")


def lab_to_rgb(img_lab):
    try:
        srgb_p = ImageCms.createProfile("sRGB")
        lab_p = ImageCms.createProfile("LAB")
        transform = ImageCms.buildTransformFromOpenProfiles(
            lab_p, srgb_p, "LAB", "RGB"
        )
        return ImageCms.applyTransform(img_lab, transform)
    except Exception:
        return img_lab.convert("RGB")


# --- GUI setup ---
root = tk.Tk()

dpi = root.winfo_fpixels("1i")
if dpi > 120:
    root.tk.call("tk", "scaling", dpi / 96)

default_font = tkfont.nametofont("TkDefaultFont")
default_font.configure(size=13)
root.option_add("*Font", default_font)

FONT_NORMAL = ("TkDefaultFont", 13)
FONT_BOLD = ("TkDefaultFont", 15)

root.title("Color Filters")
root.geometry("1600x900")
fullscreen_state = False


# --- Funkcja do wyświetlania obrazów w Labelach ---
def show_images(orig_img, working_img):
    """Wyświetla obraz oryginalny i roboczy w Labelach GUI (tego samego rozmiaru)."""
    try:
        if orig_img is None and working_img is None:
            image_label_orig.config(image=None, text="Brak")
            image_label_orig.image = None
            image_label_working.config(image=None, text="Brak")
            image_label_working.image = None
            return

        orig_preview = make_preview_source(orig_img) if orig_img else None
        working_preview = make_preview_source(working_img) if working_img else None

        if orig_preview and working_preview:
            w = min(orig_preview.width, working_preview.width)
            h = min(orig_preview.height, working_preview.height)
            orig_preview = orig_preview.resize((w, h), Image.LANCZOS)
            working_preview = working_preview.resize((w, h), Image.LANCZOS)

        if orig_preview:
            orig_photo = ImageTk.PhotoImage(orig_preview)
            image_label_orig.config(image=orig_photo, text="")
            image_label_orig.image = orig_photo
        else:
            image_label_orig.config(image=None, text="")
            image_label_orig.image = None

        if working_preview:
            working_photo = ImageTk.PhotoImage(working_preview)
            image_label_working.config(image=working_photo, text="")
            image_label_working.image = working_photo
        else:
            image_label_working.config(image=None, text="")
            image_label_working.image = None

    except Exception as e:
        print("Błąd przy wyświetlaniu obrazów:", e)


def toggle_fullscreen(event=None):
    global fullscreen_state
    fullscreen_state = not fullscreen_state
    root.attributes("-fullscreen", fullscreen_state)
    refresh_preview()


root.bind("<F11>", toggle_fullscreen)
style = ttk.Style()

# colors
SLIDER_COLOR = "#1E90FF"
SLIDER_COLOR_R = "#E64C4C"
SLIDER_COLOR_G = "#4CB96B"
SLIDER_COLOR_B = "#4C7BE6"
SLIDER_COLOR_HUE = "#FFD166"
SLIDER_COLOR_DEFAULT = SLIDER_COLOR


# --- theme & styles ---
def update_widget_colors(widget, fg, bg):
    try:
        cls = widget.__class__.__name__
        if cls in ("Label", "Button", "Checkbutton"):
            try:
                widget.config(fg=fg, bg=bg)
            except Exception:
                pass
        if cls == "Canvas":
            try:
                widget.config(bg=bg)
            except Exception:
                pass
    except Exception:
        pass
    for child in widget.winfo_children():
        update_widget_colors(child, fg, bg)


def apply_theme():
    global controls_canvas, controls_inner, style

    if current_theme == "dark":
        bg_main = "#333333"
        control_bg = "#2e2e2e"
        fg = "white"
        btn_bg = "#5d5d5d"
        btn_fg = "black"
        entry_bg = "#555555"
        slider_trough = control_bg
    else:
        bg_main = "#f0f0f0"
        control_bg = "#ececec"
        fg = "black"
        btn_bg = "#d0d0d0"
        btn_fg = "black"
        entry_bg = "white"
        slider_trough = control_bg

    try:
        root.configure(bg=bg_main)
    except Exception:
        pass

    try:
        style.configure(
            "TLabel", background=control_bg, foreground=fg, font=FONT_NORMAL
        )
        style.configure("TFrame", background=control_bg, foreground=fg)
        style.configure(
            "Gray.TButton",
            background=btn_bg,
            foreground=btn_fg,
            borderwidth=1,
            font=FONT_NORMAL,
            padding=(4, 2)
        )
        style.map(
            "Gray.TButton",
            background=[("active", btn_bg), ("pressed", btn_bg)],
            foreground=[("!disabled", btn_fg)],
        )
        style.configure("TButton", background=btn_bg, foreground=btn_fg, font=FONT_NORMAL)
        style.configure("Horizontal.TScale", troughcolor=slider_trough)
        style.configure("TEntry", fieldbackground=entry_bg, foreground=fg, font=FONT_NORMAL)
        style.configure(
            "TCombobox", fieldbackground=entry_bg, foreground=fg, font=FONT_NORMAL
        )
    except Exception:
        pass

    try:
        controls_canvas.configure(bg=control_bg)
        controls_inner.configure(bg=control_bg)
    except Exception:
        pass

    update_widget_colors(root, fg, control_bg)
    try:
        controls_canvas.update_idletasks()
    except Exception:
        pass


# --- MAIN MENU ---
menubar = tk.Menu(root)
root.config(menu=menubar)

lang_menu = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label=t("language"), menu=lang_menu)


def set_language(lang):
    global current_language
    current_language = lang
    settings["language"] = lang
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    rebuild_ui()
    refresh_preview()


lang_menu.add_command(label=translations["pl"]["polish"], command=lambda: set_language("pl"))
lang_menu.add_command(label=translations["en"]["english"], command=lambda: set_language("en"))

theme_menu = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label=t("theme"), menu=theme_menu)


def set_theme(theme):
    global current_theme
    current_theme = theme
    settings["theme"] = theme
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    apply_theme()
    rebuild_ui()
    refresh_preview()


theme_menu.add_command(label=t("light"), command=lambda: set_theme("light"))
theme_menu.add_command(label=t("dark"), command=lambda: set_theme("dark"))

# --- MAIN FRAME (panel + top bar + obrazy) ---
main_frame = ttk.Frame(root, padding=8)
main_frame.pack(side="top", fill="both", expand=True)

# --- Controls container with scrollable canvas (LEWA STRONA, OD GÓRY) ---
controls_container = ttk.Frame(main_frame)
controls_container.pack(side="left", fill="y", padx=4, pady=4)

controls_canvas = tk.Canvas(
    controls_container,
    highlightthickness=0,
    bg="#333",
    width=400  # Zwiększono szerokość panelu
)

controls_vsb = ttk.Scrollbar(
    controls_container,
    orient="vertical",
    command=controls_canvas.yview
)

controls_canvas.configure(yscrollcommand=controls_vsb.set)

controls_canvas.pack(side="left", fill="y", expand=True)
controls_vsb.pack(side="left", fill="y")


controls_inner = tk.Frame(controls_canvas, bg=controls_canvas["bg"])
controls_window = controls_canvas.create_window(
    (0, 0), window=controls_inner, anchor="nw"
)

# --- PRAWA KOLUMNA: górny pasek + obrazy ---
right_column = ttk.Frame(main_frame)
right_column.pack(side="right", fill="both", expand=True)

# --- TOP BAR (górny pasek zadań) z poziomym scrollem ---
top_bar_container = ttk.Frame(right_column)
top_bar_container.pack(side="top", fill="x")

# --- canvas ---
TOP_BAR_HEIGHT = 180

top_bar_canvas = tk.Canvas(
    top_bar_container,
    highlightthickness=0,
    height=TOP_BAR_HEIGHT,
    bg=controls_canvas.cget("bg")
)
top_bar_canvas.pack(side="left", fill="x", expand=True)

# --- scroll pionowy ---
top_bar_vscroll = ttk.Scrollbar(
    top_bar_container,
    orient="vertical",
    command=top_bar_canvas.yview
)
top_bar_vscroll.pack(side="right", fill="y")

# --- scroll poziomy ---
top_bar_hscroll = ttk.Scrollbar(
    right_column,
    orient="horizontal",
    command=top_bar_canvas.xview
)
top_bar_hscroll.pack(side="top", fill="x")

top_bar_canvas.configure(
    xscrollcommand=top_bar_hscroll.set,
    yscrollcommand=top_bar_vscroll.set
)


top_bar = ttk.Frame(top_bar_canvas, padding=4)
top_bar_id = top_bar_canvas.create_window((0, 0), window=top_bar, anchor="nw")




def _on_top_bar_configure(event):
    top_bar_canvas.configure(scrollregion=top_bar_canvas.bbox("all"))

top_bar.bind("<Configure>", _on_top_bar_configure)

# --- miejsce na obrazy: dwa obok siebie (POD GÓRNYM PASKIEM) ---
images_container = tk.Frame(right_column, bg="gray")
images_container.pack(
    side="top",
    fill="both",
    expand=True,
    padx=4,
    pady=(2, 2)
)

swap_bar = tk.Frame(images_container, bg=images_container["bg"])
swap_bar.pack(side="top", fill="x")

swap_btn = tk.Button(
    swap_bar,
    text="⇄",
    command=swap_images,
    font=("TkDefaultFont", 18),
    relief="raised",
    bd=1,
    padx=6,
    pady=0
)
swap_btn.pack(pady=2)

images_frame = tk.Frame(images_container, bg="gray")
images_frame.pack(side="top", fill="both", expand=True)

left_image_frame = tk.Frame(images_frame, bg="gray")
left_image_frame.pack(side="left", fill="both", expand=True)

right_image_frame = tk.Frame(images_frame, bg="gray")
right_image_frame.pack(side="left", fill="both", expand=True)

image_label_orig = tk.Label(left_image_frame, bg="gray", anchor="center", highlightthickness=0, bd=0)
image_label_orig.pack(expand=True)

image_label_working = tk.Label(right_image_frame, bg="gray", anchor="center", highlightthickness=0, bd=0)
image_label_working.pack(expand=True)


def _on_controls_configure(event):
    controls_canvas.configure(scrollregion=controls_canvas.bbox("all"))


controls_inner.bind("<Configure>", _on_controls_configure)



# mouse wheel support
def _on_controls_mousewheel(event):
    if sys.platform == "darwin":
        delta = -1 * (event.delta)
    else:
        delta = -1 * int(event.delta / 120)
    controls_canvas.yview_scroll(delta, "units")


controls_canvas.bind_all("<MouseWheel>", _on_controls_mousewheel)
controls_canvas.bind_all("<Button-4>", lambda e: controls_canvas.yview_scroll(-1, "units"))
controls_canvas.bind_all("<Button-5>", lambda e: controls_canvas.yview_scroll(1, "units"))

controls = controls_inner

apply_theme()

# state
base_image = None        # zawsze pierwszy, „czysty” obraz z pliku
orig_image = None        # aktualny oryginał (może być po commit)
orig_preview = None
working_image = None
preview_tk = None
_debounce_job = None
_vector_thread = None


# control vars
color_balance_r = tk.DoubleVar(value=1.0)
color_balance_g = tk.DoubleVar(value=1.0)
color_balance_b = tk.DoubleVar(value=1.0)
hue_var = tk.DoubleVar(value=0.0)
saturation_var = tk.DoubleVar(value=1.0)
sepia_var = tk.DoubleVar(value=0.0)
equalize_var = tk.BooleanVar(value=False)
blur_var = tk.DoubleVar(value=0.0)
sharpen_var = tk.DoubleVar(value=1.0)
median_var = tk.DoubleVar(value=1.0)
lpf_var = tk.DoubleVar(value=1.0)
color_space_var = tk.StringVar(value="RGB")
vector_radius_var = tk.DoubleVar(value=1.0)
gauss_var = tk.DoubleVar(value=0)
saltpepper_var = tk.DoubleVar(value=0)


# --- colored scale factory (tk.Scale) ---
def make_colored_scale(
    parent,
    var,
    frm,
    to,
    value_label,
    fmt_fn=None,
    resolution=0.01,
    length=200,
    slider_color=SLIDER_COLOR,
    bg_color=None,
    sliderlength=28,
):
    if bg_color is None:
        try:
            bg_color = controls_canvas.cget("bg")
        except Exception:
            bg_color = "#333333" if current_theme == "dark" else "#f0f0f0"

    border_color = "white" if current_theme == "dark" else "black"

    s = tk.Scale(
        parent,
        from_=frm,
        to=to,
        orient="horizontal",
        variable=var,
        resolution=resolution,
        showvalue=False,
        bg=bg_color,
        troughcolor=bg_color,
        highlightthickness=1,
        sliderrelief="raised",
        length=length,
        sliderlength=sliderlength,
        bd=1,
        activebackground=slider_color,
        highlightbackground=border_color,
        highlightcolor=border_color,
        relief="flat",
        font=FONT_NORMAL,
        command=lambda val, v=var, l=value_label, f=fmt_fn: on_scale_change(
            val, v, l, f
        ),
    )
    try:
        s.config(fg=slider_color)
    except Exception:
        pass

    s.pack(fill="x", padx=4)
    return s


# --- processing (preview + full) ---
def apply_filters_preview():
    global working_image, orig_preview
    if orig_image is None:
        return

    if orig_preview is None:
        orig_preview = make_preview_source(orig_image)
    img = orig_preview.copy()

    img = adjust_color_balance(img, color_balance_r.get(), color_balance_g.get(), color_balance_b.get())
    if abs(hue_var.get()) > 0.01:
        img = hue_shift(img, hue_var.get())
    if abs(saturation_var.get() - 1) > 0.01:
        img = adjust_saturation(img, saturation_var.get())
    if sepia_var.get() > 0:
        img = fast_sepia(img, sepia_var.get())
    if equalize_var.get():
        img = equalize_per_channel(img)
    if blur_var.get() > 0.01:
        img = apply_blur(img, blur_var.get())
    if abs(sharpen_var.get() - 1) > 0.01:
        img = apply_sharpen(img, sharpen_var.get())
    if gauss_var.get() > 0.01:
        img = add_gaussian_noise(img, std=gauss_var.get())
    if saltpepper_var.get() > 0.01:
        img = add_salt_and_pepper_noise(img, amount=saltpepper_var.get() / 100)

    working_image = img
    if orig_image is not None:
        show_images(orig_image, working_image)
    refresh_preview()


def apply_filters_full():
    global working_image, orig_preview
    if orig_image is None:
        return
    img = orig_image.copy()
    img = adjust_color_balance(img, color_balance_r.get(), color_balance_g.get(), color_balance_b.get())
    if abs(hue_var.get()) > 0.01:
        img = hue_shift(img, hue_var.get())
    if abs(saturation_var.get() - 1) > 0.01:
        img = adjust_saturation(img, saturation_var.get())
    if sepia_var.get() > 0:
        img = sepia(img, sepia_var.get())
    if equalize_var.get():
        img = equalize_per_channel(img)
    if blur_var.get() > 0.01:
        img = apply_blur(img, blur_var.get())
    if abs(sharpen_var.get() - 1) > 0.01:
        img = apply_sharpen(img, sharpen_var.get())
    if gauss_var.get() > 0.01:
        img = add_gaussian_noise(img, std=gauss_var.get())
    if saltpepper_var.get() > 0.01:
        img = add_salt_and_pepper_noise(img, amount=saltpepper_var.get() / 100)

    working_image = img
    orig_preview = make_preview_source(img)
    working_image = orig_preview.copy() if orig_preview else img
    if orig_image is not None:
        show_images(orig_image, working_image)
    refresh_preview()


def _run_full_in_background():
    try:
        apply_filters_full()
    except Exception:
        pass


def debounced_apply(*_):
    global _debounce_job
    if _debounce_job is not None:
        try:
            root.after_cancel(_debounce_job)
        except Exception:
            pass
    _debounce_job = root.after(DEBOUNCE_MS, apply_filters_preview)
    global _vector_thread
    if _vector_thread is None or not _vector_thread.is_alive():
        threading.Thread(target=_run_full_in_background, daemon=True).start()


# --- median / lpf / vector median handlers (background) ---
def apply_median_bg(button_widget=None):
    global working_image, orig_preview
    if orig_preview is None:
        return
    r = max(0, int(median_var.get()))
    if r == 0:
        if button_widget:
            try:
                button_widget.config(text="Brak zmian (radius 0)", state="disabled")
            except Exception:
                pass
            root.after(
                600,
                lambda: button_widget.config(text=t("apply_median"), state="normal"),
            )
        return
    img_to_process = orig_preview.copy()
    if button_widget:
        try:
            button_widget.config(text="Przetwarzanie mediany...", state="disabled")
        except Exception:
            pass

    def _worker():
        try:
            result = apply_median_per_channel(img_to_process, radius=r)

            def _finish():
                global working_image, orig_preview
                orig_preview = result.copy()
                working_image = result.copy()
                show_images(orig_image, working_image)
                refresh_preview()
                if button_widget:
                    try:
                        button_widget.config(text=t("apply_median"), state="normal")
                    except Exception:
                        pass

            root.after(0, _finish)
        except Exception as e:
            def _err():
                messagebox.showerror("Median", f"Błąd: {e}")
                if button_widget:
                    try:
                        button_widget.config(text=t("apply_median"), state="normal")
                    except Exception:
                        pass

            root.after(0, _err)

    threading.Thread(target=_worker, daemon=True).start()


def apply_lpf_bg(button_widget=None):
    global working_image, orig_preview
    if orig_preview is None:
        return
    r = max(0, lpf_var.get())
    img_to_process = orig_preview.copy()
    if button_widget:
        try:
            button_widget.config(text="Przetwarzanie LPF...", state="disabled")
        except Exception:
            pass

    def _worker():
        try:
            result = apply_gaussian_per_channel(img_to_process, radius=r)

            def _finish():
                global working_image, orig_preview
                orig_preview = result.copy()
                working_image = result.copy()
                show_images(orig_image, working_image)
                refresh_preview()
                if button_widget:
                    try:
                        button_widget.config(text=t("apply_lpf"), state="normal")
                    except Exception:
                        pass

            root.after(0, _finish)
        except Exception as e:
            def _err():
                messagebox.showerror("LPF", f"Błąd: {e}")
                if button_widget:
                    try:
                        button_widget.config(text=t("apply_lpf"), state="normal")
                    except Exception:
                        pass

            root.after(0, _err)

    threading.Thread(target=_worker, daemon=True).start()


def _vector_worker(img, radius, button_widget):
    try:
        result = apply_vector_median_to(img, radius)

        def _finish():
            global working_image, orig_preview
            orig_preview = result.copy()
            working_image = result.copy()
            show_images(orig_image, working_image)
            refresh_preview()
            try:
                button_widget.config(text=t("vector_done"), state="normal")
            except Exception:
                pass

        root.after(0, _finish)
    except Exception as e:
        def _err():
            messagebox.showerror("Vector median", f"Błąd: {e}")
            try:
                button_widget.config(text=t("vector_done"), state="normal")
            except Exception:
                pass

        root.after(0, _err)


def apply_vector_median_bg(button_widget):
    global _vector_thread
    if working_image is None:
        return
    img_to_process = working_image.copy()
    r = max(1, int(vector_radius_var.get()))
    try:
        button_widget.config(text=t("vector_running"), state="disabled")
    except Exception:
        pass
    _vector_thread = threading.Thread(
        target=_vector_worker, args=(img_to_process, r, button_widget), daemon=True
    )
    _vector_thread.start()


# --- preview render ---
def refresh_preview():
    if orig_image is None and working_image is None:
        image_label_orig.config(image=None, text="Brak")
        image_label_orig.image = None
        image_label_working.config(image=None, text="Brak")
        image_label_working.image = None
        return
    show_images(orig_image, working_image)


# --- open/save/reset ---
def open_image():
    global base_image, orig_image, working_image, orig_preview

    path = filedialog.askopenfilename(
        initialdir=IMAGES_DIR,
        filetypes=[("Images", "*.png;*.jpg;*.jpeg;*.bmp;*.tiff")],
    )
    if not path:
        return

    try:
        # czytamy z pliku
        base_image = Image.open(path).convert("RGB")  # ZAPAMIĘTANY na stałe
        orig_image = base_image.copy()               # bieżący „oryginał”
        working_image = orig_image.copy()
        orig_preview = make_preview_source(orig_image)

        settings["last_image"] = path
        save_settings()

        show_images(orig_image, working_image)

    except Exception as e:
        print("Nie udało się wczytać obrazu:", e)
        base_image = orig_image = working_image = None



def save_settings():
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def save_image():
    if orig_image is None:
        messagebox.showwarning("", t("no_image"))
        return
    apply_filters_full()
    path = filedialog.asksaveasfilename(
        defaultextension=".png",
        initialdir=RESULTS_DIR,
        filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg"), ("All files", "*.*")],
    )
    if path:
        full = orig_image.copy()
        full = adjust_color_balance(
            full, color_balance_r.get(), color_balance_g.get(), color_balance_b.get()
        )
        if abs(hue_var.get()) > 0.01:
            full = hue_shift(full, hue_var.get())
        if abs(saturation_var.get() - 1) > 0.01:
            full = adjust_saturation(full, saturation_var.get())
        if sepia_var.get() > 0:
            full = sepia(full, sepia_var.get())
        if equalize_var.get():
            full = equalize_per_channel(full)
        if blur_var.get() > 0.01:
            full = apply_blur(full, blur_var.get())
        if abs(sharpen_var.get() - 1) > 0.01:
            full = apply_sharpen(full, sharpen_var.get())
        try:
            full.save(path)
            messagebox.showinfo("", f"{t('save')} OK")
        except Exception as e:
            messagebox.showerror("", f"Save failed: {e}")


def reset_image():
    """
    Reset do PIERWSZEGO, czystego obrazu z pliku (base_image)
    i wyzerowanie wszystkich suwaków.
    """
    global base_image, orig_image, orig_preview, working_image

    if base_image is None:
        return

    # przywracamy pierwszy, nieprzetworzony obraz
    orig_image = base_image.copy()
    orig_preview = make_preview_source(orig_image)
    working_image = orig_preview.copy() if orig_preview else orig_image.copy()

    # reset suwaków / opcji
    color_balance_r.set(1.0)
    color_balance_g.set(1.0)
    color_balance_b.set(1.0)
    hue_var.set(0.0)
    saturation_var.set(1.0)
    sepia_var.set(0.0)
    equalize_var.set(False)
    blur_var.set(0.0)
    sharpen_var.set(1.0)
    median_var.set(1.0)
    lpf_var.set(1.0)
    vector_radius_var.set(1.0)
    color_space_var.set("RGB")
    gauss_var.set(0.0)
    saltpepper_var.set(0.0)

    rebuild_ui()
    show_images(orig_image, working_image)
    refresh_preview()

        

def rgb_to_hsi_python(img_pil):
    img = np.asarray(img_pil).astype(np.float64) / 255.0
    R = img[:,:,0]
    G = img[:,:,1]
    B = img[:,:,2]

    num = 0.5 * ((R - G) + (R - B))
    den = np.sqrt((R - G)**2 + (R - B)*(G - B)) + 1e-12
    theta = np.arccos(np.clip(num / den, -1, 1))

    H = theta.copy()
    H[B > G] = 2*np.pi - H[B > G]
    H /= (2*np.pi)

    min_rgb = np.minimum(np.minimum(R, G), B)
    I = (R + G + B) / 3.0
    S = 1 - (min_rgb / (I + 1e-12))

    HSI = np.stack([H, S, I], axis=2)
    return HSI

from PIL import Image
import numpy as np
import colorsys

def make_channels(mode, img_pil):
    img = np.asarray(img_pil).astype(np.float64) / 255.0
    h, w = img.shape[:2]

    if mode == "hsv":
        hsv = np.zeros_like(img)
        for i in range(h):
            for j in range(w):
                hsv[i,j] = colorsys.rgb_to_hsv(*img[i,j])

        H = hsv[:,:,0]
        S = hsv[:,:,1]
        V = hsv[:,:,2]

        H_RGB = np.array([colorsys.hsv_to_rgb(h, 1, 1) for h in H.flatten()]).reshape(h,w,3)
        S_RGB = np.stack([S, np.zeros_like(S), np.zeros_like(S)], axis=2)
        V_RGB = np.stack([V, V, V], axis=2)

        return (Image.fromarray((H_RGB*255).astype(np.uint8)),
                Image.fromarray((S_RGB*255).astype(np.uint8)),
                Image.fromarray((V_RGB*255).astype(np.uint8)))

    elif mode == "hsi":
        HSI = rgb_to_hsi_python(img_pil)
        H = HSI[:,:,0]
        S = HSI[:,:,1]
        I = HSI[:,:,2]

        H_RGB = np.array([colorsys.hsv_to_rgb(h, 1, 1) for h in H.flatten()]).reshape(h,w,3)
        S_RGB = np.stack([S, np.zeros_like(S), np.zeros_like(S)], axis=2)
        I_RGB = np.stack([I, I, I], axis=2)

        return (Image.fromarray((H_RGB*255).astype(np.uint8)),
                Image.fromarray((S_RGB*255).astype(np.uint8)),
                Image.fromarray((I_RGB*255).astype(np.uint8)))

    elif mode == "cielab":
        import cv2
        lab = cv2.cvtColor((img*255).astype(np.uint8), cv2.COLOR_RGB2LAB)
        L = lab[:,:,0] / 100.0
        a = (lab[:,:,1] - 128) / 128.0
        b = (lab[:,:,2] - 128) / 128.0

        L_RGB = np.stack([L, L, L], axis=2)
        a_RGB = np.stack([np.zeros_like(a), a, np.zeros_like(a)], axis=2)
        b_RGB = np.stack([np.zeros_like(b), np.zeros_like(b), b], axis=2)

        return (Image.fromarray((L_RGB*255).astype(np.uint8)),
                Image.fromarray((a_RGB*255).astype(np.uint8)),
                Image.fromarray((b_RGB*255).astype(np.uint8)))

    else:
        raise ValueError("Unknown mode")


def convert_channels_python(mode, img_pil, tag=None):
    mode = mode.lower()
    return make_channels(mode, img_pil)


def visualize_channels():
    global orig_image, working_image

    if orig_image is None or working_image is None:
        return

    space = color_space_var.get()  # "RGB" / "HSV" / "HSI" / "CIELAB"

    # --- NAZWY KANAŁÓW ---
    if space == "RGB":
        names = ["R", "G", "B"]
        window_title = "Kanały RGB"
    elif space == "HSV":
        names = ["H", "S", "V"]
        window_title = f"{t('visualize_channels')}: HSV"
    elif space == "HSI":
        names = ["H", "S", "I"]
        window_title = f"{t('visualize_channels')}: HSI"
    elif space == "CIELAB":
        names = ["L", "a", "b"]
        window_title = f"{t('visualize_channels')}: CIELAB"
    else:
        names = ["C1", "C2", "C3"]
        window_title = f"Kanały {space}"

    # --- PRZYGOTOWANIE OBRAZÓW ---
    if space in ["HSV", "HSI", "CIELAB"]:
        o1, o2, o3 = convert_channels_python(space.lower(), orig_image, "orig")
        f1, f2, f3 = convert_channels_python(space.lower(), working_image, "filt")

        # KOLEJNOŚĆ ZGODNA Z GUI:
        # kanał → oryginał → filtr
        all_images = [
            o1, f1,
            o2, f2,
            o3, f3
        ]

    else:  # RGB
        img_orig = orig_image
        img_filt = working_image

        o1, o2, o3 = img_orig.split()
        f1, f2, f3 = img_filt.split()

        def make_color_channel(chan, idx):
            zero = Image.new("L", chan.size, 0)
            if idx == 0:
                return Image.merge("RGB", (chan, zero, zero))
            if idx == 1:
                return Image.merge("RGB", (zero, chan, zero))
            if idx == 2:
                return Image.merge("RGB", (zero, zero, chan))

        # KOLEJNOŚĆ ZGODNA Z GUI
        all_images = [
            make_color_channel(o1, 0),  # R orig
            make_color_channel(f1, 0),  # R filt
            make_color_channel(o2, 1),  # G orig
            make_color_channel(f2, 1),  # G filt
            make_color_channel(o3, 2),  # B orig
            make_color_channel(f3, 2),  # B filt
        ]

    # --- OKNO ---
    win = tk.Toplevel(root)
    win.title(window_title)
    win.geometry("1100x650")

    # --- KONFIGURACJA GRID ---
    for r in (0, 2):
        win.rowconfigure(r, weight=0)
    for r in (1, 3):
        win.rowconfigure(r, weight=1)
    win.rowconfigure(4, weight=0)

    for c in (0, 1, 2):
        win.columnconfigure(c, weight=1)

    # --- ETYKIETY + OBRAZY ---
    labels = []
    img_idx = 0

    for channel_idx in range(3):        # kanały
        for row_type in range(2):       # 0 = orig, 1 = filt

            img_type = t('original') if row_type == 0 else t('filtered')
            label_row = row_type * 2
            image_row = row_type * 2 + 1

            lbl_text = f"{names[channel_idx]} ({img_type})"
            name_lbl = tk.Label(win, text=lbl_text, font=FONT_NORMAL)
            name_lbl.grid(row=label_row, column=channel_idx, sticky="w",
                          padx=5, pady=(5, 2))

            lbl = tk.Label(win, bg="black")
            lbl.grid(row=image_row, column=channel_idx, sticky="nsew")

            labels.append(lbl)
            img_idx += 1

    # --- PRZECHOWANIE PIL-owych obrazów ---
    pil_images = all_images[:]  # TERAZ KOLEJNOŚĆ JEST POPRAWNA

    def update_images(event=None):
        """Skalowanie obrazów podczas zmiany rozmiaru okna."""
        # W tej nowej strukturze `labels` zawiera tylko 6 labeli dla obrazów (wiersze 1 i 3)
        for lbl, img in zip(labels, pil_images):
            w = lbl.winfo_width()
            h = lbl.winfo_height()
            if w <= 1 or h <= 1:
                continue

            img_resized = img.copy()
            img_resized.thumbnail((w, h), Image.LANCZOS)

            ph = ImageTk.PhotoImage(img_resized)
            lbl.config(image=ph)
            lbl.image = ph  # trzymamy referencję

    # obrazy dopasowują się przy zmianie rozmiaru okna
    win.bind("<Configure>", update_images)

    # wywołaj raz po utworzeniu okna, żeby od razu coś było widać
    win.after(50, update_images)

    # przycisk Zamknij na dole, w środku (w wierszu 4)
    close_btn = ttk.Button(win, text="Zamknij", command=win.destroy)
    close_btn.grid(row=4, column=1, pady=10)

def visualize_channels_gray():
    # --- visualize channels w odcieniach szarości ---
    if orig_image is None or working_image is None:
        return

    img_orig = orig_image
    img_filt = working_image
    space = color_space_var.get()

    if space == "RGB":
        o1, o2, o3 = img_orig.split()
        f1, f2, f3 = img_filt.split()
        names = ["R", "G", "B"]
    elif space == "HSV":
        hsv_orig = img_orig.convert("HSV")
        hsv_filt = img_filt.convert("HSV")
        o1, o2, o3 = hsv_orig.split()
        f1, f2, f3 = hsv_filt.split()
        names = ["H", "S", "V"]
    elif space == "HSI":
        o1, o2, o3 = rgb_to_hsi(img_orig)
        f1, f2, f3 = rgb_to_hsi(img_filt)
        names = ["H", "S", "I"]
    elif space == "CIELAB":
        lab_orig = rgb_to_lab(img_orig)
        lab_filt = rgb_to_lab(img_filt)
        o1, o2, o3 = lab_orig.split()
        f1, f2, f3 = lab_filt.split()
        names = ["L", "a", "b"]
    else:
        o1, o2, o3 = img_orig.split()
        f1, f2, f3 = img_filt.split()
        names = ["C1", "C2", "C3"]

    # okno na pełny ekran
    win = tk.Toplevel(root)
    win.title(t("visualize_channels"))
    win.state("zoomed")   # <--- tutaj maksymalizujemy okno

    for i, (orig_chan, filt_chan) in enumerate(zip([o1, o2, o3], [f1, f2, f3])):
        # ORYGINAŁ – w skali szarości
        pv_orig = ImageTk.PhotoImage(
            make_preview(orig_chan.convert("L").convert("RGB"), (400, 400))
        )
        lbl_o = tk.Label(win, text=f"{t('original')} {names[i]}")
        lbl_o.grid(row=0, column=i)
        canvas_o = tk.Label(win, image=pv_orig)
        canvas_o.image = pv_orig
        canvas_o.grid(row=1, column=i)

        # PO FILTRZE – w skali szarości
        pv_filt = ImageTk.PhotoImage(
            make_preview(filt_chan.convert("L").convert("RGB"), (400, 400))
        )
        lbl_f = tk.Label(win, text=f"{t('filtered')} {names[i]}")
        lbl_f.grid(row=2, column=i)
        canvas_f = tk.Label(win, image=pv_filt)
        canvas_f.image = pv_filt
        canvas_f.grid(row=3, column=i)

    ttk.Button(
        win,
        text="Zamknij" if current_language == "pl" else "Close",
        command=win.destroy,
    ).grid(row=4, column=1, pady=6)



# --- UI helpers ---
def make_value_label(parent, text, bg=None, fg=None):
    if bg is None:
        bg = controls_canvas.cget("bg")
    if fg is None:
        fg = "white" if current_theme == "dark" else "black"
    lbl = tk.Label(parent, text=text, bg=bg, fg=fg)
    lbl.pack(anchor="w")
    return lbl


def on_scale_change(_val, var, label, fmt=None):
    v = var.get()
    label.config(text=fmt(v) if fmt else str(v))
    debounced_apply()


# --- BUILD UI ---
def rebuild_ui():
    # zaktualizuj etykiety menu
    try:
        menubar.entryconfig(0, label=t("language"))
        menubar.entryconfig(1, label=t("theme"))
    except Exception:
        pass

    # czyść top bar i panel boczny
    for w in top_bar.winfo_children():
        w.destroy()
    for w in controls.winfo_children():
        w.destroy()

    control_bg = controls_canvas.cget("bg")
    fg = "white" if current_theme == "dark" else "black"

    PADX = 30


    # 0: Szum Gaussowski (std) – suwak jak przy medianie
    gauss_frame = ttk.Frame(top_bar)
    gauss_frame.grid(row=0, column=0, padx=PADX, sticky="w")
    ttk.Label(gauss_frame, text=t("Szum_Gauss")).pack(anchor="w")


    gauss_lbl = make_value_label(
        gauss_frame, f"{gauss_var.get():.0f}", bg=control_bg, fg=fg
    )
    make_colored_scale(
        gauss_frame,
        gauss_var,
        0,
        100,
        gauss_lbl,
        fmt_fn=lambda x: f"{float(x):.0f}",
        resolution=1,
        slider_color=SLIDER_COLOR_DEFAULT,
        sliderlength=16,
    )

    # 1: Szum Pieprz i Sól (%) – suwak jak przy medianie
    sp_frame = ttk.Frame(top_bar)
    sp_frame.grid(row=0, column=1, padx=PADX, sticky="w")
    ttk.Label(sp_frame, text=t("Szum_SaltPepper")).pack(anchor="w")

    for r in (0, 1):
        top_bar.grid_rowconfigure(r, weight=0)
    sp_lbl = make_value_label(
        sp_frame, f"{saltpepper_var.get():.1f} %", bg=control_bg, fg=fg
    )
    make_colored_scale(
        sp_frame,
        saltpepper_var,
        0,
        10,
        sp_lbl,
        fmt_fn=lambda x: f"{float(x):.1f} %",
        resolution=0.1,
        slider_color=SLIDER_COLOR_DEFAULT,
        sliderlength=16,
    )


    # 2: Medianowy — opis kernela + suwak + przycisk
    median_frame = ttk.Frame(top_bar)
    median_frame.grid(row=1, column=0, padx=PADX, sticky="w")

    ttk.Label(median_frame, text=t("median_filter")).pack(anchor="w")

    def fmt_m(v):
        r = int(float(v))
        k = 2 * r + 1
        return f"radius {r} → kernel {k}×{k}"

    med_lbl = make_value_label(
        median_frame, fmt_m(median_var.get()), bg=control_bg, fg=fg
    )
    make_colored_scale(
        median_frame,
        median_var,
        0,
        5,
        med_lbl,
        fmt_fn=lambda x: fmt_m(x),
        resolution=1,
        slider_color=SLIDER_COLOR_DEFAULT,
        sliderlength=16,
    )
    median_btn = ttk.Button(
        median_frame,
        text=t("apply_median"),
        command=lambda b=None: apply_median_bg(median_btn),
        style="Gray.TButton",
    )
    median_btn.pack(fill="x", pady=(2, 8))

    # 3: LPF
    lpf_frame = ttk.Frame(top_bar)
    lpf_frame.grid(row=1, column=1, padx=PADX, sticky="w")

    ttk.Label(lpf_frame, text=t("lpf_filter")).pack(anchor="w")
    lpf_lbl = make_value_label(
        lpf_frame, f"{lpf_var.get():.1f} px", bg=control_bg, fg=fg
    )
    make_colored_scale(
        lpf_frame,
        lpf_var,
        0,
        10,
        lpf_lbl,
        fmt_fn=lambda x: f"{float(x):.1f} px",
        resolution=0.1,
        slider_color=SLIDER_COLOR_DEFAULT,
    )
    lpf_btn = ttk.Button(
        lpf_frame,
        text=t("apply_lpf"),
        command=lambda b=None: apply_lpf_bg(lpf_btn),
        style="Gray.TButton",
    )
    lpf_btn.pack(fill="x", pady=(2, 8))

    # 4: Wektorowa mediana
    vec_frame = ttk.Frame(top_bar)
    vec_frame.grid(row=1, column=2, padx=PADX, sticky="w")

    ttk.Label(vec_frame, text=t("vector_median")).pack(anchor="w")

    def fmt_vec(v):
        r = int(float(v))
        k = 2 * r + 1
        return f"{r} → window {k}×{k}"

    vec_lbl = make_value_label(
        vec_frame,
        fmt_vec(vector_radius_var.get()),
        bg=control_bg,
        fg=fg,
    )
    make_colored_scale(
        vec_frame,
        vector_radius_var,
        1,
        5,
        vec_lbl,
        fmt_fn=lambda x: fmt_vec(x),
        resolution=1,
        slider_color=SLIDER_COLOR_DEFAULT,
        sliderlength=16,
    )
    vec_btn = ttk.Button(
        vec_frame,
        text=t("apply_vector_median"),
        command=lambda b=None: apply_vector_median_bg(vec_btn),
        style="Gray.TButton",
    )
    vec_btn.pack(fill="x", pady=(2, 8))

    # rozciąganie kolumn w poziomie (0..4)
    for col in range(5):
        top_bar.grid_columnconfigure(col, weight=1)


    # --- PANEL BOCZNY: reszta opcji ---

    ttk.Button(controls, text=t("open"), command=open_image, style="Gray.TButton").pack(
        fill="x", pady=6
    )
    ttk.Button(controls, text=t("save"), command=save_image, style="Gray.TButton").pack(
        fill="x", pady=6
    )
    ttk.Button(
        controls, text=t("reset"), command=reset_image, style="Gray.TButton"
    ).pack(fill="x", pady=6)
  

    ttk.Separator(controls).pack(fill="x", pady=4)

        # Przestrzeń barw + wizualizacja kanałów (po lewej stronie)
    ttk.Label(controls, text=t("color_space")).pack(anchor="w", pady=(6, 0))
    ttk.Combobox(
        controls,
        textvariable=color_space_var,
        values=["RGB", "HSV", "HSI", "CIELAB"],
        state="readonly",
    ).pack(fill="x", pady=(0, 6))

    ttk.Button(
        controls,
        text=t("visualize_channels"),
        command=visualize_channels,
        style="Gray.TButton",
    ).pack(fill="x", pady=(0, 10))

    ttk.Button(
        controls,
        text=t("visualize_channels_gray"),
        command=visualize_channels_gray,
        style="Gray.TButton",
    ).pack(fill="x", pady=(0, 10))



    ttk.Label(controls, text=t("color_balance")).pack(anchor="w")
    cb_frame = ttk.Frame(controls)
    cb_frame.pack(fill="x")

    def fmt_rgb(v):
        return f"{int(float(v)*100)}%"

    for var, knob_color in (
        (color_balance_r, SLIDER_COLOR_R),
        (color_balance_g, SLIDER_COLOR_G),
        (color_balance_b, SLIDER_COLOR_B),
    ):
        sub = tk.Frame(cb_frame, bg=control_bg)
        sub.pack(fill="x", pady=6)
        lbl = make_value_label(sub, fmt_rgb(var.get()), bg=control_bg, fg=fg)
        make_colored_scale(
            sub,
            var,
            0,
            2,
            lbl,
            fmt_fn=lambda x, fn=fmt_rgb: fn(float(x)),
            resolution=0.01,
            slider_color=knob_color,
        )

    ttk.Label(controls, text=t("hue")).pack(anchor="w", pady=(6, 0))
    hue_lbl = make_value_label(
        controls, f"{int(hue_var.get())}°", bg=control_bg, fg=fg
    )
    make_colored_scale(
        controls,
        hue_var,
        -180,
        180,
        hue_lbl,
        fmt_fn=lambda x: f"{int(float(x))}°",
        resolution=1,
        slider_color=SLIDER_COLOR_HUE,
    )

    ttk.Label(controls, text=t("saturation")).pack(anchor="w", pady=(6, 0))
    sat_lbl = make_value_label(
        controls, f"{int(saturation_var.get()*100)}%", bg=control_bg, fg=fg
    )
    make_colored_scale(
        controls,
        saturation_var,
        0,
        3,
        sat_lbl,
        fmt_fn=lambda x: f"{int(float(x)*100)}%",
        resolution=0.01,
        slider_color=SLIDER_COLOR_DEFAULT,
    )

    ttk.Label(controls, text=t("sepia")).pack(anchor="w", pady=(6, 0))
    sep_lbl = make_value_label(
        controls, f"{int(sepia_var.get()*100)}%", bg=control_bg, fg=fg
    )
    make_colored_scale(
        controls,
        sepia_var,
        0,
        1,
        sep_lbl,
        fmt_fn=lambda x: f"{int(float(x)*100)}%",
        resolution=0.01,
        slider_color=SLIDER_COLOR_DEFAULT,
    )

    eq_frame = tk.Frame(controls, bg=control_bg)
    eq_frame.pack(fill="x", pady=(6, 0))
    eq_cb = tk.Checkbutton(
        eq_frame,
        text=t("equalize"),
        variable=equalize_var,
        command=debounced_apply,
        bg=control_bg,
        fg=fg,
        activebackground=control_bg,
        selectcolor=control_bg,
    )
    eq_cb.pack(anchor="w")

    ttk.Label(controls, text=t("blur")).pack(anchor="w", pady=(6, 0))
    blur_lbl = make_value_label(
        controls, f"{blur_var.get():.1f} px", bg=control_bg, fg=fg
    )
    make_colored_scale(
        controls,
        blur_var,
        0,
        10,
        blur_lbl,
        fmt_fn=lambda x: f"{float(x):.1f} px",
        resolution=0.1,
        slider_color=SLIDER_COLOR_DEFAULT,
    )

    ttk.Label(controls, text=t("sharpen")).pack(anchor="w", pady=(6, 0))
    sharp_lbl = make_value_label(
        controls, f"{int(sharpen_var.get()*100)}%", bg=control_bg, fg=fg
    )
    make_colored_scale(
        controls,
        sharpen_var,
        0,
        5,
        sharp_lbl,
        fmt_fn=lambda x: f"{int(float(x)*100)}%",
        resolution=0.01,
        slider_color=SLIDER_COLOR_DEFAULT,
    )

    ttk.Button(
        controls, text=t("fullscreen"), command=toggle_fullscreen, style="Gray.TButton"
    ).pack(fill="x", pady=6)

    hint_lbl = tk.Label(
        controls, text=t("hint"), wraplength=220, bg=control_bg, fg=fg
    )
    hint_lbl.pack(pady=(12, 0))
    ttk.Separator(controls).pack(fill="x", pady=6)

    controls_canvas.update_idletasks()
    controls_canvas.configure(scrollregion=controls_canvas.bbox("all"))


# --- initial UI + start ---
rebuild_ui()
refresh_preview()
root.mainloop()
