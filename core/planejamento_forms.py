import json

from django import forms

from .models import PlanejamentoVoo, Piloto
from .planejamento_service import calcular_geometria
from .planejamento_kml import extrair_poligono_kml


class PlanejamentoVooForm(forms.ModelForm):
    area_geojson_texto = forms.CharField(widget=forms.HiddenInput(), required=False)
    arquivo_area = forms.FileField(required=False, label="Importar área KML/KMZ", widget=forms.FileInput(
        attrs={"class":"form-control", "accept":".kml,.kmz"}
    ), help_text="Opcional. O maior polígono do arquivo será usado como área planejada.")

    class Meta:
        model = PlanejamentoVoo
        fields = [
            "titulo", "piloto", "local", "data", "data_fim", "hora_inicio", "hora_fim", "finalidade",
            "altura_maxima_m", "gera_dados_aerolevantamento", "tipo_aerolevantamento",
            "atividade_agroflorestal", "exclusivo_proprietario_rural", "dentro_condicionantes_ica",
            "interseca_area_sensivel_defesa", "projeto_contiguo_12_meses", "observacoes",
        ]
        widgets = {
            "titulo": forms.TextInput(attrs={"class": "form-control"}),
            "piloto": forms.Select(attrs={"class": "form-select"}),
            "local": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex.: Parque Ambiental, Guarapuava/PR"}),
            "data": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "data_fim": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "hora_inicio": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
            "hora_fim": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
            "finalidade": forms.Select(attrs={"class": "form-select"}),
            "altura_maxima_m": forms.NumberInput(attrs={"class": "form-control", "min": 1, "max": 500}),
            "gera_dados_aerolevantamento": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "tipo_aerolevantamento": forms.Select(attrs={"class": "form-select"}),
            "atividade_agroflorestal": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "exclusivo_proprietario_rural": forms.Select(attrs={"class": "form-select"}),
            "dentro_condicionantes_ica": forms.Select(attrs={"class": "form-select"}),
            "interseca_area_sensivel_defesa": forms.Select(attrs={"class": "form-select"}),
            "projeto_contiguo_12_meses": forms.Select(attrs={"class": "form-select"}),
            "observacoes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_fields([
            "titulo", "piloto", "local", "data", "data_fim", "hora_inicio", "hora_fim", "finalidade",
            "altura_maxima_m", "arquivo_area", "gera_dados_aerolevantamento", "tipo_aerolevantamento",
            "atividade_agroflorestal", "exclusivo_proprietario_rural", "dentro_condicionantes_ica",
            "interseca_area_sensivel_defesa", "projeto_contiguo_12_meses", "observacoes", "area_geojson_texto",
        ])
        self.fields["piloto"].queryset = Piloto.objects.filter(ativo=True)
        self.fields["data"].label = "Data inicial"
        self.fields["data_fim"].label = "Data final"
        self.fields["data_fim"].required = True
        if self.instance and self.instance.pk:
            self.fields["area_geojson_texto"].initial = json.dumps(self.instance.area_geojson)
        self.fields["tipo_aerolevantamento"].required = False
        self.fields["tipo_aerolevantamento"].help_text = "Preencha quando a operação produzir dados de aerolevantamento."
        self.fields["interseca_area_sensivel_defesa"].help_text = "A camada AISWEB não substitui esta confirmação; consulte o SisCLATEN/Ministério da Defesa."

    def clean(self):
        dados = super().clean()
        data, data_fim = dados.get("data"), dados.get("data_fim")
        inicio, fim = dados.get("hora_inicio"), dados.get("hora_fim")
        if data and data_fim and data_fim < data:
            self.add_error("data_fim", "A data final não pode ser anterior à data inicial.")
        if data and data_fim == data and inicio and fim and fim <= inicio:
            self.add_error("hora_fim", "O horário final deve ser posterior ao inicial.")
        if dados.get("gera_dados_aerolevantamento") and not dados.get("tipo_aerolevantamento"):
            self.add_error("tipo_aerolevantamento", "Informe o tipo de aerolevantamento.")
        bruto = dados.get("area_geojson_texto")
        arquivo = dados.get("arquivo_area")
        if arquivo:
            try:
                geometria = extrair_poligono_kml(arquivo)
                dados["geometria_calculada"] = calcular_geometria(geometria)
            except (TypeError, ValueError) as erro:
                self.add_error("arquivo_area", str(erro))
        elif bruto:
            try:
                geometria = json.loads(bruto)
                calculada = calcular_geometria(geometria)
                dados["geometria_calculada"] = calculada
            except (TypeError, ValueError, json.JSONDecodeError) as erro:
                self.add_error("area_geojson_texto", str(erro))
        else:
            self.add_error("area_geojson_texto", "Desenhe a área no mapa ou envie um KML/KMZ.")
        return dados

    def save(self, commit=True):
        obj = super().save(commit=False)
        calculada = self.cleaned_data["geometria_calculada"]
        obj.area_geojson = calculada["geojson"]
        obj.centro_latitude = calculada["centro_latitude"]
        obj.centro_longitude = calculada["centro_longitude"]
        obj.area_hectares = calculada["area_hectares"]
        if commit:
            obj.save()
        return obj
