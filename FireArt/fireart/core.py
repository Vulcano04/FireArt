"""Núcleo de FireArt: documento, capas, cuadros de animación, deshacer, guardado y exportación."""
from __future__ import annotations

import itertools
import json
import zipfile

import numpy as np
from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PySide6.QtGui import QColor, QImage, QPainter

from . import relleno

FMT = QImage.Format.Format_ARGB32_Premultiplied
CM = QPainter.CompositionMode

MODOS = {
    "Normal": CM.CompositionMode_SourceOver,
    "Multiplicar": CM.CompositionMode_Multiply,
    "Pantalla": CM.CompositionMode_Screen,
    "Superponer": CM.CompositionMode_Overlay,
    "Aclarar": CM.CompositionMode_Lighten,
    "Oscurecer": CM.CompositionMode_Darken,
    "Sobreexponer color": CM.CompositionMode_ColorDodge,
    "Añadir": CM.CompositionMode_Plus,
}
_uid = itertools.count(1)


def imagen_vacia(w: int, h: int, color=None) -> QImage:
    img = QImage(w, h, FMT)
    img.fill(color if color is not None else Qt.GlobalColor.transparent)
    return img


def a_array(img: QImage) -> np.ndarray:
    """Vista de solo lectura (alto, ancho, 4) BGRA premultiplicado."""
    return np.frombuffer(img.constBits(), dtype=np.uint8).reshape(img.height(), img.width(), 4)


def desde_array(arr: np.ndarray) -> QImage:
    arr = np.ascontiguousarray(arr)
    h, w = arr.shape[:2]
    return QImage(arr.data, w, h, w * 4, FMT).copy()


def _png(img: QImage) -> bytes:
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    buf.close()
    return bytes(ba.data())


class Capa:
    def __init__(self, nombre: str, w: int, h: int, relleno_color=None):
        self.uid = next(_uid)
        self.nombre = nombre
        self.visible = True
        self.opacidad = 1.0
        self.modo = "Normal"
        self.bloqueada = False
        self.cels: dict[int, QImage] = {0: imagen_vacia(w, h, relleno_color)}

    def clave(self, cuadro: int):
        ks = [k for k in self.cels if k <= cuadro]
        return max(ks) if ks else None

    def imagen(self, cuadro: int):
        k = self.clave(cuadro)
        return self.cels[k] if k is not None else None


