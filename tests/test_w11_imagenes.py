# Función reutilizable que se usará dentro de los tests:
import io
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile


def _imagen_valida(nombre='test.jpg', formato='JPEG',
                   content_type='image/jpeg',
                   ancho=100, alto=100) -> SimpleUploadedFile:
    """Crea una imagen válida en memoria para tests.

    Args:
        nombre:       Nombre del archivo simulado.
        formato:      Formato Pillow ('JPEG', 'PNG', 'WEBP').
        content_type: MIME type del archivo.
        ancho, alto:  Dimensiones en píxeles.

    Returns:
        SimpleUploadedFile listo para incluir en request.FILES.
    """
    buf = io.BytesIO()
    img = Image.new('RGB', (ancho, alto), color='navy')
    img.save(buf, format=formato)
    buf.seek(0)
    return SimpleUploadedFile(
        name=nombre, content=buf.read(), content_type=content_type
    )


def _archivo_invalido(nombre='virus.exe') -> SimpleUploadedFile:
    """Crea un archivo que NO es imagen (contenido texto)."""
    return SimpleUploadedFile(
        name=nombre,
        content=b'Este no es una imagen. Es texto plano.',
        content_type='application/octet-stream'
    )
