"""Unitarias de RetiredUserVectorService: adaptador retirado que conserva la
interfaz de vectores de usuario sin tocar ninguna tabla (identidad vive en
profile_identity_backend)."""

from django.test import SimpleTestCase

from apps.custom_auth.domain.services.user_vector_service import user_vector_service


class TestRetiredUserVectorService(SimpleTestCase):
    def test_update_user_job_embedding_retorna_false(self):
        self.assertFalse(user_vector_service.update_user_job_embedding("1"))

    def test_update_user_feed_embedding_retorna_false(self):
        self.assertFalse(user_vector_service.update_user_feed_embedding("1"))

    def test_update_user_vectors_on_interaction_no_lanza(self):
        user_vector_service.update_user_vectors_on_interaction("1", "like", "hola")

    def test_get_users_for_job_recommendations_retorna_lista_vacia(self):
        self.assertEqual(
            user_vector_service.get_users_for_job_recommendations([0.1, 0.2]), []
        )
