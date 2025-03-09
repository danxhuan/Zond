from django.db import models


class Zone(models.Model):
    matrix_path = models.FilePathField()
    time_update = models.DateTimeField()
    interpolation = models.BooleanField()
    watercourses = models.BooleanField()
    relief = models.BooleanField()
