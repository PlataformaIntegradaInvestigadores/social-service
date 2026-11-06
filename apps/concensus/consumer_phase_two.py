from apps.concensus.consumer import GroupConnectionConsumer


class PhaseTwoConsumer(GroupConnectionConsumer):
    """Consumer del grupo en la fase 2 del consenso."""

    group_prefix = "phase2_group_"
