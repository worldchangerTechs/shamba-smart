from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework.views import APIView

from accounts.models import User, Ward
from common.api import PublicReadOnlyViewSet
from farms.models import Crop, Farm
from .models import Buyer, MarketPrice, SellListing, TrainingEvent
from .serializers import (
    BuyerSerializer,
    MarketPriceSerializer,
    PriceCompareQuerySerializer,
    PriceLookupQuerySerializer,
    PriceTrendQuerySerializer,
    SellListingSerializer,
    TrainingEventSerializer,
)
from .services import compare_local_price, crop_price_trends, public_price_lookup


class MarketPricePermission(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return request.user.is_superuser or request.user.role in (
            User.Role.OFFICER,
            User.Role.ADMIN,
        )

    def has_object_permission(self, request, view, obj):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        user = request.user
        return bool(
            user.is_superuser
            or user.role == User.Role.ADMIN
            or (
                user.role == User.Role.OFFICER
                and user.assigned_wards.filter(pk=obj.ward_id).exists()
            )
        )


class MarketPriceViewSet(ModelViewSet):
    permission_classes = [MarketPricePermission]
    queryset = MarketPrice.objects.select_related("crop", "ward")
    serializer_class = MarketPriceSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        crop_id = self.request.query_params.get("crop_id")
        ward_id = self.request.query_params.get("ward_id")
        if crop_id:
            queryset = queryset.filter(crop_id=crop_id)
        if ward_id:
            queryset = queryset.filter(ward_id=ward_id)
        if self.request.user.role == User.Role.OFFICER and self.action in {
            "update",
            "partial_update",
            "destroy",
        }:
            queryset = queryset.filter(ward__in=self.request.user.assigned_wards.all())
        return queryset

    @action(detail=False, methods=["get"], url_path="trends")
    @extend_schema(
        parameters=[
            OpenApiParameter("crop_id", int, required=True),
            OpenApiParameter("ward_id", int, required=False),
            OpenApiParameter("market_name", str, required=False),
        ],
        responses=dict,
    )
    def trends(self, request):
        serializer = PriceTrendQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        crop = get_object_or_404(Crop, pk=data["crop_id"])
        ward = (
            get_object_or_404(Ward, pk=data["ward_id"])
            if data.get("ward_id")
            else None
        )
        return Response(
            crop_price_trends(
                crop=crop,
                ward=ward,
                market_name=data.get("market_name"),
            )
        )

    @action(detail=False, methods=["get"], url_path="compare")
    @extend_schema(
        parameters=[
            OpenApiParameter("farm_id", int, required=True),
            OpenApiParameter("crop_id", int, required=True),
            OpenApiParameter("middleman_price_per_kg", str, required=True),
            OpenApiParameter("quantity_kg", str, required=False),
        ],
        responses=dict,
    )
    def compare(self, request):
        if request.user.role != User.Role.FARMER and not request.user.is_superuser and request.user.role != User.Role.ADMIN:
            raise PermissionDenied("Price comparison is available to farmers.")
        serializer = PriceCompareQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        farms = Farm.objects.select_related("farmer__user")
        if request.user.role == User.Role.FARMER and not request.user.is_superuser:
            farms = farms.filter(farmer__user=request.user)
        farm = get_object_or_404(farms, pk=data["farm_id"])
        crop = get_object_or_404(Crop, pk=data["crop_id"])
        if not farm.plantings.filter(crop=crop).exists():
            raise PermissionDenied("The selected crop is not recorded on this farm.")
        return Response(
            compare_local_price(
                farm=farm,
                crop=crop,
                middleman_price=data["middleman_price_per_kg"],
                quantity_kg=data["quantity_kg"],
            )
        )

    def perform_create(self, serializer):
        if self.request.user.role == User.Role.OFFICER:
            ward = serializer.validated_data["ward"]
            if not self.request.user.assigned_wards.filter(pk=ward.pk).exists():
                raise PermissionDenied("You can add prices only for your assigned wards.")
        serializer.save(is_sample_data=False)

    def perform_update(self, serializer):
        if self.request.user.role == User.Role.OFFICER:
            ward = serializer.validated_data.get("ward", serializer.instance.ward)
            if not self.request.user.assigned_wards.filter(pk=ward.pk).exists():
                raise PermissionDenied("You can edit prices only in your assigned wards.")
        serializer.save(is_sample_data=False)


class BuyerViewSet(PublicReadOnlyViewSet):
    queryset = Buyer.objects.filter(verified=True).select_related("ward").prefetch_related("crops")
    serializer_class = BuyerSerializer


class TrainingEventViewSet(PublicReadOnlyViewSet):
    queryset = TrainingEvent.objects.select_related("ward")
    serializer_class = TrainingEventSerializer


class SellListingViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = SellListing.objects.select_related(
        "farmer__user", "farmer__ward", "crop"
    )
    serializer_class = SellListingSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.user.role == User.Role.FARMER:
            queryset = queryset.filter(
                Q(status=SellListing.Status.OPEN)
                | Q(farmer__user=self.request.user)
            )
        elif self.request.user.role == User.Role.OFFICER:
            queryset = queryset.filter(
                Q(status=SellListing.Status.OPEN)
                | Q(farmer__ward__in=self.request.user.assigned_wards.all())
            )
        return queryset

    def create(self, request, *args, **kwargs):
        if request.user.role != User.Role.FARMER:
            raise PermissionDenied("Only farmers can post crop listings.")
        try:
            farmer = request.user.farmer_profile
        except AttributeError:
            raise PermissionDenied("This account has no farmer profile.") from None
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        listing = serializer.save(farmer=farmer)
        return Response(
            self.get_serializer(listing).data, status=status.HTTP_201_CREATED
        )

    def perform_update(self, serializer):
        listing = serializer.instance
        user = self.request.user
        if user.role == User.Role.FARMER and listing.farmer.user_id != user.pk:
            raise PermissionDenied("You can edit only your own listings.")
        if user.role == User.Role.OFFICER and not user.assigned_wards.filter(
            pk=listing.farmer.ward_id
        ).exists():
            raise PermissionDenied("You can edit listings only in your assigned wards.")
        serializer.save()

    def perform_destroy(self, instance):
        user = self.request.user
        if user.role == User.Role.FARMER and instance.farmer.user_id != user.pk:
            raise PermissionDenied("You can remove only your own listings.")
        if user.role == User.Role.OFFICER and not user.assigned_wards.filter(
            pk=instance.farmer.ward_id
        ).exists():
            raise PermissionDenied("You can remove listings only in your assigned wards.")
        instance.delete()


class PublicMarketPriceLookupView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        parameters=[
            OpenApiParameter("crop", str, required=True),
            OpenApiParameter("ward", str, required=True),
            OpenApiParameter("language", str, required=False),
        ],
        responses=dict,
    )
    def get(self, request):
        serializer = PriceLookupQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        result = public_price_lookup(
            crop_name=data["crop"],
            ward_name=data["ward"],
            language=data["language"],
        )
        if result is None:
            raise NotFound("No market prices are available for that crop and ward.")
        return Response(result)
