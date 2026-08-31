from django import forms


class LicencaUploadForm(forms.Form):
    arquivo = forms.FileField(
        label="Arquivo de licença",
        widget=forms.ClearableFileInput(attrs={"class": "form-control", "accept": ".json,.sismod-license"}),
    )

    def clean_arquivo(self):
        arquivo = self.cleaned_data["arquivo"]
        if arquivo.size > 128 * 1024:
            raise forms.ValidationError("O arquivo de licença excede 128 KB.")
        return arquivo
