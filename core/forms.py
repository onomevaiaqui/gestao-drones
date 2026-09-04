from datetime import datetime

from django import forms
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
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
        fields = ["nome", "cpf", "codigo_sarpas", "matricula", "perfil", "ativo"]
        widgets = {
            "nome": forms.TextInput(attrs={"class": "form-control"}),
            "cpf": forms.TextInput(attrs={"class": "form-control"}),
            "codigo_sarpas": forms.TextInput(attrs={"class": "form-control"}),
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

    def clean_senha(self):
        senha = self.cleaned_data["senha"]
        candidato = User(username=self.cleaned_data.get("username", ""), email=self.cleaned_data.get("email", ""))
        validate_password(senha, candidato)
        return senha

    def save(self, commit=True):
        piloto = super().save(commit=False)
        user = User.objects.create_user(
            username=self.cleaned_data["username"],
            email=self.cleaned_data.get("email", ""),
            password=self.cleaned_data["senha"],
            is_active=piloto.ativo,
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
        fields = ["nome", "cpf", "codigo_sarpas", "matricula", "perfil", "ativo"]
        widgets = {
            "nome": forms.TextInput(attrs={"class": "form-control"}),
            "cpf": forms.TextInput(attrs={"class": "form-control"}),
            "codigo_sarpas": forms.TextInput(attrs={"class": "form-control"}),
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

    def clean_nova_senha(self):
        senha = self.cleaned_data.get("nova_senha")
        if senha:
            validate_password(senha, self.instance.user if self.instance and self.instance.user_id else None)
        return senha

    def save(self, commit=True):
        piloto = super().save(commit=False)
        user = piloto.user

        if user is None:
            user = User(username=self.cleaned_data["username"])
            piloto.user = user

        user.username = self.cleaned_data["username"]
        user.email = self.cleaned_data.get("email", "")
        user.is_active = piloto.ativo

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
        fields = ["nome", "prefixo", "modelo", "numero_serie", "localizacao", "status"]
        widgets = {
            "nome": forms.TextInput(attrs={"class": "form-control"}),
            "prefixo": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex.: M300-01"}),
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
        fields = ["piloto", "drone", "finalidade", "local", "observacoes"]
        widgets = {
            "piloto": forms.Select(attrs={"class": "form-select"}),
            "drone": forms.Select(attrs={"class": "form-select"}),
            "finalidade": forms.Select(attrs={"class": "form-select"}),
            "local": forms.TextInput(attrs={"class": "form-control"}),
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
            "data_fim": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
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
        self.fields["data"].label = "Data inicial"
        self.fields["data_fim"].label = "Data final"
        self.fields["data_fim"].required = True

        if self.instance and self.instance.pk:
            self.fields["piloto"].queryset = Piloto.objects.filter(
                Q(ativo=True) | Q(pk=self.instance.piloto_id)
            ).distinct()
            self.fields["drone"].queryset = Drone.objects.filter(
                Q(status="ativo") | Q(pk=self.instance.drone_id)
            ).distinct()

    def clean(self):
        from .operacao_service import erro_intervalo, existe_conflito_alocacao

        cleaned = super().clean()
        data = cleaned.get("data")
        data_fim = cleaned.get("data_fim") or data
        inicio = cleaned.get("hora_inicio")
        fim = cleaned.get("hora_fim")
        drone = cleaned.get("drone")

        erro = erro_intervalo(data, inicio, data_fim, fim)
        if erro:
            campo = "data_fim" if data and data_fim and data_fim < data else "hora_fim"
            self.add_error(campo, erro)

        if data and data_fim and inicio and fim and drone:
            if existe_conflito_alocacao(
                drone, data, inicio, data_fim, fim,
                excluir_pk=self.instance.pk if self.instance and self.instance.pk else None,
            ):
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
from .models import Bateria, RegistroPosVoo

class RegistroPosVooForm(forms.ModelForm):
    class Meta:
        model = RegistroPosVoo
        fields = [
            "hora_inicio_real", "hora_fim_real", "resultado",
            "baterias_utilizadas",
            "baterias",
            "distancia_m", "ocorrencias", "danos", "necessita_manutencao",
            "observacoes", "concluido",
        ]
        widgets = {
            "hora_inicio_real": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
            "hora_fim_real": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
            "resultado": forms.Select(attrs={"class": "form-select"}),
            "baterias_utilizadas": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "baterias": forms.CheckboxSelectMultiple(),
            "distancia_m": forms.NumberInput(attrs={"class": "form-control", "min": 0, "step": "0.01"}),
            "ocorrencias": forms.Textarea(attrs={"rows": 4, "class": "form-control"}),
            "danos": forms.Textarea(attrs={"rows": 4, "class": "form-control"}),
            "observacoes": forms.Textarea(attrs={"rows": 4, "class": "form-control"}),
            "necessita_manutencao": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "concluido": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        self.resumo_telemetria = kwargs.pop("resumo_telemetria", None)
        super().__init__(*args, **kwargs)
        selecionadas = self.instance.baterias.all() if self.instance and self.instance.pk else Bateria.objects.none()
        reconhecidas = (
            Bateria.objects.filter(pk__in=[item.pk for item in self.resumo_telemetria["baterias"]])
            if self.resumo_telemetria else Bateria.objects.none()
        )
        self.fields["baterias"].queryset = (
            Bateria.objects.filter(status="disponivel") | selecionadas | reconhecidas
        ).distinct().order_by("codigo")
        self.fields["baterias"].required = False
        self.fields["baterias"].label = "Baterias utilizadas"
        for nome in ("baterias_utilizadas", "baterias", "distancia_m"):
            self.fields[nome].disabled = True
        if self.resumo_telemetria:
            self.fields["baterias_utilizadas"].initial = self.resumo_telemetria["quantidade_baterias"]
            self.fields["distancia_m"].initial = self.resumo_telemetria["distancia_m"]
            self.fields["baterias"].initial = self.resumo_telemetria["baterias"]

    def clean(self):
        dados = super().clean()
        return dados
