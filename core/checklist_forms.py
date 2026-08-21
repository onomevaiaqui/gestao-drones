from django import forms
from .models import ChecklistPreVoo

class ChecklistPreVooForm(forms.ModelForm):
    class Meta:
        model = ChecklistPreVoo
        fields = [
            "bateria_ok", "helices_ok", "estrutura_ok", "controle_ok",
            "gps_ok", "memoria_ok", "area_segura", "meteorologia_ok",
            "observacoes",
        ]
        labels = {
            "bateria_ok": "Bateria inspecionada e carregada",
            "helices_ok": "Hélices sem danos e corretamente fixadas",
            "estrutura_ok": "Estrutura e braços sem danos",
            "controle_ok": "Controle remoto e comunicação verificados",
            "gps_ok": "GPS/GNSS disponível e funcionando",
            "memoria_ok": "Armazenamento disponível",
            "area_segura": "Área de decolagem/pouso segura",
            "meteorologia_ok": "Condições meteorológicas adequadas",
            "observacoes": "Observações",
        }
        widgets = {
            "observacoes": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        }
