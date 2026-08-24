from django import forms

from .models import Documento, QualificacaoPiloto


class QualificacaoPilotoForm(forms.ModelForm):
    class Meta:
        model = QualificacaoPiloto
        exclude = ["piloto", "criado_por"]
        widgets = {
            "nome": forms.TextInput(attrs={"class": "form-control"}),
            "categoria": forms.Select(attrs={"class": "form-select"}),
            "nivel": forms.Select(attrs={"class": "form-select"}),
            "instituicao": forms.TextInput(attrs={"class": "form-control"}),
            "numero_certificado": forms.TextInput(attrs={"class": "form-control"}),
            "modelo_drone": forms.TextInput(attrs={"class": "form-control"}),
            "tipo_operacao": forms.TextInput(attrs={"class": "form-control"}),
            "carga_horaria": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "data_conclusao": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "data_validade": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "documento": forms.Select(attrs={"class": "form-select"}),
            "observacoes": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "ativo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, piloto=None, **kwargs):
        super().__init__(*args, **kwargs)
        if piloto:
            self.fields["documento"].queryset = Documento.objects.filter(piloto=piloto, ativo=True)
