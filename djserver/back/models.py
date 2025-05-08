from django.db import models

# Здесь тоже поменять

class Region(models.Model):
    Matrix = models.CharField(max_length=255)
    Date_of_update = models.DateField()
    Processed = models.BooleanField()