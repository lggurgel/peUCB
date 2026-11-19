import csv
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from accounts.models import Profile
from windows.forms import WindowForm
from windows.models import KIND_LABELS, MATERIAL_LABELS, STATUS_LABELS, CollectionWindow
from windows.queries import (
    agreement_of,
    filter_by_material,
    generator_pins,
    open_windows,
    records_summary,
    wait_minutes,
)
from windows.services import WindowActionError, can_see_agreement, close_window, confirm_window

ACTION_MESSAGES = {
    "not_collector": "Só um coletador pode confirmar uma janela.",
    "own_window": "Você não pode confirmar a própria janela.",
    "past": "O horário desta janela já passou.",
    "already_reserved": "Esta janela já foi reservada.",
    "not_generator": "Só o estabelecimento pode encerrar a coleta.",
    "not_owner": "Esta janela é de outro estabelecimento.",
    "not_reserved": "Só uma janela já reservada pode ser encerrada.",
    "bad_outcome": "Não foi possível encerrar esta janela.",
}

PAGE_SIZE = 20
# The list sits below the map on a phone, so filter links land on it.
LIST_ANCHOR = "#janelas"


def _query(**params):
    return "?" + urlencode({key: value for key, value in params.items() if value})


def _open_list(request):
    """Open windows narrowed by the material chips and by one establishment."""
    material = request.GET.get("material", "")
    if material not in MATERIAL_LABELS:
        material = ""
    generator = None
    raw_generator = request.GET.get("generator", "")
    if raw_generator.isdigit() and len(raw_generator) <= 18:
        generator = Profile.objects.filter(pk=int(raw_generator), role=Profile.Role.GENERATOR).first()
    generator_id = generator.pk if generator else ""

    windows = filter_by_material(open_windows(), material)
    if generator:
        windows = windows.filter(generator=generator)
    page = Paginator(windows, PAGE_SIZE).get_page(request.GET.get("page"))

    def page_url(number):
        return _query(material=material, generator=generator_id, page=number) + LIST_ANCHOR

    filters = [{"label": "Todos", "url": _query(generator=generator_id) + LIST_ANCHOR, "active": not material}]
    for code, label in MATERIAL_LABELS.items():
        filters.append(
            {
                "label": label,
                "url": _query(material=code, generator=generator_id) + LIST_ANCHOR,
                "active": material == code,
            }
        )
    return {
        "page": page,
        "material": material,
        "filters": filters,
        "selected_generator": generator,
        "all_generators_url": _query(material=material) + LIST_ANCHOR,
        "previous_url": page_url(page.previous_page_number()) if page.has_previous() else "",
        "next_url": page_url(page.next_page_number()) if page.has_next() else "",
    }


def explore(request):
    completed = CollectionWindow.objects.filter(status=CollectionWindow.Status.COMPLETED)
    pins = generator_pins()
    context = _open_list(request)
    context.update(
        {
            "pins": pins,
            "completed": completed.select_related("generator").order_by("-scheduled_date", "-scheduled_time")[:5],
            "counts": {
                "open": open_windows().count(),
                "places": len(pins),
                "completed": completed.count(),
            },
        }
    )
    return render(request, "windows/home.html", context)


def window_list(request):
    """The old address of the list. Explorar shows the same list beside the map."""
    return render(request, "windows/window_list.html", _open_list(request))


def _steps(window):
    """State of the confirmation and collection steps: done, current, todo or missed."""
    status = CollectionWindow.Status
    if window.status == status.OPEN:
        return {"confirmed": "missed" if window.is_past else "current", "collect": "todo"}
    collect = {status.RESERVED: "current", status.COMPLETED: "done", status.MISSED: "missed"}[window.status]
    return {"confirmed": "done", "collect": collect}


def _action(window, profile, user, can_see):
    """The one thing this visitor can do on the window page, if any."""
    status = CollectionWindow.Status
    if window.status == status.OPEN:
        if window.is_past:
            return "past"
        if profile is not None and profile.is_collector:
            return "confirm"
        if not user.is_authenticated:
            return "login"
    elif window.status == status.RESERVED and can_see and profile.is_generator:
        return "close"
    return ""


