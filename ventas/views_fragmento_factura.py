import mimetypes
import os
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import urlparse, unquote

from django.conf import settings
from django.contrib.staticfiles import finders
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string

from weasyprint import HTML, default_url_fetcher

from .models import Venta, ConfiguracionEmpresa


def _ruta_segura(base, relativa):
    """
    Devuelve la ruta absoluta solo si queda dentro de `base`.
    Evita que rutas con '..' lean archivos fuera de MEDIA_ROOT.
    """
    base = os.path.abspath(base)
    ruta = os.path.abspath(os.path.join(base, relativa))
    if os.path.commonpath([base, ruta]) != base:
        return None
    return ruta


def url_fetcher_local(url, *args, **kwargs):
    """
    WeasyPrint llama a esta función para cada recurso (imágenes, CSS, fuentes).
    Si la URL apunta a /media/ o /static/, lee el archivo directamente del disco
    en lugar de hacer una petición HTTP al propio servidor.
    """
    path = unquote(urlparse(url).path)

    if path.startswith(settings.MEDIA_URL):
        local = _ruta_segura(settings.MEDIA_ROOT, path[len(settings.MEDIA_URL):])
    elif path.startswith(settings.STATIC_URL):
        local = finders.find(path[len(settings.STATIC_URL):])
    else:
        # URLs externas: se delegan al fetcher por defecto
        return default_url_fetcher(url, *args, **kwargs)

    if not local or not os.path.isfile(local):
        # Recurso inválido o inexistente: se devuelve vacío para que
        # WeasyPrint omita la imagen sin tumbar la generación del PDF
        return {"string": b"", "mime_type": "application/octet-stream"}

    mime, _ = mimetypes.guess_type(local)
    with open(local, "rb") as f:
        return {"string": f.read(), "mime_type": mime or "application/octet-stream"}


def venta_pdf(request, pk):
    venta = get_object_or_404(Venta, pk=pk)

    config = ConfiguracionEmpresa.objects.first()
    if config is None:
        raise Http404("Falta la configuración de la empresa.")

    detalles = venta.detalles.all()
    subtotal = sum((d.subtotal for d in detalles), Decimal("0"))
    subtotal = subtotal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    iva = (subtotal * Decimal(str(config.iva_porcentaje)) / 100).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    total_con_iva = subtotal + iva

    contexto = {
        "venta": venta,
        "config": config,
        "subtotal": subtotal,
        "iva": iva,
        "total_con_iva": total_con_iva,
        "hoy": date.today(),
    }

    html_string = render_to_string("ventas/factura_pdf.html", contexto, request=request)

    pdf = HTML(
        string=html_string,
        base_url=request.build_absolute_uri("/"),  # ej. http://localhost:8000/
        url_fetcher=url_fetcher_local,
    ).write_pdf()

    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="factura_{venta.pk}.pdf"'
    return response