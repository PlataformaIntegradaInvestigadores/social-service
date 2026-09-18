from dataclasses import dataclass, field


def _clean(value):
    return "" if value is None else str(value)


@dataclass
class IdentityPrincipal:
    id: str
    username: str = ""
    first_name: str = ""
    last_name: str = ""
    profile_picture: str = ""
    is_active: bool = True
    is_staff: bool = False
    is_superuser: bool = False
    extra: dict = field(default_factory=dict)

    @property
    def pk(self):
        return self.id

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def has_perm(self, *_args, **_kwargs):
        return False

    def has_module_perms(self, *_args, **_kwargs):
        return False

    def __str__(self):
        return self.username or self.id


@dataclass
class GroupPrincipal:
    id: str
    name: str = ""
    title: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def pk(self):
        return self.id

    def __str__(self):
        return self.title or self.name or self.id


def principal_from_token(validated_token):
    token_payload = getattr(validated_token, "payload", validated_token)
    user_id = validated_token.get("user_id") or validated_token.get("sub")
    if not user_id:
        return None
    return IdentityPrincipal(
        id=str(user_id),
        username=_clean(
            validated_token.get("email") or validated_token.get("username")
        ),
        first_name=_clean(validated_token.get("first_name")),
        last_name=_clean(validated_token.get("last_name")),
        extra=dict(token_payload),
    )


def snapshot_from_principal(principal):
    return {
        "id": _clean(getattr(principal, "id", "")),
        "username": _clean(getattr(principal, "username", "")),
        "first_name": _clean(getattr(principal, "first_name", "")),
        "last_name": _clean(getattr(principal, "last_name", "")),
        "profile_picture": _clean(getattr(principal, "profile_picture", "")),
    }


def ref_from_snapshot(identity_id, snapshot=None):
    snapshot = snapshot or {}
    return IdentityPrincipal(
        id=_clean(identity_id),
        username=_clean(snapshot.get("username")),
        first_name=_clean(snapshot.get("first_name")),
        last_name=_clean(snapshot.get("last_name")),
        profile_picture=_clean(snapshot.get("profile_picture")),
    )


def group_snapshot_from_principal(group):
    return {
        "id": _clean(getattr(group, "id", "")),
        "name": _clean(getattr(group, "name", "")),
        "title": _clean(getattr(group, "title", "")),
    }


def group_ref_from_snapshot(identity_id, snapshot=None):
    snapshot = snapshot or {}
    return GroupPrincipal(
        id=_clean(identity_id),
        name=_clean(snapshot.get("name")),
        title=_clean(snapshot.get("title")),
    )
