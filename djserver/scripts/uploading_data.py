import sys
import os
from pathlib import Path
import django

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ZOND.settings")
django.setup()

from back.models import Zone
from django.utils.timezone import now

ML_APP_DIR = BASE_DIR / "ml" / "matrix"


def save_file_paths_to_db():
    if not ML_APP_DIR.exists():
        print(f"Папка {ML_APP_DIR} не существует.")
        return

    print(f"Папка с файлами: {ML_APP_DIR}")

    for file_path in ML_APP_DIR.iterdir():
        if file_path.is_file():
            zone_record, created = Zone.objects.update_or_create(
                matrix_path=str(file_path),
                defaults={
                    "time_update": now(),
                    "interpolation": False,
                    "watercourses": False,
                    "relief": False,
                },
            )
            if created:
                print(f"Добавлен путь к матрице: {file_path}")
            else:
                print(f"Обновлён путь к матрийе: {file_path}")


if __name__ == "__main__":
    save_file_paths_to_db()
