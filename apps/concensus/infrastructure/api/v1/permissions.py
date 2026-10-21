from rest_framework import permissions

from apps.custom_auth.identity_profile_client import get_identity_group_detail


class IsGroupMember(permissions.BasePermission):
    """Allow only the admin or a member of the group named in the URL.

    Group membership lives in identity-service, which already answers 403 to
    non-members on GET /api/groups/<id>/. We ask it with the caller's own token
    and re-check the returned ids, so this service never trusts a group_id just
    because the caller is authenticated. Fails closed: if identity cannot be
    reached or does not return the group, access is denied.
    """

    message = "You do not have permission to access this group."

    def has_permission(self, request, view):
        group_id = view.kwargs.get("group_id")
        user_id = str(getattr(request.user, "id", "") or "")
        if not group_id or not user_id:
            return False

        group = get_identity_group_detail(
            group_id,
            authorization_header=request.headers.get("Authorization", ""),
        )
        if not group:
            return False

        member_ids = {str(user.get("id")) for user in group.get("users", [])}
        return user_id == str(group.get("admin_id")) or user_id in member_ids
