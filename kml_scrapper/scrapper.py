import os
import numpy as np
import rasterio
import rasterio.errors
import rasterio.windows


def scrape_from_file(path: str) -> list:
    ''' Достаёт список координат точек из файла'''
    try:
        file = open(path, 'r')
    except OSError:
        print(f"Can't open file on path: {path}!")
        return []
    text = file.read()
    subs = "coordinates"
    pos1, pos2 = text.find(subs) + 1 + len(subs), text.find('/' + subs) - 1
    text = text[pos1:pos2]
    res = [list(map(np.float64, i.split(','))) for i in text.split('\n')]
    file.close()
    return res


def get_box(ls: list) -> list:
    ''' Формирует список крайних координат, в которые вписана область'''
    if len(ls) == 0:
        return []
    x1 = ls[0][0]
    x2 = ls[0][0]
    y1 = ls[0][1]
    y2 = ls[0][1]
    for point in ls:
        if point[0] < x1:
            x1 = point[0]
        if point[0] > x2:
            x2 = point[0]
        if point[1] < y1:
            y1 = point[1]
        if point[1] > y2:
            y2 = point[1]
    return [x1, y1, x2, y2]


def get_kml_regions(kml_path: str, tif_path: str, forced=True) -> None:
    ''' Получение областей из исходной ЦМР по файлам kml'''
    # проверка путей
    if not os.path.isdir(kml_path) or not os.path.isfile(tif_path):
        raise OSError
    # выходная директория 
    res_path = os.path.join(os.path.split(tif_path)[0], 'regions/')

    if (not os.path.exists(res_path)):
        os.mkdir(res_path)

    contents = os.listdir(kml_path)  # список файлов kml

    try:
        file = rasterio.open(tif_path)
    except rasterio.errors.RasterioIOError:
        print("Can't open original file!")
        return None

    # перебираем файлы
    for entry in contents:
        name = os.path.join(kml_path, entry)  # полное имя файла
        res_name = os.path.join(
                    res_path, entry.split('.')[0] + '.tif')
        if (not forced and os.path.isfile(res_name)):
            print("File already exists!")
        if os.path.isfile(name) and entry.split('.')[-1] == 'kml':
            print(f"Found entry: {entry}")
            # получаем границы региона
            points = get_box(scrape_from_file(name))  
            if (len(points) == 0):
                continue
            bounds = file.bounds  # получаем границы файла

            # проверка на пренадлежность региону
            if ((points[0] < bounds[0] or points[1] < bounds[1])
                or (points[2] > bounds[2] or points[3] > bounds[3])):
                print("Desired region out of bounds! Abort!")
                continue

            # формируем выходную область
            rows1, cols1 = file.index(points[0], points[1])
            rows2, cols2 = file.index(points[2], points[3])
            rows_max, rows_min = max(rows1, rows2), min(rows1, rows2)
            cols_max, cols_min = max(cols1, cols2), min(cols1, cols2)
            rows_dist, cols_dist = rows_max - rows_min, cols_max - cols_min
            window = rasterio.windows.Window.from_slices(
                (max(rows_min - rows_dist, 0),
                 min(rows_max + rows_dist, file.shape[0] - 1)),
                (max(cols_min - cols_dist, 0),
                 min(cols_max + cols_dist, file.shape[1] - 1))
            )
            img = file.read(1, window=window)
            mt = file.meta.copy()
            mt.update(
                {
                    'height': window.height,
                    'width': window.width,
                    'transform': rasterio.windows.transform(window,
                                                            file.transform)
                }
            )
            try:
                newfile = rasterio.open(res_name, 'w', **mt)
            except rasterio.errors.RasterioIOError:
                print("Can't save this file!")
                continue
            newfile.write(img, 1)
            newfile.close()
            print("File processed!")
    file.close()


if __name__ == "__main__":
    print("Импортируй этот скрипт как модуль и вызови get_kml_regions!")
