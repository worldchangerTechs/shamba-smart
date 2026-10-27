from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from accounts.models import User


class ScopedModelViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated]
    farmer_user_paths = ()
    farmer_ward_paths = ()
    ward_paths = ()

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.is_superuser or user.role == User.Role.ADMIN:
            return queryset

        if user.role == User.Role.FARMER:
            scoped = Q()
            for path in self.farmer_user_paths:
                scoped |= Q(**{path: user.pk})
            farmer = getattr(user, "farmer_profile", None)
            if farmer and self.farmer_ward_paths:
                for path in self.farmer_ward_paths:
                    scoped |= Q(**{path: farmer.ward_id})
            return queryset.filter(scoped).distinct() if scoped else queryset.none()

        if user.role == User.Role.OFFICER:
            ward_ids = user.assigned_wards.values_list("pk", flat=True)
            scoped = Q()
            for path in self.ward_paths:
                scoped |= Q(**{f"{path}__in": ward_ids})
            return queryset.filter(scoped).distinct() if self.ward_paths else queryset.none()

        return queryset.none()

    def _ensure_scoped(self, instance):
        if not self.get_queryset().filter(pk=instance.pk).exists():
            raise PermissionDenied("You do not have access to this record.")

    def perform_create(self, serializer):
        with transaction.atomic():
            instance = serializer.save()
            self._ensure_scoped(instance)

    def perform_update(self, serializer):
        with transaction.atomic():
            instance = serializer.save()
            self._ensure_scoped(instance)


class AdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (
                request.method in ("GET", "HEAD", "OPTIONS")
                or request.user.is_superuser
                or request.user.role == User.Role.ADMIN
            )
        )


class PublicReadOnlyViewSet(ModelViewSet):
    permission_classes = [AdminOrReadOnly]
