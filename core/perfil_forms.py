from django import forms

from .documento_forms import DOCUMENTO_WIDGETS, DocumentoArquivoMixin
from .models import Documento, Piloto


class PerfilUsuarioForm(forms.ModelForm):
    email = forms.EmailField(label="E-mail", required=False, widget=forms.EmailInput(attrs={"class": "form-control"}))

    class Meta:
        model = Piloto
        fields = ["nome", "cpf", "codigo_sarpas", "matricula", "foto"]
        widgets = {
            "nome": forms.TextInput(attrs={"class": "form-control"}),
            "cpf": forms.TextInput(attrs={"class": "form-control", "placeholder": "000.000.000-00"}),
            "codigo_sarpas": forms.TextInput(attrs={"class": "form-control", "placeholder": "Código do usuário no SARPAS"}),
            "matricula": forms.TextInput(attrs={"class": "form-control"}),
            "foto": forms.ClearableFileInput(attrs={"class": "form-control", "accept": "image/*"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user_id:
            self.fields["email"].initial = self.instance.user.email

    def save(self, commit=True):
        piloto = super().save(commit=commit)
        if piloto.user_id:
            piloto.user.email = self.cleaned_data.get("email", "")
            if commit:
                piloto.user.save(update_fields=["email"])
        return piloto


class DocumentoPerfilForm(DocumentoArquivoMixin, forms.ModelForm):
    class Meta:
        model = Documento
        fields = ["titulo", "tipo", "numero", "data_emissao", "data_validade", "arquivo", "observacoes"]
        widgets = {campo: DOCUMENTO_WIDGETS[campo] for campo in (
            "titulo", "tipo", "numero", "data_emissao", "data_validade", "arquivo", "observacoes"
        )}
