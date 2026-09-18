import django.db.models.deletion
from django.db import migrations, models

import apps.jobs.domain.entities.company


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("custom_auth", "0006_remove_legacy_identity_contenttypes"),
        ("jobs", "0005_external_identity_jobinteraction"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                    DO $$
                    BEGIN
                        IF EXISTS (
                            SELECT 1 FROM django_content_type
                            WHERE app_label = 'custom_auth' AND model = 'company'
                        ) AND NOT EXISTS (
                            SELECT 1 FROM django_content_type
                            WHERE app_label = 'jobs' AND model = 'company'
                        ) THEN
                            UPDATE django_content_type
                            SET app_label = 'jobs'
                            WHERE app_label = 'custom_auth' AND model = 'company';
                        ELSIF EXISTS (
                            SELECT 1 FROM django_content_type
                            WHERE app_label = 'custom_auth' AND model = 'company'
                        ) THEN
                            DELETE FROM auth_permission
                            WHERE content_type_id IN (
                                SELECT id FROM django_content_type
                                WHERE app_label = 'custom_auth' AND model = 'company'
                            );
                            DELETE FROM django_content_type
                            WHERE app_label = 'custom_auth' AND model = 'company';
                        END IF;
                    END $$;
                    """,
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
            state_operations=[
                migrations.CreateModel(
                    name="Company",
                    fields=[
                        (
                            "last_login",
                            models.DateTimeField(
                                blank=True, null=True, verbose_name="last login"
                            ),
                        ),
                        (
                            "is_superuser",
                            models.BooleanField(
                                default=False,
                                help_text="Designates that this user has all permissions without explicitly assigning them.",
                                verbose_name="superuser status",
                            ),
                        ),
                        (
                            "id",
                            models.CharField(
                                default=apps.jobs.domain.entities.company.generate_unique_id,
                                editable=False,
                                max_length=10,
                                primary_key=True,
                                serialize=False,
                            ),
                        ),
                        (
                            "company_name",
                            models.CharField(
                                max_length=200, verbose_name="Nombre de la empresa"
                            ),
                        ),
                        (
                            "username",
                            models.EmailField(
                                max_length=254,
                                unique=True,
                                verbose_name="Correo electronico",
                            ),
                        ),
                        ("password", models.CharField(max_length=128)),
                        (
                            "industry",
                            models.CharField(
                                choices=[
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
                                ],
                                default="other",
                                max_length=20,
                                verbose_name="Industria",
                            ),
                        ),
                        (
                            "description",
                            models.TextField(
                                blank=True,
                                max_length=1000,
                                null=True,
                                verbose_name="Descripcion",
                            ),
                        ),
                        ("website", models.URLField(blank=True, null=True)),
                        (
                            "phone",
                            models.CharField(
                                blank=True,
                                max_length=20,
                                null=True,
                                verbose_name="Telefono",
                            ),
                        ),
                        (
                            "address",
                            models.CharField(
                                blank=True,
                                max_length=300,
                                null=True,
                                verbose_name="Direccion",
                            ),
                        ),
                        (
                            "logo",
                            models.ImageField(
                                blank=True,
                                default="company_logos/default_company_logo.png",
                                null=True,
                                upload_to=apps.jobs.domain.entities.company.get_company_logo_filepath,
                                verbose_name="Logo",
                            ),
                        ),
                        (
                            "founded_year",
                            models.IntegerField(
                                blank=True, null=True, verbose_name="Anio de fundacion"
                            ),
                        ),
                        (
                            "employee_count",
                            models.CharField(
                                blank=True,
                                choices=[
                                    ("1-10", "1-10 empleados"),
                                    ("11-50", "11-50 empleados"),
                                    ("51-200", "51-200 empleados"),
                                    ("201-500", "201-500 empleados"),
                                    ("501-1000", "501-1000 empleados"),
                                    ("1000+", "Mas de 1000 empleados"),
                                ],
                                max_length=20,
                                null=True,
                                verbose_name="Numero de empleados",
                            ),
                        ),
                        ("is_active", models.BooleanField(default=True)),
                        ("is_staff", models.BooleanField(default=False)),
                        ("date_joined", models.DateTimeField(auto_now_add=True)),
                        (
                            "is_verified",
                            models.BooleanField(
                                default=False, verbose_name="Empresa verificada"
                            ),
                        ),
                        (
                            "groups",
                            models.ManyToManyField(
                                blank=True,
                                db_table="companies_groups",
                                help_text="The groups this company belongs to.",
                                related_name="company_set_custom",
                                to="auth.group",
                                verbose_name="groups",
                            ),
                        ),
                        (
                            "user_permissions",
                            models.ManyToManyField(
                                blank=True,
                                db_table="companies_user_permissions",
                                help_text="Specific permissions for this company.",
                                related_name="company_set_custom",
                                to="auth.permission",
                                verbose_name="user permissions",
                            ),
                        ),
                    ],
                    options={
                        "verbose_name": "Empresa",
                        "verbose_name_plural": "Empresas",
                        "db_table": "companies",
                    },
                ),
                migrations.AlterField(
                    model_name="jobs",
                    name="company",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="jobs",
                        to="jobs.company",
                        verbose_name="Empresa",
                    ),
                ),
            ],
        ),
    ]
