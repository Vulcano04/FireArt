"""Ventana principal de FireArt: menús, paneles acoplables, pestañas de documentos y herramientas."""
from __future__ import annotations

import os

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QActionGroup, QColor, QKeySequence
from PySide6.QtWidgets import (QApplication, QDockWidget, QFileDialog, QLabel, QMainWindow,
                               QMessageBox, QTabBar, QToolBar, QVBoxLayout, QWidget)

from . import __version__
from .canvas import Ajustes, Lienzo
from .core import Documento
from .dialogs import NuevoLienzo
from .widgets import (LineaTiempo, ListaSub, Navegador, PaletaTamano, PanelAjustes, PanelCapas,
                      RuedaColor)

TEMA = """
* { font-size: 12px; }
QMainWindow, QDialog, QWidget { background:#2f2f2f; color:#e0e0e0; }
QMenuBar { background:#262626; } QMenuBar::item:selected { background:#4a6fa5; }
QMenu { background:#2b2b2b; border:1px solid #1a1a1a; } QMenu::item:selected { background:#4a6fa5; }
QMenu::item:disabled { color:#777; }
QDockWidget { titlebar-close-icon:none; font-weight:bold; }
QDockWidget::title { background:#3a3a3a; padding:4px 6px; border-bottom:1px solid #1f1f1f; }
QToolBar { background:#2b2b2b; border:0; spacing:2px; padding:2px; }
QToolButton { background:#3b3b3b; border:1px solid #1f1f1f; border-radius:2px; padding:3px; }
QToolButton:hover { background:#474747; } QToolButton:checked { background:#4a6fa5; }
QPushButton { background:#3f3f3f; border:1px solid #1f1f1f; padding:4px 8px; border-radius:2px; }
QPushButton:hover { background:#4b4b4b; }
QListWidget, QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QScrollArea
  { background:#262626; border:1px solid #1a1a1a; selection-background-color:#4a6fa5; }
QListWidget::item { padding:3px; } QListWidget::item:selected { background:#4a6fa5; }
QTabBar::tab { background:#3a3a3a; padding:5px 12px; border:1px solid #1f1f1f; }
QTabBar::tab:selected { background:#4a6fa5; }
QSlider::groove:horizontal { height:4px; background:#1c1c1c; }
QSlider::handle:horizontal { background:#cfcfcf; width:10px; margin:-5px 0; border-radius:5px; }
QStatusBar { background:#262626; }
QGroupBox { border:1px solid #444; margin-top:8px; padding-top:8px; }
QGroupBox::title { subcontrol-origin: margin; left:8px; }
"""

HERRAMIENTAS = [
    ("dibujo", "✎", "Pincel y pluma (B)", "B"),
    ("borrador", "⌫", "Borrador (E)", "E"),
    ("cubeta", "◍", "Cubeta de pintura (G)", "G"),
    ("cuentagotas", "✚", "Cuentagotas (I)", "I"),
    ("mano", "✋", "Mano / desplazar (H)", "H"),
    ("zoom", "⌕", "Lupa (Z). Alt+clic: alejar", "Z"),
    ("rotar", "⟳", "Rotar vista (R)", "R"),
]


def aplicar_tema(app: QApplication):
    app.setStyle("Fusion")
    app.setStyleSheet(TEMA)


