from django import forms

from .models import Documento


DOCUMENTO_WIDGETS = {
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
    "observacoes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    "ativo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
}


class DocumentoArquivoMixin:
    limite_arquivo = 10 * 1024 * 1024

    def clean_arquivo(self):
        arquivo = self.cleaned_data.get("arquivo")
        if arquivo and arquivo.size > self.limite_arquivo:
            raise forms.ValidationError("O arquivo não pode exceder 10 MB.")
        return arquivo


class DocumentoForm(DocumentoArquivoMixin, forms.ModelForm):
    class Meta:
        model = Documento
        exclude = ["criado_por"]
        widgets = DOCUMENTO_WIDGETS
        labels = {
            "numero": "Número / referência",
            "organizacional": "Documento geral da organização",
            "data_emissao": "Data de emissão",
            "data_validade": "Data de validade",
        }