def window_detail(request, pk):
    window = get_object_or_404(
        CollectionWindow.objects.select_related("generator", "generator__user"),
        pk=pk,
    )
    profile = getattr(request.user, "profile", None) if request.user.is_authenticated else None
    can_see = can_see_agreement(profile, window)
    place = None
    generator = window.generator
    if generator.latitude is not None and generator.longitude is not None:
        place = {
            "name": generator.public_name,
            "lat": float(generator.latitude),
            "lng": float(generator.longitude),
        }
    return render(
        request,
        "windows/window_detail.html",
        {
            "window": window,
            "can_see_agreement": can_see,
            "steps": _steps(window),
            "action": _action(window, profile, request.user, can_see),
            "place": place,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def window_create(request):
    profile = request.user.profile
    if not profile.is_generator:
        messages.error(request, "Só um estabelecimento pode publicar uma janela.")
        return redirect("home")
    if profile.latitude is None or profile.longitude is None:
        messages.error(request, "Marque o ponto do estabelecimento no perfil antes de publicar.")
        return redirect("profile")
    form = WindowForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        window = form.save(profile)
        messages.success(request, "Janela publicada. O primeiro coletador que confirmar fica com o horário.")
        return redirect("window_detail", pk=window.pk)
    return render(request, "windows/window_form.html", {"form": form})


def _reviewer_only(request):
    """None for the review account, otherwise the redirect with the refusal."""
    profile = getattr(request.user, "profile", None)
    if profile is not None and profile.is_reviewer:
        return None
    messages.error(request, "Os registros completos ficam na conta de acompanhamento.")
    return redirect("home")


def _all_windows():
    return list(
        CollectionWindow.objects.select_related("generator", "agreement__collector")
        .order_by("-scheduled_date", "-scheduled_time")
    )


@login_required
def records(request):
    refusal = _reviewer_only(request)
    if refusal:
        return refusal
    generators = list(
        Profile.objects.filter(role=Profile.Role.GENERATOR)
        .annotate(window_count=Count("windows"))
        .order_by("organization_name", "display_name")
    )
    windows = _all_windows()
    return render(
        request,
        "windows/records.html",
        {
            "generators": generators,
            "windows": windows,
            "summary": records_summary(windows, generators),
        },
    )


CSV_COLUMNS = [
    "Estabelecimento",
    "Endereço",
    "Data da coleta",
    "Hora da coleta",
    "Materiais",
    "Volume estimado",
    "Observação de acesso",
    "Situação",
    "Publicada em",
    "Confirmada por",
    "Tipo de coletador",
    "Confirmada em",
    "Espera até a confirmação (min)",
]


def _csv_text(value):
    """Typed text for a spreadsheet cell. The apostrophe stops it from running as a formula."""
    text = str(value or "")
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def _csv_moment(value):
    return timezone.localtime(value).strftime("%d/%m/%Y %H:%M")


@login_required
def records_csv(request):
    """Every window in one file. Same content as the records page: no phone, no e-mail."""
    refusal = _reviewer_only(request)
    if refusal:
        return refusal
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="janela-de-coleta-registros.csv"'
    # Excel in Portuguese reads accents with the byte-order mark and columns with ";".
    response.write("\ufeff")
    writer = csv.writer(response, delimiter=";")
    writer.writerow(CSV_COLUMNS)
    for window in _all_windows():
        agreement = agreement_of(window)
        row = [
            _csv_text(window.generator.public_name),
            _csv_text(window.generator.address),
            window.scheduled_date.strftime("%d/%m/%Y"),
            window.scheduled_time.strftime("%H:%M"),
            ", ".join(MATERIAL_LABELS.get(code, code) for code in window.material_list),
            _csv_text(window.estimated_volume),
            _csv_text(window.access_notes),
            STATUS_LABELS.get(window.status, window.status),
            _csv_moment(window.created_at),
        ]
        if agreement is None:
            row += ["", "", "", ""]
        else:
            minutes = wait_minutes(agreement.wait)
            row += [
                _csv_text(agreement.collector.display_name),
                KIND_LABELS.get(agreement.collector.collector_kind, ""),
                _csv_moment(agreement.confirmed_at),
                "" if minutes is None else minutes,
            ]
        writer.writerow(row)
    return response


@login_required
def mine(request):
    profile = request.user.profile
    if profile.is_reviewer:
        return redirect("records")
    if profile.is_generator:
        windows = profile.windows.select_related("generator").order_by("-scheduled_date", "-scheduled_time")
    else:
        windows = (
            CollectionWindow.objects.filter(agreement__collector=profile)
            .select_related("generator")
            .order_by("-scheduled_date", "-scheduled_time")
        )
    return render(request, "windows/mine.html", {"windows": windows})


@login_required
@require_POST
def window_confirm(request, pk):
    try:
        confirm_window(pk, request.user.profile)
    except CollectionWindow.DoesNotExist:
        messages.error(request, "Janela não encontrada.")
        return redirect("home")
    except WindowActionError as exc:
        messages.error(request, ACTION_MESSAGES[exc.code])
    else:
        messages.success(request, "Janela reservada. O acordo está visível para as duas partes.")
    return redirect("window_detail", pk=pk)


@login_required
@require_POST
def window_complete(request, pk):
    return _close(request, pk, CollectionWindow.Status.COMPLETED, "Coleta marcada como realizada.")


@login_required
@require_POST
def window_miss(request, pk):
    return _close(request, pk, CollectionWindow.Status.MISSED, "Coleta marcada como não realizada.")


def _close(request, pk, outcome, success):
    try:
        close_window(pk, request.user.profile, outcome)
    except CollectionWindow.DoesNotExist:
        messages.error(request, "Janela não encontrada.")
        return redirect("mine")
    except WindowActionError as exc:
        messages.error(request, ACTION_MESSAGES[exc.code])
    else:
        messages.success(request, success)
    return redirect("window_detail", pk=pk)