class VentanaPrincipal(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FireArt")
        self.resize(1560, 940)
        self.aj = Ajustes()
        self.lienzo = Lienzo(self.aj)
        self.docs: list[Documento] = []
        self.doc: Documento | None = None

        self.pestanas = QTabBar()
        self.pestanas.setTabsClosable(True)
        self.pestanas.setMovable(True)
        self.pestanas.setExpanding(False)
        centro = QWidget()
        v = QVBoxLayout(centro)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addWidget(self.pestanas)
        v.addWidget(self.lienzo, 1)
        self.setCentralWidget(centro)

        self._crear_paneles()
        self._crear_herramientas()
        self._crear_menus()
        self._estado = QLabel()
        self.statusBar().addPermanentWidget(self._estado)
        self._conectar()
        self.lienzo.usar_herramienta("dibujo")
        self.sub.set_grupo("dibujo")
        self.ajustes.mostrar_para("dibujo")
        self._actualizar_estado()

    # ----------------------------------------------------------------- UI
    def _dock(self, titulo, widget, zona, nombre):
        d = QDockWidget(titulo, self)
        d.setObjectName(nombre)
        d.setWidget(widget)
        d.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable |
                      QDockWidget.DockWidgetFeature.DockWidgetFloatable |
                      QDockWidget.DockWidgetFeature.DockWidgetClosable)
        self.addDockWidget(zona, d)
        return d

    def _crear_paneles(self):
        L, R, B = (Qt.DockWidgetArea.LeftDockWidgetArea, Qt.DockWidgetArea.RightDockWidgetArea,
                   Qt.DockWidgetArea.BottomDockWidgetArea)
        self.sub = ListaSub()
        self.sub.setMaximumHeight(130)
        self.ajustes = PanelAjustes(self.aj)
        self.tamanos = PaletaTamano()
        self.rueda = RuedaColor()
        self.navegador = Navegador(self.lienzo)
        self.capas = PanelCapas()
        self.linea = LineaTiempo()
        self.docks = [
            self._dock("Subherramienta", self.sub, L, "sub"),
            self._dock("Ajustes de herramienta", self.ajustes, L, "ajustes"),
            self._dock("Tamaño del pincel", self.tamanos, L, "tamanos"),
            self._dock("Color", self.rueda, L, "color"),
            self._dock("Navegador", self.navegador, R, "navegador"),
            self._dock("Capa", self.capas, R, "capas"),
        ]
        self.dock_linea = self._dock("Línea de tiempo", self.linea, B, "linea")
        self.dock_linea.hide()

    def _crear_herramientas(self):
        tb = QToolBar("Herramientas")
        tb.setOrientation(Qt.Orientation.Vertical)
        tb.setIconSize(QSize(28, 28))
        tb.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, tb)
        grupo = QActionGroup(self)
        self.acc_herr = {}
        for nombre, glifo, tip, tecla in HERRAMIENTAS:
            a = QAction(glifo, self)
            a.setCheckable(True)
            a.setToolTip(tip)
            a.setShortcut(QKeySequence(tecla))
            a.triggered.connect(lambda _=False, n=nombre: self._elegir_herramienta(n))
            grupo.addAction(a)
            tb.addAction(a)
            self.acc_herr[nombre] = a
            w = tb.widgetForAction(a)
            if w:
                w.setFixedSize(40, 36)
                w.setStyleSheet("font-size:18px;")
        self.acc_herr["dibujo"].setChecked(True)

    def _accion(self, menu, texto, fn, atajo=None, checkable=False):
        a = QAction(texto, self)
        if atajo:
            a.setShortcut(QKeySequence(atajo))
        a.setCheckable(checkable)
        a.triggered.connect(fn)
        menu.addAction(a)
        return a

    def _pendiente(self, menu):
        a = QAction("(Próximamente)", self)
        a.setEnabled(False)
        menu.addAction(a)

    def _crear_menus(self):
        mb = self.menuBar()
        m = mb.addMenu("Archivo")
        self._accion(m, "Nuevo…", self.nuevo, "Ctrl+N")
        self._accion(m, "Abrir…", self.abrir, "Ctrl+O")
        self._accion(m, "Guardar", self.guardar, "Ctrl+S")
        self._accion(m, "Guardar como…", lambda: self.guardar(True), "Ctrl+Shift+S")
        m.addSeparator()
        ex = m.addMenu("Exportar")
        self._accion(ex, "Imagen PNG / JPG…", self.exp_imagen)
        self.acc_gif = self._accion(ex, "Animación GIF…", self.exp_gif)
        self.acc_mp4 = self._accion(ex, "Video MP4…", self.exp_mp4)
        self.acc_seq = self._accion(ex, "Secuencia de imágenes PNG…", self.exp_secuencia)
        m.addSeparator()
        self._accion(m, "Salir", self.close, "Ctrl+Q")

        m = mb.addMenu("Edición")
        self._accion(m, "Deshacer", self.deshacer, "Ctrl+Z")
        a = self._accion(m, "Rehacer", self.rehacer, "Ctrl+Y")
        a.setShortcuts([QKeySequence("Ctrl+Y"), QKeySequence("Ctrl+Shift+Z")])
        m.addSeparator()
        self._accion(m, "Borrar contenido de la capa", self.borrar_capa, "Del")

        self._pendiente(mb.addMenu("Gestión de páginas"))

        m = mb.addMenu("Animación")
        self.acc_anim = self._accion(m, "Activar animación", self.alternar_animacion, None, True)
        m.addSeparator()
        self._accion(m, "Cuadro siguiente", lambda: self.linea.paso(1), ".")
        self._accion(m, "Cuadro anterior", lambda: self.linea.paso(-1), ",")
        self._accion(m, "Reproducir / Detener", self.linea.alternar_reproduccion, "P")
        self.acc_cebolla = self._accion(m, "Papel cebolla", self._set_cebolla, None, True)

        m = mb.addMenu("Capa")
        self._accion(m, "Nueva capa raster", self.capas._nueva, "Ctrl+Shift+N")
        self._accion(m, "Duplicar capa", self.capas._dup)
        self._accion(m, "Eliminar capa", self.capas._del)
        self._accion(m, "Unir con la capa inferior", self.capas._unir, "Ctrl+E")
        m.addSeparator()
        self._accion(m, "Subir capa", lambda: self.capas._mover(1), "Ctrl+]")
        self._accion(m, "Bajar capa", lambda: self.capas._mover(-1), "Ctrl+[")

        self._pendiente(mb.addMenu("Seleccionar"))

        m = mb.addMenu("Ver")
        self._accion(m, "Ajustar a la ventana", self.lienzo.ajustar, "Ctrl+0")
        self._accion(m, "Tamaño real (100%)", lambda: self.lienzo.fijar_zoom(1.0), "Ctrl+1")
        self._accion(m, "Acercar", lambda: self.lienzo.zoom_en(1.25), "Ctrl+=")
        self._accion(m, "Alejar", lambda: self.lienzo.zoom_en(0.8), "Ctrl+-")
        m.addSeparator()
        self._accion(m, "Girar vista 15° a la derecha", lambda: self.lienzo.fijar_angulo(self.lienzo.angulo + 15))
        self._accion(m, "Girar vista 15° a la izquierda", lambda: self.lienzo.fijar_angulo(self.lienzo.angulo - 15))
        self._accion(m, "Restablecer giro", lambda: self.lienzo.fijar_angulo(0), "Ctrl+Shift+0")
        self._accion(m, "Voltear vista horizontalmente", self.navegador._espejo)

        self._pendiente(mb.addMenu("Filtro"))

        m = mb.addMenu("Ventana")
        for d in self.docks + [self.dock_linea]:
            m.addAction(d.toggleViewAction())

        m = mb.addMenu("Ayuda")
        self._accion(m, "Acerca de FireArt", self.acerca)

    def _conectar(self):
        self.pestanas.currentChanged.connect(self._cambiar_doc)
        self.pestanas.tabCloseRequested.connect(self._cerrar_pestana)
        self.rueda.cambiado.connect(lambda c: setattr(self.aj, "color", c))
        self.lienzo.color_tomado.connect(self._color_tomado)
        self.lienzo.vista_cambiada.connect(self._actualizar_estado)
        self.lienzo.documento_modificado.connect(self._modificado)
        self.lienzo.mensaje.connect(lambda t: self.statusBar().showMessage(t, 4000))
        self.sub.elegido.connect(self._preset)
        self.tamanos.elegido.connect(self._tamano)
        self.capas.cambiado.connect(self.lienzo.refrescar)
        self.capas.cambiado.connect(self.navegador.miniatura)
        self.capas.seleccion.connect(self.linea.refrescar)
        self.linea.cuadro_cambiado.connect(self.lienzo.refrescar)
        self.linea.cuadro_cambiado.connect(self.navegador.miniatura)
        self.linea.capa_elegida.connect(self.capas.refrescar)
        self.linea.cebolla_cambiada.connect(self._set_cebolla)

    # --------------------------------------------------------- herramientas
    def _elegir_herramienta(self, n):
        self.lienzo.usar_herramienta(n)
        self.sub.set_grupo(n)
        self.ajustes.mostrar_para(n)
        self.ajustes.cargar()

    def _preset(self, d):
        self.aj.aplicar(d)
        self.ajustes.cargar()

    def _tamano(self, t):
        self.aj.tamano = t
        self.ajustes.cargar()

    def _color_tomado(self, c: QColor):
        c.setAlpha(255)
        self.aj.color = c
        self.rueda.set_color(c)

    # ----------------------------------------------------------- documentos
    def _titulo(self, d: Documento) -> str:
        return d.nombre + (" *" if d.modificado else "")

    def _agregar_doc(self, doc: Documento):
        self.docs.append(doc)
        self.pestanas.blockSignals(True)
        i = self.pestanas.addTab(self._titulo(doc))
        self.pestanas.setCurrentIndex(i)
        self.pestanas.blockSignals(False)
        self._cambiar_doc(i)

    def _cambiar_doc(self, i):
        self.linea.detener()
        self.doc = self.docs[i] if 0 <= i < len(self.docs) else None
        for w in (self.lienzo, self.capas, self.linea):
            w.set_documento(self.doc)
        anim = bool(self.doc and self.doc.animacion)
        self.dock_linea.setVisible(anim)
        self._sincronizar_anim()
        self.navegador.miniatura()
        self.setWindowTitle(f"{self._titulo(self.doc)} - FireArt" if self.doc else "FireArt")
        self._actualizar_estado()

    def _sincronizar_anim(self):
        anim = bool(self.doc and self.doc.animacion)
        self.acc_anim.blockSignals(True)
        self.acc_anim.setChecked(anim)
        self.acc_anim.blockSignals(False)
        for a in (self.acc_gif, self.acc_mp4, self.acc_seq):
            a.setEnabled(anim)

    def _modificado(self):
        if self.doc:
            i = self.docs.index(self.doc)
            self.pestanas.setTabText(i, self._titulo(self.doc))
            self.setWindowTitle(f"{self._titulo(self.doc)} - FireArt")
        self.navegador.miniatura()
        self.linea.refrescar()

    def _confirmar(self, doc: Documento) -> bool:
        if not doc.modificado:
            return True
        cuadro = QMessageBox(QMessageBox.Icon.Question, "Guardar cambios",
                             f"¿Guardar los cambios de «{doc.nombre}»?", parent=self)
        b_si = cuadro.addButton("Guardar", QMessageBox.ButtonRole.AcceptRole)
        b_no = cuadro.addButton("No guardar", QMessageBox.ButtonRole.DestructiveRole)
        cuadro.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
        cuadro.exec()
        r = cuadro.clickedButton()
        if r is not b_si and r is not b_no:
            return False
        if r is b_si:
            prev, self.doc = self.doc, doc
            ok = self.guardar()
            self.doc = prev
            return ok
        return True

    def _cerrar_pestana(self, i):
        if not self._confirmar(self.docs[i]):
            return
        self.docs.pop(i)
        self.pestanas.blockSignals(True)
        self.pestanas.removeTab(i)
        self.pestanas.blockSignals(False)
        self._cambiar_doc(self.pestanas.currentIndex())

    def closeEvent(self, e):
        for d in list(self.docs):
            if not self._confirmar(d):
                e.ignore()
                return
        e.accept()

    # -------------------------------------------------------------- archivo
    def nuevo(self):
        dlg = NuevoLienzo(self)
        if dlg.exec():
            r = dlg.resultado()
            self._agregar_doc(Documento(**r))
            self.statusBar().showMessage(f"Lienzo creado: {r['ancho']} × {r['alto']} px", 4000)

    def abrir(self):
        ruta, _ = QFileDialog.getOpenFileName(self, "Abrir", "", "Proyectos FireArt (*.fireart)")
        if ruta:
            self.abrir_ruta(ruta)

    def abrir_ruta(self, ruta: str):
        try:
            self._agregar_doc(Documento.abrir(ruta))
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo abrir", str(e))

    def guardar(self, como=False) -> bool:
        d = self.doc
        if not d:
            return False
        ruta = d.ruta
        if como or not ruta:
            ruta, _ = QFileDialog.getSaveFileName(self, "Guardar", f"{d.nombre}.fireart",
                                                  "Proyectos FireArt (*.fireart)")
            if not ruta:
                return False
            if not ruta.lower().endswith(".fireart"):
                ruta += ".fireart"
        try:
            d.guardar(ruta)
            d.nombre = os.path.splitext(os.path.basename(ruta))[0]
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo guardar", str(e))
            return False
        i = self.docs.index(d)
        self.pestanas.setTabText(i, self._titulo(d))
        self.statusBar().showMessage(f"Guardado en {ruta}", 4000)
        return True

    def _exportar(self, titulo, filtro, ext, fn):
        d = self.doc
        if not d:
            return
        ruta, _ = QFileDialog.getSaveFileName(self, titulo, f"{d.nombre}{ext}", filtro)
        if not ruta:
            return
        if "." not in os.path.basename(ruta):
            ruta += ext
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            fn(d, ruta)
            self.statusBar().showMessage(f"Exportado: {ruta}", 5000)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Error al exportar", str(e))
        finally:
            QApplication.restoreOverrideCursor()

    def exp_imagen(self):
        self._exportar("Exportar imagen", "PNG (*.png);;JPEG (*.jpg)", ".png",
                       lambda d, r: d.exportar_imagen(r))

    def exp_gif(self):
        self._exportar("Exportar GIF", "GIF animado (*.gif)", ".gif", lambda d, r: d.exportar_gif(r))

    def exp_mp4(self):
        self._exportar("Exportar video", "Video MP4 (*.mp4)", ".mp4", lambda d, r: d.exportar_mp4(r))

    def exp_secuencia(self):
        d = self.doc
        if not d:
            return
        carpeta = QFileDialog.getExistingDirectory(self, "Carpeta de destino")
        if carpeta:
            n = d.exportar_secuencia(carpeta)
            self.statusBar().showMessage(f"{n} imágenes exportadas en {carpeta}", 5000)

    # -------------------------------------------------------------- edición
    def deshacer(self):
        if self.doc and self.doc.deshacer_paso():
            self.lienzo.refrescar()
            self._modificado()

    def rehacer(self):
        if self.doc and self.doc.rehacer_paso():
            self.lienzo.refrescar()
            self._modificado()

    def borrar_capa(self):
        d = self.doc
        if d and not d.capa_activa().bloqueada:
            cel = d.guardar_deshacer(d.capa_activa(), d.cuadro)
            cel.fill(Qt.GlobalColor.transparent)
            self.lienzo.refrescar()
            self._modificado()

    # ------------------------------------------------------------ animación
    def alternar_animacion(self, on: bool):
        d = self.doc
        if not d:
            self.acc_anim.setChecked(False)
            return
        d.animacion = on
        if on and d.cuadros < 2:
            d.cuadros = 24
        if not on:
            self.linea.detener()
            d.cuadro = 0
        self.linea.set_documento(d)
        self.dock_linea.setVisible(on)
        self._sincronizar_anim()
        self.lienzo.refrescar()
        self.navegador.miniatura()

    def _set_cebolla(self, on: bool):
        self.lienzo.cebolla = on
        for w in (self.acc_cebolla, self.linea.chk):
            w.blockSignals(True)
            w.setChecked(on)
            w.blockSignals(False)
        self.lienzo.update()

    # --------------------------------------------------------------- estado
    def _actualizar_estado(self):
        z, a = self.lienzo.zoom, self.lienzo.angulo
        txt = f"Zoom {z * 100:.1f}%    Giro {a if a <= 180 else a - 360:.1f}°"
        if self.doc:
            txt += f"    {self.doc.ancho} × {self.doc.alto} px    {self.doc.dpi} dpi    {self.doc.modo_color}"
        self._estado.setText(txt)

    def acerca(self):
        QMessageBox.about(
            self, "Acerca de FireArt",
            f"<h3>FireArt {__version__}</h3><p><b>Una alternativa limpia y gratuita</b> para ilustración, "
            "cómic y animación.</p><p>Código propio, escrito desde cero (clean room). "
            "No está afiliado a ningún otro programa de dibujo.</p>")
