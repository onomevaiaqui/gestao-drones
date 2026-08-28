from django import forms

from .models import TermoCoordenacao


SIM_NAO = (("", "Selecione"), ("true", "Sim"), ("false", "Não"))


class TermoCoordenacaoForm(forms.ModelForm):
    class Meta:
        model = TermoCoordenacao
        fields = [
            "operador_nome", "operador_endereco", "operador_telefone", "operador_email", "operador_sarpas",
            "responsavel_nome", "responsavel_funcao", "responsavel_endereco", "responsavel_telefone", "responsavel_email",
            "local_codigo", "local_natureza", "local_funcionamento", "local_observacoes",
            "limites_verticais", "limites_laterais", "coordenadas_wgs84",
            "objetivo_operacao", "periodo_operacao", "frequencia_duracao", "horarios_operacao",
            "tipo_operacao", "operacao_observacoes", "contato_previo", "informar_inicio_termino",
            "pessoal_dedicado_contatos", "suspensao_por_seguranca", "informar_contingencia",
            "procedimentos_emergencia", "descricao_coordenacao", "validade_meses", "local_assinatura",
            "data_assinatura", "representante_operador", "representante_ats",
        ]
        widgets = {
            "operador_nome": forms.TextInput(attrs={"class": "form-control"}),
            "operador_endereco": forms.TextInput(attrs={"class": "form-control"}),
            "operador_telefone": forms.TextInput(attrs={"class": "form-control"}),
            "operador_email": forms.EmailInput(attrs={"class": "form-control"}),
            "operador_sarpas": forms.TextInput(attrs={"class": "form-control"}),
            "responsavel_nome": forms.TextInput(attrs={"class": "form-control"}),
            "responsavel_funcao": forms.TextInput(attrs={"class": "form-control"}),
            "responsavel_endereco": forms.TextInput(attrs={"class": "form-control"}),
            "responsavel_telefone": forms.TextInput(attrs={"class": "form-control"}),
            "responsavel_email": forms.EmailInput(attrs={"class": "form-control"}),
            "local_codigo": forms.TextInput(attrs={"class": "form-control"}),
            "local_natureza": forms.TextInput(attrs={"class": "form-control"}),
            "local_funcionamento": forms.TextInput(attrs={"class": "form-control"}),
            "local_observacoes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "limites_verticais": forms.TextInput(attrs={"class": "form-control"}),
            "limites_laterais": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "coordenadas_wgs84": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "objetivo_operacao": forms.TextInput(attrs={"class": "form-control"}),
            "periodo_operacao": forms.TextInput(attrs={"class": "form-control"}),
            "frequencia_duracao": forms.TextInput(attrs={"class": "form-control"}),
            "horarios_operacao": forms.TextInput(attrs={"class": "form-control"}),
            "tipo_operacao": forms.Select(attrs={"class": "form-select"}),
            "operacao_observacoes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "descricao_coordenacao": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "validade_meses": forms.NumberInput(attrs={"class": "form-control", "min": 1, "max": 24}),
            "local_assinatura": forms.TextInput(attrs={"class": "form-control"}),
            "data_assinatura": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "representante_operador": forms.TextInput(attrs={"class": "form-control"}),
            "representante_ats": forms.TextInput(attrs={"class": "form-control"}),
        }
        labels = {
            "operador_nome": "Nome completo", "operador_endereco": "Endereço",
            "operador_telefone": "Telefone", "operador_email": "E-mail",
            "operador_sarpas": "ID operacional (Código SARPAS)",
            "responsavel_nome": "Nome completo", "responsavel_funcao": "Função",
            "responsavel_endereco": "Endereço", "responsavel_telefone": "Telefone",
            "responsavel_email": "E-mail", "local_codigo": "Código ICAO / identificação do EAC",
            "local_natureza": "Natureza / finalidade", "local_funcionamento": "Horário de funcionamento / ativação",
            "local_observacoes": "Observações", "limites_verticais": "Limites verticais",
            "limites_laterais": "Limites laterais", "coordenadas_wgs84": "Coordenadas geográficas (WGS84)",
            "objetivo_operacao": "Objetivo da operação", "periodo_operacao": "Período da operação",
            "frequencia_duracao": "Frequência / duração dos voos", "horarios_operacao": "Horários da operação",
            "tipo_operacao": "Tipo de operação", "operacao_observacoes": "Observações da operação",
            "descricao_coordenacao": "Descrição e procedimentos acordados", "validade_meses": "Validade em meses",
            "local_assinatura": "Local de assinatura", "data_assinatura": "Data de assinatura",
            "representante_operador": "Representante do operador UAS", "representante_ats": "Representante do órgão ATS / administrador",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        perguntas = {
            "contato_previo": "Haverá contato prévio com o operador do aeródromo/heliponto ou detentor do EAC?",
            "informar_inicio_termino": "A equipe informará o início e o término da operação?",
            "pessoal_dedicado_contatos": "Haverá pessoa dedicada para atendimento imediato dos contatos?",
            "suspensao_por_seguranca": "O órgão ATS/administrador poderá suspender a operação por segurança?",
            "informar_contingencia": "Serão informados os meios de contingência/emergência acionados?",
            "procedimentos_emergencia": "Os procedimentos de emergência e contingência foram acordados?",
        }
        for nome, rotulo in perguntas.items():
            valor = getattr(self.instance, nome, None) if self.instance and self.instance.pk else None
            self.fields[nome] = forms.TypedChoiceField(
                label=rotulo, choices=SIM_NAO, coerce=lambda item: item == "true",
                empty_value=None, initial="true" if valor is True else "false" if valor is False else "",
                widget=forms.Select(attrs={"class": "form-select"}),
            )
