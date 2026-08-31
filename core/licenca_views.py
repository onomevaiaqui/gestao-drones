from django.contrib import messages
from django.shortcuts import redirect, render

from .licenca_forms import LicencaUploadForm
from .licenciamento import ErroLicenca, ativar_licenca, estado_licenca
from .models import InstalacaoSISMOD, LicencaSISMOD
from .permissoes import admin_required


@admin_required
def configuracao_licenca(request):
    instalacao = InstalacaoSISMOD.atual()
    form = LicencaUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            licenca = ativar_licenca(form.cleaned_data["arquivo"].read(), request.user)
        except ErroLicenca as exc:
            form.add_error("arquivo", str(exc))
        else:
            messages.success(request, f"Licença de {licenca.empresa_nome} ativada até {licenca.valida_ate:%d/%m/%Y}.")
            return redirect("configuracao_licenca")
    return render(request, "licenciamento/configuracao.html", {
        "form": form,
        "instalacao": instalacao,
        "estado_licenca": estado_licenca(),
        "historico": LicencaSISMOD.objects.select_related("ativada_por")[:10],
        "eh_admin": True,
        "visao_global": True,
    })
