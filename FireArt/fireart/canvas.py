"""Lienzo de FireArt: vista (zoom/rotación/desplazamiento), motor de pincel y herramientas."""
from __future__ import annotations

import math

from PySide6.QtCore import QEvent, QPointF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QPixmap, QRadialGradient, QTransform
from PySide6.QtWidgets import QWidget

from .core import CM, Documento, imagen_vacia

HERRAMIENTAS_DIBUJO = ("dibujo", "borrador")


class Ajustes:
    """Parámetros de la herramienta activa (los edita el panel «Ajustes de herramienta»)."""
    def __init__(self):
        self.herramienta = "dibujo"      # dibujo, borrador, cubeta, cuentagotas, mano, zoom, rotar
        self.color = QColor("#000000")
        self.tamano = 10.0
        self.opacidad = 1.0
        self.dureza = 1.0
        self.estabilizador = 20          # 0-100
        self.espaciado = 0.08            # fracción del diámetro
        self.presion_tamano = True
        self.presion_opacidad = False
        self.tamano_min = 0.1            # fracción del tamaño con presión mínima
        self.curva_presion = 1.0         # <1 más sensible, >1 más firme
        self.tolerancia = 20
        self.expandir = 1
        self.referenciar = False

    def aplicar(self, d: dict):
        for k, v in d.items():
            setattr(self, k, v)


