"""Diálogo «Nuevo lienzo»: nombre, uso, tamaño, unidades, resolución, modo de color y animación."""
from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QColorDialog, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
                               QFormLayout, QGroupBox, QHBoxLayout, QLineEdit, QMessageBox,
                               QPushButton, QSpinBox, QVBoxLayout)

# (descripción, ancho, alto, unidad, dpi)
PREAJUSTES = {
    "Ilustración": [
        ("Cuadrado 2000 × 2000 px, 350 dpi", 2000, 2000, "px", 350),
        ("A4 vertical (21 × 29.7 cm), 350 dpi", 21.0, 29.7, "cm", 350),
        ("A3 póster (29.7 × 42 cm), 300 dpi", 29.7, 42.0, "cm", 300),
        ("Postal (14.8 × 10 cm), 350 dpi", 14.8, 10.0, "cm", 350),
        ("Redes sociales 1080 × 1350 px, 72 dpi", 1080, 1350, "px", 72),
    ],
    "Cómic": [
        ("B5 (18.2 × 25.7 cm), 600 dpi", 18.2, 25.7, "cm", 600),
        ("A5 (14.8 × 21 cm), 600 dpi", 14.8, 21.0, "cm", 600),
        ("Webtoon 800 × 1280 px, 72 dpi", 800, 1280, "px", 72),
    ],
    "Animación": [
        ("HD 1920 × 1080 px, 72 dpi", 1920, 1080, "px", 72),
        ("HD vertical 1080 × 1920 px, 72 dpi", 1080, 1920, "px", 72),
        ("HD 720p 1280 × 720 px, 72 dpi", 1280, 720, "px", 72),
        ("4K 3840 × 2160 px, 72 dpi", 3840, 2160, "px", 72),
    ],
}
MAX_PX = 30000


def px_por_unidad(unidad: str, dpi: int) -> float:
    return {"px": 1.0, "in": float(dpi), "cm": dpi / 2.54, "mm": dpi / 25.4}[unidad]


