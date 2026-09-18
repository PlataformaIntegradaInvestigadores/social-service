"""Unitarias de las entidades de dominio de jobs: Company, Jobs,
Postulants y JobInteraction (propiedades derivadas de snapshot, display
names, comportamiento de save)."""

from django.test import TestCase

from apps.custom_auth.identity_principal import IdentityPrincipal
from apps.jobs.domain.entities.company import Company, generate_unique_id
from apps.jobs.domain.entities.job_interaction import JobInteraction
from apps.jobs.domain.entities.jobs import Jobs
from apps.jobs.domain.entities.postulants import Postulants


class TestGenerateUniqueId(TestCase):
    def test_genera_id_de_longitud_esperada(self):
        self.assertEqual(len(generate_unique_id()), 10)
        self.assertEqual(len(generate_unique_id(length=5)), 5)


class TestCompany(TestCase):
    def test_create_user_normaliza_email_y_hashea_password(self):
        company = Company.objects.create_user(
            username="Empresa@Example.com",
            password="secret123",
            company_name="Empresa Uno",
        )

        self.assertEqual(company.username, "Empresa@example.com")
        self.assertNotEqual(company.password, "secret123")
        self.assertTrue(company.check_password("secret123"))

    def test_create_user_sin_username_lanza_value_error(self):
        with self.assertRaises(ValueError):
            Company.objects.create_user(username="", password="x")

    def test_create_superuser_marca_staff_y_superuser(self):
        company = Company.objects.create_superuser(
            username="admin@example.com",
            password="secret123",
            company_name="Admin Co",
        )

        self.assertTrue(company.is_staff)
        self.assertTrue(company.is_superuser)

    def test_create_superuser_rechaza_is_staff_false(self):
        with self.assertRaises(ValueError):
            Company.objects.create_superuser(
                username="admin2@example.com",
                password="secret123",
                company_name="Admin Co",
                is_staff=False,
            )

    def test_create_superuser_rechaza_is_superuser_false(self):
        with self.assertRaises(ValueError):
            Company.objects.create_superuser(
                username="admin3@example.com",
                password="secret123",
                company_name="Admin Co",
                is_superuser=False,
            )

    def test_str_incluye_nombre_y_username(self):
        company = Company.objects.create_user(
            username="empresa@example.com",
            password="secret123",
            company_name="Empresa Uno",
        )
        self.assertEqual(str(company), "Empresa Uno (empresa@example.com)")

    def test_save_asigna_logo_por_defecto_si_no_tiene(self):
        company = Company.objects.create_user(
            username="empresa2@example.com",
            password="secret123",
            company_name="Empresa Dos",
        )
        self.assertEqual(str(company.logo), "company_logos/default_company_logo.png")

    def test_get_industry_display_name_retorna_otro_por_defecto(self):
        company = Company.objects.create_user(
            username="empresa3@example.com",
            password="secret123",
            company_name="Empresa Tres",
        )
        self.assertEqual(company.get_industry_display_name(), "Otro")

    def test_get_industry_display_name_conocido(self):
        company = Company.objects.create_user(
            username="empresa4@example.com",
            password="secret123",
            company_name="Empresa Cuatro",
            industry="technology",
        )
        self.assertEqual(company.get_industry_display_name(), "Tecnologia")


class TestJobs(TestCase):
    def setUp(self):
        self.company = Company.objects.create_user(
            username="empresa@example.com",
            password="secret123",
            company_name="Empresa Uno",
        )

    def test_str_incluye_titulo_y_empresa(self):
        job = Jobs.objects.create(
            company=self.company, title="Backend Dev", description="desc"
        )
        self.assertEqual(str(job), "Backend Dev - Empresa Uno")

    def test_get_experience_display_name_conocido(self):
        job = Jobs.objects.create(
            company=self.company,
            title="Backend Dev",
            description="desc",
            experience_level="senior",
        )
        self.assertEqual(job.get_experience_display_name(), "Senior (5+ años)")

    def test_get_experience_display_name_desconocido_usa_default(self):
        job = Jobs.objects.create(
            company=self.company, title="Backend Dev", description="desc"
        )
        job.experience_level = "no-existe"
        self.assertEqual(job.get_experience_display_name(), "Sin experiencia")

    def test_get_job_type_display_name_conocido(self):
        job = Jobs.objects.create(
            company=self.company,
            title="Backend Dev",
            description="desc",
            job_type="internship",
        )
        self.assertEqual(job.get_job_type_display_name(), "Prácticas")

    def test_get_job_type_display_name_desconocido_usa_default(self):
        job = Jobs.objects.create(
            company=self.company, title="Backend Dev", description="desc"
        )
        job.job_type = "no-existe"
        self.assertEqual(job.get_job_type_display_name(), "Tiempo completo")


