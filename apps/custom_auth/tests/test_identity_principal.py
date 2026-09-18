"""Unitarias de apps/custom_auth/identity_principal.py: construccion de
principales (usuario/grupo) a partir de claims JWT o snapshots denormalizados."""

from django.test import SimpleTestCase

from apps.custom_auth.identity_principal import (
    GroupPrincipal,
    IdentityPrincipal,
    group_ref_from_snapshot,
    group_snapshot_from_principal,
    principal_from_token,
    ref_from_snapshot,
    snapshot_from_principal,
)


class TestIdentityPrincipal(SimpleTestCase):
    def test_pk_es_el_id(self):
        principal = IdentityPrincipal(id="u1")
        self.assertEqual(principal.pk, "u1")

    def test_siempre_esta_autenticado_y_no_es_anonimo(self):
        principal = IdentityPrincipal(id="u1")
        self.assertTrue(principal.is_authenticated)
        self.assertFalse(principal.is_anonymous)

    def test_get_full_name_combina_nombre_y_apellido(self):
        principal = IdentityPrincipal(id="u1", first_name="Ana", last_name="Perez")
        self.assertEqual(principal.get_full_name(), "Ana Perez")

    def test_has_perm_y_has_module_perms_son_siempre_false(self):
        principal = IdentityPrincipal(id="u1")
        self.assertFalse(principal.has_perm("any.perm"))
        self.assertFalse(principal.has_module_perms("any_app"))

    def test_str_usa_username_o_id(self):
        self.assertEqual(str(IdentityPrincipal(id="u1", username="ana")), "ana")
        self.assertEqual(str(IdentityPrincipal(id="u1")), "u1")


class TestGroupPrincipal(SimpleTestCase):
    def test_pk_es_el_id(self):
        self.assertEqual(GroupPrincipal(id="g1").pk, "g1")

    def test_str_prefiere_title_sobre_name_sobre_id(self):
        self.assertEqual(GroupPrincipal(id="g1", title="T", name="N").__str__(), "T")
        self.assertEqual(GroupPrincipal(id="g1", name="N").__str__(), "N")
        self.assertEqual(GroupPrincipal(id="g1").__str__(), "g1")


class TestPrincipalFromToken(SimpleTestCase):
    def test_sin_user_id_ni_sub_retorna_none(self):
        self.assertIsNone(principal_from_token({}))

    def test_construye_principal_desde_user_id(self):
        token = {"user_id": 42, "email": "ana@example.com", "first_name": "Ana"}
        principal = principal_from_token(token)
        self.assertEqual(principal.id, "42")
        self.assertEqual(principal.username, "ana@example.com")
        self.assertEqual(principal.first_name, "Ana")

    def test_usa_sub_si_no_hay_user_id(self):
        token = {"sub": "u9"}
        principal = principal_from_token(token)
        self.assertEqual(principal.id, "u9")

    def test_prefiere_username_sobre_email_si_no_hay_email(self):
        token = {"user_id": "1", "username": "ana"}
        principal = principal_from_token(token)
        self.assertEqual(principal.username, "ana")

    def test_usa_payload_del_token_si_existe(self):
        class FakeToken(dict):
            payload = {"user_id": "1", "extra_claim": "x"}

        token = FakeToken(user_id="1")
        principal = principal_from_token(token)
        self.assertEqual(principal.extra, {"user_id": "1", "extra_claim": "x"})


class TestSnapshotFromPrincipal(SimpleTestCase):
    def test_incluye_los_campos_esperados(self):
        principal = IdentityPrincipal(
            id="1", username="ana", first_name="Ana", last_name="Perez"
        )
        snapshot = snapshot_from_principal(principal)
        self.assertEqual(
            snapshot,
            {
                "id": "1",
                "username": "ana",
                "first_name": "Ana",
                "last_name": "Perez",
                "profile_picture": "",
            },
        )

    def test_atributos_faltantes_se_limpian_a_string_vacio(self):
        class Bare:
            id = "1"

        snapshot = snapshot_from_principal(Bare())
        self.assertEqual(snapshot["username"], "")


class TestRefFromSnapshot(SimpleTestCase):
    def test_construye_principal_desde_snapshot(self):
        principal = ref_from_snapshot("1", {"username": "ana"})
        self.assertIsInstance(principal, IdentityPrincipal)
        self.assertEqual(principal.id, "1")
        self.assertEqual(principal.username, "ana")

    def test_snapshot_none_no_falla(self):
        principal = ref_from_snapshot("1", None)
        self.assertEqual(principal.id, "1")
        self.assertEqual(principal.username, "")


class TestGroupSnapshotFromPrincipal(SimpleTestCase):
    def test_incluye_id_name_title(self):
        group = GroupPrincipal(id="g1", name="n", title="t")
        self.assertEqual(
            group_snapshot_from_principal(group),
            {"id": "g1", "name": "n", "title": "t"},
        )


class TestGroupRefFromSnapshot(SimpleTestCase):
    def test_construye_group_principal_desde_snapshot(self):
        group = group_ref_from_snapshot("g1", {"name": "n", "title": "t"})
        self.assertIsInstance(group, GroupPrincipal)
        self.assertEqual(group.id, "g1")
        self.assertEqual(group.name, "n")

    def test_snapshot_none_no_falla(self):
        group = group_ref_from_snapshot("g1", None)
        self.assertEqual(group.id, "g1")
        self.assertEqual(group.name, "")
