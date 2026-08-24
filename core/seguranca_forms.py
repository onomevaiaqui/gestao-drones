from django import forms

from .models import AvaliacaoRisco, Incidente


class AvaliacaoRiscoForm(forms.ModelForm):
    class Meta:
        model = AvaliacaoRisco
        fields = [
            "perigos_identificados", "probabilidade_inicial", "impacto_inicial",
            "medidas_mitigadoras", "probabilidade_residual", "impacto_residual",
            "condicoes_meteorologicas", "pessoas_expostas", "area_controlada", "observacoes",
        ]
        widgets = {
            "perigos_identificados": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "probabilidade_inicial": forms.Select(attrs={"class": "form-select"}),
            "impacto_inicial": forms.Select(attrs={"class": "form-select"}),
            "medidas_mitigadoras": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "probabilidade_residual": forms.Select(attrs={"class": "form-select"}),
            "impacto_residual": forms.Select(attrs={"class": "form-select"}),
            "condicoes_meteorologicas": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "pessoas_expostas": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "area_controlada": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "observacoes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }


class IncidenteForm(forms.ModelForm):
    class Meta:
        model = Incidente
        fields = [
            "alocacao", "tipo", "gravidade", "data_hora", "descricao",
            "acoes_imediatas", "danos", "houve_lesao", "houve_dano_terceiro",
            "notificacao_obrigatoria", "anexo", "status", "causa_raiz",
            "acoes_corretivas", "responsavel_investigacao",
        ]
        widgets = {
            "alocacao": forms.Select(attrs={"class": "form-select"}),
            "tipo": forms.Select(attrs={"class": "form-select"}),
            "gravidade": forms.Select(attrs={"class": "form-select"}),
            "data_hora": forms.DateTimeInput(attrs={"class": "form-control", "type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "descricao": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "acoes_imediatas": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "danos": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "houve_lesao": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "houve_dano_terceiro": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "notificacao_obrigatoria": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "anexo": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "causa_raiz": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "acoes_corretivas": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "responsavel_investigacao": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, eh_admin=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["data_hora"].input_formats = ["%Y-%m-%dT%H:%M"]
        if not eh_admin:
            for campo in ["status", "causa_raiz", "acoes_corretivas", "responsavel_investigacao", "notificacao_obrigatoria"]:
                self.fields.pop(campo)

    def clean(self):
        dados = super().clean()
        if dados.get("status") == "encerrado":
            if not dados.get("causa_raiz"):
                self.add_error("causa_raiz", "Informe a causa-raiz antes de encerrar.")
            if not dados.get("acoes_corretivas"):
                self.add_error("acoes_corretivas", "Informe as ações corretivas antes de encerrar.")
        return dados
