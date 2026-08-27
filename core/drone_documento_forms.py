from django import forms

from .documento_forms import DOCUMENTO_WIDGETS, DocumentoArquivoMixin
from .models import Documento


class DocumentoDroneForm(DocumentoArquivoMixin, forms.ModelForm):
    class Meta:
        model = Documento
        fields = ["titulo", "tipo", "data_emissao", "data_validade", "arquivo", "observacoes"]
        widgets = {campo: DOCUMENTO_WIDGETS[campo] for campo in (
            "titulo", "tipo", "data_emissao", "data_validade", "arquivo", "observacoes"
        )}
        labels = {"data_emissao": "Emissão", "data_validade": "Validade"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["arquivo"].widget.attrs["accept"] = ".pdf,.jpg,.jpeg,.png,.doc,.docx"
        permitidos = {"registro_drone", "seguro", "autorizacao", "manual", "nota_fiscal", "outro"}
        self.fields["tipo"].choices = [(v, n) for v, n in Documento.TIPO_CHOICES if v in permitidos]
