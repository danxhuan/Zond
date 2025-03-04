import numpy as np
import heapq


SQRT = np.sqrt(2)
d_row = [-1, -1, -1, 0, 1, 1, 1, 0]
d_col = [-1, 0, 1, 1, 1, 0, -1, -1]


def find_depressions(dem: np.ndarray) -> tuple:
    rows, cols = dem.shape
    visited = np.zeros_like(dem, dtype=bool)
    depression_id = np.zeros_like(dem, dtype=int)
    curr_id = 1
    depressions = []

    def neighbors(x, y):
        res = []
        for d in range(8):
            nx, ny = x + d_row[d], y + d_col[d]
            if nx < 0 or nx >= rows or ny < 0 or ny >= cols:
                continue
            res.append((nx, ny))
        return res

    def mark_depression(x: int, y: int, spill_elevation: np.float64) -> tuple:
        cells = []
        stack = [(x, y)]
        min_spill = float('inf')
        spill_point = None
        while stack:
            cx, cy = stack.pop()
            if visited[cx, cy] or dem[cx, cy] > spill_elevation:
                continue
            visited[cx, cy] = True
            depression_id[cx, cy] = curr_id
            cells.append((cx, cy))
            for nx, ny in neighbors(cx, cy):
                if dem[nx, ny] > spill_elevation and dem[nx, ny] < min_spill:
                    min_spill = dem[nx, ny]
                    spill_point = (nx, ny)
                if not visited[nx, ny] and dem[nx, ny] <= spill_elevation:
                    stack.append((nx, ny))
        return cells, spill_point, min_spill

    for x in range(rows):
        for y in range(cols):
            if not visited[x, y]:
                is_pit = all((dem[x, y] <= dem[nx, ny] for nx, ny in neighbors(x, y)))
                if is_pit:
                    cells, spill_point, spill_elevation = mark_depression(x, y, dem[x, y])
                    if cells:
                        depressions.append((
                            cells,
                            spill_point,
                            spill_elevation
                        ))
                        curr_id += 1

    return depressions, depression_id


def breach_depressions_pit_cells(dem: np.ndarray, max_dist: int) -> np.ndarray:
    dem = dem.copy()  # Работаем с копией DEM
    rows, cols = dem.shape
    
    def get_neighbors(x: int, y: int) -> list:
        res = []
        for d in range(8):
            nx, ny = x + d_row[d], y + d_col[d]
            if nx < 0 or nx >= rows or ny < 0 or ny >= cols:
                continue
            res.append((nx, ny))
        return res

    pits = []
    for i in range(rows):
        for j in range(cols):
            neighbors = get_neighbors(i, j)
            if all(dem[i, j] <= dem[nx, ny] for nx, ny in neighbors):
                pits.append((i, j))

    for pit_x, pit_y in pits:
        if not all(dem[pit_x, pit_y] <= dem[nx, ny] for nx, ny in get_neighbors(pit_x, pit_y)):
            continue
        pit_elevation = dem[pit_x, pit_y]   
        cost = np.full(dem.shape, float('inf'), dtype=np.float64)
        path = np.full((rows, cols, 2), -1, dtype=np.int64)  
        queue = [(0.0, pit_x, pit_y)] 
        cost[pit_x, pit_y] = 0.0
        
        while queue:
            current_cost = 0.0
            current_cost, x, y = heapq.heappop(queue)
            if current_cost > cost[x, y]:
                continue
            
            if dem[x, y] < pit_elevation:
                break
            
            dist = abs(x - pit_x) + abs(y - pit_y)
            if dist > max_dist:
                continue
            
            for nx, ny in get_neighbors(x, y):
                height_diff = max(0.0, dem[nx, ny] - pit_elevation)
                new_cost = current_cost + (height_diff)
                
                if new_cost < cost[nx, ny]:
                    cost[nx, ny] = new_cost
                    path[nx, ny] = [np.int64(x), np.int64(y)]
                    heapq.heappush(queue, (new_cost, nx, ny))

        if dem[x, y] < pit_elevation:  
            breach_path = []
            cx, cy = x, y
            while (cx, cy) != (pit_x, pit_y):
                breach_path.append((cx, cy))
                cx, cy = map(int, path[cx, cy])
            breach_path.append((pit_x, pit_y))
            breach_path.reverse()
            
            target_elevation = dem[x, y]
            for i, (px, py) in enumerate(breach_path[1:], 1):
                dem[px, py] = min(dem[px, py], 
                                pit_elevation + (target_elevation - pit_elevation) * i / len(breach_path))
    
    return dem


def breach_depressions(orig_dem: np.ndarray,
                       max_dist: int = 1000) -> np.ndarray:

    dem = orig_dem.copy()
    rows, cols = dem.shape

    depressions, depression_id = find_depressions(dem)

    def neighbors(x, y):
        res = []
        for d in range(8):
            nx, ny = x + d_row[d], y + d_col[d]
            if nx < 0 or nx >= rows or ny < 0 or ny >= cols:
                continue
            res.append((nx, ny))
        return res
    
    for depression in depressions:
        cells, spill_point, spill_elevation = depression
        if spill_point is None:
            print(cells, depression_id[cells[0]])
            continue
        min_elevation = min(dem[x, y] for (x, y) in cells)
        boundary_cells = [(x, y) for x, y in cells
                          if any(depression_id[nx, ny] != depression_id[x, y] for nx, ny in neighbors(x, y))]
        start_cell = min(boundary_cells,
                         key=lambda p:
                         (p[0] - spill_point[0]) ** 2 + (p[1] - spill_point[1]) ** 2)
        cost = np.full((rows, cols), float('inf'))
        path = np.full((rows, cols, 2), -1, dtype=int)
        queue = [(0, start_cell[0], start_cell[1])]
        cost[start_cell] = 0
        while queue:

            current_cost, x, y = heapq.heappop(queue)
            if current_cost > cost[x, y]:
                continue

            if dem[x, y] < min_elevation:
                break

            dist = (x - start_cell[0]) ** 2 + (y - start_cell[1]) ** 2
            if dist > max_dist:
                continue
            
            for nx, ny in neighbors(x, y):
                height_diff = max(0, dem[nx, ny] - dem[start_cell])
                new_cost = current_cost + (height_diff)
                if new_cost < cost[nx, ny]:
                    cost[nx, ny] = new_cost
                    path[nx, ny] = [x, y]
                    heapq.heappush(queue, (new_cost, nx, ny))
        
        if dem[x, y] < min_elevation:
            breach_path = []
            cx, cy = x, y
            while (cx, cy) != start_cell:
                breach_path.append((cx, cy))
                cx, cy = path[cx, cy]
            breach_path.append(start_cell)
            breach_path.reverse()
            
            # Модификация DEM вдоль пути
            for i, (px, py) in enumerate(breach_path[1:], 1):
                dem[px, py] = min(dem[px, py],
                                  dem[start_cell] + (min_elevation - dem[start_cell]) * i / len(breach_path))
            
            # Корректировка депрессии для стока в канал
            for dx, dy in cells:
                if (dx, dy) not in breach_path:
                    min_dist_to_path = min(((dx - px)**2 + (dy - py)**2, px, py)
                                           for px, py in breach_path)
                    nearest_x, nearest_y = min_dist_to_path[1], min_dist_to_path[2]
                    dem[dx, dy] = max(dem[dx, dy], dem[nearest_x, nearest_y] + 0.01)  # Небольшой уклон

    # Шаг 4: Заполнение оставшихся депрессий (если fill=True)
    return dem


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
