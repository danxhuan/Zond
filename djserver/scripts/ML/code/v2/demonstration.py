import os
import numpy as np
import tensorflow as tf
import rasterio
from rasterio.plot import show
import matplotlib.pyplot as plt
from scipy import ndimage
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

            # Сохранение
            with rasterio.open(output_path, 'w', **profile) as dst:
                dst.write(output.astype(np.float32), 1)

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


def classic_interpolation(input_path, output_path, scale_factor=6):
    """Классическая бикубическая интерполяция"""
    try:
        with rasterio.open(input_path) as src:
            data = src.read(1, masked=True).astype(np.float32)
            profile = src.profile.copy()
            transform = src.transform

            # Интерполяция
            interp_data = ndimage.zoom(data, scale_factor, order=3, mode='reflect')

            # Обновление метаданных
            new_transform = rasterio.Affine(
                transform.a / scale_factor,
                transform.b,
                transform.c,
                transform.d,
                transform.e / scale_factor,
                transform.f
            )
            profile.update({
                'driver': 'GTiff',
                'height': interp_data.shape[0],
                'width': interp_data.shape[1],
                'transform': new_transform,
                'dtype': 'float32',
                'nodata': NODATA,
                'compress': 'lzw'
            })

            # Сохранение
            with rasterio.open(output_path, 'w', **profile) as dst:
                dst.write(np.where(np.isnan(interp_data), NODATA, interp_data), 1)

            return True
    except Exception as e:
        print(f"Ошибка классической интерполяции: {str(e)}")
        return False


def visualize_comparison(orig_path, nn_path, classic_path=None):
    """Визуализация с сравнением методов интерполяции"""
    fig = plt.figure(figsize=(20, 12))

    # Создаем сетку 2x3
    grid = plt.GridSpec(2, 3, hspace=0.3, wspace=0.2)

    with rasterio.open(orig_path) as src:
        orig = src.read(1, masked=True)
        vmin, vmax = np.nanpercentile(orig, [2, 98])
        res_orig = src.res[0]

    # Исходный DEM
    ax1 = fig.add_subplot(grid[0, 0])
    show(orig, ax=ax1, cmap='terrain', vmin=vmin, vmax=vmax)
    ax1.set_title(f'Исходный DEM\nРазрешение: {res_orig} м')

    # Нейросетевая интерполяция
    ax2 = fig.add_subplot(grid[0, 1], sharex=ax1, sharey=ax1)
    with rasterio.open(nn_path) as src:
        nn_data = src.read(1, masked=True)
        show(nn_data, ax=ax2, cmap='terrain', vmin=vmin, vmax=vmax)
        ax2.set_title(f'Нейросетевая интерполяция\nРазрешение: {src.res[0]:.1f} м')

    # Классическая интерполяция
    ax3 = fig.add_subplot(grid[0, 2], sharex=ax1, sharey=ax1)
    if classic_path and os.path.exists(classic_path):
        with rasterio.open(classic_path) as src:
            classic_data = src.read(1, masked=True)
            show(classic_data, ax=ax3, cmap='terrain', vmin=vmin, vmax=vmax)
            ax3.set_title(f'Бикубическая интерполяция\nРазрешение: {src.res[0]:.1f} м')
    else:
        ax3.axis('off')
        ax3.text(0.5, 0.5, 'Нет данных', ha='center', va='center')

    # Разница нейросеть - оригинал
    ax4 = fig.add_subplot(grid[1, 0])
    diff_nn = orig - nn_data[::SCALE_FACTOR, ::SCALE_FACTOR]
    im4 = show(diff_nn, ax=ax4, cmap='coolwarm', vmin=-2, vmax=2)
    plt.colorbar(im4.get_images()[0], ax=ax4, orientation='horizontal')
    ax4.set_title('Разница: Исходный - Нейросеть')

    # Разница классика - оригинал
    ax5 = fig.add_subplot(grid[1, 1])
    if classic_path and os.path.exists(classic_path):
        diff_classic = orig - classic_data[::SCALE_FACTOR, ::SCALE_FACTOR]
        im5 = show(diff_classic, ax=ax5, cmap='coolwarm', vmin=-2, vmax=2)
        plt.colorbar(im5.get_images()[0], ax=ax5, orientation='horizontal')
        ax5.set_title('Разница: Исходный - Бикубическая')
    else:
        ax5.axis('off')

    # Разница нейросеть - классика
    ax6 = fig.add_subplot(grid[1, 2])
    if classic_path and os.path.exists(classic_path):
        diff_methods = nn_data - classic_data
        im6 = show(diff_methods, ax=ax6, cmap='coolwarm', vmin=-2, vmax=2)
        plt.colorbar(im6.get_images()[0], ax=ax6, orientation='horizontal')
        ax6.set_title('Разница: Нейросеть - Бикубическая')
    else:
        ax6.axis('off')

    # Статистика
    stats = []
    stats.append(f"Нейросеть:\nMAE: {np.nanmean(np.abs(diff_nn)):.2f} м\nMax: {np.nanmax(diff_nn):.2f} м")
    if classic_path:
        stats.append(
            f"Бикубическая:\nMAE: {np.nanmean(np.abs(diff_classic)):.2f} м\nMax: {np.nanmax(diff_classic):.2f} м")
        stats.append(f"Методы:\nMAE: {np.nanmean(np.abs(diff_methods)):.2f} м\nMax: {np.nanmax(diff_methods):.2f} м")

    plt.figtext(0.5, 0.05, "\n".join(stats), ha='center', va='bottom')
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    input_tif = "2207.tif"
    nn_output = "2207_5.tif"
    classic_output = "2207_classic.tif"

    # Запуск интерполяций
    if interpolate_terrain(input_tif, nn_output, "3_model.h5"):
        # Выполнение классической интерполяции
        classic_interpolation(input_tif, classic_output, SCALE_FACTOR)

        # Визуализация всех результатов
        visualize_comparison(input_tif, nn_output, classic_output)