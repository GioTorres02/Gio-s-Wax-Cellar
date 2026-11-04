# ventas/views.py
"""Vistas de la app ventas: W07, W08, W09 y factura PDF.

W07: Lista y detalle.
W08: crear_venta y borrado.
W09: Permisos con decoradores y PermissionRequiredMixin.
Factura: venta_pdf con WeasyPrint (import diferido).
"""
import mimetypes
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import unquote, urlparse

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.views import redirect_to_login
from django.contrib.staticfiles import finders
from django.http import HttpResponse
from django.http.request import validate_host
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import DeleteView, DetailView, ListView

from configuracion.models import ConfiguracionERP
from .forms import DetalleVentaForm, VentaForm
from .models import Venta


class VentaListView(ListView):
    """Lista paginada de ventas en orden cronológico inverso."""

    model               = Venta
    template_name       = 'ventas/lista.html'
    context_object_name = 'ventas'
    paginate_by         = 20

    def get_queryset(self):
        """Pre-carga cliente para evitar N+1 en la tabla de ventas."""
        return (
            Venta.objects
            .select_related('cliente')
            .order_by('-fecha')
        )


class VentaDetailView(DetailView):
    """Detalle de una venta."""

    model               = Venta
    template_name       = 'ventas/detalle.html'
    context_object_name = 'venta'
    pk_url_kwarg        = 'venta_id'

    def get_queryset(self):
        return Venta.objects.select_related('cliente')


@login_required
@permission_required('ventas.add_venta', raise_exception=True)
def crear_venta(request):
    """Crea un encabezado de venta con una línea de detalle.

    GET  → muestra los dos formularios vacíos.
    POST → valida ambos, guarda si correctos, muestra errores si no.
    Nota: para múltiples líneas usar formsets (implementar en Espiral 5).
    """
    venta_form   = VentaForm(request.POST or None)
    detalle_form = DetalleVentaForm(request.POST or None)

    if request.method == 'POST':
        if venta_form.is_valid() and detalle_form.is_valid():
            venta         = venta_form.save()
            detalle       = detalle_form.save(commit=False)
            detalle.venta = venta
            # precio_unitario se auto-captura en save() si es None
            detalle.save()
            messages.success(
                request,
                f'Venta #{venta.pk} registrada. '
                f'Total: ${venta.total:.2f}'
            )
            return redirect('ventas:detalle', venta_id=venta.pk)

    return render(request, 'ventas/crear.html', {
        'venta_form':   venta_form,
        'detalle_form': detalle_form,
    })


class VentaDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    """Confirmación y borrado de una venta (y sus detalles en cascada).

    Anónimo → login (302). Autenticado sin permiso → 403.
    """

    model               = Venta
    template_name       = 'ventas/eliminar.html'
    pk_url_kwarg        = 'venta_id'
    success_url         = reverse_lazy('ventas:lista')
    permission_required = 'ventas.delete_venta'
    raise_exception     = True

    def handle_no_permission(self):
        """Anónimo → login (302). Autenticado sin permiso → 403."""
        if not self.request.user.is_authenticated:
            return redirect_to_login(
                self.request.get_full_path(),
                self.get_login_url(),
                self.get_redirect_field_name(),
            )
        return super().handle_no_permission()

    def form_valid(self, form):
        pk       = self.object.pk
        response = super().form_valid(form)
        messages.success(self.request, f'Venta #{pk} eliminada.')
        return response


# ── Factura PDF ──────────────────────────────────────────────────────────

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

    Evita peticiones HTTP al propio servidor, que pueden bloquearse con
    un solo worker de Gunicorn. Si un recurso propio no existe, lanza
    FileNotFoundError y WeasyPrint omite solo esa imagen.
    Las URLs externas usan el fetcher por defecto.
    """
    from weasyprint import default_url_fetcher  # import diferido

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

    return default_url_fetcher(url, timeout=timeout, ssl_context=ssl_context)


def calcular_totales(subtotal, iva_porcentaje) -> dict:
    """Devuelve subtotal, IVA y total con 2 decimales (redondeo comercial).

    Ejemplo: calcular_totales(Decimal("3000"), 16)
             -> subtotal 3000.00, iva 480.00, total_con_iva 3480.00
    """
    centavos = Decimal("0.01")
    subtotal = Decimal(subtotal or 0).quantize(centavos, ROUND_HALF_UP)
    iva = (subtotal * Decimal(str(iva_porcentaje)) / 100).quantize(centavos, ROUND_HALF_UP)
    return {"subtotal": subtotal, "iva": iva, "total_con_iva": subtotal + iva}


@login_required
def venta_pdf(request, venta_id: int) -> HttpResponse:
    """Genera la factura de una venta en PDF con WeasyPrint.

    Si no existe ConfiguracionERP, usa valores por defecto en lugar de fallar.
    """
    import weasyprint  # import diferido: solo se necesita al generar el PDF

    venta = get_object_or_404(
        Venta.objects.select_related("cliente").prefetch_related("detalles__producto"),
        pk=venta_id,
    )
    config = ConfiguracionERP.objects.first() or SimpleNamespace(
        nombre_empresa="UTEC Celaya",
        rfc="",
        moneda="MXN",
        iva_porcentaje=16,
        logo=None,
    )

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