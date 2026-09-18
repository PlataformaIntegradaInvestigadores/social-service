from django.urls import re_path

from apps.concensus.consumer import GroupConsumer
from apps.concensus.consumer_phase_three import PhaseThreeConsumer
from apps.concensus.consumer_phase_two import PhaseTwoConsumer
from apps.concensus.debate_consumer import ChatConsumer

websocket_urlpatterns = [
    re_path(r"ws/groups/(?P<group_id>\w+)/$", GroupConsumer.as_asgi()),
    re_path(r"ws/phase2/groups/(?P<group_id>\w+)/$", PhaseTwoConsumer.as_asgi()),
    re_path(r"ws/phase3/groups/(?P<group_id>\w+)/$", PhaseThreeConsumer.as_asgi()),
    re_path(
        r"^ws/chat/(?P<group_id>[a-zA-Z0-9_-]+)/(?P<debate_id>\d+)/$",
        ChatConsumer.as_asgi(),
    ),
]