class Lienzo(QWidget):
    vista_cambiada = Signal()
    documento_modificado = Signal()
    color_tomado = Signal(QColor)
    mensaje = Signal(str)

    def __init__(self, ajustes: Ajustes, parent=None):
        super().__init__(parent)
        self.aj = ajustes
        self.doc: Documento | None = None
        self.zoom, self.angulo, self.espejo = 1.0, 0.0, False
        self.pan = QPointF(0, 0)
        self.cebolla = False
        self.cebolla_antes, self.cebolla_despues = 1, 1
        self._cache = None
        self._modo = None
        self._espacio = False
        self._raton = None
        self._cache_tinte: dict = {}
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(300, 300)
        damero = QPixmap(16, 16)
        damero.fill(QColor("#ffffff"))
        pp = QPainter(damero)
        pp.fillRect(0, 0, 8, 8, QColor("#cfcfcf"))
        pp.fillRect(8, 8, 8, 8, QColor("#cfcfcf"))
        pp.end()
        self._damero = QBrush(damero)

    # ----------------------------------------------------------- herramienta
    CURSORES = {"mano": Qt.CursorShape.OpenHandCursor, "zoom": Qt.CursorShape.PointingHandCursor,
                "rotar": Qt.CursorShape.SizeHorCursor, "cubeta": Qt.CursorShape.PointingHandCursor}

    def usar_herramienta(self, nombre: str):
        self.aj.herramienta = nombre
        self.setCursor(self.CURSORES.get(nombre, Qt.CursorShape.CrossCursor))
        self.update()

    # ------------------------------------------------------------ documento
    def set_documento(self, doc: Documento | None):
        self.doc = doc
        self._cache = None
        if doc:
            self.ajustar()
        self.update()

    def refrescar(self):
        self._cache = None
        self.update()

    # ----------------------------------------------------------------- vista
    def _xf(self) -> QTransform:
        t = QTransform()
        t.translate(self.width() / 2 + self.pan.x(), self.height() / 2 + self.pan.y())
        t.rotate(self.angulo)
        t.scale(-self.zoom if self.espejo else self.zoom, self.zoom)
        t.translate(-self.doc.ancho / 2, -self.doc.alto / 2)
        return t

    def a_doc(self, pos) -> QPointF:
        inv, _ = self._xf().inverted()
        return inv.map(QPointF(pos))

    def ajustar(self):
        if not self.doc:
            return
        self.zoom = max(0.02, min(self.width() / self.doc.ancho, self.height() / self.doc.alto) * 0.92)
        self.pan, self.angulo = QPointF(0, 0), 0.0
        self.vista_cambiada.emit()
        self.update()

    def zoom_en(self, factor: float, centro: QPointF | None = None):
        if not self.doc:
            return
        centro = centro or QPointF(self.width() / 2, self.height() / 2)
        antes = self.a_doc(centro)
        self.zoom = max(0.02, min(32.0, self.zoom * factor))
        despues = self._xf().map(antes)
        self.pan = self.pan + (centro - despues)
        self.vista_cambiada.emit()
        self.update()

    def fijar_zoom(self, z: float):
        self.zoom_en(z / self.zoom)

    def fijar_angulo(self, a: float):
        self.angulo = a % 360
        self.vista_cambiada.emit()
        self.update()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.vista_cambiada.emit()

    # --------------------------------------------------------------- dibujo
    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#2f2f2f"))
        if not self.doc:
            p.setPen(QColor("#9a9a9a"))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       "Archivo ▸ Nuevo (Ctrl+N) para crear un lienzo")
            return
        d = self.doc
        if self._cache is None:
            self._cache = d.render()
        p.setTransform(self._xf())
        p.fillRect(0, 0, d.ancho, d.alto, self._damero)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, self.zoom < 1 or self.angulo != 0)
        p.drawImage(0, 0, self._cache)
        if self.cebolla and d.animacion:
            self._pintar_cebolla(p)
        p.setPen(QPen(QColor(0, 0, 0, 160), 0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(0, 0, d.ancho, d.alto)
        p.resetTransform()
        if self._raton is not None and self.aj.herramienta in HERRAMIENTAS_DIBUJO and self._modo != "pan":
            r = max(1.0, self.aj.tamano * self.zoom / 2)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setPen(QPen(QColor(255, 255, 255, 220), 1))
            p.drawEllipse(self._raton, r + 1, r + 1)
            p.setPen(QPen(QColor(0, 0, 0, 220), 1))
            p.drawEllipse(self._raton, r, r)

    def _pintar_cebolla(self, p: QPainter):
        capa = self.doc.capa_activa()
        actual = capa.imagen(self.doc.cuadro)
        for delta, color in [(-i, QColor(255, 60, 60)) for i in range(1, self.cebolla_antes + 1)] + \
                            [(i, QColor(60, 140, 255)) for i in range(1, self.cebolla_despues + 1)]:
            c = self.doc.cuadro + delta
            if c < 0 or c >= self.doc.cuadros:
                continue
            img = capa.imagen(c)
            if img is None or img is actual:
                continue
            clave = (img.cacheKey(), color.rgb())
            tinte = self._cache_tinte.get(clave)
            if tinte is None:
                tinte = img.copy()
                q = QPainter(tinte)
                q.setCompositionMode(CM.CompositionMode_SourceIn)
                q.fillRect(tinte.rect(), color)
                q.end()
                if len(self._cache_tinte) > 12:
                    self._cache_tinte.clear()
                self._cache_tinte[clave] = tinte
            p.setOpacity(0.45)
            p.drawImage(0, 0, tinte)
        p.setOpacity(1.0)

    # ------------------------------------------------------ entrada: ratón
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.MiddleButton:
            self._ult = e.position()
            self._modo = "pan"
        elif e.button() == Qt.MouseButton.LeftButton:
            self._inicio(e.position(), 1.0, e.modifiers())

    def mouseMoveEvent(self, e):
        self._raton = e.position()
        self._mover(e.position(), 1.0)

    def mouseReleaseEvent(self, e):
        self._fin()

    def leaveEvent(self, _):
        self._raton = None
        self.update()

    def wheelEvent(self, e):
        d = e.angleDelta().y()
        if d:
            self.zoom_en(1.15 ** (d / 120), e.position())

    # --------------------------------------------------- entrada: tableta
    def tabletEvent(self, e):
        t, pos, pr = e.type(), e.position(), e.pressure()
        self._raton = pos
        if t == QEvent.Type.TabletPress:
            self._inicio(pos, pr, e.modifiers())
        elif t == QEvent.Type.TabletMove:
            self._mover(pos, pr)
        elif t == QEvent.Type.TabletRelease:
            self._fin()
        e.accept()

    # ------------------------------------------------------------- teclado
    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Space and not e.isAutoRepeat():
            self._espacio = True
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            super().keyPressEvent(e)

    def keyReleaseEvent(self, e):
        if e.key() == Qt.Key.Key_Space and not e.isAutoRepeat():
            self._espacio = False
            self.usar_herramienta(self.aj.herramienta)
        else:
            super().keyReleaseEvent(e)

    # ---------------------------------------------------- lógica de punteros
    def _presion(self, pr: float) -> float:
        return max(0.0, min(1.0, pr)) ** self.aj.curva_presion

    def _inicio(self, pos: QPointF, pr: float, mods):
        if not self.doc:
            return
        h = self.aj.herramienta
        self._ult = pos
        if self._espacio or h == "mano":
            self._modo = "pan"
            return
        if h == "rotar":
            self._modo = "rotar"
            return
        if h == "zoom":
            self.zoom_en(1 / 1.3 if mods & Qt.KeyboardModifier.AltModifier else 1.3, pos)
            return
        d = self.doc
        p = self.a_doc(pos)
        if h == "cuentagotas":
            img = d.render(None, False)
            x, y = int(p.x()), int(p.y())
            if 0 <= x < d.ancho and 0 <= y < d.alto:
                self.color_tomado.emit(img.pixelColor(x, y))
            return
        capa = d.capa_activa()
        if capa.bloqueada or not capa.visible:
            self.mensaje.emit("La capa está bloqueada u oculta.")
            return
        if h == "cubeta":
            ok = d.rellenar(capa, int(p.x()), int(p.y()), self.aj.color, self.aj.tolerancia,
                            self.aj.expandir, self.aj.referenciar)
            if ok:
                self.refrescar()
                self.documento_modificado.emit()
            return
        # --- dibujo / borrador
        cel = d.guardar_deshacer(capa, d.cuadro)
        self._modo = "trazo"
        if h == "borrador":
            self._destino, self._cm = cel, CM.CompositionMode_DestinationOut
        else:
            d.buffer_trazo = imagen_vacia(d.ancho, d.alto)
            d.trazo_opacidad = self.aj.opacidad
            self._destino, self._cm = d.buffer_trazo, CM.CompositionMode_SourceOver
        self._cel = cel
        self._suave, self._pr_suave = p, self._presion(pr)
        self._resto = 0.0
        self._sello(p, self._pr_suave)
        self._resto = self._paso()
        self._tras_trazo()

    def _mover(self, pos: QPointF, pr: float):
        if self._modo is None:
            self.update()
            return
        if self._modo == "pan":
            self.pan = self.pan + (pos - self._ult)
            self._ult = pos
            self.update()
        elif self._modo == "rotar":
            self.fijar_angulo(self.angulo + (pos.x() - self._ult.x()) * 0.3)
            self._ult = pos
        elif self._modo == "trazo":
            s = self.aj.estabilizador / 100.0 * 0.92
            crudo, prc = self.a_doc(pos), self._presion(pr)
            nuevo = QPointF(self._suave.x() + (crudo.x() - self._suave.x()) * (1 - s),
                            self._suave.y() + (crudo.y() - self._suave.y()) * (1 - s))
            npr = self._pr_suave + (prc - self._pr_suave) * (1 - s * 0.5)
            self._segmento(self._suave, self._pr_suave, nuevo, npr)
            self._suave, self._pr_suave = nuevo, npr
            self._tras_trazo()

    def _fin(self):
        if self._modo == "trazo":
            d = self.doc
            if d.buffer_trazo is not None:
                p = QPainter(self._cel)
                p.setOpacity(self.aj.opacidad)
                p.drawImage(0, 0, d.buffer_trazo)
                p.end()
                d.buffer_trazo = None
            self.refrescar()
            self.documento_modificado.emit()
        self._modo = None
        self.update()

    def _tras_trazo(self):
        self._cache = None
        self.update()

    # ------------------------------------------------------------ pincel
    def _paso(self) -> float:
        return max(0.6, self.aj.tamano * self.aj.espaciado)

    def _segmento(self, a: QPointF, pa: float, b: QPointF, pb: float):
        dist = math.hypot(b.x() - a.x(), b.y() - a.y())
        if dist == 0:
            return
        paso, pos = self._paso(), self._resto
        while pos <= dist:
            t = pos / dist
            self._sello(QPointF(a.x() + (b.x() - a.x()) * t, a.y() + (b.y() - a.y()) * t), pa + (pb - pa) * t)
            pos += paso
        self._resto = pos - dist

    def _sello(self, c: QPointF, pr: float):
        aj = self.aj
        diam = aj.tamano * (aj.tamano_min + (1 - aj.tamano_min) * pr) if aj.presion_tamano else aj.tamano
        diam = max(0.5, diam)
        alfa = pr if aj.presion_opacidad else 1.0
        if aj.herramienta == "borrador":
            alfa *= aj.opacidad
        col = QColor(aj.color if aj.herramienta != "borrador" else QColor("black"))
        col.setAlphaF(max(0.0, min(1.0, alfa)))
        r = diam / 2
        p = QPainter(self._destino)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setCompositionMode(self._cm)
        p.setPen(Qt.PenStyle.NoPen)
        if aj.dureza >= 0.98 or diam < 3:
            p.setBrush(col)
        else:
            g = QRadialGradient(c, r)
            transparente = QColor(col)
            transparente.setAlpha(0)
            g.setColorAt(0, col)
            g.setColorAt(max(0.01, aj.dureza), col)
            g.setColorAt(1, transparente)
            p.setBrush(QBrush(g))
        p.drawEllipse(c, r, r)
        p.end()
