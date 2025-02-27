import numpy as np
import heapq


SQRT = np.sqrt(2)
d_row = [-1, -1, -1, 0, 1, 1, 1, 0]
d_col = [-1, 0, 1, 1, 1, 0, -1, -1]


def fill_depressions(dem: np.ndarray) -> np.ndarray:
    """Алгоритм заполнения впадин ЦМР (priority flood)"""
    rows, cols = dem.shape
    filled_dem: np.ndarray = dem.copy()
    pq: list[tuple] = []  # бинарная куча aka очередь с приоритетом
    processed: np.ndarray = np.zeros_like(dem, dtype=bool)
    # Добавляем границы в pq
    for r in range(rows):
        for c in [0, cols - 1]:
            heapq.heappush(pq, (dem[r, c], r, c))
            processed[r, c] = True
    for c in range(1, cols - 2):
        for r in [0, rows - 1]:
            heapq.heappush(pq, (dem[r, c], r, c))
            processed[r, c] = True
    h: np.float64 = np.float64(0)
    while pq:  # Пока куча не пуста
        # Достаём с вершины кучи элемент с наивысшим приоритетом (мин. высотой)
        h, r, c = heapq.heappop(pq)
        for i in range(8):
            nr, nc = r + d_row[i], c + d_col[i]
            if (0 <= nr < rows and 0 <= nc < cols and
                    not processed[nr, nc]):
                filled_dem[nr, nc] = max(dem[nr, nc], h) 
                heapq.heappush(pq, (filled_dem[nr, nc], nr, nc))
                processed[nr, nc] = True
    return filled_dem


def calc_flow(dem: np.ndarray, cell_sz: float,
              exponent: float = 1.1) -> np.ndarray:
    """Вычисление направлений потока алгоритмом MFD-md"""
    rows, cols = dem.shape
    flow = np.zeros((rows, cols, 8))
    slopes = np.zeros((rows, cols, 8))
    for r in range(1, rows - 1):
        for c in range(1, cols - 1):
            z0: np.float64 = dem[r, c]  # Высота тек. клетки
            total_weight: np.float64 = np.float64(0)  # Общий вес по направлениям для нормировки
            for d in range(8):  # Перебираем все доступные направления
                nr, nc = r + d_row[d], c + d_col[d]
                dz: np.float64 = z0 - dem[nr, nc]  # Перепад высот по направлению
                if dz > 0:  # Условие потока в заданном направлении
                    distance = cell_sz if d % 2 == 1 else cell_sz * SQRT
                    slopes[r, c, d] = np.float64(np.power(dz / distance,
                                                          exponent))
                    total_weight += np.float64(slopes[r, c, d])
                if total_weight:
                    # Нормировка
                    flow[r, c, :] = slopes[r, c, :] / total_weight
    return flow


def calc_flow_accumulation(flow: np.ndarray) -> np.ndarray:
    """Алгоритм вычисления накопления потока"""
    rows, cols, _ = flow.shape
    # Изначально в каждой клетке есть единица воды
    accumulation = np.ones((rows, cols))
    for r in range(1, rows - 1):
        for c in range(1, cols - 1):
            for d in range(8):
                nr, nc = r + d_row[d], c + d_col[d]
                if 0 <= nr < rows and 0 <= nc < cols:
                    accumulation[nr, nc] += accumulation[r, c] * flow[r, c, d]
    return accumulation


def get_streams(accumulation: np.ndarray, quantile: float) -> np.ndarray:
    """Исключаем данные по заданному квантилю"""
    threshold = np.float64(np.quantile(accumulation, quantile))
    streams: np.ndarray = np.where(accumulation > threshold,
                                               accumulation, 0)
    return streams
