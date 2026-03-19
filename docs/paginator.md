# Paginador — Core

Template tag reutilizable para paginación. Disponible en todas las apps via `{% load core_tags %}`.

## Uso básico

### 1. Vista

Usa `paginate_queryset()` de `core.utils` en cualquier vista:
```python
from core.utils import paginate_queryset
from multiverse.models import Card

class CardListView(TemplateView):
    template_name = "multiverse/card_list.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs = Card.objects.filter(is_active=True)
        ctx["page_obj"] = paginate_queryset(qs, self.request.GET.get("page"), per_page=20)
        return ctx
```

O con `ListView` directamente:
```python
from django.views.generic import ListView
from multiverse.models import Card

class CardListView(ListView):
    model = Card
    template_name = "multiverse/card_list.html"
    context_object_name = "cards"
    paginate_by = 20
```

### 2. Template
```django
{% load core_tags %}

{% for card in page_obj %}
  <div class="card p-4">{{ card.name }}</div>
{% empty %}
  <p>No hay resultados.</p>
{% endfor %}

{% paginator page_obj %}
```

## Comportamiento

- Solo se renderiza si hay más de una página (`has_other_pages`).
- Muestra páginas cercanas (±2 a la actual).
- Preserva todos los query params del request (filtros, búsqueda) al paginar.
- Ejemplo: `/cards/?color=blue&page=3` → los links de paginación mantienen `color=blue`.

## Parámetros de `paginate_queryset`

| Parámetro | Tipo | Default | Descripción |
|---|---|---|---|
| `queryset` | `QuerySet` | — | El queryset a paginar |
| `page` | `str / int` | — | Número de página (viene de `request.GET.get("page")`) |
| `per_page` | `int` | `20` | Elementos por página |

Maneja automáticamente `PageNotAnInteger` y `EmptyPage` — nunca lanza excepción.

## Ejemplo con filtros
```python
class CardListView(TemplateView):
    template_name = "multiverse/card_list.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs = Card.objects.filter(is_active=True)

        # Filtros desde GET
        color = self.request.GET.get("color")
        if color:
            qs = qs.filter(colors__contains=color)

        ctx["page_obj"] = paginate_queryset(
            qs,
            self.request.GET.get("page"),
            per_page=20,
        )
        ctx["current_color"] = color
        return ctx
```
```django
{% load core_tags %}

<!-- Filtros -->
<form method="get">
  <select name="color" onchange="this.form.submit()">
    <option value="">Todos</option>
    <option value="W" {% if current_color == "W" %}selected{% endif %}>Blanco</option>
    <option value="U" {% if current_color == "U" %}selected{% endif %}>Azul</option>
    <option value="B" {% if current_color == "B" %}selected{% endif %}>Negro</option>
    <option value="R" {% if current_color == "R" %}selected{% endif %}>Rojo</option>
    <option value="G" {% if current_color == "G" %}selected{% endif %}>Verde</option>
  </select>
</form>

<!-- Lista -->
{% for card in page_obj %}
  <div class="card p-4">{{ card.name }}</div>
{% endfor %}

<!-- Paginador — preserva ?color=X automáticamente -->
{% paginator page_obj %}
```