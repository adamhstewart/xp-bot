"""
Permission checking utilities for XP Bot
"""


def has_role(user, allowed_roles):
    """Return True if user has at least one allowed role name."""
    return any(role.name in allowed_roles for role in getattr(user, 'roles', []))
