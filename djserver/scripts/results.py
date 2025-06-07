import sys
import time
from datetime import datetime
from pathlib import Path

# Django ORM setup
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'djserver.settings')
import django
django.setup()
from mainside.models import TerrainRegion
from django.db import connection

from .kml_scrapper.scrapper import get_kml_regions
from .ML.code.v2.to_do import interpolate_terrain
from .calculations.flow import FlowCalc
from .calculations.landforms import LandformCalc

SCRIPT_DIR = Path(__file__).parent.absolute()
sys.path.append(str(SCRIPT_DIR))  # Добавляет djserver/scripts/ в PYTHONPATH

# Конфигурация
# Получаем путь к директории, где находится скрипт
SCRIPT_DIR = Path(__file__).parent.absolute()

# Основная рабочая директория будет называться working_files и находиться рядом со скриптом
BASE_DIR = SCRIPT_DIR / 'working_files'

RAW_FILES_DIR = BASE_DIR / 'raw_kml'  # Исходные KML файлы
TIF_REGIONS_DIR = BASE_DIR / 'tif_regions_for_scrapper'  # Базовые TIF для Scrapper
REGIONS_DIR = BASE_DIR / 'regions'  # Выход Scrapper
ENHANCED_DIR = BASE_DIR / 'enhanced'  # Выход ML
RESULTS_DIR = BASE_DIR / 'results'  # Выход Calculations
MODEL_PATH = SCRIPT_DIR / 'ML' / 'code' / 'v2' / '7_model.h5'
CELL_SIZE = 30


def wait_for_db(max_retries=10, delay=5):
    """Ожидание готовности базы данных через Django ORM"""
    retries = 0
    while retries < max_retries:
        try:
            connection.ensure_connection()
            print("База данных доступна")
            return True
        except Exception:
            retries += 1
            print(f"Попытка {retries}/{max_retries}: База данных не доступна, повтор через {delay} сек...")
            time.sleep(delay)
    raise Exception("Не удалось подключиться к базе данных")


def scrapper_process(session_id):
    """Обработка KML через Scrapper с группировкой по папкам"""
    # Получаем все необработанные KML файлы только для текущей сессии через ORM
    tasks = TerrainRegion.objects.filter(region_path__isnull=True, is_processed=False, session_id=session_id)
    REGIONS_DIR.mkdir(exist_ok=True)
    # Группируем KML файлы по папкам и соответствующим TIF файлам
    folder_map = {}
    for region in tasks:
        kml_path = Path(region.source_path)
        parent_folder = kml_path.parent
        if parent_folder not in folder_map:
            folder_map[parent_folder] = {
                'tif_path': region.base_tif_path,
                'region_ids': []
            }
        folder_map[parent_folder]['region_ids'].append(region.id)
    # Обрабатываем каждую уникальную папку
    for folder, data in folder_map.items():
        tif_path = data['tif_path']
        region_ids = data['region_ids']
        try:
            result_path = get_kml_regions(
                kml_path=str(folder),
                tif_path=str(tif_path),
                forced=True
            )
            if result_path:
                created_files = list(Path(result_path).glob('*.tif'))
                for tif_file in created_files:
                    kml_name = tif_file.stem + '.kml'
                    kml_file = folder / kml_name
                    # Обновляем все подходящие записи
                    for region in TerrainRegion.objects.filter(source_path=str(kml_file), base_tif_path=str(tif_path), session_id=session_id):
                        region.region_path = str(tif_file)
                        region.save()
                print(f"Обработана папка {folder} -> {len(created_files)} файлов")
            else:
                print(f"Ошибка обработки папки {folder}")
        except Exception as e:
            print(f"Ошибка обработки папки {folder}: {str(e)}")


def ml_process(session_id):
    """Обработка через ML блок"""
    tasks = TerrainRegion.objects.filter(enhanced_path__isnull=True, region_path__isnull=False, session_id=session_id)
    ENHANCED_DIR.mkdir(exist_ok=True)
    for region in tasks:
        try:
            input_tiff = Path(region.region_path)
            if not input_tiff.exists() or input_tiff.suffix.lower() != '.tif':
                print(f"Неверный путь к TIFF: {input_tiff}")
                continue
            output_path = ENHANCED_DIR / f"{input_tiff.stem}_enhanced.tif"
            if interpolate_terrain(
                    input_path=str(input_tiff),
                    output_path=str(output_path),
                    model_path=str(MODEL_PATH)
            ):
                region.enhanced_path = str(output_path)
                region.save()
                print(f"Обработан ML {input_tiff} -> {output_path}")
            else:
                print(f"Ошибка ML обработки {input_tiff}")
        except Exception as e:
            print(f"Ошибка ML обработки {region.region_path}: {str(e)}")


def calculations_process(session_id):
    """Обработка через Calculations блок"""
    tasks = TerrainRegion.objects.filter(result_path__isnull=True, enhanced_path__isnull=False, session_id=session_id)
    RESULTS_DIR.mkdir(exist_ok=True)
    for region in tasks:
        try:
            tif_filename = Path(region.base_tif_path).stem
            filename = Path(region.enhanced_path).stem.split("_enhanced")[0]
            result_folder = RESULTS_DIR / tif_filename / filename
            result_folder.mkdir(parents=True, exist_ok=True)
            flow = FlowCalc(region.enhanced_path, CELL_SIZE, save_dir=str(result_folder))
            flow.find_results()
            flow.save_results()
            landform = LandformCalc(region.enhanced_path, CELL_SIZE, save_dir=str(result_folder))
            landform.find_results()
            landform.save_results()
            if not result_folder.exists() or not any(result_folder.iterdir()):
                print(f"Папка результатов не создана или пуста: {str(result_folder)}")
                continue
            region.result_path = str(result_folder)
            region.update_date = datetime.now()
            region.is_processed = True
            region.save()
            print(f"Обработано Calculations {region.enhanced_path} -> {str(result_folder)}")
        except Exception as e:
            print(f"Ошибка расчетов для {region.enhanced_path}: {str(e)}")


def process_pipeline(session_id):
    """Основной пайплайн обработки"""
    try:
        print("1. Ожидание БД...")
        wait_for_db()

        print("2. Обработка Scrapper...")
        scrapper_process(session_id)

        print("3. Обработка ML...")
        ml_process(session_id)

        print("4. Выполнение расчетов...")
        calculations_process(session_id)

        print("Обработка завершена успешно!")
    except Exception as e:
        print(f"Критическая ошибка: {str(e)}")
        raise


if __name__ == "__main__":
    # Создаем необходимые папки
    for folder in [RAW_FILES_DIR, TIF_REGIONS_DIR, REGIONS_DIR, ENHANCED_DIR, RESULTS_DIR]:
        print(f"Пытаюсь создать папку: {folder}")
        try:
            folder.mkdir(exist_ok=True, parents=True)
            print(f"Папка создана: {folder.exists()}")
        except Exception as e:
            print(f"Ошибка при создании папки: {e}")

    process_pipeline(session_id)
