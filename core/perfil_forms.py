from django import forms

from .models import Documento, Piloto


class PerfilUsuarioForm(forms.ModelForm):
    email = forms.EmailField(label="E-mail", required=False, widget=forms.EmailInput(attrs={"class": "form-control"}))

    class Meta:
        model = Piloto
        fields = ["nome", "matricula", "foto"]
        widgets = {
            "nome": forms.TextInput(attrs={"class": "form-control"}),
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


class DocumentoPerfilForm(forms.ModelForm):
    class Meta:
        model = Documento
        fields = ["titulo", "tipo", "numero", "data_emissao", "data_validade", "arquivo", "observacoes"]
        widgets = {
            "titulo": forms.TextInput(attrs={"class": "form-control"}),
            "tipo": forms.Select(attrs={"class": "form-select"}),
            "numero": forms.TextInput(attrs={"class": "form-control"}),
            "data_emissao": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "data_validade": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "arquivo": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "observacoes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def clean_arquivo(self):
        arquivo = self.cleaned_data.get("arquivo")
        if arquivo and arquivo.size > 10 * 1024 * 1024:
            raise forms.ValidationError("O arquivo não pode exceder 10 MB.")
        return arquivo
