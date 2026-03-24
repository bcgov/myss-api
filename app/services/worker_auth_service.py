from app.models.admin import IDIRGroup, WorkerRole


class WorkerAuthService:
    @staticmethod
    def resolve_role(groups: list[str]) -> WorkerRole:
        """Resolve worker role from IDIR groups.

        Unknown groups are treated as SSBC_WORKER (least-privilege fallback).
        Does NOT raise HTTP 403 for unknown groups.
        """
        if IDIRGroup.MYSS_ADMINS in groups or IDIRGroup.MYSS_ADMINS.value in groups:
            return WorkerRole.SUPER_ADMIN
        return WorkerRole.SSBC_WORKER  # least-privilege default
