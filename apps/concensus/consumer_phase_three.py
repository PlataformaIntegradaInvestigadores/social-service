from apps.concensus.consumer import GroupConnectionConsumer


class PhaseThreeConsumer(GroupConnectionConsumer):
    """Consumer del grupo en la fase 3 del consenso."""

    group_prefix = "phase3_group_"
