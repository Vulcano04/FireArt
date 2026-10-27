"""Prueba rápida de humo (sin pantalla): dibuja, rellena, deshace, guarda, abre y exporta."""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from fireart.app import VentanaPrincipal, aplicar_tema
from fireart.core import Documento, a_array

SIN = Qt.KeyboardModifier.NoModifier


def opacos(img):
    return int((a_array(img)[:, :, 3] > 0).sum())


app = QApplication([])
aplicar_tema(app)
w = VentanaPrincipal()
w.show()
doc = Documento("prueba", 400, 300, 300, QColor("white"), True, 12, 6)
w._agregar_doc(doc)
lz = w.lienzo
lz.resize(800, 600)
lz.fijar_zoom(1.0)
c = QPointF(lz.width() / 2, lz.height() / 2)

# 1) Trazo con presión variable
lz.aj.herramienta = "dibujo"
lz._inicio(c, 0.8, SIN)
for i in range(1, 15):
    lz._mover(c + QPointF(i * 8, (i % 5) * 6), 0.3 + i / 25)
lz._fin()
cel = doc.capa_activa().cels[0]
assert opacos(cel) > 100, "el trazo no dejó píxeles"

# 2) Cubeta en la capa de abajo (papel bloqueado → debe avisar y no pintar) y en la capa activa
antes = opacos(cel)
lz.aj.herramienta = "cubeta"
lz.aj.color = QColor("#ff0000")
lz._inicio(c + QPointF(-150, -100), 1.0, SIN)
assert opacos(doc.capa_activa().cels[0]) > antes, "la cubeta no rellenó"

# 3) Deshacer / rehacer
assert doc.deshacer_paso() and opacos(doc.capa_activa().cels[0]) == antes
assert doc.rehacer_paso() and opacos(doc.capa_activa().cels[0]) > antes

# 4) Animación: dibujar en el cuadro 3 crea un cel nuevo
w.linea.ir_a(2)
lz.aj.herramienta = "dibujo"
lz._inicio(c, 1.0, SIN)
lz._mover(c + QPointF(40, 10), 1.0)
lz._fin()
assert 2 in doc.capa_activa().cels

# 5) Capas
doc.nueva_capa()
doc.mover_capa(-1)
doc.duplicar_capa()
doc.unir_abajo()

with tempfile.TemporaryDirectory() as t:
    # 6) Guardar y abrir
    ruta = os.path.join(t, "p.fireart")
    doc.guardar(ruta)
    d2 = Documento.abrir(ruta)
    assert (d2.ancho, d2.alto, len(d2.capas), d2.animacion) == (doc.ancho, doc.alto, len(doc.capas), True)
    assert sorted(d2.capas[doc.activa].cels) == sorted(doc.capas[doc.activa].cels)
    # 7) Exportar
    doc.exportar_imagen(os.path.join(t, "a.png"))
    doc.exportar_imagen(os.path.join(t, "a.jpg"))
    doc.exportar_gif(os.path.join(t, "a.gif"))
    assert doc.exportar_secuencia(t) == 6
    for f in ("a.png", "a.jpg", "a.gif"):
        assert os.path.getsize(os.path.join(t, f)) > 0, f

print("PRUEBA DE HUMO: TODO OK")
