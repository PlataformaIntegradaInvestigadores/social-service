"""Unitarias de las entidades de dominio de concensus: todas siguen el mismo
patron ACL (identity_id + snapshot denormalizado -> propiedad get/set que
envuelve group_ref_from_snapshot/ref_from_snapshot), asi que se prueban en
instancias sin persistir (no requieren DB para el getter/setter/str)."""

from datetime import timedelta

from django.test import SimpleTestCase
from django.utils.timezone import now

from apps.concensus.domain.entities.debate import Debate
from apps.concensus.domain.entities.debate_message import Message
from apps.concensus.domain.entities.debate_participant import DebateParticipant
from apps.concensus.domain.entities.debate_participant_posture import UserPosture
from apps.concensus.domain.entities.debate_reaction import Reaction
from apps.concensus.domain.entities.final_topic_order import FinalTopicOrder
from apps.concensus.domain.entities.notification import (
    NotificationPhaseOne,
    NotificationPhaseTwo,
)
from apps.concensus.domain.entities.topic import (
    RecommendedTopic,
    Topic,
    TopicAddedUser,
)
from apps.concensus.domain.entities.user_expertice import UserExpertise
from apps.concensus.domain.entities.user_phase import UserPhase
from apps.concensus.domain.entities.user_satisfaction import UserSatisfaction
from apps.custom_auth.identity_principal import GroupPrincipal, IdentityPrincipal


def _group(id="g1", name="Grupo Uno", title="Grupo Uno"):
    return GroupPrincipal(id=id, name=name, title=title)


def _user(id="u1", username="ana"):
    return IdentityPrincipal(id=id, username=username)


class TestDebate(SimpleTestCase):
    def _debate(self, **extra):
        d = Debate(title="T1", description="d", end_time=timedelta(hours=1), **extra)
        d.group = _group()
        return d

    def test_group_setter_llena_identity_id_y_snapshot(self):
        d = self._debate()
        self.assertEqual(d.group_identity_id, "g1")
        self.assertEqual(d.group.name, "Grupo Uno")

    def test_str_incluye_titulo_y_grupo(self):
        self.assertEqual(str(self._debate()), "T1 - Grupo Uno")

    def test_is_time_exceeded_false_recien_creado(self):
        d = self._debate(created_at=now())
        self.assertFalse(d.is_time_exceeded())

    def test_is_time_exceeded_true_si_ya_paso_el_tiempo(self):
        d = self._debate(created_at=now() - timedelta(hours=2))
        self.assertTrue(d.is_time_exceeded())

    def test_get_closing_time_suma_created_at_y_end_time(self):
        created = now()
        d = self._debate(created_at=created)
        self.assertEqual(d.get_closing_time(), created + timedelta(hours=1))


class TestMessage(SimpleTestCase):
    def _debate(self):
        d = Debate(title="T1", description="d", end_time=timedelta(hours=1))
        d.group = _group()
        return d

    def test_user_setter_getter(self):
        m = Message(debate=self._debate(), text="hola")
        m.user = _user()
        self.assertEqual(m.user_identity_id, "u1")
        self.assertEqual(m.user.username, "ana")

    def test_group_none_por_defecto(self):
        m = Message(debate=self._debate(), text="hola")
        self.assertIsNone(m.group)

    def test_group_setter_none_limpia_snapshot(self):
        m = Message(debate=self._debate(), text="hola")
        m.group = _group()
        m.group = None
        self.assertIsNone(m.group_identity_id)
        self.assertEqual(m.group_snapshot, {})

    def test_str_incluye_usuario_y_debate(self):
        debate = self._debate()
        m = Message(debate=debate, text="hola")
        m.user = _user()
        self.assertEqual(str(m), "Message by ana in T1")


class TestDebateParticipant(SimpleTestCase):
    def test_participant_setter_getter_y_str(self):
        debate = Debate(title="T1", description="d", end_time=timedelta(hours=1))
        p = DebateParticipant(debate=debate)
        p.participant = _user()
        self.assertEqual(p.participant_identity_id, "u1")
        self.assertEqual(str(p), "ana in debate T1")


