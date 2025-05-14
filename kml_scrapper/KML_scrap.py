from scrapper import *
import os
from pathlib import Path

from djserver.scripts.kml_scrapper.scrapper import get_kml_regions

BASE_DIR = Path(__file__).resolve().parent.parent

if __name__ == '__main__':

    kml_path = os.path.join(BASE_DIR, 'matrix_folder/kml')

    get_kml_regions('')