import os
import threading
import uuid
import zipfile
from io import BytesIO

import psycopg2
from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import UploadSession, KmlUpload, TifUpload, ProcessingStatus, TerrainRegion


DB_CONFIG = {
    'dbname': 'terrain_db',
    'user': 'terrain_user',
    'password': 'terrain_password',
    'host': 'localhost',
    'port': '5432'
}


def index(request):
    if not request.session.get('upload_session_id'):
        request.session['can_download_results'] = False
    return render(request, 'mainside/index.html')


def upload(request):
    return render(request, 'mainside/index.html')


def register_files_in_database(session, tif_path=None):
    """Регистрация файлов в основной системе через Django ORM"""
    try:
        # Если tif_path не передан, ищем среди объектов TifUpload
        if tif_path is None:
            tif_upload = session.tifs.first()
            if not tif_upload:
                raise Exception("Не найден TIF файл для сессии")
            tif_path = tif_upload.tif_file.path

        session_id = session.session_id

        # Для каждого KML файла в сессии
        for kml_upload in session.kmls.all():
            kml_path = kml_upload.kml_file.path

            # Проверяем существование файлов
            if not os.path.exists(kml_path) or not os.path.exists(tif_path):
                continue

            # Регистрируем в базе через ORM
            TerrainRegion.objects.get_or_create(
                source_path=kml_path,
                defaults={
                    'base_tif_path': tif_path,
                    'is_processed': False,
                    'session_id': session_id
                }
            )
    except Exception as e:
        print(f"Ошибка при регистрации в базе: {str(e)}")
        raise


def process_files_async(session_id):
    """Асинхронная обработка файлов"""
    try:
        status = ProcessingStatus.objects.get(session__session_id=session_id)
        status.status = 'processing'
        status.message = 'Начало обработки файлов...'
        status.save()

        from scripts.results import process_pipeline
        process_pipeline(session_id)

        status.status = 'completed'
        status.message = 'Обработка завершена успешно'
        status.save()

        # Устанавливаем флаг can_download_results в базе
        session = UploadSession.objects.get(session_id=session_id)
        session.processing_status.update(can_download_results=True)
    except Exception as e:
        status.status = 'error'
        status.message = str(e)
        status.save()


@require_POST
def upload_all(request):
    try:
        request.session['can_download_results'] = False
        session = UploadSession.objects.create(session_id=str(uuid.uuid4()))

        # Создаём начальный статус обработки
        ProcessingStatus.objects.create(session=session, status='pending', message='Подготовка к обработке...')

        # Получаем и фильтруем KML-файлы
        kml_files = [
            f for f in request.FILES.getlist('kml_file')
            if os.path.splitext(f.name)[1].lower() == '.kml'
        ]

        if not kml_files:
            return JsonResponse({
                'status': 'error',
                'message': 'Не найдено ни одного KML файла'
            })

        # Сохраняем KML-файлы
        for file in kml_files:
            KmlUpload.objects.create(
                session=session,
                kml_file=file,
                original_name=file.name
            )

        # Получаем и проверяем TIF-файл
        tif_file = request.FILES.get('tif_file')
        if not tif_file:
            return JsonResponse({
                'status': 'error',
                'message': 'TIF файл не загружен'
            })

        tif_ext = os.path.splitext(tif_file.name)[1].lower()
        if tif_ext not in ['.tif', '.tiff']:
            return JsonResponse({
                'status': 'error',
                'message': 'Неверный формат TIF файла'
            })

        # Проверяем, существует ли уже TIF-файл с таким именем
        tif_upload_dir = os.path.join(settings.MEDIA_ROOT, 'tif_regions_for_scrapper')
        tif_path = os.path.join(tif_upload_dir, tif_file.name)
        tif_upload_obj = None
        tif_exists_message = None
        if os.path.exists(tif_path):
            tif_exists_message = f'Файл {tif_file.name} уже существует, будет использован существующий файл.'
            register_files_in_database(session, tif_path=tif_path)
        else:
            tif_upload_obj = TifUpload.objects.create(
                session=session,
                tif_file=tif_file,
                original_name=tif_file.name
            )
            register_files_in_database(session)

        # Запускаем асинхронную обработку
        thread = threading.Thread(target=process_files_async, args=(session.session_id,))
        thread.daemon = True
        thread.start()

        request.session['upload_session_id'] = str(session.session_id)

        return JsonResponse({
            'status': 'processing',
            'session_id': session.session_id,
            'message': 'Начало обработки файлов...',
            'tif_exists_message': tif_exists_message
        })

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        })


@csrf_exempt
def check_processing_status(request, session_id):
    """Проверка статуса обработки файлов"""
    try:
        status = ProcessingStatus.objects.get(session__session_id=session_id)
        return JsonResponse({
            'status': status.status,
            'message': status.message,
            'can_download_results': status.can_download_results
        })
    except ProcessingStatus.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Статус обработки не найден',
            'can_download_results': False
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e),
            'can_download_results': False
        })


def download_results_zip(request):
    upload_session_id = request.session.get('upload_session_id')
    if not upload_session_id:
        messages.error(request, 'Сессия загрузки не найдена.')
        return redirect('index')

    try:
        session = UploadSession.objects.get(session_id=upload_session_id)
        status = ProcessingStatus.objects.get(session=session)
        if not status.can_download_results:
            messages.error(request, 'Сначала загрузите файлы для обработки.')
            return redirect('index')
    except (UploadSession.DoesNotExist, ProcessingStatus.DoesNotExist):
        messages.error(request, 'Статус обработки не найден.')
        return redirect('index')

    # ORM вместо SQL
    result_paths = list(
        TerrainRegion.objects.filter(session_id=upload_session_id, is_processed=True)
        .exclude(result_path__isnull=True)
        .values_list('result_path', flat=True)
    )
    print('DEBUG: result_paths:', result_paths)

    files_added = []
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for result_path in result_paths:
            if os.path.exists(result_path):
                for root, dirs, files in os.walk(result_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, result_path)
                        zip_file.write(file_path, os.path.join(os.path.basename(result_path), arcname))
                        files_added.append(file_path)
    print('DEBUG: files_added:', files_added)

    zip_buffer.seek(0)
    if files_added:
        response = HttpResponse(zip_buffer, content_type='application/zip')
        response['Content-Disposition'] = 'attachment; filename="results.zip"'

        status.can_download_results = False
        status.save()
        return response
    else:
        messages.error(request, 'Нет обработанных результатов для скачивания.')
        return redirect('index')


def get_results_list(request):
    results_dir = settings.RESULTS_DIR
    regions = []
    if os.path.exists(results_dir):
        for name in os.listdir(results_dir):
            path = os.path.join(results_dir, name)
            if os.path.isdir(path) or os.path.isfile(path):
                regions.append(name)
    return JsonResponse({'regions': regions})


@csrf_exempt  # Для простоты, если используете AJAX, иначе настройте CSRF
@require_POST
def download_selected_results(request):
    import json
    selected = json.loads(request.body).get('regions', [])
    results_dir = settings.RESULTS_DIR
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for region in selected:
            region_path = os.path.join(results_dir, region)
            if os.path.exists(region_path):
                if os.path.isdir(region_path):
                    for root, dirs, files in os.walk(region_path):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, results_dir)
                            zip_file.write(file_path, arcname)
                else:
                    zip_file.write(region_path, region)
    zip_buffer.seek(0)
    response = HttpResponse(zip_buffer, content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename="selected_results.zip"'
    return response
