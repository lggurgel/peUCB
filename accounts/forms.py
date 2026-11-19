from django import forms
from django.contrib.auth.forms import AuthenticationForm

from accounts.models import Profile, User


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "E-mail"
        self.fields["username"].widget.attrs["autocomplete"] = "email"
        self.fields["password"].label = "Senha"
        self.fields["password"].widget.attrs["autocomplete"] = "current-password"


class SignupForm(forms.Form):
    role = forms.ChoiceField(
        label="Eu sou",
        choices=[
            (Profile.Role.GENERATOR, "Estabelecimento que gera embalagem"),
            (Profile.Role.COLLECTOR, "Coletador"),
        ],
        widget=forms.RadioSelect,
    )
    display_name = forms.CharField(label="Seu nome", max_length=120)
    email = forms.EmailField(label="E-mail")
    password = forms.CharField(label="Senha", widget=forms.PasswordInput, min_length=8)
    password_confirm = forms.CharField(label="Confirmar senha", widget=forms.PasswordInput, min_length=8)
    organization_name = forms.CharField(label="Nome do estabelecimento", max_length=160, required=False)
    address = forms.CharField(label="Endereço", max_length=255, required=False)
    latitude = forms.DecimalField(required=False, widget=forms.HiddenInput, max_digits=9, decimal_places=6)
    longitude = forms.DecimalField(required=False, widget=forms.HiddenInput, max_digits=9, decimal_places=6)
    collector_kind = forms.ChoiceField(
        label="Tipo",
        required=False,
        choices=[
            ("", "Escolha"),
            (Profile.CollectorKind.INDIVIDUAL, "Pessoa física"),
            (Profile.CollectorKind.COMPANY, "Empresa"),
        ],
    )
    phone = forms.CharField(label="Telefone (opcional)", max_length=20, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["collector_kind"].choices = [
            ("", "Escolha"),
            (Profile.CollectorKind.INDIVIDUAL, "Pessoa física"),
            (Profile.CollectorKind.COMPANY, "Empresa"),
        ]
        self.fields["email"].widget.attrs["autocomplete"] = "email"
        self.fields["password"].widget.attrs["autocomplete"] = "new-password"
        self.fields["password_confirm"].widget.attrs["autocomplete"] = "new-password"

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Já existe uma conta com este e-mail.")
        return email

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("password") != cleaned.get("password_confirm"):
            self.add_error("password_confirm", "As senhas não conferem.")
        role = cleaned.get("role")
        if role == Profile.Role.GENERATOR:
            if not cleaned.get("organization_name"):
                self.add_error("organization_name", "Informe o nome do estabelecimento.")
            if not cleaned.get("address"):
                self.add_error("address", "Informe o endereço.")
            if cleaned.get("latitude") is None or cleaned.get("longitude") is None:
                self.add_error("latitude", "Clique no mapa para marcar o estabelecimento.")
        if role == Profile.Role.COLLECTOR:
            if not cleaned.get("collector_kind"):
                self.add_error("collector_kind", "Escolha pessoa física ou empresa.")
        return cleaned

    def save(self):
        data = self.cleaned_data
        user = User.objects.create_user(email=data["email"], password=data["password"])
        return Profile.objects.create(
            user=user,
            role=data["role"],
            display_name=data["display_name"].strip(),
            phone=data["phone"].strip() if data["role"] == Profile.Role.COLLECTOR else "",
            organization_name=data["organization_name"].strip() if data["role"] == Profile.Role.GENERATOR else "",
            collector_kind=data["collector_kind"] if data["role"] == Profile.Role.COLLECTOR else "",
            address=data["address"].strip() if data["role"] == Profile.Role.GENERATOR else "",
            latitude=data["latitude"] if data["role"] == Profile.Role.GENERATOR else None,
            longitude=data["longitude"] if data["role"] == Profile.Role.GENERATOR else None,
        )


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = [
            "display_name",
            "phone",
            "organization_name",
            "collector_kind",
            "address",
            "latitude",
            "longitude",
        ]
        labels = {
            "display_name": "Seu nome",
            "phone": "Telefone (opcional, não aparece para os outros)",
            "organization_name": "Nome do estabelecimento",
            "collector_kind": "Tipo",
            "address": "Endereço",
        }
        widgets = {
            "latitude": forms.HiddenInput,
            "longitude": forms.HiddenInput,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["collector_kind"].choices = [
            ("", "Escolha"),
            (Profile.CollectorKind.INDIVIDUAL, "Pessoa física"),
            (Profile.CollectorKind.COMPANY, "Empresa"),
        ]
        if self.instance.is_generator:
            for name in ("phone", "collector_kind"):
                self.fields.pop(name, None)
        elif self.instance.is_collector:
            for name in ("organization_name", "address", "latitude", "longitude"):
                self.fields.pop(name, None)
        else:
            for name in ("phone", "collector_kind", "organization_name", "address", "latitude", "longitude"):
                self.fields.pop(name, None)

    def clean(self):
        cleaned = super().clean()
        if self.instance.is_generator:
            if not cleaned.get("organization_name"):
                self.add_error("organization_name", "Informe o nome do estabelecimento.")
            if not cleaned.get("address"):
                self.add_error("address", "Informe o endereço.")
            if cleaned.get("latitude") is None or cleaned.get("longitude") is None:
                self.add_error("latitude", "Clique no mapa para marcar o estabelecimento.")
        if self.instance.is_collector and not cleaned.get("collector_kind"):
            self.add_error("collector_kind", "Escolha pessoa física ou empresa.")
        return cleaned
