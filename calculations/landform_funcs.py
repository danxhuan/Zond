import numpy as np

FLAT_SLOPE_ANGLE_TRESHOLD = np.float64(5.0)

TERN_NEUTRAL = 0
TERN_POS = 1
TERN_NEG = 2

# GEOMORPHON CLASSES

NODATA = 0
FLAT = 1
PEAK = 2
RIDGE = 3
SHOULDER = 4
SPUR = 5
SLOPE = 6
HOLLOW = 7
FOOTSLOPE = 8
VALLEY = 9
PIT = 10

# CALCULATION TABLE FOR GEOMORPHON CLASSES

CLASSES = [
    [FLAT, FLAT, FLAT, FOOTSLOPE, FOOTSLOPE, VALLEY, VALLEY, VALLEY, PIT],
    [FLAT, FLAT, FOOTSLOPE, FOOTSLOPE, FOOTSLOPE, VALLEY, VALLEY, VALLEY,
     NODATA],
    [FLAT, SHOULDER, SLOPE, SLOPE, HOLLOW, HOLLOW, VALLEY, NODATA, NODATA],
    [SHOULDER, SHOULDER, SLOPE, SLOPE, SLOPE, HOLLOW, NODATA, NODATA, NODATA],
    [SHOULDER, SHOULDER, SPUR, SLOPE, SLOPE, NODATA, NODATA, NODATA, NODATA],
    [RIDGE, RIDGE, SPUR, SPUR, NODATA, NODATA, NODATA, NODATA, NODATA],
    [RIDGE, RIDGE, RIDGE, NODATA, NODATA, NODATA, NODATA, NODATA, NODATA],
    [RIDGE, RIDGE, NODATA, NODATA, NODATA, NODATA, NODATA, NODATA, NODATA],
    [PEAK, NODATA, NODATA, NODATA, NODATA, NODATA, NODATA, NODATA, NODATA]
]


UPPER_SLOPE = 1
MIDDLE_SLOPE = 2
LOWER_SLOPE = 3

EXPOSITION_CODES = {"N": 1, "NE": 2, "E": 3, "SE": 4,
                    "S": 5, "SW": 6, "W": 7, "NW": 8}


def get_geom_class(code: np.ndarray) -> int:
    """Get geomorphon class from 8 digits ternary code

    Args:
        code (np.ndarray): ternary code

    Returns:
        int: code of geomorphon class ()
    """
    pos = 0
    neg = 0
    pos = code[code == TERN_POS].shape[0]
    neg = code[code == TERN_NEG].shape[0]
    return CLASSES[neg][pos]


def slope_segment(geomorphon: int) -> int:
    """Classify segment of slope by it's geomorphon

    Args:
        geomorphon (int): geomorphon

    Returns:
        int: code of slope segment
    """
    if geomorphon in [PEAK, RIDGE, SHOULDER]:
        return UPPER_SLOPE
    if geomorphon in [SLOPE, SPUR, HOLLOW]:
        return MIDDLE_SLOPE
    if geomorphon in [FOOTSLOPE, VALLEY, PIT]:
        return LOWER_SLOPE
    else:
        return NODATA


def find_geomorphons(dem: np.ndarray, cell_size: int, max_dist: float,
                     max_angle: float) -> np.ndarray:
    """Find geomorphons for each DEM cell.
    Idea of geomorphons can be read from here
    https://www.researchgate.net/publication/264850233_Geomorphons_-_A_new_approach_to_classification_of_landforms

    Args:
        dem (np.ndarray): original DEM (cell values in meters)
        cell_size (int): size of DEM cell (in meters)
        max_dist (float): distance of search (in meters)
        max_angle (float): angle treshold

    Returns:
        np.ndarray: geomorphons mask
    """
    # Проверка, что в зоне поиска будет хотя бы одна ячейка
    if max_dist < cell_size:
        max_dist = float(cell_size)
    # Направления смещения при поиске
    dx = [1, 1, 1, 0, -1, -1, -1, 0]
    dy = [-1, 0, 1, 1, 1, 0, -1, -1]
    sqrt2 = np.sqrt(2)
    # Коэффициенты для диагоналей
    dd = [sqrt2, 1] * 4
    geom = np.zeros_like(dem, dtype=np.uint8)
    rows, cols = dem.shape
    # Дистанция поиска в ячейках
    offset = np.int32(np.ceil(max_dist / cell_size))
    # Для крайних точек нельзя получить корректный тернарный код
    # Игнорируем их
    for r in range(offset, rows - offset):
        for c in range(offset, cols - offset):
            code = np.zeros((8), dtype=np.uint8)
            for d in range(8):
                # Вместо просчёта углов между зенитом и надиром
                # будем считать угол между рассматриваемой точкой и горизонтом
                # и сохранять максимальный и минимальный углы
                zen_angle = -361
                nad_angle = 361
                for off in range(1, offset + 1):
                    nr, nc = r + dy[d] * off, c + dx[d] * off
                    angle = np.degrees(np.arctan2((dem[nr, nc] - dem[r, c]),
                                                  (off * cell_size * dd[d])))
                    zen_angle = max(zen_angle, angle)
                    nad_angle = min(nad_angle, angle)
                # Минимальный угол может быть отрицательным
                # (ячейка ниже текущей точки)
                if (zen_angle > -nad_angle and zen_angle > max_angle):
                    code[d] = TERN_POS
                elif (-nad_angle > zen_angle and -nad_angle > max_angle):
                    code[d] = TERN_NEG
                else:
                    code[d] = TERN_NEUTRAL
            geom[r, c] = get_geom_class(code)
    return geom


