import json

from django import forms

from .models import PlanejamentoVoo, Piloto
from .planejamento_service import calcular_geometria


class PlanejamentoVooForm(forms.ModelForm):
    area_geojson_texto = forms.CharField(widget=forms.HiddenInput(), required=True)

    class Meta:
        model = PlanejamentoVoo
        fields = [
            "titulo", "piloto", "data", "hora_inicio", "hora_fim",
            "altura_maxima_m", "observacoes",
        ]
        widgets = {
            "titulo": forms.TextInput(attrs={"class": "form-control"}),
            "piloto": forms.Select(attrs={"class": "form-select"}),
            "data": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "hora_inicio": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
            "hora_fim": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
            "altura_maxima_m": forms.NumberInput(attrs={"class": "form-control", "min": 1, "max": 500}),
            "observacoes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["piloto"].queryset = Piloto.objects.filter(ativo=True)
        if self.instance and self.instance.pk:
            self.fields["area_geojson_texto"].initial = json.dumps(self.instance.area_geojson)

    def clean(self):
        dados = super().clean()
        inicio, fim = dados.get("hora_inicio"), dados.get("hora_fim")
        if inicio and fim and fim <= inicio:
            self.add_error("hora_fim", "O horário final deve ser posterior ao inicial.")
        bruto = dados.get("area_geojson_texto")
        if bruto:
            try:
                geometria = json.loads(bruto)
                calculada = calcular_geometria(geometria)
                dados["geometria_calculada"] = calculada
            except (TypeError, ValueError, json.JSONDecodeError) as erro:
                self.add_error("area_geojson_texto", str(erro))
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
