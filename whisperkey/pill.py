"""Dibujo del indicador flotante con antialiasing real.

El Canvas de tkinter dibuja sin suavizado: sus óvalos y esquinas redondeadas
salen en escalones. Acá la píldora se dibuja con Pillow a 4x y se reduce con
remuestreo LANCZOS, que es lo que da los bordes limpios.

El resultado se muestra en Windows como *layered window* con alfa por píxel, no
con color clave. Con color clave el borde suavizado se mezclaría contra el color
de transparencia y dejaría una aureola; con alfa por píxel se mezcla contra lo
que haya detrás, que es lo correcto.
"""

from __future__ import annotations

import logging
import pathlib
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger(__name__)

# Factor de supermuestreo: se dibuja grande y se reduce. 4x es donde la mejora
# deja de notarse a simple vista.
SUPERSAMPLE = 4

_FONT_CANDIDATES = (
    "SegUIVar.ttf",      # Segoe UI Variable (Windows 11)
    "segoeui.ttf",       # Segoe UI
    "DejaVuSans.ttf",
)

_font_cache: dict[int, ImageFont.FreeTypeFont] = {}


def _load_font(size_px: int) -> ImageFont.FreeTypeFont:
    """Fuente del sistema al tamaño pedido, con caché."""
    cached = _font_cache.get(size_px)
    if cached is not None:
        return cached

    directorios = [pathlib.Path(r"C:\Windows\Fonts")] if sys.platform == "win32" else []
    directorios += [
        pathlib.Path("/usr/share/fonts/truetype/dejavu"),
        pathlib.Path("/Library/Fonts"),
    ]
    for carpeta in directorios:
        for nombre in _FONT_CANDIDATES:
            ruta = carpeta / nombre
            if ruta.exists():
                try:
                    fuente = ImageFont.truetype(str(ruta), size_px)
                    _font_cache[size_px] = fuente
                    return fuente
                except Exception:  # pragma: no cover - fuente ilegible
                    continue

    fuente = ImageFont.load_default()
    _font_cache[size_px] = fuente
    return fuente


