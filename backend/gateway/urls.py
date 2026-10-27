from rest_framework.routers import DefaultRouter
from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from analytics.views import SummaryView
from accounts.views import FarmerViewSet, LoginView, RegisterView, UserViewSet, WardViewSet
from advice.views import AdviceContentViewSet, AdviceRecommendationViewSet
from alerts.views import AlertDeliveryViewSet, AlertViewSet, RuleViewSet
from academy.views import (
    BadgeViewSet,
    FrequentlyAskedQuestionViewSet,
    LessonProgressViewSet,
    LessonViewSet,
    OfficerQuestionViewSet,
)
from farms.views import CropViewSet, FarmViewSet, PlantingViewSet
from market.views import (
    BuyerViewSet,
    MarketPriceViewSet,
    PublicMarketPriceLookupView,
    SellListingViewSet,
    TrainingEventViewSet,
)
from pests.views import (
    OutbreakViewSet,
    PestIdentificationView,
    PestKnowledgeView,
    PestOutbreakGeoJSONView,
    PestPublicStatsView,
    PestReportViewSet,
    SprayLogViewSet,
)
from weather.views import WeatherSnapshotViewSet
from waste.views import DisposalPointViewSet, WasteLogViewSet
from .views import HealthView
from .ussd_views import ussd_callback
from .sms.views import (
    vendel_webhook,
    warning_audit_log,
    warning_batch,
    warning_preview,
    warning_provider,
    warning_retry,
    warning_send,
)

router = DefaultRouter()
router.register("wards", WardViewSet)
router.register("users", UserViewSet)
router.register("farmers", FarmerViewSet)
router.register("crops", CropViewSet)
router.register("farms", FarmViewSet)
router.register("plantings", PlantingViewSet)
router.register("weather", WeatherSnapshotViewSet)
router.register("rules", RuleViewSet)
router.register("alerts", AlertViewSet)
router.register("alert-deliveries", AlertDeliveryViewSet)
router.register("advice", AdviceRecommendationViewSet)
router.register("advice-content", AdviceContentViewSet)
router.register("pest-reports", PestReportViewSet)
router.register("outbreaks", OutbreakViewSet)
router.register("spray-logs", SprayLogViewSet)
router.register("market-prices", MarketPriceViewSet)
router.register("sell-listings", SellListingViewSet)
router.register("buyers", BuyerViewSet)
router.register("training-events", TrainingEventViewSet)
router.register("lessons", LessonViewSet)
router.register("lesson-progress", LessonProgressViewSet)
router.register("badges", BadgeViewSet)
router.register("officer-questions", OfficerQuestionViewSet, basename="officer-question")
router.register(
    "faqs", FrequentlyAskedQuestionViewSet, basename="frequently-asked-question"
)
router.register("waste-logs", WasteLogViewSet)
router.register("disposal-points", DisposalPointViewSet)


urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("health/", HealthView.as_view(), name="health"),
    # Africa's Talking USSD callback (no JWT - AT posts form-data)
    path("ussd/", ussd_callback, name="ussd-callback"),
    path("admin/warnings/provider/", warning_provider, name="warning-provider"),
    path("admin/warnings/preview/", warning_preview, name="warning-preview"),
    path("admin/warnings/send/", warning_send, name="warning-send"),
    path("admin/warnings/audit/", warning_audit_log, name="warning-audit"),
    path("admin/warnings/<int:batch_id>/", warning_batch, name="warning-batch"),
    path(
        "admin/warnings/<int:batch_id>/retry/",
        warning_retry,
        name="warning-retry",
    ),
    path("sms/vendel/webhook/", vendel_webhook, name="vendel-sms-webhook"),

    path("analytics/summary/", SummaryView.as_view(), name="analytics-summary"),
    path("market/price-lookup/", PublicMarketPriceLookupView.as_view(), name="market-price-lookup"),
    path("gateway/market-price/", PublicMarketPriceLookupView.as_view(), name="gateway-market-price"),
    path("pests/outbreaks/", PestOutbreakGeoJSONView.as_view(), name="pest-outbreaks-geojson"),
    path("pests/knowledge/", PestKnowledgeView.as_view(), name="pest-knowledge"),
    path("pests/identify/", PestIdentificationView.as_view(), name="pest-identify"),
    path("pests/stats/", PestPublicStatsView.as_view(), name="pest-public-stats"),
    *router.urls,
]
