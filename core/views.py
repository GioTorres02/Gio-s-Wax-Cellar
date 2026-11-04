# ventas/views.py
import mimetypes
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from urllib.parse import unquote, urlparse

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles import finders
from django.http import HttpResponse
from django.http.request import validate_host
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone

import weasyprint

from .models import ConfiguracionERP, Venta


# ── Recursos locales para WeasyPrint ─────────────────────────────────────

def _ruta_local(url_path: str) -> Path | None:
    """Traduce /static/... o /media/... a un archivo en disco, o None."""
    static_prefix = "/" + settings.STATIC_URL.lstrip("/")
    media_prefix = "/" + settings.MEDIA_URL.lstrip("/")

    if url_path.startswith(static_prefix):
        relativa = url_path[len(static_prefix):]
        candidata = Path(settings.STATIC_ROOT) / relativa
        if candidata.is_file():
            return candidata
        encontrada = finders.find(relativa)  # funciona sin collectstatic
        return Path(encontrada) if encontrada else None

    if url_path.startswith(media_prefix):
        raiz = Path(settings.MEDIA_ROOT).resolve()
        candidata = (raiz / url_path[len(media_prefix):]).resolve()
        # Bloquea rutas con ../ que salgan de MEDIA_ROOT
        if raiz in candidata.parents and candidata.is_file():
            return candidata

    return None


def _url_fetcher_local(url: str, timeout: int = 10, ssl_context=None):
    """url_fetcher de WeasyPrint: lee /static/ y /media/ desde disco.

    Así WeasyPrint no hace peticiones HTTP al propio servidor, que pueden
    bloquearse con un solo worker de Gunicorn. Si un recurso propio no
    existe, lanza FileNotFoundError y WeasyPrint omite solo esa imagen.
    Las URLs externas usan el fetcher por defecto.
    """
    parsed = urlparse(url)

    if parsed.scheme in ("http", "https", "file"):
        ruta = _ruta_local(unquote(parsed.path))
        if ruta is not None:
            return {
                "string": ruta.read_bytes(),
                "mime_type": mimetypes.guess_type(ruta.name)[0] or "application/octet-stream",
                "filename": ruta.name,
            }

        es_propio = parsed.scheme == "file" or validate_host(
            parsed.hostname or "",
            ["localhost", "127.0.0.1", *settings.ALLOWED_HOSTS],
        )
        if es_propio:
            raise FileNotFoundError(url)

    return weasyprint.default_url_fetcher(url, timeout=timeout, ssl_context=ssl_context)


# ── Cálculos ─────────────────────────────────────────────────────────────

def calcular_totales(subtotal, iva_porcentaje) -> dict:
    """Devuelve subtotal, IVA y total con 2 decimales (redondeo comercial).

    Ejemplo: calcular_totales(Decimal("3000"), 16)
             -> subtotal 3000.00, iva 480.00, total_con_iva 3480.00
    """
    centavos = Decimal("0.01")
    subtotal = Decimal(subtotal or 0).quantize(centavos, ROUND_HALF_UP)
    iva = (subtotal * Decimal(str(iva_porcentaje)) / 100).quantize(centavos, ROUND_HALF_UP)
    return {"subtotal": subtotal, "iva": iva, "total_con_iva": subtotal + iva}


# ── Vistas ───────────────────────────────────────────────────────────────

@login_required
def venta_pdf(request, venta_id: int) -> HttpResponse:
    """Genera la factura de una venta en PDF con WeasyPrint."""
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
        "hoy": timezone.localdate(),
        **calcular_totales(venta.total, config.iva_porcentaje),
    }

    html_string = render_to_string("ventas/factura_pdf.html", context, request=request)

    pdf_bytes = weasyprint.HTML(
        string=html_string,
        base_url=request.build_absolute_uri("/"),
        url_fetcher=_url_fetcher_local,
    ).write_pdf()

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="factura_{venta.pk:05d}.pdf"'
    return response