class TestUserPosture(SimpleTestCase):
    def test_user_setter_getter_y_str(self):
        debate = Debate(title="T1", description="d", end_time=timedelta(hours=1))
        posture = UserPosture(debate=debate, posture="agree")
        posture.user = _user()
        self.assertEqual(posture.user_identity_id, "u1")
        self.assertEqual(str(posture), "ana - agree - T1")


class TestReaction(SimpleTestCase):
    def test_user_setter_getter_y_str(self):
        debate = Debate(title="T1", description="d", end_time=timedelta(hours=1))
        message = Message(debate=debate, text="hola", id=5)
        reaction = Reaction(message=message)
        reaction.user = _user()
        self.assertEqual(reaction.user_identity_id, "u1")
        self.assertEqual(str(reaction), "Reaction by ana to message 5")


class TestFinalTopicOrder(SimpleTestCase):
    def test_idgroup_iduser_setters_y_str(self):
        topic = RecommendedTopic(topic_name="ML")
        order = FinalTopicOrder(idTopic=topic, posFinal=1)
        order.idGroup = _group()
        order.idUser = _user()
        self.assertEqual(order.idGroup_identity_id, "g1")
        self.assertEqual(order.idUser_identity_id, "u1")
        self.assertIn("Position 1", str(order))


class TestNotifications(SimpleTestCase):
    def test_phase_one_user_group_setters_y_str(self):
        n = NotificationPhaseOne(notification_type="new_topic", message="hola")
        n.user = _user()
        n.group = _group()
        self.assertEqual(n.user_identity_id, "u1")
        self.assertEqual(n.group_identity_id, "g1")
        self.assertEqual(str(n), "ana - new_topic")

    def test_phase_two_user_group_setters_y_str(self):
        n = NotificationPhaseTwo(notification_type="topic_reorder", message="hola")
        n.user = _user()
        n.group = _group()
        self.assertEqual(str(n), "ana - topic_reorder")


class TestTopic(SimpleTestCase):
    def test_group_setter_getter_y_str(self):
        t = Topic(name="IA")
        t.group = _group()
        self.assertEqual(t.group_identity_id, "g1")
        self.assertEqual(str(t), "IA")


class TestRecommendedTopic(SimpleTestCase):
    def test_group_none_por_defecto(self):
        rt = RecommendedTopic(topic_name="IA")
        self.assertIsNone(rt.group)

    def test_group_setter_getter(self):
        rt = RecommendedTopic(topic_name="IA")
        rt.group = _group()
        self.assertEqual(rt.group_identity_id, "g1")
        self.assertEqual(str(rt), "IA")

    def test_group_setter_none_limpia_snapshot(self):
        rt = RecommendedTopic(topic_name="IA")
        rt.group = _group()
        rt.group = None
        self.assertIsNone(rt.group_identity_id)
        self.assertEqual(rt.group_snapshot, {})


class TestTopicAddedUser(SimpleTestCase):
    def test_group_user_setters_y_str(self):
        topic = RecommendedTopic(topic_name="IA")
        tau = TopicAddedUser(topic=topic)
        tau.group = _group()
        tau.user = _user()
        self.assertEqual(tau.group_identity_id, "g1")
        self.assertEqual(tau.user_identity_id, "u1")
        self.assertEqual(str(tau), "ana added IA to Grupo Uno")


class TestUserExpertise(SimpleTestCase):
    def test_user_group_setters_y_str(self):
        topic = RecommendedTopic(topic_name="IA")
        ue = UserExpertise(topic=topic, expertise_level=3)
        ue.user = _user()
        ue.group = _group()
        self.assertEqual(str(ue), "ana - IA - 3")


class TestUserPhase(SimpleTestCase):
    def test_user_group_setter_getter(self):
        phase = UserPhase(phase=2)
        phase.user = _user()
        phase.group = _group()
        self.assertEqual(phase.user_identity_id, "u1")
        self.assertEqual(phase.group_identity_id, "g1")


class TestUserSatisfaction(SimpleTestCase):
    def test_user_group_setter_getter(self):
        s = UserSatisfaction(satisfaction_level="Satisfied", message="ok")
        s.user = _user()
        s.group = _group()
        self.assertEqual(s.user_identity_id, "u1")
        self.assertEqual(s.group_identity_id, "g1")