class TestPostulants(TestCase):
    def setUp(self):
        self.company = Company.objects.create_user(
            username="empresa@example.com",
            password="secret123",
            company_name="Empresa Uno",
        )
        self.job = Jobs.objects.create(
            company=self.company, title="Backend Dev", description="desc"
        )

    def test_user_property_desde_snapshot(self):
        postulant = Postulants.objects.create(
            user_identity_id="u1",
            user_snapshot={"id": "u1", "username": "ana", "first_name": "Ana"},
            job=self.job,
        )
        self.assertEqual(postulant.user.id, "u1")
        self.assertEqual(postulant.user.username, "ana")

    def test_user_setter_actualiza_id_y_snapshot(self):
        postulant = Postulants(job=self.job)
        postulant.user = IdentityPrincipal(id="u2", username="beto")

        self.assertEqual(postulant.user_identity_id, "u2")
        self.assertEqual(postulant.user_snapshot["username"], "beto")

    def test_str_incluye_nombre_completo_y_titulo(self):
        postulant = Postulants.objects.create(
            user_identity_id="u1",
            user_snapshot={
                "id": "u1",
                "username": "ana",
                "first_name": "Ana",
                "last_name": "Perez",
            },
            job=self.job,
        )
        self.assertIn("Backend Dev", str(postulant))

    def test_get_status_display_name_conocido(self):
        postulant = Postulants.objects.create(
            user_identity_id="u1", job=self.job, status="interviewed"
        )
        self.assertEqual(postulant.get_status_display_name(), "Entrevistado")

    def test_get_status_display_name_desconocido_usa_default(self):
        postulant = Postulants.objects.create(user_identity_id="u1", job=self.job)
        postulant.status = "no-existe"
        self.assertEqual(postulant.get_status_display_name(), "Pendiente")


class TestJobInteraction(TestCase):
    def setUp(self):
        self.company = Company.objects.create_user(
            username="empresa@example.com",
            password="secret123",
            company_name="Empresa Uno",
        )
        self.job = Jobs.objects.create(
            company=self.company, title="Backend Dev", description="desc"
        )

    def test_user_property_desde_snapshot(self):
        interaction = JobInteraction.objects.create(
            user_identity_id="u1",
            user_snapshot={"id": "u1", "username": "ana"},
            job=self.job,
            interaction_type="view",
        )
        self.assertEqual(interaction.user.username, "ana")

    def test_user_setter_actualiza_id_y_snapshot(self):
        interaction = JobInteraction(job=self.job, interaction_type="view")
        interaction.user = IdentityPrincipal(id="u3", username="cami")

        self.assertEqual(interaction.user_identity_id, "u3")
        self.assertEqual(interaction.user_snapshot["username"], "cami")

    def test_str_incluye_usuario_titulo_y_tipo(self):
        interaction = JobInteraction.objects.create(
            user_identity_id="u1",
            user_snapshot={"id": "u1", "username": "ana"},
            job=self.job,
            interaction_type="save",
        )
        self.assertEqual(str(interaction), "ana - Backend Dev - save")

    def test_unique_together_evita_duplicados(self):
        JobInteraction.objects.create(
            user_identity_id="u1", job=self.job, interaction_type="view"
        )
        with self.assertRaises(Exception):
            JobInteraction.objects.create(
                user_identity_id="u1", job=self.job, interaction_type="view"
            )
