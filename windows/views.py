from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from windows.forms import WindowForm
from windows.models import MATERIAL_LABELS, CollectionWindow
from windows.queries import filter_by_material, generator_pins, open_windows
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


def home(request):
    windows = open_windows()[:5]
    completed = (
        CollectionWindow.objects.filter(status=CollectionWindow.Status.COMPLETED)
        .select_related("generator")
        .order_by("-scheduled_date", "-scheduled_time")[:5]
    )
    return render(
        request,
        "windows/home.html",
        {"pins": generator_pins(), "windows": windows, "completed": completed},
    )


def window_list(request):
    material = request.GET.get("material", "")
    generator_id = request.GET.get("generator", "")
    windows = open_windows()
    windows = filter_by_material(windows, material)
    if generator_id.isdigit():
        windows = windows.filter(generator_id=int(generator_id))
    page = Paginator(windows, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "windows/window_list.html",
        {
            "page": page,
            "material": material if material in MATERIAL_LABELS else "",
            "materials": MATERIAL_LABELS,
            "generator_id": generator_id if generator_id.isdigit() else "",
        },
    )


def window_detail(request, pk):
    window = get_object_or_404(
        CollectionWindow.objects.select_related("generator", "generator__user"),
        pk=pk,
    )
    profile = getattr(request.user, "profile", None) if request.user.is_authenticated else None
    return render(
        request,
        "windows/window_detail.html",
        {
            "window": window,
            "can_see_agreement": can_see_agreement(profile, window),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def window_create(request):
    profile = request.user.profile
    if not profile.is_generator:
        messages.error(request, "Só um estabelecimento pode publicar uma janela.")
        return redirect("window_list")
    if profile.latitude is None or profile.longitude is None:
        messages.error(request, "Marque o ponto do estabelecimento no perfil antes de publicar.")
        return redirect("profile")
    form = WindowForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        window = form.save(profile)
        messages.success(request, "Janela publicada. O primeiro coletador que confirmar fica com o horário.")
        return redirect("window_detail", pk=window.pk)
    return render(request, "windows/window_form.html", {"form": form})


@login_required
def mine(request):
    profile = request.user.profile
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
        return redirect("window_list")
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
