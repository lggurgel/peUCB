from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required.")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True or extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_staff and is_superuser.")
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    username = None
    email = models.EmailField("email", unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email


class Profile(models.Model):
    class Role(models.TextChoices):
        GENERATOR = "generator", "Generator"
        COLLECTOR = "collector", "Collector"
        REVIEWER = "reviewer", "Reviewer"

    class CollectorKind(models.TextChoices):
        INDIVIDUAL = "individual", "Individual"
        COMPANY = "company", "Company"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=20, choices=Role.choices)
    display_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=20, blank=True)
    organization_name = models.CharField(max_length=160, blank=True)
    collector_kind = models.CharField(max_length=20, choices=CollectorKind.choices, blank=True)
    address = models.CharField(max_length=255, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    def __str__(self):
        return self.public_name

    @property
    def public_name(self):
        if self.role == self.Role.GENERATOR and self.organization_name:
            return self.organization_name
        return self.display_name

    @property
    def is_generator(self):
        return self.role == self.Role.GENERATOR

    @property
    def is_collector(self):
        return self.role == self.Role.COLLECTOR

    @property
    def is_reviewer(self):
        return self.role == self.Role.REVIEWER
