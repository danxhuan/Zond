from django import forms
from .models import KmlUpload, TifUpload
import zipfile
from pathlib import Path

class KmlUploadForm(forms.ModelForm):
    class Meta:
        model = KmlUpload
        fields = ['kml_file']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['kml_file'].widget.attrs.update({
            'webkitdirectory': True,
            'directory': True,
            'accept': '.kml'
        })

class TifUploadForm(forms.ModelForm):
    class Meta:
        model = TifUpload
        fields = ['tif_file']