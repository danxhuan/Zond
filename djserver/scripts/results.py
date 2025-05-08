import os
import psycopg2
from datetime import datetime
from pathlib import Path
import time
from kml_scrapper.scrapper import get_kml_regions
from calculations.flow import FlowCalc
from calculations.landforms import LandformCalc
from ML.code.v2.to_do import interpolate_terrain

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

# Настройки PostgreSQL
DB_CONFIG = {
    'dbname': 'terrain_db',
    'user': 'terrain_user',
    'password': 'terrain_password',
    'host': 'localhost',
    'port': '5432'
}

def wait_for_db(max_retries=10, delay=5):
    """Ожидание готовности базы данных"""
    retries = 0
    while retries < max_retries:
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            conn.close()
            print("База данных доступна")
            return True
        except psycopg2.OperationalError:
            retries += 1
            print(f"Попытка {retries}/{max_retries}: База данных не доступна, повтор через {delay} сек...")
            time.sleep(delay)
    raise Exception("Не удалось подключиться к базе данных")

def init_database():
    """Создание таблицы если не существует"""
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS terrain_regions (
                    id SERIAL PRIMARY KEY,
                    source_path TEXT NOT NULL UNIQUE, -- Исходный KML
                    base_tif_path TEXT NOT NULL,      -- Базовый TIF для региона
                    region_path TEXT,                 -- Выход Scrapper
                    enhanced_path TEXT,               -- Выход ML
                    result_path TEXT,                 -- Выход Calculations
                    update_date TIMESTAMP,
                    is_processed BOOLEAN DEFAULT FALSE
                );
            """)
            conn.commit()
            print("Таблица 'terrain_regions' создана или уже существует")
    except Exception as e:
        print(f"Ошибка при создании таблицы: {str(e)}")
        raise
    finally:
        if conn:
            conn.close()

def register_kml_files():
    """Регистрация KML файлов в БД"""
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor() as cur:
            # Получаем список базовых TIF файлов
            base_tifs = list(TIF_REGIONS_DIR.glob('*.tif'))
            if not base_tifs:
                raise Exception("Не найдены базовые TIF файлы в папке tif_regions_for_scrapper")
            
            # Регистрируем каждый KML с соответствующим TIF
            for kml_file in RAW_FILES_DIR.glob('*.kml'):
                # Находим подходящий TIF (можно улучшить логику сопоставления)
                # Тут 100% нужно как-нибудь оптимизировать. Мб отдельную папку добавлять для каждого
                # tif файла или еще что-нибудь
                base_tif = base_tifs[0]  # Упрощение - берем первый подходящий
                
                cur.execute("""
                    INSERT INTO terrain_regions (source_path, base_tif_path, is_processed)
                    VALUES (%s, %s, FALSE)
                    ON CONFLICT (source_path) DO NOTHING
                    RETURNING id;
                """, (str(kml_file), str(base_tif)))
                
                if cur.rowcount > 0:
                    file_id = cur.fetchone()[0]
                    print(f"Зарегистрирован KML: {kml_file} с TIF: {base_tif} (ID: {file_id})")
                
            conn.commit()
    except Exception as e:
        print(f"Ошибка регистрации KML: {str(e)}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

def scrapper_process():
    """Обработка KML через Scrapper с группировкой по папкам"""
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor() as cur:
            # Получаем все необработанные KML файлы
            cur.execute("""
                SELECT id, source_path, base_tif_path FROM terrain_regions 
                WHERE region_path IS NULL AND is_processed = FALSE;
            """)
            tasks = cur.fetchall()

            REGIONS_DIR.mkdir(exist_ok=True)
            
            # Группируем KML файлы по папкам и соответствующим TIF файлам
            folder_map = {}
            for file_id, kml_path, tif_path in tasks:
                kml_path = Path(kml_path)
                parent_folder = kml_path.parent
                if parent_folder not in folder_map:
                    folder_map[parent_folder] = {
                        'tif_path': tif_path,
                        'file_ids': []
                    }
                folder_map[parent_folder]['file_ids'].append(file_id)

            # Обрабатываем каждую уникальную папку
            for folder, data in folder_map.items():
                tif_path = data['tif_path']
                file_ids = data['file_ids']
                
                try:
                    # Вызываем скраппер для всей папки
                    result_path = get_kml_regions(
                        kml_path=str(folder),
                        tif_path=str(tif_path),
                        forced=True
                    )
                    
                    if result_path:
                        # Находим все созданные .tif файлы в result_path
                        created_files = list(Path(result_path).glob('*.tif'))
                        
                        # Сопоставляем созданные файлы с исходными KML
                        for tif_file in created_files:
                            # Ищем соответствующий KML файл
                            kml_name = tif_file.stem + '.kml'
                            kml_file = folder / kml_name
                            
                            # Находим ID записи для этого KML
                            cur.execute("""
                                SELECT id FROM terrain_regions
                                WHERE source_path = %s AND base_tif_path = %s
                            """, (str(kml_file), str(tif_path)))
                            matching_ids = [row[0] for row in cur.fetchall()]
                            
                            # Обновляем все подходящие записи
                            for file_id in matching_ids:
                                cur.execute("""
                                    UPDATE terrain_regions 
                                    SET region_path = %s
                                    WHERE id = %s;
                                """, (str(tif_file), file_id))
                        
                        conn.commit()
                        print(f"Обработана папка {folder} -> {len(created_files)} файлов")
                    else:
                        print(f"Ошибка обработки папки {folder}")
                        conn.rollback()
                        
                except Exception as e:
                    print(f"Ошибка обработки папки {folder}: {str(e)}")
                    conn.rollback()
                    
    except Exception as e:
        print(f"Ошибка в процессе Scrapper: {str(e)}")
        raise
    finally:
        if conn:
            conn.close()

def ml_process():
    """Обработка через ML блок"""
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor() as cur:
            # Получаем файлы для обработки ML
            cur.execute("""
                SELECT id, region_path FROM terrain_regions 
                WHERE enhanced_path IS NULL AND region_path IS NOT NULL;
            """)
            tasks = cur.fetchall()

            # Создаем выходную папку
            ENHANCED_DIR.mkdir(exist_ok=True)
            
            for file_id, region_path in tasks:
                try:
                    input_tiff = Path(region_path)
                    
                    # Проверяем, что файл существует и это .tif
                    if not input_tiff.exists() or input_tiff.suffix.lower() != '.tif':
                        print(f"Неверный путь к TIFF: {input_tiff}")
                        continue

                    # Генерируем путь для выходного файла
                    output_path = ENHANCED_DIR / f"{input_tiff.stem}_enhanced.tif"
                    
                    # Обрабатываем через ML
                    if interpolate_terrain(
                        input_path=str(input_tiff),
                        output_path=str(output_path),
                        model_path=str(MODEL_PATH)
                    ):
                        # Обновляем БД
                        cur.execute("""
                            UPDATE terrain_regions 
                            SET enhanced_path = %s 
                            WHERE id = %s;
                        """, (str(output_path), file_id))
                        conn.commit()
                        print(f"Обработан ML {input_tiff} -> {output_path}")
                    else:
                        print(f"Ошибка ML обработки {input_tiff}")
                        conn.rollback()
                        
                except Exception as e:
                    print(f"Ошибка ML обработки {region_path}: {str(e)}")
                    conn.rollback()
    except Exception as e:
        print(f"Ошибка в процессе ML: {str(e)}")
        raise
    finally:
        if conn:
            conn.close()

def calculations_process():
    """Обработка через Calculations блок"""
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor() as cur:
            # Получаем файлы для расчетов
            cur.execute("""
                SELECT id, enhanced_path FROM terrain_regions 
                WHERE result_path IS NULL AND enhanced_path IS NOT NULL;
            """)
            tasks = cur.fetchall()
            
            # Создаем выходную папку
            RESULTS_DIR.mkdir(exist_ok=True)

            for file_id, enhanced_tiff in tasks:
                try:
                    # Получаем имя файла без расширения
                    filename = Path(enhanced_tiff).stem
                    
                    # Выполняем расчеты водотоков
                    flow = FlowCalc(enhanced_tiff, CELL_SIZE)
                    flow.find_results()
                    flow.save_results()
                    
                    # Выполняем расчеты форм рельефа
                    landform = LandformCalc(enhanced_tiff, CELL_SIZE)
                    landform.find_results()
                    landform.save_results()
                    
                    # Формируем путь к папке с результатами
                    result_folder = RESULTS_DIR / filename

                    # Проверяем что папка с результатами создана и не пуста
                    if not result_folder.exists():
                        print(f"Папка результатов не создана: {str(result_folder)}")
                        continue
                    if not any(result_folder.iterdir()):
                        print(f"Папка результатов пуста: {str(result_folder)}")
                        continue
                    
                    # Обновляем БД
                    cur.execute("""
                        UPDATE terrain_regions 
                        SET result_path = %s,
                            update_date = %s,
                            is_processed = TRUE
                        WHERE id = %s;
                    """, (str(result_folder), datetime.now(), file_id))
                    conn.commit()
                    print(f"Обработано Calculations {enhanced_tiff} -> {str(result_folder)}")
                    
                except Exception as e:
                    print(f"Ошибка расчетов для {enhanced_tiff}: {str(e)}")
                    conn.rollback()
    except Exception as e:
        print(f"Ошибка в процессе Calculations: {str(e)}")
        raise
    finally:
        if conn:
            conn.close()

def process_pipeline():
    """Основной пайплайн обработки"""
    try:
        print("1. Ожидание БД...")
        wait_for_db()
        
        print("2. Инициализация БД...")
        init_database()
        
        print("3. Регистрация KML файлов...")
        register_kml_files()
        
        print("4. Обработка Scrapper...")
        scrapper_process()
        
        print("5. Обработка ML...")
        ml_process()
        
        print("6. Выполнение расчетов...")
        calculations_process()
        
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
    
    process_pipeline()