def render_pill(
    text: str,
    text_color: str,
    dot_color: str,
    surface: str,
    border: str,
    font_size: int = 14,
    scale: float = 1.0,
    pad_x: int = 15,
    pad_y: int = 9,
    dot_radius: int = 4,
    dot_gap: int = 10,
) -> Image.Image:
    """Devuelve la píldora como imagen RGBA con bordes suavizados.

    *font_size* va en PUNTOS, igual que en tkinter, y *scale* convierte a
    píxeles. Tratarlo como píxeles achicaba la píldora un 30%: en una pantalla
    al 125%, un punto son 1,33 píxeles.
    """
    s = SUPERSAMPLE
    px = lambda v: int(round(v * scale * s))  # noqa: E731 - conversión local

    fuente = _load_font(px(font_size))
    medidor = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    caja = medidor.textbbox((0, 0), text, font=fuente)
    ancho_texto = caja[2] - caja[0]
    # Alto de LÍNEA, no de la tinta: usar la caja del texto hacía que la altura
    # cambiara según si la palabra tenía tildes o letras con cola.
    ascenso, descenso = fuente.getmetrics()
    alto_linea = ascenso + descenso

    r = px(dot_radius)
    w = px(pad_x) * 2 + r * 2 + px(dot_gap) + ancho_texto
    h = max(alto_linea + px(pad_y) * 2, r * 6)

    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    radio = h // 2
    d.rounded_rectangle(
        (0, 0, w - 1, h - 1),
        radius=radio,
        fill=surface,
        outline=border,
        width=max(1, s // 2),
    )

    cx = px(pad_x) + r
    cy = h // 2
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=dot_color)

    d.text(
        (px(pad_x) + r * 2 + px(dot_gap) - caja[0], cy),
        text,
        font=fuente,
        fill=text_color,
        anchor="lm",
    )

    destino = (max(1, w // s), max(1, h // s))
    return img.resize(destino, Image.LANCZOS)


# ----------------------------------------------------------------------
# Ventana con alfa por píxel (Windows)
# ----------------------------------------------------------------------

_GWL_EXSTYLE = -20
_WS_EX_LAYERED = 0x00080000
_ULW_ALPHA = 0x00000002
_AC_SRC_OVER = 0x00
_AC_SRC_ALPHA = 0x01


def top_level_hwnd(hwnd: int) -> int:
    """Sube por la cadena de padres hasta la ventana de nivel superior.

    En Windows, `winfo_id()` de tkinter devuelve una ventana HIJA. Aplicarle a
    ésa el estilo de capa deja la ventana real sin transparencia, pintada de su
    color de fondo alrededor de la píldora.
    """
    if sys.platform != "win32":
        return hwnd
    try:
        import ctypes
        from ctypes import wintypes

        actual = hwnd
        padre = ctypes.windll.user32.GetParent(wintypes.HWND(actual))
        while padre:
            actual = padre
            padre = ctypes.windll.user32.GetParent(wintypes.HWND(actual))
        return actual
    except Exception:  # pragma: no cover - sin API de Windows
        return hwnd


def device_scale(logical_width: int) -> float:
    """Píxeles físicos por píxel lógico.

    tkinter trabaja en coordenadas lógicas y UpdateLayeredWindow en físicas. En
    una pantalla al 125% son cosas distintas, y `winfo_fpixels` no lo refleja:
    devuelve 96 igual. La proporción entre anchos de pantalla sí.
    """
    if sys.platform != "win32" or logical_width <= 0:
        return 1.0
    try:
        import ctypes

        fisico = ctypes.windll.user32.GetSystemMetrics(0)
        if fisico <= 0:
            return 1.0
        return max(1.0, fisico / logical_width)
    except Exception:  # pragma: no cover - sin API de Windows
        return 1.0


def screen_size_physical() -> tuple[int, int]:
    """Tamaño de pantalla en píxeles físicos."""
    if sys.platform != "win32":
        return (0, 0)
    try:
        import ctypes

        u = ctypes.windll.user32
        return (u.GetSystemMetrics(0), u.GetSystemMetrics(1))
    except Exception:  # pragma: no cover - sin API de Windows
        return (0, 0)


def supports_per_pixel_alpha() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        return hasattr(ctypes.windll.user32, "UpdateLayeredWindow")
    except Exception:  # pragma: no cover - sin API de Windows
        return False


def _premultiply(img: Image.Image) -> bytes:
    """BGRA con alfa premultiplicado, que es lo que espera Windows."""
    arr = np.asarray(img.convert("RGBA"), dtype=np.uint16)
    alpha = arr[:, :, 3:4]
    rgb = (arr[:, :, :3] * alpha) // 255
    bgra = np.dstack([rgb[:, :, 2], rgb[:, :, 1], rgb[:, :, 0], arr[:, :, 3]])
    return bgra.astype(np.uint8).tobytes()


def push_layered(hwnd: int, img: Image.Image, x: int, y: int) -> bool:
    """Pinta *img* como contenido de la ventana con alfa por píxel.

    Devuelve False si la plataforma no lo permite, para que el llamador use el
    camino de dibujo normal.
    """
    if not supports_per_pixel_alpha():
        return False

    import ctypes
    from ctypes import wintypes

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", wintypes.DWORD),
            ("biWidth", wintypes.LONG),
            ("biHeight", wintypes.LONG),
            ("biPlanes", wintypes.WORD),
            ("biBitCount", wintypes.WORD),
            ("biCompression", wintypes.DWORD),
            ("biSizeImage", wintypes.DWORD),
            ("biXPelsPerMeter", wintypes.LONG),
            ("biYPelsPerMeter", wintypes.LONG),
            ("biClrUsed", wintypes.DWORD),
            ("biClrImportant", wintypes.DWORD),
        ]

    class BITMAPINFO(ctypes.Structure):
        _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]

    class POINT(ctypes.Structure):
        _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

    class SIZE(ctypes.Structure):
        _fields_ = [("cx", wintypes.LONG), ("cy", wintypes.LONG)]

    class BLENDFUNCTION(ctypes.Structure):
        _fields_ = [
            ("BlendOp", ctypes.c_byte),
            ("BlendFlags", ctypes.c_byte),
            ("SourceConstantAlpha", ctypes.c_byte),
            ("AlphaFormat", ctypes.c_byte),
        ]

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32

    ancho, alto = img.size
    datos = _premultiply(img)

    # Quitar y volver a poner el estilo descarta cualquier estado dejado por
    # SetLayeredWindowAttributes, que de lo contrario hace fallar esta llamada
    # con ERROR_INVALID_WINDOW_STYLE.
    estilo = user32.GetWindowLongW(hwnd, _GWL_EXSTYLE)
    user32.SetWindowLongW(hwnd, _GWL_EXSTYLE, estilo & ~_WS_EX_LAYERED)
    user32.SetWindowLongW(hwnd, _GWL_EXSTYLE, estilo | _WS_EX_LAYERED)

    dc_pantalla = user32.GetDC(0)
    dc_memoria = gdi32.CreateCompatibleDC(dc_pantalla)

    cabecera = BITMAPINFOHEADER()
    cabecera.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    cabecera.biWidth = ancho
    cabecera.biHeight = -alto  # negativo: origen arriba, como la imagen
    cabecera.biPlanes = 1
    cabecera.biBitCount = 32
    cabecera.biCompression = 0  # BI_RGB

    info = BITMAPINFO()
    info.bmiHeader = cabecera

    bits = ctypes.c_void_p()
    bitmap = gdi32.CreateDIBSection(
        dc_memoria, ctypes.byref(info), 0, ctypes.byref(bits), None, 0
    )
    if not bitmap:
        gdi32.DeleteDC(dc_memoria)
        user32.ReleaseDC(0, dc_pantalla)
        return False

    ctypes.memmove(bits, datos, len(datos))
    anterior = gdi32.SelectObject(dc_memoria, bitmap)

    mezcla = BLENDFUNCTION(_AC_SRC_OVER, 0, 255, _AC_SRC_ALPHA)
    destino = POINT(int(x), int(y))
    tamano = SIZE(ancho, alto)
    origen = POINT(0, 0)

    ok = user32.UpdateLayeredWindow(
        wintypes.HWND(hwnd),
        dc_pantalla,
        ctypes.byref(destino),
        ctypes.byref(tamano),
        dc_memoria,
        ctypes.byref(origen),
        0,
        ctypes.byref(mezcla),
        _ULW_ALPHA,
    )

    gdi32.SelectObject(dc_memoria, anterior)
    gdi32.DeleteObject(bitmap)
    gdi32.DeleteDC(dc_memoria)
    user32.ReleaseDC(0, dc_pantalla)
    return bool(ok)
