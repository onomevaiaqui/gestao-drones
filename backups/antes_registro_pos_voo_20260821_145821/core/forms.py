from django import forms
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.models import User
from django.db.models import Q

from .models import Piloto, Drone, Voo, Alocacao, Manutencao


class PilotoForm(forms.ModelForm):
    username = forms.CharField(label="Usuário para login", max_length=150)
    email = forms.EmailField(label="E-mail", required=False)
    senha = forms.CharField(label="Senha inicial", widget=forms.PasswordInput)
    enviar_email_acesso = forms.BooleanField(
        label="Enviar e-mail de acesso ao salvar",
        required=False
    )

    class Meta:
        model = Piloto
        fields = ["nome", "matricula", "perfil", "ativo"]
        widgets = {
            "nome": forms.TextInput(attrs={"class": "form-control"}),
            "matricula": forms.TextInput(attrs={"class": "form-control"}),
            "perfil": forms.Select(attrs={"class": "form-select"}),
            "ativo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nome in ("username", "email", "senha"):
            self.fields[nome].widget.attrs.setdefault("class", "form-control")

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Este usuário já existe.")
        return username

    def save(self, commit=True):
        piloto = super().save(commit=False)
        user = User.objects.create_user(
            username=self.cleaned_data["username"],
            email=self.cleaned_data.get("email", ""),
            password=self.cleaned_data["senha"],
        )
        piloto.user = user
        if hasattr(piloto, "primeiro_acesso"):
            piloto.primeiro_acesso = True
        if commit:
            piloto.save()
        return piloto


class PilotoEditForm(forms.ModelForm):
    username = forms.CharField(label="Usuário para login", max_length=150)
    email = forms.EmailField(label="E-mail", required=False)
    nova_senha = forms.CharField(
        label="Nova senha",
        widget=forms.PasswordInput,
        required=False
    )
    enviar_email_acesso = forms.BooleanField(
        label="Enviar e-mail de acesso ao salvar",
        required=False
    )

    class Meta:
        model = Piloto
        fields = ["nome", "matricula", "perfil", "ativo"]
        widgets = {
            "nome": forms.TextInput(attrs={"class": "form-control"}),
            "matricula": forms.TextInput(attrs={"class": "form-control"}),
            "perfil": forms.Select(attrs={"class": "form-select"}),
            "ativo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nome in ("username", "email", "nova_senha"):
            self.fields[nome].widget.attrs.setdefault("class", "form-control")

        if self.instance and self.instance.pk and self.instance.user:
            self.fields["username"].initial = self.instance.user.username
            self.fields["email"].initial = self.instance.user.email

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        qs = User.objects.filter(username=username)
        if self.instance and self.instance.user_id:
            qs = qs.exclude(pk=self.instance.user_id)
        if qs.exists():
            raise forms.ValidationError("Este usuário já existe.")
        return username

    def save(self, commit=True):
        piloto = super().save(commit=False)
        user = piloto.user

        if user is None:
            user = User(username=self.cleaned_data["username"])
            piloto.user = user

        user.username = self.cleaned_data["username"]
        user.email = self.cleaned_data.get("email", "")

        nova_senha = self.cleaned_data.get("nova_senha")
        if nova_senha:
            user.set_password(nova_senha)
            if hasattr(piloto, "primeiro_acesso"):
                piloto.primeiro_acesso = True

        if commit:
            user.save()
            piloto.save()

        return piloto


class PrimeiroAcessoSenhaForm(SetPasswordForm):
    def __init__(self, user, *args, **kwargs):
        super().__init__(user, *args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


class DroneForm(forms.ModelForm):
    class Meta:
        model = Drone
        fields = ["nome", "modelo", "numero_serie", "localizacao", "status"]
        widgets = {
            "nome": forms.TextInput(attrs={"class": "form-control"}),
            "modelo": forms.TextInput(attrs={"class": "form-control"}),
            "numero_serie": forms.TextInput(attrs={"class": "form-control"}),
            "localizacao": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Ex.: Almoxarifado, Unidade Foz, Veículo 01"
            }),
            "status": forms.Select(attrs={"class": "form-select"}),
        }


class VooForm(forms.ModelForm):
    class Meta:
        model = Voo
        exclude = ["criado_por"]
        widgets = {
            "data": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "hora_inicio": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
            "hora_fim": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
            "piloto": forms.Select(attrs={"class": "form-select"}),
            "drone": forms.Select(attrs={"class": "form-select"}),
            "finalidade": forms.Select(attrs={"class": "form-select"}),
            "local": forms.TextInput(attrs={"class": "form-control"}),
            "bateria_inicial": forms.NumberInput(attrs={"class": "form-control"}),
            "bateria_final": forms.NumberInput(attrs={"class": "form-control"}),
            "distancia_m": forms.NumberInput(attrs={"class": "form-control"}),
            "observacoes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "piloto" in self.fields:
            self.fields["piloto"].queryset = Piloto.objects.filter(ativo=True)
        if "drone" in self.fields:
            self.fields["drone"].queryset = Drone.objects.filter(status="ativo")

        # Ao editar um voo antigo, mantém os itens já vinculados visíveis.
        if self.instance and self.instance.pk:
            if "piloto" in self.fields and self.instance.piloto_id:
                self.fields["piloto"].queryset = Piloto.objects.filter(
                    Q(ativo=True) | Q(pk=self.instance.piloto_id)
                ).distinct()
            if "drone" in self.fields and self.instance.drone_id:
                self.fields["drone"].queryset = Drone.objects.filter(
                    Q(status="ativo") | Q(pk=self.instance.drone_id)
                ).distinct()


class AlocacaoForm(forms.ModelForm):
    class Meta:
        model = Alocacao
        exclude = ["criado_por", "status"]
        widgets = {
            "data": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "hora_inicio": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
            "hora_fim": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
            "piloto": forms.Select(attrs={"class": "form-select"}),
            "drone": forms.Select(attrs={"class": "form-select"}),
            "finalidade": forms.TextInput(attrs={"class": "form-control"}),
            "local": forms.TextInput(attrs={"class": "form-control"}),
            "observacoes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["piloto"].queryset = Piloto.objects.filter(ativo=True)
        self.fields["drone"].queryset = Drone.objects.filter(status="ativo")

        if self.instance and self.instance.pk:
            self.fields["piloto"].queryset = Piloto.objects.filter(
                Q(ativo=True) | Q(pk=self.instance.piloto_id)
            ).distinct()
            self.fields["drone"].queryset = Drone.objects.filter(
                Q(status="ativo") | Q(pk=self.instance.drone_id)
            ).distinct()

    def clean(self):
        cleaned = super().clean()
        data = cleaned.get("data")
        inicio = cleaned.get("hora_inicio")
        fim = cleaned.get("hora_fim")
        drone = cleaned.get("drone")

        if inicio and fim and fim <= inicio:
            self.add_error("hora_fim", "A hora final deve ser posterior à hora inicial.")

        if data and inicio and fim and drone:
            qs = Alocacao.objects.filter(
                data=data,
                drone=drone,
                status="reservado",
                hora_inicio__lt=fim,
                hora_fim__gt=inicio,
            )
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error(
                    "drone",
                    "Este drone já possui uma reserva nesse intervalo de horário."
                )
        return cleaned


class ManutencaoForm(forms.ModelForm):
    class Meta:
        model = Manutencao
        exclude = ["criado_por"]
        widgets = {
            "drone": forms.Select(attrs={"class": "form-select"}),
            "concluida": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
# PATCH REGISTRO POS-VOO: FORMULARIO
from django import forms as pos_voo_forms
from .models import RegistroPosVoo

class RegistroPosVooForm(pos_voo_forms.ModelForm):
    class Meta:
        model = RegistroPosVoo
        fields = [
            "hora_inicio_real", "hora_fim_real", "resultado",
            "baterias_utilizadas", "bateria_inicial", "bateria_final",
            "distancia_m", "ocorrencias", "danos", "necessita_manutencao",
            "observacoes", "concluido",
        ]
        widgets = {
            "hora_inicio_real": pos_voo_forms.TimeInput(attrs={"type": "time"}),
            "hora_fim_real": pos_voo_forms.TimeInput(attrs={"type": "time"}),
            "ocorrencias": pos_voo_forms.Textarea(attrs={"rows": 3}),
            "danos": pos_voo_forms.Textarea(attrs={"rows": 3}),
            "observacoes": pos_voo_forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        dados = super().clean()
        for campo in ("bateria_inicial", "bateria_final"):
            valor = dados.get(campo)
            if valor is not None and not 0 <= valor <= 100:
                self.add_error(campo, "Informe um percentual entre 0 e 100.")
        if dados.get("baterias_utilizadas") == 0:
            self.add_error("baterias_utilizadas", "Informe ao menos uma bateria.")
        return dados
