from django import forms

from .models import Documento


class DocumentoDroneForm(forms.ModelForm):
    class Meta:
        model = Documento
        fields = ["titulo", "tipo", "numero", "data_emissao", "data_validade", "arquivo", "observacoes"]
        widgets = {
            "titulo": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex.: Certificado de cadastro"}),
            "tipo": forms.Select(attrs={"class": "form-select"}),
            "numero": forms.TextInput(attrs={"class": "form-control"}),
            "data_emissao": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "data_validade": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "arquivo": forms.ClearableFileInput(attrs={"class": "form-control", "accept": ".pdf,.jpg,.jpeg,.png,.doc,.docx"}),
            "observacoes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }
        labels = {"numero": "Número / referência", "data_emissao": "Emissão", "data_validade": "Validade"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        permitidos = {"registro_drone", "seguro", "autorizacao", "manual", "nota_fiscal", "outro"}
        self.fields["tipo"].choices = [(v, n) for v, n in Documento.TIPO_CHOICES if v in permitidos]

    def clean_arquivo(self):
        arquivo = self.cleaned_data.get("arquivo")
        if arquivo and arquivo.size > 10 * 1024 * 1024:
            raise forms.ValidationError("O arquivo não pode exceder 10 MB.")
        return arquivo
