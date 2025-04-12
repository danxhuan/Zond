import sys
import os
sys.path.append('/'.join(os.path.abspath(__file__).split('/')[:-2]))
from kml_scrapper.scrapper import get_kml_regions
from calculations.flow import FlowCalc
from calculations.landforms import LandformCalc

# GLOBALS
dem_path = '/home/egor/dev/IT/Zond/output_SRTMGL1.tif'
tasks_path = '/home/egor/dev/kmls'
cell_size = 30


def routine(forced=True):
    global dem_path
    global tasks_path
    global cell_size
    path = get_kml_regions(tasks_path, dem_path, forced=forced)
    entries = os.listdir(path)
    successful = 0
    num = 0
    for entry in entries:
        entry_path = os.path.join(path, entry)
        if (os.path.isdir(entry_path)):
            continue
        if (os.path.isfile(entry_path)
            and entry.split('.')[-1] not in ('tif', 'tiff', 'geotiff')):
            continue
        num += 1
        print()
        print(f"Calculating for entry: {entry}")
        try:
            # Здесь предпологается интерполяция отдельного снимка
            calc = FlowCalc(entry_path, cell_size)
            calc.find_results()
            calc.save_results()
            calc = LandformCalc(entry_path, cell_size)
            calc.find_results()
            calc.save_results()
            successful += 1
        except ZeroDivisionError:
            print("Unknown error was caught while processing!")
    print("Routine is done!")
    print(f"{successful} succesful of {num} TIFF files.")


if __name__ == '__main__':
    print("Starting routine with:")
    print(f'KML files in {tasks_path}')
    print(f'GeoTIFF file {dem_path}')
    print(f'Cell size set to {cell_size}')
    print('Starting!')
    routine()
