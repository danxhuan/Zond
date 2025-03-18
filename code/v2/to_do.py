import glob
import os
import numpy as np
import tensorflow as tf
import rasterio
from rasterio.plot import show
import matplotlib.pyplot as plt
from tqdm import tqdm
from scipy.ndimage import median_filter

# Конфигурация
PATCH_SIZE = 64
SCALE_FACTOR = 6
NODATA = -9999


def robust_normalization(data):
    """Робастная нормализация с защитой от выбросов"""
    valid_data = data[~np.isnan(data)]
    q01, q99 = np.quantile(valid_data, [0.01, 0.99])
    mean = np.mean(valid_data[(valid_data >= q01) & (valid_data <= q99)])
    std = np.std(valid_data[(valid_data >= q01) & (valid_data <= q99)])
    return (data - mean) / (std + 1e-7), mean, std


def interpolate_terrain(input_path, output_path, model_path):
    """Интерполяция DEM с сохранением полного диапазона высот"""
    try:
        # Загрузка модели
        model = tf.keras.models.load_model(model_path, compile=False)

        with rasterio.open(input_path) as src:
            data = src.read(1, masked=True).astype(np.float32)
            profile = src.profile.copy()
            transform = src.transform

            # Сохраняем дополнительные метаданные
            tags = src.tags()
            band_description = src.descriptions[0] if src.descriptions else None
            scale = src.scales[0] if src.scales else None
            offset = src.offsets[0] if src.offsets else None

            # Обработка NODATA
            data = np.ma.filled(data, np.nan)

            # Робастная нормализация
            data_norm, global_mean, global_std = robust_normalization(data)
            data_norm = np.where(np.isnan(data_norm), 0, data_norm)

            # Подготовка патчей
            height, width = data_norm.shape
            pad_y = (PATCH_SIZE - height % PATCH_SIZE) % PATCH_SIZE
            pad_x = (PATCH_SIZE - width % PATCH_SIZE) % PATCH_SIZE

            padded_data = np.pad(data_norm, ((0, pad_y), (0, pad_x)), mode='edge')
            patches = [
                padded_data[y:y + PATCH_SIZE, x:x + PATCH_SIZE][..., np.newaxis]
                for y in range(0, padded_data.shape[0], PATCH_SIZE)
                for x in range(0, padded_data.shape[1], PATCH_SIZE)
            ]

            # Прогнозирование
            hr_patches = []
            for patch in tqdm(patches, desc="Обработка патчей"):
                pred = model.predict(patch[np.newaxis, ...], verbose=0)[0, ..., 0]
                hr_patches.append(pred)

            # Сборка выходного изображения
            hr_height = padded_data.shape[0] * SCALE_FACTOR
            hr_width = padded_data.shape[1] * SCALE_FACTOR
            output = np.zeros((hr_height, hr_width), dtype=np.float32)

            patch_idx = 0
            for y in range(0, padded_data.shape[0], PATCH_SIZE):
                for x in range(0, padded_data.shape[1], PATCH_SIZE):
                    y_start = y * SCALE_FACTOR
                    x_start = x * SCALE_FACTOR
                    output[y_start:y_start + PATCH_SIZE * SCALE_FACTOR,
                    x_start:x_start + PATCH_SIZE * SCALE_FACTOR] = hr_patches[patch_idx]
                    patch_idx += 1

            # Обрезка и денормализация
            output = output[:height * SCALE_FACTOR, :width * SCALE_FACTOR]
            output = output * global_std + global_mean

            # Постобработка
            output = median_filter(output, size=3)
            output = np.where(np.isnan(output), NODATA, output)

            # Обновление метаданных
            new_transform = rasterio.Affine(
                transform.a / SCALE_FACTOR,
                transform.b,
                transform.c,
                transform.d,
                transform.e / SCALE_FACTOR,
                transform.f
            )
            profile.update({
                'driver': 'GTiff',
                'height': output.shape[0],
                'width': output.shape[1],
                'transform': new_transform,
                'dtype': 'float32',
                'nodata': NODATA,
                'compress': 'lzw'
            })

            # Сохранение с восстановлением метаданных
            with rasterio.open(output_path, 'w', **profile) as dst:
                dst.write(output.astype(np.float32), 1)
                dst.update_tags(**tags)
                if band_description:
                    dst.set_band_description(1, band_description)
                if scale is not None:
                    dst.scales = [scale]
                if offset is not None:
                    dst.offsets = [offset]

            print(f"Успешно сохранено в {output_path}")
            return True

    except Exception as e:
        print(f"Ошибка: {str(e)}")
        return False

def visualize_comparison(orig_path, result_path):
    """Визуализация результатов с общей шкалой"""
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))

    with rasterio.open(orig_path) as src:
        orig = src.read(1, masked=True)
        vmin, vmax = np.nanpercentile(orig, [2, 98])
        show(orig, ax=axes[0], cmap='terrain', vmin=vmin, vmax=vmax)
        axes[0].set_title(f'Исходный DEM\n({src.res[0]} м)')

    with rasterio.open(result_path) as src:
        result = src.read(1, masked=True)
        show(result, ax=axes[1], cmap='terrain', vmin=vmin, vmax=vmax)
        axes[1].set_title(f'Интерполированный DEM\n({src.res[0]:.1f} м)')

    # Разница с учетом масштаба
    diff = orig - result[::SCALE_FACTOR, ::SCALE_FACTOR]
    show(diff, ax=axes[2], cmap='coolwarm', vmin=-1, vmax=1)
    axes[2].set_title('Разница (исходный - интерполированный)')

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    directory = r'C:\Users\vova\PycharmProjects\PythonProject7\to_do\regions'

    # Поиск всех файлов с расширением .tif или .tiff
    tif_files = glob.glob(os.path.join(directory, '*.tif'))

    for file in tif_files:
        # Запуск интерполяции
        if interpolate_terrain(file, file.split(".")[0] + "_5" + file.split(".")[1], "7_model.h5"):
            # Визуализация результатов
            print("OK")
            visualize_comparison(file, file.split(".")[0] + "_5" + file.split(".")[1])
