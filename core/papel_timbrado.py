from io import BytesIO

from django import forms
from pypdf import PageObject, PdfReader, PdfWriter, Transformation

from .models import ConfiguracaoPapelTimbrado


class PapelTimbradoRelatorioForm(forms.ModelForm):
    class Meta:
        model = ConfiguracaoPapelTimbrado
        fields = ["modelo_relatorios"]
        widgets = {"modelo_relatorios": forms.ClearableFileInput(attrs={"class": "form-control", "accept": "application/pdf,.pdf"})}
        labels = {"modelo_relatorios": "Modelo PDF dos relatórios"}

    def clean_modelo_relatorios(self):
        return _validar_pdf(self.cleaned_data.get("modelo_relatorios"))


class PapelTimbradoRiscoForm(forms.ModelForm):
    class Meta:
        model = ConfiguracaoPapelTimbrado
        fields = ["modelo_avaliacao_risco"]
        widgets = {"modelo_avaliacao_risco": forms.ClearableFileInput(attrs={"class": "form-control", "accept": "application/pdf,.pdf"})}
        labels = {"modelo_avaliacao_risco": "Modelo PDF da avaliação de risco"}

    def clean_modelo_avaliacao_risco(self):
        return _validar_pdf(self.cleaned_data.get("modelo_avaliacao_risco"))


def _validar_pdf(arquivo):
    if not arquivo:
        return arquivo
    if arquivo.size > 10 * 1024 * 1024:
        raise forms.ValidationError("O modelo não pode exceder 10 MB.")
    if not arquivo.name.lower().endswith(".pdf"):
        raise forms.ValidationError("Envie um arquivo PDF.")
    try:
        PdfReader(arquivo).pages[0]
        arquivo.seek(0)
    except Exception as exc:
        raise forms.ValidationError("O arquivo não é um PDF válido.") from exc
    return arquivo


def aplicar_papel_timbrado(conteudo_pdf, arquivo_modelo):
    if not arquivo_modelo:
        return conteudo_pdf
    try:
        conteudo = PdfReader(BytesIO(conteudo_pdf))
        with arquivo_modelo.open("rb") as modelo_arquivo:
            modelo = PdfReader(modelo_arquivo)
            base_original = modelo.pages[0]
            escritor = PdfWriter()
            for pagina_conteudo in conteudo.pages:
                largura = float(pagina_conteudo.mediabox.width)
                altura = float(pagina_conteudo.mediabox.height)
                escala_x = largura / float(base_original.mediabox.width)
                escala_y = altura / float(base_original.mediabox.height)
                pagina = PageObject.create_blank_page(width=largura, height=altura)
                pagina.merge_transformed_page(base_original, Transformation().scale(escala_x, escala_y))
                pagina.merge_page(pagina_conteudo)
                escritor.add_page(pagina)
            saida = BytesIO(); escritor.write(saida)
            return saida.getvalue()
    except Exception:
        return conteudo_pdf
