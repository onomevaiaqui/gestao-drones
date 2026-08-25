from pathlib import Path

from django import forms

from .models import Voo


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def clean(self, data, initial=None):
        limpar = super().clean
        if isinstance(data, (list, tuple)):
            return [limpar(item, initial) for item in data]
        return [limpar(data, initial)] if data else []


class VooChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, voo):
        data = voo.data.strftime("%d/%m/%Y") if voo.data else "data pela telemetria"
        total_logs = getattr(voo, "total_logs", None)
        if total_logs is None:
            total_logs = voo.importacoes_log.count()
        logs = f"{total_logs} log" if total_logs == 1 else f"{total_logs} logs"
        return (
            f"Voo #{voo.pk} · {voo.drone.nome} · {voo.piloto.nome} · "
            f"{voo.get_finalidade_display()} · {data} · {logs}"
        )


class ImportacaoLogForm(forms.Form):
    MODO_CHOICES = [("arquivo", "Arquivo individual"), ("pasta", "Pasta completa")]

    voo = VooChoiceField(
        label="Voo que receberá os logs",
        queryset=Voo.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    modo = forms.ChoiceField(
        choices=MODO_CHOICES, initial="arquivo", widget=forms.RadioSelect(attrs={"class": "import-mode-choice"})
    )
    arquivo = forms.FileField(
        required=False, widget=forms.FileInput(attrs={"class": "form-control", "accept": ".csv,.txt"})
    )
    pasta = MultipleFileField(
        required=False,
        widget=MultipleFileInput(attrs={
            "class": "form-control", "accept": ".csv,.txt", "webkitdirectory": "", "directory": "",
        }),
    )

    def __init__(self, *args, voos=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["voo"].queryset = voos if voos is not None else Voo.objects.none()

    @staticmethod
    def _validar_arquivo(arquivo):
        if Path(arquivo.name).suffix.lower() not in [".csv", ".txt"]:
            return False
        if arquivo.size > 20 * 1024 * 1024:
            raise forms.ValidationError(f"{arquivo.name}: o arquivo não pode exceder 20 MB.")
        return True

    def clean(self):
        dados = super().clean()
        if dados.get("modo") == "arquivo":
            arquivo = dados.get("arquivo")
            if not arquivo:
                self.add_error("arquivo", "Selecione um arquivo de telemetria.")
            elif not self._validar_arquivo(arquivo):
                self.add_error("arquivo", "Envie um arquivo CSV ou TXT.")
            dados["arquivos"] = [arquivo] if arquivo else []
        else:
            recebidos = dados.get("pasta") or []
            compativeis = [arquivo for arquivo in recebidos if self._validar_arquivo(arquivo)]
            if not compativeis:
                self.add_error("pasta", "A pasta não contém arquivos CSV ou TXT compatíveis.")
            elif len(compativeis) > 100:
                self.add_error("pasta", "Selecione uma pasta com no máximo 100 logs.")
            dados["arquivos"] = compativeis
        return dados
