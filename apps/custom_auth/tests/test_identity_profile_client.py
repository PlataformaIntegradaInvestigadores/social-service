"""Unitarias de apps/custom_auth/identity_profile_client.py: cliente HTTP hacia
profile_identity_backend para resolver snapshots de usuarios/grupos."""

from unittest.mock import MagicMock, patch

import requests
from django.test import SimpleTestCase, override_settings

from apps.custom_auth.identity_profile_client import (
    get_identity_group_detail,
    get_identity_user_snapshot,
    merge_identity_snapshot,
    normalize_profile_picture,
)


class TestNormalizeProfilePicture(SimpleTestCase):
    def test_vacio_retorna_string_vacio(self):
        self.assertEqual(normalize_profile_picture(""), "")
        self.assertEqual(normalize_profile_picture(None), "")

    def test_url_absoluta_o_ruta_raiz_se_mantiene(self):
        self.assertEqual(normalize_profile_picture("http://x/y.png"), "http://x/y.png")
        self.assertEqual(normalize_profile_picture("/media/y.png"), "/media/y.png")

    def test_prefijo_media_se_completa_con_slash(self):
        self.assertEqual(normalize_profile_picture("media/y.png"), "/media/y.png")

    def test_ruta_relativa_se_prefija_con_media(self):
        self.assertEqual(normalize_profile_picture("y.png"), "/media/y.png")


class TestMergeIdentitySnapshot(SimpleTestCase):
    def test_sin_payload_solo_normaliza_la_foto_existente(self):
        base = {"id": "1", "profile_picture": "y.png"}
        merged = merge_identity_snapshot(base, None)
        self.assertEqual(merged["profile_picture"], "/media/y.png")
        self.assertEqual(merged["id"], "1")

    def test_payload_sobreescribe_campos_no_vacios(self):
        base = {"id": "1", "first_name": "Old"}
        payload = {"first_name": "New", "last_name": "", "scopus_id": None}
        merged = merge_identity_snapshot(base, payload)
        self.assertEqual(merged["first_name"], "New")
        self.assertNotIn("last_name", merged)  # vacio no sobreescribe
        self.assertEqual(merged["id"], "1")

    def test_profile_picture_del_payload_tiene_prioridad(self):
        base = {"profile_picture": "old.png"}
        payload = {"profile_picture": "new.png"}
        merged = merge_identity_snapshot(base, payload)
        self.assertEqual(merged["profile_picture"], "/media/new.png")


class TestGetIdentityUserSnapshot(SimpleTestCase):
    def test_sin_user_id_retorna_none(self):
        self.assertIsNone(get_identity_user_snapshot(""))
        self.assertIsNone(get_identity_user_snapshot(None))

    @override_settings(PROFILE_IDENTITY_BASE_URL="http://identity.local")
    def test_llamada_exitosa_retorna_el_json(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"id": "1", "username": "ana"}
        with patch(
            "apps.custom_auth.identity_profile_client.requests.get",
            return_value=mock_resp,
        ):
            data = get_identity_user_snapshot("1")
        self.assertEqual(data, {"id": "1", "username": "ana"})

    @override_settings(PROFILE_IDENTITY_BASE_URL="http://identity.local")
    def test_error_de_red_retorna_none(self):
        with patch(
            "apps.custom_auth.identity_profile_client.requests.get",
            side_effect=requests.ConnectionError("down"),
        ):
            self.assertIsNone(get_identity_user_snapshot("1"))

    @override_settings(PROFILE_IDENTITY_BASE_URL="http://identity.local")
    def test_usa_cache_cuando_ya_existe_la_clave(self):
        cache = {"1": {"id": "1", "cached": True}}
        with patch("apps.custom_auth.identity_profile_client.requests.get") as mock_get:
            data = get_identity_user_snapshot("1", cache=cache)
        mock_get.assert_not_called()
        self.assertEqual(data, {"id": "1", "cached": True})

    @override_settings(PROFILE_IDENTITY_BASE_URL="http://identity.local")
    def test_guarda_en_cache_tras_resolver(self):
        cache = {}
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"id": "1"}
        with patch(
            "apps.custom_auth.identity_profile_client.requests.get",
            return_value=mock_resp,
        ):
            get_identity_user_snapshot("1", cache=cache)
        self.assertEqual(cache["1"], {"id": "1"})

    @override_settings(PROFILE_IDENTITY_BASE_URL="http://identity.local")
    def test_incluye_authorization_header_si_se_provee(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {}
        with patch(
            "apps.custom_auth.identity_profile_client.requests.get",
            return_value=mock_resp,
        ) as mock_get:
            get_identity_user_snapshot("1", authorization_header="Bearer tok")
        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer tok")


class TestGetIdentityGroupDetail(SimpleTestCase):
    def test_sin_group_id_retorna_none(self):
        self.assertIsNone(get_identity_group_detail(""))

    @override_settings(PROFILE_IDENTITY_BASE_URL="http://identity.local")
    def test_llamada_exitosa_retorna_el_json(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"id": "g1", "users": []}
        with patch(
            "apps.custom_auth.identity_profile_client.requests.get",
            return_value=mock_resp,
        ):
            data = get_identity_group_detail("g1")
        self.assertEqual(data, {"id": "g1", "users": []})

    @override_settings(PROFILE_IDENTITY_BASE_URL="http://identity.local")
    def test_error_de_red_retorna_none(self):
        with patch(
            "apps.custom_auth.identity_profile_client.requests.get",
            side_effect=requests.Timeout("slow"),
        ):
            self.assertIsNone(get_identity_group_detail("g1"))
