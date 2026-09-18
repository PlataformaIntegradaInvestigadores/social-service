"""Unitarias de los management commands retirados de custom_auth: son stubs
que solo emiten una advertencia (la identidad canonica vive en
profile_identity_backend), pero se conservan para no romper scripts de ops
que los invoquen por nombre."""

from io import StringIO

from django.core.management import call_command
from django.test import SimpleTestCase


class TestRetiredCommands(SimpleTestCase):
    def _run(self, name):
        out = StringIO()
        call_command(name, stdout=out)
        return out.getvalue()

    def test_create_test_data_advierte_y_no_falla(self):
        self.assertIn("retirado", self._run("create_test_data"))

    def test_export_identity_profile_data_advierte_y_no_falla(self):
        self.assertIn("retirado", self._run("export_identity_profile_data"))

    def test_seed_presentation_data_advierte_y_no_falla(self):
        self.assertIn("retirado", self._run("seed_presentation_data"))

    def test_update_user_embeddings_advierte_y_no_falla(self):
        self.assertIn("retirado", self._run("update_user_embeddings"))
