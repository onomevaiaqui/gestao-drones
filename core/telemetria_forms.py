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
    EXTENSOES_SUPORTADAS = [".csv", ".txt", ".json", ".bin", ".ulg"]

    voo = VooChoiceField(
        label="Voo que receberá os logs",
        queryset=Voo.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    modo = forms.ChoiceField(
        choices=MODO_CHOICES, initial="arquivo", widget=forms.RadioSelect(attrs={"class": "import-mode-choice"})
    )
    arquivo = forms.FileField(
        required=False, widget=forms.FileInput(attrs={"class": "form-control"})
    )
    pasta = MultipleFileField(
        required=False,
        widget=MultipleFileInput(attrs={
            "class": "form-control", "webkitdirectory": "", "directory": "",
        }),
    )

    def __init__(self, *args, voos=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["voo"].queryset = voos if voos is not None else Voo.objects.none()

    @staticmethod
    def _validar_arquivo(arquivo):
        extensao = Path(arquivo.name).suffix.lower()
        autel_sem_extensao = False
        if not extensao:
            posicao = arquivo.tell()
            autel_sem_extensao = arquivo.read(8) == b"AUTEL_FR"
            arquivo.seek(posicao)
        if extensao not in ImportacaoLogForm.EXTENSOES_SUPORTADAS and not autel_sem_extensao:
            return False
        limite_mb = 200 if extensao in [".bin", ".ulg"] or autel_sem_extensao else 20
        if arquivo.size > limite_mb * 1024 * 1024:
            raise forms.ValidationError(f"{arquivo.name}: o arquivo não pode exceder {limite_mb} MB.")
        return True

    def clean(self):
        dados = super().clean()
        if dados.get("modo") == "arquivo":
            arquivo = dados.get("arquivo")
            if not arquivo:
                self.add_error("arquivo", "Selecione um arquivo de telemetria.")
            elif not self._validar_arquivo(arquivo):
                self.add_error("arquivo", "Envie CSV, DJI TXT, AUTEL_FR, JSON (eMotion), BIN (ArduPilot) ou ULG (PX4/Wingtra).")
            dados["arquivos"] = [arquivo] if arquivo else []
        else:
            recebidos = dados.get("pasta") or []
            compativeis = [arquivo for arquivo in recebidos if self._validar_arquivo(arquivo)]
            if not compativeis:
                self.add_error("pasta", "A pasta não contém arquivos CSV, DJI TXT, AUTEL_FR, JSON, BIN ou ULG compatíveis.")
            elif len(compativeis) > 100:
                self.add_error("pasta", "Selecione uma pasta com no máximo 100 logs.")
            dados["arquivos"] = compativeis
        return dados
