from django import forms

from .models import Componente


class ComponenteForm(forms.ModelForm):
    motivo_movimentacao = forms.CharField(
        label="Motivo da alteração", required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex.: instalação, substituição ou envio para manutenção"}),
    )

    class Meta:
        model = Componente
        fields = [
            "codigo", "nome", "tipo", "fabricante", "modelo", "numero_serie", "localizacao",
            "drone", "status", "data_aquisicao", "data_instalacao", "vida_util_horas", "observacoes",
        ]
        widgets = {
            "codigo": forms.TextInput(attrs={"class": "form-control"}),
            "nome": forms.TextInput(attrs={"class": "form-control"}),
            "tipo": forms.Select(attrs={"class": "form-select"}),
            "fabricante": forms.TextInput(attrs={"class": "form-control"}),
            "modelo": forms.TextInput(attrs={"class": "form-control"}),
            "numero_serie": forms.TextInput(attrs={"class": "form-control"}),
            "localizacao": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Ex.: Almoxarifado, Laboratório ou aeronave",
            }),
            "drone": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "data_aquisicao": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "data_instalacao": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "vida_util_horas": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "observacoes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def clean(self):
        cleaned = super().clean()
        drone, status = cleaned.get("drone"), cleaned.get("status")
        if status == "instalado" and not drone:
            self.add_error("drone", "Informe em qual drone o componente está instalado.")
        if drone and status != "instalado":
            self.add_error("status", "Um componente vinculado a um drone deve estar com status Instalado.")
        return cleaned
