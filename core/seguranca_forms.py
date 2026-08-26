import json

from django import forms

from .models import AvaliacaoRisco, Incidente


class AvaliacaoRiscoForm(forms.ModelForm):
    situacoes_risco_json = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = AvaliacaoRisco
        fields = [
            "operador_nome", "operador_documento", "aeronave_identificacao",
            "cenario_operacional", "aspectos_gerais", "legislacao_aplicavel",
            "area_distante_terceiros", "treinamento_requerido", "descricao_treinamento",
            "procedimento_acidente", "condicoes_meteorologicas",
            "pessoas_expostas", "area_controlada", "observacoes",
            "responsavel_informacoes", "data_avaliacao", "validade_ate", "declaracao_conformidade",
        ]
        widgets = {
            "operador_nome": forms.TextInput(attrs={"class": "form-control"}),
            "operador_documento": forms.TextInput(attrs={"class": "form-control"}),
            "aeronave_identificacao": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "cenario_operacional": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "aspectos_gerais": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "legislacao_aplicavel": forms.Textarea(attrs={"class": "form-control", "rows": 7}),
            "area_distante_terceiros": forms.Select(attrs={"class": "form-select"}),
            "treinamento_requerido": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "descricao_treinamento": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "procedimento_acidente": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "condicoes_meteorologicas": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "pessoas_expostas": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "area_controlada": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "observacoes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "responsavel_informacoes": forms.TextInput(attrs={"class": "form-control"}),
            "data_avaliacao": forms.DateInput(attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"),
            "validade_ate": forms.DateInput(attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"),
            "declaracao_conformidade": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["data_avaliacao"].input_formats = ["%Y-%m-%d"]
        self.fields["validade_ate"].input_formats = ["%Y-%m-%d"]
        situacoes = self.initial.get("situacoes_risco") or (self.instance.situacoes_risco if self.instance.pk else [])
        self.initial["situacoes_risco_json"] = json.dumps(situacoes, ensure_ascii=False)
        modernos = not self.is_bound or "situacoes_risco_json" in self.data
        for nome in ["operador_nome", "operador_documento", "aeronave_identificacao", "cenario_operacional", "aspectos_gerais", "legislacao_aplicavel", "area_distante_terceiros", "procedimento_acidente", "responsavel_informacoes", "data_avaliacao", "validade_ate", "declaracao_conformidade"]:
            self.fields[nome].required = True
            if self.is_bound and not modernos:
                self.fields[nome].required = False

    def clean_situacoes_risco_json(self):
        bruto = self.cleaned_data.get("situacoes_risco_json") or self.initial.get("situacoes_risco_json") or "[]"
        try:
            itens = json.loads(bruto)
        except (TypeError, ValueError):
            raise forms.ValidationError("A tabela de riscos está inválida. Recarregue a página e tente novamente.")
        if (not isinstance(itens, list) or len(itens) < 3) and "situacoes_risco_json" in self.data:
            raise forms.ValidationError("Mantenha ao menos três situações de risco na avaliação.")
        if not itens:
            return []
        for item in itens:
            if not all(str(item.get(c, "")).strip() for c in ("titulo", "perigo", "medidas")):
                raise forms.ValidationError("Preencha situação, perigo e mitigação em todas as linhas.")
            if int(item.get("probabilidade", 0)) not in range(1, 6) or item.get("severidade") not in "ABCDE":
                raise forms.ValidationError("Probabilidade ou severidade inválida na tabela de riscos.")
        return itens

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.situacoes_risco = self.cleaned_data.get("situacoes_risco_json", [])
        if obj.situacoes_risco:
            obj.perigos_identificados = "\n".join(f"• {i['titulo']}: {i['perigo']}" for i in obj.situacoes_risco)
            obj.medidas_mitigadoras = "\n".join(f"• {i['titulo']}: {i['medidas']}" for i in obj.situacoes_risco)
            obj.probabilidade_inicial = max(int(i["probabilidade"]) for i in obj.situacoes_risco)
            obj.impacto_inicial = max(5 - "ABCDE".index(i["severidade"]) for i in obj.situacoes_risco)
            obj.probabilidade_residual = max(int(i.get("probabilidade_residual", 1)) for i in obj.situacoes_risco)
            obj.impacto_residual = max(5 - "ABCDE".index(i.get("severidade_residual", "E")) for i in obj.situacoes_risco)
        if commit: obj.save()
        return obj


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
