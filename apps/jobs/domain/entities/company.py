import random
import string
import uuid

from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models


def generate_unique_id(length=10):
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


def get_company_logo_filepath(instance, filename):
    ext = filename.split(".")[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return f"company_logos/{filename}"


class CompanyManager(BaseUserManager):
    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError("El campo email debe ser establecido")
        email = self.normalize_email(username)
        company = self.model(username=email, **extra_fields)
        company.set_password(password)
        company.save(using=self._db)
        return company

    def create_superuser(self, username, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("El superusuario debe tener is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("El superusuario debe tener is_superuser=True.")

        return self.create_user(username, password, **extra_fields)


class Company(AbstractBaseUser, PermissionsMixin):
    INDUSTRY_CHOICES = [
        ("technology", "Tecnologia"),
        ("health", "Salud"),
        ("sales", "Ventas"),
        ("finance", "Finanzas"),
        ("education", "Educacion"),
        ("manufacturing", "Manufactura"),
        ("retail", "Comercio"),
        ("consulting", "Consultoria"),
        ("energy", "Energia"),
        ("telecommunications", "Telecomunicaciones"),
        ("automotive", "Automotriz"),
        ("food", "Alimentaria"),
        ("real_estate", "Bienes raices"),
        ("media", "Medios de comunicacion"),
        ("transportation", "Transporte"),
        ("other", "Otro"),
    ]

    id = models.CharField(
        max_length=10, primary_key=True, default=generate_unique_id, editable=False
    )
    company_name = models.CharField(max_length=200, verbose_name="Nombre de la empresa")
    username = models.EmailField(unique=True, verbose_name="Correo electronico")
    password = models.CharField(max_length=128)
    industry = models.CharField(
        max_length=20,
        choices=INDUSTRY_CHOICES,
        default="other",
        verbose_name="Industria",
    )
    description = models.TextField(
        max_length=1000, null=True, blank=True, verbose_name="Descripcion"
    )
    website = models.URLField(max_length=200, null=True, blank=True)
    phone = models.CharField(
        max_length=20, null=True, blank=True, verbose_name="Telefono"
    )
    address = models.CharField(
        max_length=300, null=True, blank=True, verbose_name="Direccion"
    )
    logo = models.ImageField(
        upload_to=get_company_logo_filepath,
        default="company_logos/default_company_logo.png",
        null=True,
        blank=True,
        verbose_name="Logo",
    )
    founded_year = models.IntegerField(
        null=True, blank=True, verbose_name="Anio de fundacion"
    )
    employee_count = models.CharField(
        max_length=20,
        choices=[
            ("1-10", "1-10 empleados"),
            ("11-50", "11-50 empleados"),
            ("51-200", "51-200 empleados"),
            ("201-500", "201-500 empleados"),
            ("501-1000", "501-1000 empleados"),
            ("1000+", "Mas de 1000 empleados"),
        ],
        null=True,
        blank=True,
        verbose_name="Numero de empleados",
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False, verbose_name="Empresa verificada")
    groups = models.ManyToManyField(
        "auth.Group",
        verbose_name="groups",
        blank=True,
        related_name="company_set_custom",
        help_text="The groups this company belongs to.",
        db_table="companies_groups",
    )
    user_permissions = models.ManyToManyField(
        "auth.Permission",
        verbose_name="user permissions",
        blank=True,
        related_name="company_set_custom",
        help_text="Specific permissions for this company.",
        db_table="companies_user_permissions",
    )

    objects = CompanyManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["company_name"]

    def __str__(self):
        return f"{self.company_name} ({self.username})"

    def save(self, *args, **kwargs):
        if not self.logo:
            self.logo = "company_logos/default_company_logo.png"

        try:
            this = Company.objects.get(id=self.id)
            default_logo = "company_logos/default_company_logo.png"
            if this.logo != self.logo and str(this.logo) != default_logo:
                this.logo.delete(save=False)
        except Company.DoesNotExist:
            pass

        super().save(*args, **kwargs)

    def get_industry_display_name(self):
        return dict(self.INDUSTRY_CHOICES).get(self.industry, "Otro")

    class Meta:
        db_table = "companies"
        verbose_name = "Empresa"
        verbose_name_plural = "Empresas"
