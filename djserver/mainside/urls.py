from django.urls import path

from . import views
from .views import download_results_zip, get_results_list, download_selected_results, check_processing_status

urlpatterns = [
    path('', views.index, name='index'),
    path('upload/', views.upload_all, name='upload_all'),
    path('download/results/', download_results_zip, name='download_results'),
    path('api/results-list/', get_results_list, name='results_list'),
    path('api/download-selected/', download_selected_results, name='download_selected'),
    path('api/processing-status/<str:session_id>/', check_processing_status, name='processing_status'),
]
