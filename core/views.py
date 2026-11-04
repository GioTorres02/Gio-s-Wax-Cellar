# ventas/views.py — imports necesarios (además de los existentes):
import mimetypes
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from urllib.parse import unquote, urlparse

from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles import finders
from django.http.request import validate_host
from django.utils import timezone

import weasyprint


# ventas/views.py — agregar las funciones auxiliares y reemplazar venta_pdf:

def _ruta_local(url_path: str) -> Path | None:
    """Traduce /static/... o /media/... a un archivo en disco (o None)."""
    static_prefix = "/" + settings.STATIC_URL.lstrip("/")
    media_prefix = "/" + settings.MEDIA_URL.lstrip("/")

    if url_path.startswith(static_prefix):
        relativa = url_path[len(static_prefix):]
        candidata = Path(settings.STATIC_ROOT) / relativa
        if candidata.is_file():
            return candidata
        encontrada = finders.find(relativa)  # útil en desarrollo, sin collectstatic
        return Path(encontrada) if encontrada else None

    if url_path.startswith(media_prefix):
        raiz = Path(settings.MEDIA_ROOT).resolve()
        candidata = (raiz / url_path[len(media_prefix):]).resolve()
        # Evita salir de MEDIA_ROOT con rutas tipo ../
        if raiz in candidata.parents and candidata.is_file():
            return candidata
    return None


def _url_fetcher_local(url: str, timeout: int = 10, ssl_context=None):
    """url_fetcher de WeasyPrint que lee /static/ y /media/ desde disco.

    Evita que WeasyPrint haga peticiones HTTP al propio servidor (lento y
    puede bloquear a los workers de Gunicorn). Si el archivo no existe
    (p. ej. un logo perdido por el disco efímero de Render), se lanza
    FileNotFoundError: WeasyPrint solo registra un aviso y omite la imagen.
    Las URLs externas (p. ej. media en S3) usan el fetcher por defecto.
    """
    parsed = urlparse(url)
    if parsed.scheme in ("http", "https", "file"):
        ruta = _ruta_local(unquote(parsed.path))
        if ruta is not None:
            return {
                "string": ruta.read_bytes(),
                "mime_type": mimetypes.guess_type(ruta.name)[0],
                "filename": ruta.name,
            }
        propio = validate_host(
            parsed.hostname or "", ["localhost", "127.0.0.1", *settings.ALLOWED_HOSTS]
        )
        if parsed.scheme == "file" or propio:
            raise FileNotFoundError(url)
    return weasyprint.default_url_fetcher(url, timeout=timeout, ssl_context=ssl_context)


def calcular_totales(subtotal, iva_porcentaje) -> dict:
    """Subtotal, IVA y total con 2 decimales (redondeo comercial).

    Venta.total es la suma de las líneas SIN IVA; el IVA se suma aparte.
    Ejemplo: calcular_totales(Decimal("3000"), Decimal("16"))
             -> subtotal 3000.00, iva 480.00, total 3480.00
    """
    centavos = Decimal("0.01")
    subtotal = Decimal(subtotal).quantize(centavos, ROUND_HALF_UP)
    iva = (subtotal * Decimal(iva_porcentaje) / 100).quantize(centavos, ROUND_HALF_UP)
    return {"subtotal": subtotal, "iva": iva, "total_con_iva": subtotal + iva}


@login_required
def venta_pdf(request, venta_id: int) -> HttpResponse:
    """Genera y descarga la factura de una venta en formato PDF.

    Motor: WeasyPrint (requiere entorno Linux o contenedor Docker).

    Args:
        request: HttpRequest de Django.
        venta_id: ID de la venta a generar.

    Returns:
        HttpResponse con Content-Type application/pdf y descarga directa.
    """

    venta = get_object_or_404(
        Venta.objects.select_related("cliente").prefetch_related(
            "detalles__producto__categoria"
        ),
        pk=venta_id,
    )
    config = ConfiguracionERP.get_instance()
    context = {
        "venta": venta,
        "config": config,
        "hoy": timezone.localdate(),  # fecha en TIME_ZONE (America/Mexico_City)
        **calcular_totales(venta.total, config.iva_porcentaje),
    }

    html_string = render_to_string("ventas/factura_pdf.html", context, request=request)

    # ── WeasyPrint: conversión HTML → PDF ─────────────────────────────
    # base_url resuelve rutas relativas como /media/... o /static/...
    # y _url_fetcher_local las lee del disco en vez de pedirlas por HTTP.
    pdf_bytes = weasyprint.HTML(
        string=html_string,
        base_url=request.build_absolute_uri("/"),
        url_fetcher=_url_fetcher_local,
    ).write_pdf()

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="factura_{venta.pk:05d}.pdf"'
    )
    return response
