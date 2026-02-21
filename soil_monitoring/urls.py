"""
URL Configuration for Soil Monitoring API
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    FieldSoilProfileViewSet,
    SensorReadingViewSet,
    RecommendationViewSet,
    NotificationViewSet,
    FieldAnalyticsViewSet,
)

# Create router
router = DefaultRouter()
router.register(r'profiles', FieldSoilProfileViewSet, basename='soil-profile')
router.register(r'readings', SensorReadingViewSet, basename='sensor-reading')
router.register(r'recommendations', RecommendationViewSet, basename='recommendation')
router.register(r'notifications', NotificationViewSet, basename='notification')
router.register(r'analytics', FieldAnalyticsViewSet, basename='analytics')

app_name = 'soil_monitoring'

urlpatterns = [
    path('', include(router.urls)),
]

"""
API Endpoints:

# Soil Profiles
GET    /api/soil/profiles/                          - List all soil profiles
POST   /api/soil/profiles/                          - Create soil profile
GET    /api/soil/profiles/{id}/                     - Get specific profile
PUT    /api/soil/profiles/{id}/                     - Update profile
PATCH  /api/soil/profiles/{id}/                     - Partial update
DELETE /api/soil/profiles/{id}/                     - Delete profile

# Sensor Readings
GET    /api/soil/readings/                          - List readings (with filters)
POST   /api/soil/readings/                          - Create reading (from IoT)
GET    /api/soil/readings/{id}/                     - Get specific reading
POST   /api/soil/readings/bulk_create/              - Bulk create readings
GET    /api/soil/readings/latest/                   - Get latest readings for all fields

# Recommendations
GET    /api/soil/recommendations/                   - List recommendations
GET    /api/soil/recommendations/{id}/              - Get specific recommendation
PUT    /api/soil/recommendations/{id}/              - Update recommendation
POST   /api/soil/recommendations/{id}/deactivate/   - Deactivate recommendation
POST   /api/soil/recommendations/deactivate_all/    - Deactivate all for field

# Notifications
GET    /api/soil/notifications/                     - List user notifications
GET    /api/soil/notifications/{id}/                - Get specific notification

# Analytics
GET    /api/soil/analytics/statistics/              - Get field statistics
GET    /api/soil/analytics/health/                  - Get field health
GET    /api/soil/analytics/dashboard/               - Get dashboard data
POST   /api/soil/analytics/analyze/                 - Run analysis for field

Query Parameters Examples:
- /api/soil/readings/?field_id=1
- /api/soil/readings/?field_id=1&start_date=2024-02-01&end_date=2024-02-20
- /api/soil/readings/?field_id=1&limit=50
- /api/soil/recommendations/?field_id=1&is_active=true&severity=HIGH
- /api/soil/analytics/statistics/?field_id=1&days=7
- /api/soil/analytics/health/?field_id=1&days=7
"""