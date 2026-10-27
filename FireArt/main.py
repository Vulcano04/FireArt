import os
import sys

from PySide6.QtWidgets import QApplication

from fireart.app import VentanaPrincipal, aplicar_tema


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("FireArt")
    aplicar_tema(app)
    ventana = VentanaPrincipal()
    ventana.show()
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        ventana.abrir_ruta(sys.argv[1])      # doble clic en un archivo .fireart
    else:
        ventana.nuevo()                      # pide el lienzo al abrir
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
