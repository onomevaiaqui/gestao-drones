from django import forms

from .models import Documento


class DocumentoForm(forms.ModelForm):
    class Meta:
        model = Documento
        exclude = ["criado_por"]
        widgets = {
            "titulo": forms.TextInput(attrs={"class": "form-control"}),
            "tipo": forms.Select(attrs={"class": "form-select"}),
            "numero": forms.TextInput(attrs={"class": "form-control"}),
            "piloto": forms.Select(attrs={"class": "form-select"}),
            "drone": forms.Select(attrs={"class": "form-select"}),
            "bateria": forms.Select(attrs={"class": "form-select"}),
            "organizacional": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "data_emissao": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "data_validade": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "arquivo": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "observacoes": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "ativo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        labels = {
            "numero": "Número / referência",
            "organizacional": "Documento geral da organização",
            "data_emissao": "Data de emissão",
            "data_validade": "Data de validade",
        }