class NuevoLienzo(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nuevo lienzo")
        self.setMinimumWidth(460)
        self.px_w, self.px_h, self._dpi_prev = 2000.0, 2000.0, 350
        self.papel = QColor("white")
        f = QFormLayout()
        self.nombre = QLineEdit("Sin título")
        self.uso = QComboBox()
        self.uso.addItems(list(PREAJUSTES))
        self.pre = QComboBox()
        self.unidad = QComboBox()
        self.unidad.addItems(["px", "cm", "mm", "in"])
        self.ancho, self.alto = QDoubleSpinBox(), QDoubleSpinBox()
        for s in (self.ancho, self.alto):
            s.setRange(0.01, 1_000_000)
        self.dpi = QSpinBox()
        self.dpi.setRange(72, 1200)
        self.dpi.setValue(350)
        self.dpi.setSuffix(" dpi")
        self.modo = QComboBox()
        self.modo.addItems(["Color", "Escala de grises", "Monocromático"])
        self.btn_papel = QPushButton()
        self.btn_papel.clicked.connect(self._elegir_papel)
        self._pintar_papel()
        self.btn_giro = QPushButton("⇄ Intercambiar ancho y alto")
        self.btn_giro.clicked.connect(self._girar)
        f.addRow("Nombre del archivo", self.nombre)
        f.addRow("Uso", self.uso)
        f.addRow("Preajuste", self.pre)
        f.addRow("Unidad", self.unidad)
        f.addRow("Ancho", self.ancho)
        f.addRow("Alto", self.alto)
        f.addRow("", self.btn_giro)
        f.addRow("Resolución", self.dpi)
        f.addRow("Modo de color", self.modo)
        f.addRow("Color del papel", self.btn_papel)

        self.anim = QGroupBox("Crear animación (activa la línea de tiempo)")
        self.anim.setCheckable(True)
        self.anim.setChecked(False)
        fa = QFormLayout(self.anim)
        self.fps = QSpinBox()
        self.fps.setRange(1, 60)
        self.fps.setValue(12)
        self.fps.setSuffix(" fps")
        self.cuadros = QSpinBox()
        self.cuadros.setRange(1, 2000)
        self.cuadros.setValue(24)
        fa.addRow("Velocidad", self.fps)
        fa.addRow("Duración", self.cuadros)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText("Aceptar")
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        bb.accepted.connect(self._aceptar)
        bb.rejected.connect(self.reject)
        v = QVBoxLayout(self)
        v.addLayout(f)
        v.addWidget(self.anim)
        v.addWidget(bb)

        self.uso.currentTextChanged.connect(self._cargar_preajustes)
        self.pre.currentIndexChanged.connect(self._aplicar_preajuste)
        self.unidad.currentTextChanged.connect(lambda _: self._mostrar())
        self.ancho.valueChanged.connect(lambda v: self._editado("w", v))
        self.alto.valueChanged.connect(lambda v: self._editado("h", v))
        self.dpi.valueChanged.connect(self._dpi_cambiado)
        self._cargar_preajustes(self.uso.currentText())

    # --- papel
    def _pintar_papel(self):
        self.btn_papel.setText(self.papel.name().upper())
        self.btn_papel.setStyleSheet(f"background:{self.papel.name()}; color:"
                                     f"{'black' if self.papel.lightness() > 128 else 'white'};")

    def _elegir_papel(self):
        c = QColorDialog.getColor(self.papel, self, "Color del papel")
        if c.isValid():
            self.papel = c
            self._pintar_papel()

    # --- tamaño
    def _ppu(self) -> float:
        return px_por_unidad(self.unidad.currentText(), self.dpi.value())

    def _mostrar(self):
        ppu, u = self._ppu(), self.unidad.currentText()
        for s, px in ((self.ancho, self.px_w), (self.alto, self.px_h)):
            s.blockSignals(True)
            s.setDecimals(0 if u == "px" else 2)
            s.setValue(px / ppu)
            s.blockSignals(False)

    def _editado(self, eje, v):
        if eje == "w":
            self.px_w = v * self._ppu()
        else:
            self.px_h = v * self._ppu()

    def _dpi_cambiado(self, nuevo):
        if self.unidad.currentText() != "px":     # conserva el tamaño físico
            k = nuevo / self._dpi_prev
            self.px_w, self.px_h = self.px_w * k, self.px_h * k
        self._dpi_prev = nuevo
        self._mostrar()

    def _girar(self):
        self.px_w, self.px_h = self.px_h, self.px_w
        self._mostrar()

    def _cargar_preajustes(self, uso):
        self.pre.blockSignals(True)
        self.pre.clear()
        self.pre.addItems([p[0] for p in PREAJUSTES[uso]])
        self.pre.blockSignals(False)
        self.anim.setChecked(uso == "Animación")
        self._aplicar_preajuste(0)

    def _aplicar_preajuste(self, i):
        lista = PREAJUSTES[self.uso.currentText()]
        if not 0 <= i < len(lista):
            return
        _, w, h, u, dpi = lista[i]
        for wd in (self.unidad, self.dpi):
            wd.blockSignals(True)
        self.unidad.setCurrentText(u)
        self.dpi.setValue(dpi)
        self._dpi_prev = dpi
        for wd in (self.unidad, self.dpi):
            wd.blockSignals(False)
        ppu = self._ppu()
        self.px_w, self.px_h = w * ppu, h * ppu
        self._mostrar()

    def _aceptar(self):
        w, h = round(self.px_w), round(self.px_h)
        if not (1 <= w <= MAX_PX and 1 <= h <= MAX_PX):
            QMessageBox.warning(self, "Tamaño no válido", f"El lienzo debe medir entre 1 y {MAX_PX} px por lado.")
            return
        if w * h > 120_000_000:
            QMessageBox.warning(self, "Lienzo demasiado grande",
                                "Más de 120 megapíxeles necesitaría demasiada memoria. Reduce el tamaño o la resolución.")
            return
        self.accept()

    def resultado(self) -> dict:
        return dict(nombre=self.nombre.text().strip() or "Sin título", ancho=round(self.px_w),
                    alto=round(self.px_h), dpi=self.dpi.value(), color_papel=self.papel,
                    animacion=self.anim.isChecked(), fps=self.fps.value(),
                    cuadros=self.cuadros.value(), modo_color=self.modo.currentText())
