from pathlib import Path

from django import forms

from .models import ImportacaoLog, Voo


class ImportacaoLogForm(forms.ModelForm):
    atualizar_voo = forms.BooleanField(
        required=False, label="Atualizar distância e bateria do voo com o resumo importado",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    class Meta:
        model = ImportacaoLog
        fields = ["voo", "arquivo"]
        widgets = {
            "voo": forms.Select(attrs={"class": "form-select"}),
            "arquivo": forms.FileInput(attrs={"class": "form-control", "accept": ".csv,.txt"}),
        }

    def __init__(self, *args, voos=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["voo"].queryset = voos if voos is not None else Voo.objects.none()

    def clean_arquivo(self):
        arquivo = self.cleaned_data["arquivo"]
        if Path(arquivo.name).suffix.lower() not in [".csv", ".txt"]:
            raise forms.ValidationError("Envie um arquivo CSV ou TXT.")
        if arquivo.size > 20 * 1024 * 1024:
            raise forms.ValidationError("O arquivo não pode exceder 20 MB.")
        return arquivo