def classify_slope_segments(geom: np.ndarray) -> np.ndarray:
    """classify slope segments of DEM using geomorphons

    Args:
        geom (np.ndarray): geomorphons mask

    Returns:
        np.ndarray: slope segments mask
    """
    res = np.zeros_like(geom, dtype=np.uint8)
    rows, cols = geom.shape
    for r in range(rows):
        for c in range(cols):
            if geom[r, c] == NODATA:
                continue
            res[r, c] = slope_segment(geom[r, c])
    return res


def calculate_slope_aspect(dem: np.ndarray,
                           cell_size: int) -> tuple:
    """Calculate slope and aspect angles of DEM using
    Horn's (1981) 3rd-order finite difference method to estimate slope.
    Used formulaes and ideas from here
    https://www.researchgate.net/publication/303543730_Primary_topographic_attributes

    Args:
        dem (np.ndarray): original DEM (cell values in meters)
        cell_size (int): size of cell (in meters)

    Returns:
        tuple: tuple consists of
        slope and aspect angles masks (in degrees)
    """
    # Радиус поиска и коэффициенты для производных (8 направлений)
    dx, dy = cell_size, cell_size
    dz_dx = np.zeros_like(dem, dtype=np.float32)
    dz_dy = np.zeros_like(dem, dtype=np.float32)
    kernel_x = np.array([[-1, 0, 1],
                         [-2, 0, 2],
                         [-1, 0, 1]]) / (8 * dx)

    kernel_y = np.array([[1, 2, 1],
                         [0, 0, 0],
                         [-1, -2, -1]]) / (8 * dy)

    for r in range(1, dem.shape[0] - 1):
        for c in range(1, dem.shape[1] - 1):
            # Зона поиска
            window = dem[r - 1:r + 2, c - 1:c + 2]
            dz_dx[r, c] = np.sum(window * kernel_x)
            dz_dy[r, c] = np.sum(window * kernel_y)
    slope_magnitude = np.sqrt(dz_dx ** 2 + dz_dy ** 2)
    slope = np.degrees(np.arctan(np.sqrt(dz_dx ** 2 + dz_dy ** 2)))
    aspect = np.degrees(np.arctan2(-dz_dx, -dz_dy))
    aspect = np.where(aspect < 0, aspect + 360, aspect)
    flat_mask = slope_magnitude <= 1e-5
    aspect[flat_mask] = -1.0
    return slope, aspect


def classify_aspect(aspect_norm: np.ndarray) -> np.ndarray:
    """Classify slope aspect by 8 cardinal directions

    Args:
        aspect_norm (np.ndarray): apect mask

    Returns:
        np.ndarray: classified aspect mask
    """
    # Границы классов (смотри EXPOSITION_CODES)
    bins = [22.5, 67.5, 112.5, 157.5, 202.5, 247.5, 292.5, 337.5]

    conditions = [
        (aspect_norm <= bins[0]) | (aspect_norm > bins[-1]),
        (aspect_norm > bins[0]) & (aspect_norm <= bins[1]),
        (aspect_norm > bins[1]) & (aspect_norm <= bins[2]),
        (aspect_norm > bins[2]) & (aspect_norm <= bins[3]),
        (aspect_norm > bins[3]) & (aspect_norm <= bins[4]),
        (aspect_norm > bins[4]) & (aspect_norm <= bins[5]),
        (aspect_norm > bins[5]) & (aspect_norm <= bins[6]),
        (aspect_norm > bins[6]) & (aspect_norm <= bins[7])
    ]

    return np.select(conditions,
                     sorted(EXPOSITION_CODES.values()),
                     default=-1).astype(dtype=np.uint8)


def classify_slope(slope_degrees: np.ndarray) -> np.ndarray:
    """Classify slope by its angle

    Args:
        slope_degrees (np.ndarray): slope degrees mask

    Returns:
        np.ndarray: classified slope mask
    """
    classes = np.zeros_like(slope_degrees, dtype=np.int8)
    classes[(slope_degrees >= 0) & (slope_degrees < 1)] = 1
    classes[(slope_degrees >= 1) & (slope_degrees < 3)] = 2
    classes[(slope_degrees >= 3) & (slope_degrees < 8)] = 3
    classes[(slope_degrees >= 8) & (slope_degrees < 15)] = 4
    classes[(slope_degrees >= 15) & (slope_degrees < 35)] = 5
    classes[slope_degrees >= 35] = 6
    return classes
