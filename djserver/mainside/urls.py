from django.urls import path

from . import views
from .views import download_results_zip

urlpatterns = [
    path('', views.index, name='index'),
    path('upload/', views.upload_all, name='upload_all'),
    path('download/results/', download_results_zip, name='download_results'),
]
