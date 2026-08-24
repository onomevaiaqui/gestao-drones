from django import forms

from .models import Bateria


class BateriaForm(forms.ModelForm):
    class Meta:
        model = Bateria
        fields = [
            "codigo", "numero_serie", "fabricante", "modelo",
            "capacidade_mah", "drone", "data_aquisicao",
            "ciclos_informados", "saude_percentual", "status",
            "localizacao", "observacoes",
        ]
        widgets = {
            "codigo": forms.TextInput(attrs={"class": "form-control"}),
            "numero_serie": forms.TextInput(attrs={"class": "form-control"}),
            "fabricante": forms.TextInput(attrs={"class": "form-control"}),
            "modelo": forms.TextInput(attrs={"class": "form-control"}),
            "capacidade_mah": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "drone": forms.Select(attrs={"class": "form-select"}),
            "data_aquisicao": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "ciclos_informados": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "saude_percentual": forms.NumberInput(attrs={"class": "form-control", "min": 0, "max": 100}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "localizacao": forms.TextInput(attrs={"class": "form-control"}),
            "observacoes": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        }
        labels = {
            "codigo": "Código interno",
            "numero_serie": "Número de série",
            "capacidade_mah": "Capacidade (mAh)",
            "ciclos_informados": "Ciclos anteriores ao cadastro",
            "saude_percentual": "Saúde estimada (%)",
        }

    def clean_saude_percentual(self):
        valor = self.cleaned_data["saude_percentual"]
        if not 0 <= valor <= 100:
            raise forms.ValidationError("Informe um valor entre 0 e 100.")
        return valor
