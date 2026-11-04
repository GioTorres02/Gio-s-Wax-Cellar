# core/views.py
from django.shortcuts import render


def bienvenida(request):
    """Página de inicio del ERP."""
    return render(request, 'core/bienvenida.html')