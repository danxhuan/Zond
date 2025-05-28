import os

from django.core.exceptions import ValidationError
from django.db import models


def validate_kml_extension(value):
    ext = os.path.splitext(value.name)[1].lower()
    if ext != '.kml':
        raise ValidationError('Поддерживаются только KML файлы')


def validate_tif_extension(value):
    ext = os.path.splitext(value.name)[1].lower()
    if ext not in ['.tif', '.tiff']:
        raise ValidationError('Поддерживаются только TIFF файлы')


class UploadSession(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    session_id = models.CharField(max_length=36, unique=True)

    def __str__(self):
        return f"Session {self.session_id}"


class KmlUpload(models.Model):
    session = models.ForeignKey(UploadSession, on_delete=models.CASCADE, related_name='kmls')

    kml_file = models.FileField(
        upload_to='raw_kml/',
        validators=[validate_kml_extension]
    )

    original_name = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        super().clean()
        validate_kml_extension(self.kml_file)

    def __str__(self):
        return f"KML: {self.original_name}"


class TifUpload(models.Model):
    session = models.ForeignKey(UploadSession, on_delete=models.CASCADE, related_name='tifs')

    tif_file = models.FileField(
        upload_to='tif_regions_for_scrapper/',
        validators=[validate_tif_extension]
    )

    original_name = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        super().clean()
        validate_tif_extension(self.tif_file)

    def __str__(self):
        return f"TIF: {self.original_name}"


class ProcessingStatus(models.Model):
    session = models.ForeignKey(UploadSession, on_delete=models.CASCADE, related_name='processing_status')
    status = models.CharField(max_length=20, default='pending')  # pending, processing, completed, error
    message = models.CharField(max_length=255, default='')
    can_download_results = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Status for {self.session.session_id}: {self.status}"


class TerrainRegion(models.Model):
    source_path = models.TextField(unique=True)
    base_tif_path = models.TextField()
    region_path = models.TextField(null=True, blank=True)
    enhanced_path = models.TextField(null=True, blank=True)
    result_path = models.TextField(null=True, blank=True)
    update_date = models.DateTimeField(null=True, blank=True)
    is_processed = models.BooleanField(default=False)
    session_id = models.CharField(max_length=64, null=True, blank=True)

    def __str__(self):
        return f"TerrainRegion: {self.source_path}"
