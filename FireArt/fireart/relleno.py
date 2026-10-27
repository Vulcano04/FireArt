"""Algoritmos de la cubeta de pintura (sin dependencias de Qt, solo NumPy)."""
import numpy as np


def inundar(coincide: np.ndarray, sx: int, sy: int) -> np.ndarray:
    """Relleno por tramos (scanline): devuelve la región conectada (4 vecinos) a la semilla."""
    alto, ancho = coincide.shape
    salida = np.zeros_like(coincide)
    if not coincide[sy, sx]:
        return salida
    pila = [(sy, sx)]
    while pila:
        y, x = pila.pop()
        if salida[y, x] or not coincide[y, x]:
            continue
        fila = coincide[y]
        izq = np.flatnonzero(~fila[:x])
        l = int(izq[-1]) + 1 if izq.size else 0
        der = np.flatnonzero(~fila[x:])
        r = x + int(der[0]) - 1 if der.size else ancho - 1
        salida[y, l:r + 1] = True
        for ny in (y - 1, y + 1):
            if 0 <= ny < alto:
                seg = coincide[ny, l:r + 1] & ~salida[ny, l:r + 1]
                if seg.any():
                    idx = np.flatnonzero(seg)
                    inicios = idx[np.r_[True, np.diff(idx) > 1]]
                    for s in inicios:
                        pila.append((ny, l + int(s)))
    return salida


def dilatar(m: np.ndarray, n: int) -> np.ndarray:
    for _ in range(n):
        d = m.copy()
        d[1:] |= m[:-1]
        d[:-1] |= m[1:]
        d[:, 1:] |= m[:, :-1]
        d[:, :-1] |= m[:, 1:]
        m = d
    return m


def calcular_mascaras(ref: np.ndarray, x: int, y: int, tolerancia: int, expandir: int):
    """ref: (alto, ancho, 4) uint8. Devuelve (region, borde_expandido) o None."""
    alto, ancho = ref.shape[:2]
    if not (0 <= x < ancho and 0 <= y < alto):
        return None
    semilla = ref[y, x].astype(np.int16)
    dif = np.abs(ref.astype(np.int16) - semilla).max(axis=2)
    region = inundar(dif <= tolerancia, x, y)
    if not region.any():
        return None
    borde = dilatar(region, expandir) & ~region if expandir > 0 else np.zeros_like(region)
    return region, borde


def pintar(base: np.ndarray, region: np.ndarray, borde: np.ndarray, pix) -> np.ndarray:
    """Pinta 'pix' (BGRA premultiplicado). La región reemplaza; el borde queda DEBAJO del trazo existente."""
    out = base.copy()
    pix = np.asarray(pix, dtype=np.uint8)
    out[region] = pix
    if borde.any():
        px = out[borde].astype(np.uint16)
        out[borde] = np.minimum(255, px + pix.astype(np.uint16) * (255 - px[:, 3:4]) // 255).astype(np.uint8)
    return out
