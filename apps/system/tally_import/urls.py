"""
URL Configuration for Tally Import API
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TallyImportViewSet, TallyFieldMappingViewSet

router = DefaultRouter()
router.register(r'tally-import', TallyImportViewSet, basename='tally-import')
router.register(r'tally-field-mappings', TallyFieldMappingViewSet, basename='tally-field-mappings')

urlpatterns = [
    path('', include(router.urls)),
]
