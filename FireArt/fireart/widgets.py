"""Paneles de la interfaz: color, navegador, capas, línea de tiempo y ajustes de herramienta."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QLinearGradient, QPainter,
                           QPainterPath, QPen, QPixmap)
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGridLayout,
                               QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton,
                               QScrollArea, QSlider, QSpinBox, QToolButton, QVBoxLayout, QWidget)

from .core import MODOS, Documento

# Presets de pinceles (nombre, ajustes) por grupo de herramienta
PRESETS = {
    "dibujo": [
        ("Pluma G", dict(tamano=10, opacidad=1.0, dureza=1.0, estabilizador=20, espaciado=0.08,
                         presion_tamano=True, presion_opacidad=False, tamano_min=0.1)),
        ("Lápiz", dict(tamano=6, opacidad=0.9, dureza=0.85, estabilizador=5, espaciado=0.12,
                       presion_tamano=True, presion_opacidad=True, tamano_min=0.2)),
        ("Pincel suave", dict(tamano=30, opacidad=0.8, dureza=0.3, estabilizador=10, espaciado=0.1,
                              presion_tamano=True, presion_opacidad=True, tamano_min=0.3)),
        ("Aerógrafo", dict(tamano=60, opacidad=0.35, dureza=0.0, estabilizador=0, espaciado=0.05,
                           presion_tamano=False, presion_opacidad=True, tamano_min=0.5)),
        ("Rotulador", dict(tamano=14, opacidad=1.0, dureza=1.0, estabilizador=0, espaciado=0.1,
                           presion_tamano=False, presion_opacidad=False, tamano_min=1.0)),
    ],
    "borrador": [
        ("Borrador duro", dict(tamano=20, opacidad=1.0, dureza=1.0, estabilizador=0, espaciado=0.08,
                               presion_tamano=True, presion_opacidad=False, tamano_min=0.2)),
        ("Borrador suave", dict(tamano=40, opacidad=0.8, dureza=0.3, estabilizador=0, espaciado=0.08,
                                presion_tamano=True, presion_opacidad=True, tamano_min=0.3)),
    ],
    "cubeta": [
        ("Rellenar color vecino", dict(tolerancia=20, expandir=1, referenciar=False)),
        ("Rellenar usando todas las capas", dict(tolerancia=20, expandir=1, referenciar=True)),
    ],
}
TAMANOS = [0.7, 1, 1.5, 2, 2.5, 3, 4, 5, 6, 7, 8, 10, 12, 15, 17, 20, 25, 30, 40, 50]


def _limitar(v, a, b):
    return max(a, min(b, v))


# ------------------------------------------------------------------ color
class RuedaColor(QWidget):
    cambiado = Signal(QColor)

    def __init__(self):
        super().__init__()
        self.setFixedSize(176, 176)
        self.h = self.s = self.v = 0.0
        self._arrastre = None

    def set_color(self, c: QColor):
        h, s, v, _ = c.getHsvF()
        self.h = h if h >= 0 else self.h
        self.s, self.v = s, v
        self.update()

    def color(self) -> QColor:
        return QColor.fromHsvF(self.h % 1.0, self.s, self.v)

    def _geo(self):
        c = QPointF(self.width() / 2, self.height() / 2)
        R = min(self.width(), self.height()) / 2 - 2
        r_in = R * 0.78
        return c, R, r_in, r_in / math.sqrt(2) * 0.97

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c, R, r_in, mitad = self._geo()
        g = QConicalGradient(c, 0)
        for i in range(13):
            g.setColorAt(i / 12, QColor.fromHsvF((i % 12) / 12, 1, 1))
        aro = QPainterPath()
        aro.addEllipse(c, R, R)
        aro.addEllipse(c, r_in, r_in)
        p.fillPath(aro, QBrush(g))
        cuad = QRectF(c.x() - mitad, c.y() - mitad, 2 * mitad, 2 * mitad)
        p.fillRect(cuad, QColor.fromHsvF(self.h % 1.0, 1, 1))
        gb = QLinearGradient(cuad.left(), 0, cuad.right(), 0)
        gb.setColorAt(0, QColor(255, 255, 255, 255))
        gb.setColorAt(1, QColor(255, 255, 255, 0))
        p.fillRect(cuad, gb)
        gn = QLinearGradient(0, cuad.top(), 0, cuad.bottom())
        gn.setColorAt(0, QColor(0, 0, 0, 0))
        gn.setColorAt(1, QColor(0, 0, 0, 255))
        p.fillRect(cuad, gn)
        a = self.h * 2 * math.pi
        rm = (R + r_in) / 2
        puntos = [QPointF(c.x() + rm * math.cos(a), c.y() - rm * math.sin(a)),
                  QPointF(cuad.left() + self.s * cuad.width(), cuad.top() + (1 - self.v) * cuad.height())]
        for q in puntos:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor("black"), 3))
            p.drawEllipse(q, 6, 6)
            p.setPen(QPen(QColor("white"), 1.5))
            p.drawEllipse(q, 6, 6)

    def _elegir(self, pos, inicio):
        c, R, r_in, mitad = self._geo()
        dx, dy = pos.x() - c.x(), pos.y() - c.y()
        if inicio:
            self._arrastre = "aro" if math.hypot(dx, dy) >= r_in * 0.98 else "cuadro"
        if self._arrastre == "aro":
            self.h = (math.atan2(-dy, dx) / (2 * math.pi)) % 1.0
        else:
            self.s = _limitar((pos.x() - (c.x() - mitad)) / (2 * mitad), 0, 1)
            self.v = 1 - _limitar((pos.y() - (c.y() - mitad)) / (2 * mitad), 0, 1)
        self.update()
        self.cambiado.emit(self.color())

    def mousePressEvent(self, e):
        self._elegir(e.position(), True)

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.MouseButton.LeftButton:
            self._elegir(e.position(), False)


# -------------------------------------------------------------- navegador
class Navegador(QWidget):
    def __init__(self, lienzo):
        super().__init__()
        self.lienzo = lienzo
        v = QVBoxLayout(self)
        v.setContentsMargins(6, 6, 6, 6)
        self.mini = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.mini.setFixedHeight(130)
        self.mini.setStyleSheet("background:#3a3a3a;")
        v.addWidget(self.mini)
        self.s_zoom = QSlider(Qt.Orientation.Horizontal)
        self.s_zoom.setRange(0, 1000)
        self.s_rot = QSlider(Qt.Orientation.Horizontal)
        self.s_rot.setRange(-180, 180)
        self.l_zoom, self.l_rot = QLabel("100%"), QLabel("0°")
        g = QGridLayout()
        g.addWidget(QLabel("Zoom"), 0, 0)
        g.addWidget(self.s_zoom, 0, 1)
        g.addWidget(self.l_zoom, 0, 2)
        g.addWidget(QLabel("Giro"), 1, 0)
        g.addWidget(self.s_rot, 1, 1)
        g.addWidget(self.l_rot, 1, 2)
        v.addLayout(g)
        fila = QHBoxLayout()
        for txt, tip, fn in [("Ajustar", "Ajustar a la ventana", lienzo.ajustar),
                             ("100%", "Tamaño real", lambda: lienzo.fijar_zoom(1.0)),
                             ("0°", "Restablecer giro", lambda: lienzo.fijar_angulo(0)),
                             ("⇋", "Voltear vista", self._espejo)]:
            b = QToolButton()
            b.setText(txt)
            b.setToolTip(tip)
            b.clicked.connect(fn)
            fila.addWidget(b)
        v.addLayout(fila)
        self.s_zoom.valueChanged.connect(lambda x: lienzo.fijar_zoom(0.02 * 1600 ** (x / 1000)))
        self.s_rot.valueChanged.connect(lambda x: lienzo.fijar_angulo(x))
        lienzo.vista_cambiada.connect(self.sincronizar)
        self._t = QTimer(self)
        self._t.setSingleShot(True)
        self._t.timeout.connect(self._miniatura)

    def _espejo(self):
        self.lienzo.espejo = not self.lienzo.espejo
        self.lienzo.update()

    def sincronizar(self):
        z, a = self.lienzo.zoom, self.lienzo.angulo
        for w in (self.s_zoom, self.s_rot):
            w.blockSignals(True)
        self.s_zoom.setValue(int(1000 * math.log(max(z, 0.02) / 0.02) / math.log(1600)))
        self.s_rot.setValue(int(a if a <= 180 else a - 360))
        for w in (self.s_zoom, self.s_rot):
            w.blockSignals(False)
        self.l_zoom.setText(f"{z * 100:.1f}%")
        self.l_rot.setText(f"{a if a <= 180 else a - 360:.0f}°")

    def miniatura(self):
        self._t.start(250)

    def _miniatura(self):
        d = self.lienzo.doc
        if not d:
            self.mini.clear()
            return
        img = d.render(None, False).scaled(260, 124, Qt.AspectRatioMode.KeepAspectRatio,
                                           Qt.TransformationMode.SmoothTransformation)
        self.mini.setPixmap(QPixmap.fromImage(img))


# ------------------------------------------------------------------ capas
class PanelCapas(QWidget):
    cambiado = Signal()       # algo que afecta a la imagen
    seleccion = Signal()      # cambió la capa activa

    def __init__(self):
        super().__init__()
        self.doc: Documento | None = None
        v = QVBoxLayout(self)
        v.setContentsMargins(4, 4, 4, 4)
        f1 = QHBoxLayout()
        self.modo = QComboBox()
        self.modo.addItems(list(MODOS))
        self.bloq = QCheckBox("Bloquear")
        f1.addWidget(self.modo, 1)
        f1.addWidget(self.bloq)
        v.addLayout(f1)
        f2 = QHBoxLayout()
        self.op = QSlider(Qt.Orientation.Horizontal)
        self.op.setRange(0, 100)
        self.op.setValue(100)
        self.op_l = QLabel("100%")
        f2.addWidget(QLabel("Opacidad"))
        f2.addWidget(self.op, 1)
        f2.addWidget(self.op_l)
        v.addLayout(f2)
        self.lista = QListWidget()
        v.addWidget(self.lista, 1)
        f3 = QHBoxLayout()
        for txt, tip, fn in [("＋", "Nueva capa raster", self._nueva), ("⧉", "Duplicar capa", self._dup),
                             ("⤓", "Unir con la capa inferior", self._unir), ("▲", "Subir capa", lambda: self._mover(1)),
                             ("▼", "Bajar capa", lambda: self._mover(-1)), ("✕", "Eliminar capa", self._del)]:
            b = QToolButton()
            b.setText(txt)
            b.setToolTip(tip)
            b.clicked.connect(fn)
            f3.addWidget(b)
        v.addLayout(f3)
        self.lista.currentRowChanged.connect(self._fila)
        self.lista.itemChanged.connect(self._item)
        self.modo.currentTextChanged.connect(self._prop_modo)
        self.op.valueChanged.connect(self._prop_op)
        self.bloq.toggled.connect(self._prop_bloq)

    def set_documento(self, doc):
        self.doc = doc
        self.refrescar()

    def refrescar(self):
        self.lista.blockSignals(True)
        self.lista.clear()
        if self.doc:
            for i in reversed(range(len(self.doc.capas))):
                c = self.doc.capas[i]
                it = QListWidgetItem(c.nombre)
                it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEditable)
                it.setCheckState(Qt.CheckState.Checked if c.visible else Qt.CheckState.Unchecked)
                it.setData(Qt.ItemDataRole.UserRole, c.uid)
                self.lista.addItem(it)
            self.lista.setCurrentRow(len(self.doc.capas) - 1 - self.doc.activa)
        self.lista.blockSignals(False)
        self._sincronizar_props()

    def _sincronizar_props(self):
        for w in (self.modo, self.op, self.bloq):
            w.blockSignals(True)
        if self.doc:
            c = self.doc.capa_activa()
            self.modo.setCurrentText(c.modo)
            self.op.setValue(round(c.opacidad * 100))
            self.op_l.setText(f"{round(c.opacidad * 100)}%")
            self.bloq.setChecked(c.bloqueada)
        for w in (self.modo, self.op, self.bloq):
            w.blockSignals(False)

    def _fila(self, r):
        if self.doc and r >= 0:
            self.doc.activa = len(self.doc.capas) - 1 - r
            self._sincronizar_props()
            self.seleccion.emit()

    def _item(self, it):
        if not self.doc:
            return
        uid = it.data(Qt.ItemDataRole.UserRole)
        c = next((x for x in self.doc.capas if x.uid == uid), None)
        if c:
            c.nombre = it.text()
            c.visible = it.checkState() == Qt.CheckState.Checked
            self.cambiado.emit()

    def _prop_modo(self, t):
        if self.doc:
            self.doc.capa_activa().modo = t
            self.cambiado.emit()

    def _prop_op(self, x):
        if self.doc:
            self.doc.capa_activa().opacidad = x / 100
            self.op_l.setText(f"{x}%")
            self.cambiado.emit()

    def _prop_bloq(self, b):
        if self.doc:
            self.doc.capa_activa().bloqueada = b

    def _accion(self, fn):
        if self.doc:
            fn()
            self.refrescar()
            self.cambiado.emit()
            self.seleccion.emit()

    def _nueva(self): self._accion(lambda: self.doc.nueva_capa())
    def _dup(self): self._accion(lambda: self.doc.duplicar_capa())
    def _del(self): self._accion(lambda: self.doc.eliminar_capa())
    def _unir(self): self._accion(lambda: self.doc.unir_abajo())
    def _mover(self, d): self._accion(lambda: self.doc.mover_capa(d))


# ---------------------------------------------------------- línea de tiempo
class Rejilla(QWidget):
    elegido = Signal(int, int)     # cuadro, índice de capa
    NOMBRE, CW, RH = 120, 16, 20

    def __init__(self):
        super().__init__()
        self.doc: Documento | None = None

    def set_documento(self, doc):
        self.doc = doc
        self.reajustar()

    def reajustar(self):
        if self.doc:
            self.setFixedSize(self.NOMBRE + self.doc.cuadros * self.CW + 4,
                              (len(self.doc.capas) + 1) * self.RH + 2)
        self.update()

    def paintEvent(self, _):
        if not self.doc:
            return
        d, N, W, H = self.doc, self.NOMBRE, self.CW, self.RH
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#2b2b2b"))
        p.setPen(QColor("#aaaaaa"))
        for c in range(d.cuadros):
            if c == 0 or (c + 1) % 5 == 0:
                p.drawText(QRectF(N + c * W, 0, W, H), Qt.AlignmentFlag.AlignCenter, str(c + 1))
        n = len(d.capas)
        for fila in range(n):
            i = n - 1 - fila
            capa, y = d.capas[i], (fila + 1) * H
            if i == d.activa:
                p.fillRect(0, y, self.width(), H, QColor("#3d5a80"))
            p.setPen(QColor("#dddddd"))
            p.drawText(QRectF(6, y, N - 8, H), Qt.AlignmentFlag.AlignVCenter, capa.nombre)
            for c in range(d.cuadros):
                x = N + c * W
                p.setPen(QPen(QColor("#444444"), 1))
                p.drawRect(x, y, W, H)
                if c in capa.cels:
                    p.setBrush(QColor("#ffffff"))
                    p.setPen(QPen(QColor("#000000"), 1))
                    p.drawEllipse(QPointF(x + W / 2, y + H / 2), 4, 4)
                    p.setBrush(Qt.BrushStyle.NoBrush)
        p.fillRect(N + d.cuadro * W, 0, W, self.height(), QColor(255, 80, 80, 60))
        p.setPen(QPen(QColor("#ff5050"), 2))
        p.drawLine(N + d.cuadro * W + W // 2, 0, N + d.cuadro * W + W // 2, self.height())

    def _clic(self, e):
        if not self.doc:
            return
        x, y = e.position().x(), e.position().y()
        if x >= self.NOMBRE:
            c = int((x - self.NOMBRE) // self.CW)
            fila = int(y // self.RH) - 1
            idx = len(self.doc.capas) - 1 - fila if fila >= 0 else self.doc.activa
            if 0 <= idx < len(self.doc.capas):
                self.elegido.emit(max(0, min(self.doc.cuadros - 1, c)), idx)

    mousePressEvent = _clic
    mouseMoveEvent = _clic


class LineaTiempo(QWidget):
    cuadro_cambiado = Signal()
    cebolla_cambiada = Signal(bool)
    capa_elegida = Signal()

    def __init__(self):
        super().__init__()
        self.doc: Documento | None = None
        v = QVBoxLayout(self)
        v.setContentsMargins(4, 4, 4, 4)
        f = QHBoxLayout()
        self.b_play = QPushButton("▶ Reproducir")
        botones = [("|◀", "Primer cuadro", lambda: self.ir_a(0)), ("◀", "Cuadro anterior", lambda: self.paso(-1)),
                   None, ("▶", "Cuadro siguiente", lambda: self.paso(1)),
                   ("▶|", "Último cuadro", lambda: self.ir_a(self.doc.cuadros - 1 if self.doc else 0))]
        for b in botones:
            if b is None:
                f.addWidget(self.b_play)
                continue
            w = QToolButton()
            w.setText(b[0])
            w.setToolTip(b[1])
            w.clicked.connect(b[2])
            f.addWidget(w)
        self.fps = QSpinBox()
        self.fps.setRange(1, 60)
        self.fps.setSuffix(" fps")
        self.cuadros = QSpinBox()
        self.cuadros.setRange(1, 2000)
        self.cuadros.setSuffix(" cuadros")
        self.chk = QCheckBox("Papel cebolla")
        self.info = QLabel("Cuadro 1 / 24")
        for w in (self.fps, self.cuadros, self.chk):
            f.addWidget(w)
        f.addStretch(1)
        f.addWidget(self.info)
        v.addLayout(f)
        self.rejilla = Rejilla()
        sc = QScrollArea()
        sc.setWidget(self.rejilla)
        v.addWidget(sc, 1)
        self.timer = QTimer(self)
        self.timer.timeout.connect(lambda: self.paso(1, True))
        self.b_play.clicked.connect(self.alternar_reproduccion)
        self.fps.valueChanged.connect(self._cambia_fps)
        self.cuadros.valueChanged.connect(self._cambia_cuadros)
        self.chk.toggled.connect(self.cebolla_cambiada)
        self.rejilla.elegido.connect(self._elegido)

    def set_documento(self, doc):
        self.detener()
        self.doc = doc
        if doc:
            for w, val in ((self.fps, doc.fps), (self.cuadros, doc.cuadros)):
                w.blockSignals(True)
                w.setValue(val)
                w.blockSignals(False)
        self.rejilla.set_documento(doc)
        self._info()

    def refrescar(self):
        self.rejilla.reajustar()
        self._info()

    def _info(self):
        if self.doc:
            self.info.setText(f"Cuadro {self.doc.cuadro + 1} / {self.doc.cuadros}")

    def _elegido(self, cuadro, capa):
        if self.doc:
            self.doc.activa = capa
            self.capa_elegida.emit()
            self.ir_a(cuadro)

    def ir_a(self, c: int):
        if self.doc:
            self.doc.cuadro = max(0, min(self.doc.cuadros - 1, c))
            self._info()
            self.rejilla.update()
            self.cuadro_cambiado.emit()

    def paso(self, d: int, ciclo=False):
        if not self.doc:
            return
        n = self.doc.cuadro + d
        self.ir_a(n % self.doc.cuadros if ciclo else n)

    def alternar_reproduccion(self):
        if self.timer.isActive():
            self.detener()
        elif self.doc:
            self.timer.start(round(1000 / self.doc.fps))
            self.b_play.setText("■ Detener")

    def detener(self):
        self.timer.stop()
        self.b_play.setText("▶ Reproducir")

    def _cambia_fps(self, v):
        if self.doc:
            self.doc.fps = v
            if self.timer.isActive():
                self.timer.start(round(1000 / v))

    def _cambia_cuadros(self, v):
        if self.doc:
            self.doc.cuadros = v
            self.doc.cuadro = min(self.doc.cuadro, v - 1)
            self.refrescar()
            self.cuadro_cambiado.emit()


# ------------------------------------------------- ajustes de herramienta
class PanelAjustes(QWidget):
    def __init__(self, ajustes):
        super().__init__()
        self.aj = ajustes
        self.filas: list[tuple] = []     # (etiqueta, campo, grupo)
        self.campos: dict = {}           # attr -> (widget, escala, tipo)
        self.form = QFormLayout(self)
        self.form.setContentsMargins(6, 6, 6, 6)
        self._spin("tamano", "Tamaño", 0.5, 500, 1, " px", 1, float, "pincel")
        self._spin("opacidad", "Opacidad", 1, 100, 0, " %", 100, float, "pincel")
        self._spin("dureza", "Dureza", 0, 100, 0, " %", 100, float, "pincel")
        self._spin("estabilizador", "Estabilizador", 0, 100, 0, "", 1, int, "pincel")
        self._spin("espaciado", "Espaciado", 1, 100, 0, " %", 100, float, "pincel")
        self._check("presion_tamano", "Presión → tamaño", "pincel")
        self._check("presion_opacidad", "Presión → opacidad", "pincel")
        self._spin("tamano_min", "Tamaño mínimo", 0, 100, 0, " %", 100, float, "pincel")
        self._spin("curva_presion", "Curva de presión", 0.3, 3.0, 2, "", 1, float, "pincel")
        self._spin("tolerancia", "Tolerancia", 0, 255, 0, "", 1, int, "relleno")
        self._spin("expandir", "Expandir relleno", 0, 10, 0, " px", 1, int, "relleno")
        self._check("referenciar", "Referenciar todas las capas", "relleno")
        self.cargar()

    def _agregar(self, texto, campo, grupo):
        et = QLabel(texto)
        self.form.addRow(et, campo)
        self.filas.append((et, campo, grupo))

    def _spin(self, attr, texto, mn, mx, dec, suf, escala, tipo, grupo):
        w = QDoubleSpinBox()
        w.setRange(mn, mx)
        w.setDecimals(dec)
        w.setSuffix(suf)
        w.valueChanged.connect(lambda v, a=attr, e=escala, t=tipo: setattr(self.aj, a, t(v / e)))
        self.campos[attr] = (w, escala, tipo)
        self._agregar(texto, w, grupo)

    def _check(self, attr, texto, grupo):
        w = QCheckBox()
        w.setText("")
        w.toggled.connect(lambda b, a=attr: setattr(self.aj, a, b))
        self.campos[attr] = (w, None, bool)
        self._agregar(texto, w, grupo)

    def cargar(self):
        for attr, (w, escala, _) in self.campos.items():
            w.blockSignals(True)
            val = getattr(self.aj, attr)
            if escala is None:
                w.setChecked(bool(val))
            else:
                w.setValue(val * escala)
            w.blockSignals(False)

    def mostrar_para(self, herramienta: str):
        grupo = {"dibujo": "pincel", "borrador": "pincel", "cubeta": "relleno"}.get(herramienta)
        for et, campo, g in self.filas:
            et.setVisible(g == grupo)
            campo.setVisible(g == grupo)


class ListaSub(QListWidget):
    elegido = Signal(dict)

    def __init__(self):
        super().__init__()
        self._grupo = None
        self.currentRowChanged.connect(self._fila)

    def set_grupo(self, grupo: str):
        self._grupo = grupo
        self.blockSignals(True)
        self.clear()
        for nombre, _ in PRESETS.get(grupo, []):
            self.addItem(nombre)
        self.blockSignals(False)
        if self.count():
            self.setCurrentRow(0)

    def _fila(self, r):
        lista = PRESETS.get(self._grupo, [])
        if 0 <= r < len(lista):
            self.elegido.emit(lista[r][1])


class PaletaTamano(QWidget):
    elegido = Signal(float)

    def __init__(self):
        super().__init__()
        g = QGridLayout(self)
        g.setContentsMargins(4, 4, 4, 4)
        g.setSpacing(2)
        for i, t in enumerate(TAMANOS):
            b = QToolButton()
            b.setText(f"{t:g}")
            b.setFixedSize(QSize(38, 26))
            b.clicked.connect(lambda _=False, v=t: self.elegido.emit(float(v)))
            g.addWidget(b, i // 4, i % 4)