class Documento:
    def __init__(self, nombre="Sin título", ancho=2000, alto=2000, dpi=350, color_papel=None,
                 animacion=False, fps=12, cuadros=24, modo_color="Color", vacio=False):
        self.nombre, self.ancho, self.alto, self.dpi = nombre, ancho, alto, dpi
        self.animacion, self.fps, self.cuadros = animacion, fps, cuadros
        self.modo_color = modo_color
        self.capas: list[Capa] = []          # de abajo hacia arriba
        self.activa = 0
        self.cuadro = 0
        self.deshacer: list = []
        self.rehacer: list = []
        self.modificado = False
        self.ruta: str | None = None
        self.buffer_trazo: QImage | None = None
        self.trazo_opacidad = 1.0
        if not vacio:
            papel = Capa("Papel", ancho, alto, color_papel or QColor("white"))
            papel.bloqueada = True
            self.capas = [papel, Capa("Capa 1", ancho, alto)]
            self.activa = 1

    # ------------------------------------------------------------ capas
    def capa_activa(self) -> Capa:
        return self.capas[self.activa]

    def nueva_capa(self):
        c = Capa(f"Capa {len(self.capas)}", self.ancho, self.alto)
        self.capas.insert(self.activa + 1, c)
        self.activa += 1
        self.modificado = True

    def duplicar_capa(self):
        o = self.capa_activa()
        c = Capa(o.nombre + " copia", self.ancho, self.alto)
        c.cels = {k: v.copy() for k, v in o.cels.items()}
        c.opacidad, c.modo, c.visible = o.opacidad, o.modo, o.visible
        self.capas.insert(self.activa + 1, c)
        self.activa += 1
        self.modificado = True

    def eliminar_capa(self):
        if len(self.capas) <= 1:
            return
        del self.capas[self.activa]
        self.activa = max(0, self.activa - 1)
        self.modificado = True

    def mover_capa(self, delta: int):
        j = self.activa + delta
        if 0 <= j < len(self.capas):
            self.capas[self.activa], self.capas[j] = self.capas[j], self.capas[self.activa]
            self.activa = j
            self.modificado = True

    def unir_abajo(self):
        if self.activa == 0:
            return
        sup, inf = self.capas[self.activa], self.capas[self.activa - 1]
        img = sup.imagen(self.cuadro)
        if img is not None:
            self.guardar_deshacer(inf, self.cuadro)
            p = QPainter(inf.cels[self.cuadro])
            p.setOpacity(sup.opacidad)
            p.setCompositionMode(MODOS[sup.modo])
            p.drawImage(0, 0, img)
            p.end()
        del self.capas[self.activa]
        self.activa -= 1
        self.modificado = True

    # ----------------------------------------------------------- deshacer
    def guardar_deshacer(self, capa: Capa, cuadro: int) -> QImage:
        """Guarda el estado previo del cel y se asegura de que exista; devuelve el cel editable."""
        previo = capa.cels[cuadro].copy() if cuadro in capa.cels else None
        self.deshacer.append((capa.uid, cuadro, previo))
        if len(self.deshacer) > 20:
            self.deshacer.pop(0)
        self.rehacer.clear()
        if cuadro not in capa.cels:
            capa.cels[cuadro] = imagen_vacia(self.ancho, self.alto)
        self.modificado = True
        return capa.cels[cuadro]

    def _capa_por_uid(self, uid):
        return next((c for c in self.capas if c.uid == uid), None)

    def _aplicar(self, entrada, destino: list):
        uid, cuadro, img = entrada
        capa = self._capa_por_uid(uid)
        if capa is None:
            return
        actual = capa.cels.get(cuadro)
        destino.append((uid, cuadro, actual.copy() if actual is not None else None))
        if img is None:
            capa.cels.pop(cuadro, None)
        else:
            capa.cels[cuadro] = img

    def deshacer_paso(self) -> bool:
        if not self.deshacer:
            return False
        self._aplicar(self.deshacer.pop(), self.rehacer)
        return True

    def rehacer_paso(self) -> bool:
        if not self.rehacer:
            return False
        self._aplicar(self.rehacer.pop(), self.deshacer)
        return True

    # ------------------------------------------------------------ render
    def render(self, cuadro: int | None = None, con_buffer: bool = True) -> QImage:
        c = self.cuadro if cuadro is None else cuadro
        out = imagen_vacia(self.ancho, self.alto)
        p = QPainter(out)
        for i, capa in enumerate(self.capas):
            if capa.visible:
                img = capa.imagen(c)
                if img is not None:
                    p.setOpacity(capa.opacidad)
                    p.setCompositionMode(MODOS[capa.modo])
                    p.drawImage(0, 0, img)
            if con_buffer and self.buffer_trazo is not None and i == self.activa:
                p.setOpacity(self.trazo_opacidad)
                p.setCompositionMode(CM.CompositionMode_SourceOver)
                p.drawImage(0, 0, self.buffer_trazo)
        p.end()
        return out

    # ------------------------------------------------------------- cubeta
    def rellenar(self, capa: Capa, x: int, y: int, color: QColor, tolerancia: int,
                 expandir: int, todas_las_capas: bool) -> bool:
        base = capa.cels.get(self.cuadro)
        base_img = base if base is not None else imagen_vacia(self.ancho, self.alto)
        ref_img = self.render(self.cuadro, False) if todas_las_capas else base_img
        m = relleno.calcular_mascaras(a_array(ref_img), x, y, tolerancia, expandir)
        if m is None:
            return False
        a = color.alpha() / 255.0
        pix = [round(color.blue() * a), round(color.green() * a), round(color.red() * a), color.alpha()]
        nuevo = desde_array(relleno.pintar(a_array(base_img), m[0], m[1], pix))
        self.guardar_deshacer(capa, self.cuadro)
        capa.cels[self.cuadro] = nuevo
        return True

    # ----------------------------------------------------- guardar / abrir
    def guardar(self, ruta: str):
        meta = {
            "version": 1, "nombre": self.nombre, "ancho": self.ancho, "alto": self.alto,
            "dpi": self.dpi, "animacion": self.animacion, "fps": self.fps,
            "cuadros": self.cuadros, "modo_color": self.modo_color, "activa": self.activa,
            "capas": [{"nombre": c.nombre, "visible": c.visible, "opacidad": c.opacidad,
                       "modo": c.modo, "bloqueada": c.bloqueada, "cels": sorted(c.cels)}
                      for c in self.capas],
        }
        with zipfile.ZipFile(ruta, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("proyecto.json", json.dumps(meta, ensure_ascii=False, indent=1))
            for i, c in enumerate(self.capas):
                for k, img in c.cels.items():
                    z.writestr(f"capas/{i}_{k}.png", _png(img))
        self.ruta = ruta
        self.modificado = False

    @classmethod
    def abrir(cls, ruta: str) -> "Documento":
        with zipfile.ZipFile(ruta) as z:
            m = json.loads(z.read("proyecto.json"))
            d = cls(m["nombre"], m["ancho"], m["alto"], m["dpi"], None, m["animacion"],
                    m["fps"], m["cuadros"], m.get("modo_color", "Color"), vacio=True)
            for i, cm in enumerate(m["capas"]):
                c = Capa(cm["nombre"], d.ancho, d.alto)
                c.cels = {}
                for k in cm["cels"]:
                    img = QImage.fromData(z.read(f"capas/{i}_{k}.png")).convertToFormat(FMT)
                    c.cels[int(k)] = img
                c.visible, c.opacidad = cm["visible"], cm["opacidad"]
                c.modo, c.bloqueada = cm["modo"], cm["bloqueada"]
                d.capas.append(c)
            d.activa = min(m.get("activa", 0), len(d.capas) - 1)
        d.ruta = ruta
        return d

    # ---------------------------------------------------------- exportar
    def _cuadros_exportables(self) -> range:
        return range(self.cuadros if self.animacion else 1)

    def exportar_imagen(self, ruta: str, cuadro: int | None = None) -> bool:
        img = self.render(cuadro, False)
        if ruta.lower().endswith((".jpg", ".jpeg")):          # JPG no tiene transparencia
            fondo = QImage(img.size(), QImage.Format.Format_RGB32)
            fondo.fill(Qt.GlobalColor.white)
            p = QPainter(fondo)
            p.drawImage(0, 0, img)
            p.end()
            img = fondo
        return img.save(ruta)

    def exportar_secuencia(self, carpeta: str) -> int:
        n = 0
        for c in self._cuadros_exportables():
            self.exportar_imagen(f"{carpeta}/{self.nombre}_{c + 1:04d}.png", c)
            n += 1
        return n

    def _frames_rgba(self):
        for c in self._cuadros_exportables():
            img = self.render(c, False).convertToFormat(QImage.Format.Format_RGBA8888)
            yield bytes(img.constBits())

    def exportar_gif(self, ruta: str):
        from PIL import Image
        frames = [Image.frombytes("RGBA", (self.ancho, self.alto), b) for b in self._frames_rgba()]
        frames[0].save(ruta, save_all=True, append_images=frames[1:], loop=0,
                       duration=max(1, round(1000 / self.fps)), disposal=2)

    def exportar_mp4(self, ruta: str):
        import imageio.v2 as iio
        ancho, alto = self.ancho - self.ancho % 2, self.alto - self.alto % 2   # H.264 pide medidas pares
        with iio.get_writer(ruta, fps=self.fps, codec="libx264", quality=8, macro_block_size=1) as w:
            for b in self._frames_rgba():
                arr = np.frombuffer(b, np.uint8).reshape(self.alto, self.ancho, 4)[:alto, :ancho, :3]
                w.append_data(arr)
