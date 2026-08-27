from datetime import datetime

from django import forms
from django.db.models import Q
from .models import Piloto, Drone, Alocacao, SolicitacaoVoo, PlanejamentoVoo

class SolicitacaoVooForm(forms.ModelForm):
    drones = forms.ModelMultipleChoiceField(
        queryset=Drone.objects.none(),
        widget=forms.CheckboxSelectMultiple(attrs={"class": "drone-checkbox-input"}),
        label="Drones",
    )

    class Meta:
        model = SolicitacaoVoo
        fields = ["planejamento", "data", "data_fim", "hora_inicio", "hora_fim", "piloto", "finalidade", "local", "observacoes", "requer_avaliacao_risco"]
        widgets = {
            "planejamento": forms.Select(attrs={"class": "form-select"}),
            "data": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": "form-control"}),
            "data_fim": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": "form-control"}),
            "hora_inicio": forms.TimeInput(format="%H:%M", attrs={"type": "time", "class": "form-control"}),
            "hora_fim": forms.TimeInput(format="%H:%M", attrs={"type": "time", "class": "form-control"}),
            "piloto": forms.Select(attrs={"class": "form-select"}),
            "finalidade": forms.Select(attrs={"class": "form-select"}),
            "local": forms.TextInput(attrs={"class": "form-control"}),
            "observacoes": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "requer_avaliacao_risco": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["requer_avaliacao_risco"].help_text = (
            "Marque quando a operação precisar ser avaliada antes da liberação do voo."
        )
        self.fields["planejamento"].required = False
        self.fields["planejamento"].help_text = "Opcional. Use um planejamento para vincular a área e a análise meteorológica."
        self.fields["planejamento"].queryset = PlanejamentoVoo.objects.all()
        self.fields["piloto"].queryset = Piloto.objects.filter(ativo=True)
        self.fields["drones"].queryset = Drone.objects.filter(status="ativo")
        self.fields["data"].label = "Data inicial"
        self.fields["data_fim"].label = "Data final"
        self.fields["data_fim"].required = True
        if self.instance and self.instance.pk:
            self.fields["piloto"].queryset = Piloto.objects.filter(Q(ativo=True) | Q(pk=self.instance.piloto_id)).distinct()
            self.fields["drones"].queryset = Drone.objects.filter(Q(status="ativo") | Q(pk=self.instance.drone_id)).distinct()
            self.fields["drones"].initial = [self.instance.drone_id]
            if not self.instance.data_fim:
                self.fields["data_fim"].initial = self.instance.data

    def clean(self):
        cleaned = super().clean()
        data = cleaned.get("data")
        data_fim = cleaned.get("data_fim")
        inicio = cleaned.get("hora_inicio")
        fim = cleaned.get("hora_fim")
        drones = cleaned.get("drones")
        planejamento = cleaned.get("planejamento")
        if data and data_fim and data_fim < data:
            self.add_error("data_fim", "A data final não pode ser anterior à data inicial.")
        if data and data_fim and data == data_fim and inicio and fim and fim <= inicio:
            self.add_error("hora_fim", "A hora final deve ser posterior à hora inicial.")
        if data and data_fim and inicio and fim and drones:
            for drone in drones:
                conflitos = Alocacao.objects.filter(
                    drone=drone, status="reservado", data__lte=data_fim,
                ).filter(Q(data_fim__gte=data) | Q(data_fim__isnull=True, data__gte=data))
                if self.instance and self.instance.alocacao_id:
                    conflitos = conflitos.exclude(pk=self.instance.alocacao_id)
                novo_inicio = datetime.combine(data, inicio)
                novo_fim = datetime.combine(data_fim, fim)
                conflito = any(
                    datetime.combine(item.data, item.hora_inicio) < novo_fim
                    and datetime.combine(item.data_final, item.hora_fim) > novo_inicio
                    for item in conflitos
                )
                if conflito:
                    self.add_error("drones", f"{drone.nome} já possui uma reserva que coincide com esse período.")
        if planejamento:
            if data and data != planejamento.data:
                self.add_error("data", "A data deve ser igual à do planejamento selecionado.")
            if data_fim and data_fim < planejamento.data:
                self.add_error("data_fim", "A data final não pode ser anterior ao planejamento.")
            if inicio and inicio != planejamento.hora_inicio:
                self.add_error("hora_inicio", "O início deve ser igual ao do planejamento selecionado.")
            if fim and fim != planejamento.hora_fim:
                self.add_error("hora_fim", "O término deve ser igual ao do planejamento selecionado.")
            if cleaned.get("piloto") and cleaned["piloto"] != planejamento.piloto:
                self.add_error("piloto", "O piloto deve ser o mesmo do planejamento.")
        return cleaned
