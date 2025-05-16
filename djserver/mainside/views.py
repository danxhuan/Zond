import os
import uuid
import zipfile
from io import BytesIO

import psycopg2
from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST

from .models import UploadSession, KmlUpload, TifUpload

DB_CONFIG = {
    'dbname': 'terrain_db',
    'user': 'terrain_user',
    'password': 'terrain_password',
    'host': 'localhost',
    'port': '5432'
}


def index(request):
    return render(request, 'mainside/index.html')


def upload(request):
    return render(request, 'mainside/index.html')


@require_POST
def upload_all(request):
    try:
        # Создаем новую сессию загрузки с уникальным UUID
        session = UploadSession.objects.create(session_id=str(uuid.uuid4()))

        # Получаем и фильтруем KML файлы
        kml_files = [
            f for f in request.FILES.getlist('kml_file')
            if os.path.splitext(f.name)[1].lower() == '.kml'
        ]

        if not kml_files:
            messages.error(request, 'Не найдено ни одного KML файла')
            return redirect('index')

        # Сохраняем KML файлы
        for file in kml_files:
            KmlUpload.objects.create(
                session=session,
                kml_file=file,
                original_name=file.name
            )

        # Получаем TIF файл и проверяем
        tif_file = request.FILES.get('tif_file')
        if not tif_file:
            messages.error(request, 'TIF файл не загружен')
            return redirect('index')

        tif_ext = os.path.splitext(tif_file.name)[1].lower()
        if tif_ext not in ['.tif', '.tiff']:
            messages.error(request, 'Неверный формат TIF файла')
            return redirect('index')

        # Сохраняем TIF файл
        TifUpload.objects.create(
            session=session,
            tif_file=tif_file,
            original_name=tif_file.name
        )

        # Регистрируем файлы в основной базе (твоя функция)
        register_files_in_database(session)
        request.session['can_download_results'] = True

        messages.success(request, 'Файлы успешно загружены и зарегистрированы!')
        return redirect('index')

    except Exception as e:
        messages.error(request, f'Произошла ошибка при загрузке: {str(e)}')
        return redirect('index')

def register_files_in_database(session):
    """Регистрация файлов в основной системе"""
    try:
        tif_upload = session.tifs.first()
        if not tif_upload:
            raise Exception("Не найден TIF файл для сессии")

        tif_path = tif_upload.tif_file.path

        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                # Для каждого KML файла в сессии
                for kml_upload in session.kmls.all():
                    kml_path = kml_upload.kml_file.path

                    # Проверяем существование файлов
                    if not os.path.exists(kml_path) or not os.path.exists(tif_path):
                        continue

                    # Регистрируем в базе
                    cur.execute("""
                        INSERT INTO terrain_regions 
                        (source_path, base_tif_path, is_processed)
                        VALUES (%s, %s, FALSE)
                        ON CONFLICT (source_path) DO NOTHING;
                    """, (kml_path, tif_path))

                conn.commit()

    except Exception as e:
        print(f"Ошибка при регистрации в базе: {str(e)}")
        raise

def download_results_zip(request):
    if not request.session.get('can_download_results'):
        messages.error(request, 'Сначала загрузите файлы для обработки.')
        return redirect('index')
    results_dir = settings.RESULTS_DIR

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for root, dirs, files in os.walk(results_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, results_dir)
                zip_file.write(file_path, arcname)

    zip_buffer.seek(0)
    response = HttpResponse(zip_buffer, content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename="results.zip"'
    request.session['can_download_results'] = False
    return response
