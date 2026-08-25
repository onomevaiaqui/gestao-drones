from django import forms
from django.db.models import Q
from .models import Piloto, Drone, Alocacao, SolicitacaoVoo

class SolicitacaoVooForm(forms.ModelForm):
    class Meta:
        model = SolicitacaoVoo
        fields = ["data", "hora_inicio", "hora_fim", "piloto", "drone", "finalidade", "local", "observacoes", "requer_avaliacao_risco"]
        widgets = {
            "data": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "hora_inicio": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
            "hora_fim": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
            "piloto": forms.Select(attrs={"class": "form-select"}),
            "drone": forms.Select(attrs={"class": "form-select"}),
            "finalidade": forms.TextInput(attrs={"class": "form-control"}),
            "local": forms.TextInput(attrs={"class": "form-control"}),
            "observacoes": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "requer_avaliacao_risco": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["requer_avaliacao_risco"].help_text = (
            "Marque quando a operação precisar ser avaliada antes da liberação do voo."
        )
        self.fields["piloto"].queryset = Piloto.objects.filter(ativo=True)
        self.fields["drone"].queryset = Drone.objects.filter(status="ativo")
        if self.instance and self.instance.pk:
            self.fields["piloto"].queryset = Piloto.objects.filter(Q(ativo=True) | Q(pk=self.instance.piloto_id)).distinct()
            self.fields["drone"].queryset = Drone.objects.filter(Q(status="ativo") | Q(pk=self.instance.drone_id)).distinct()

    def clean(self):
        cleaned = super().clean()
        data = cleaned.get("data")
        inicio = cleaned.get("hora_inicio")
        fim = cleaned.get("hora_fim")
        drone = cleaned.get("drone")
        if inicio and fim and fim <= inicio:
            self.add_error("hora_fim", "A hora final deve ser posterior à hora inicial.")
        if data and inicio and fim and drone:
            conflito = Alocacao.objects.filter(
                data=data,
                drone=drone,
                status="reservado",
                hora_inicio__lt=fim,
                hora_fim__gt=inicio,
            ).exists()
            if conflito:
                self.add_error("drone", "Este drone já possui uma reserva nesse horário.")
        return cleaned
