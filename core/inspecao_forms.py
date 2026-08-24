from django import forms

from .models import ExecucaoInspecao, PlanoInspecao


class PlanoInspecaoForm(forms.ModelForm):
    class Meta:
        model = PlanoInspecao
        exclude = ["criado_por", "voos_base", "minutos_base", "ciclos_base"]
        widgets = {
            "nome": forms.TextInput(attrs={"class": "form-control"}),
            "tipo": forms.Select(attrs={"class": "form-select"}),
            "drone": forms.Select(attrs={"class": "form-select"}),
            "bateria": forms.Select(attrs={"class": "form-select"}),
            "descricao": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "intervalo_dias": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "intervalo_voos": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "intervalo_horas": forms.NumberInput(attrs={"class": "form-control", "min": 0.1, "step": 0.1}),
            "intervalo_ciclos": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "ultima_execucao": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "ativo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        labels = {
            "ultima_execucao": "Data inicial / última execução",
            "intervalo_dias": "Executar a cada (dias)",
            "intervalo_voos": "Executar a cada (voos)",
            "intervalo_horas": "Executar a cada (horas voadas)",
            "intervalo_ciclos": "Executar a cada (ciclos)",
        }


class ExecucaoInspecaoForm(forms.ModelForm):
    class Meta:
        model = ExecucaoInspecao
        fields = ["data", "observacoes"]
        widgets = {
            "data": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "observacoes": forms.Textarea(attrs={"class": "form-control", "rows": 5}),
        }
