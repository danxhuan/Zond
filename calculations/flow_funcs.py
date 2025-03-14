import numpy as np
import heapq

SQRT = np.sqrt(2)
d_row = [-1, -1, -1, 0, 1, 1, 1, 0]
d_col = [-1, 0, 1, 1, 1, 0, -1, -1]


def left(a):
    return a * 2 + 1


def right(a):
    return a * 2 + 2


def parent(a):
    return (a - 1) // 2


class Heap():
    def __init__(self, minheap=True):
        self.data = []
        self.min = minheap

    def prior(self, a: tuple, b: tuple):
        if ((a[0] <= b[0] and self.min) or (a[0] >= b[0] and not self.min)):
            return True
        return False

    def swap(self, pos1: int, pos2: int) -> None:
        self.data[pos1], self.data[pos2] = self.data[pos2], self.data[pos1]

    def insert(self, elem: tuple) -> None:
        self.data.append(elem)
        pos = len(self.data) - 1
        while (pos > 0 and self.prior(self.data[pos], self.data[parent(pos)])):
            self.swap(pos, parent(pos))
            pos = parent(pos)

    def heapify(self, pos):
        pr = pos
        if (left(pos) < len(self.data) and self.prior(self.data[left(pos)], self.data[pos])):
            pr = left(pos)
        if (right(pos) < len(self.data) and self.prior(self.data[right(pos)], self.data[pr])):
            pr = right(pos)
        if pos != pr:
            self.swap(pr, pos)
            self.heapify(pr)

    def pop(self) -> tuple:
        if (not self.data):
            return None
        item = self.data[0]
        self.data[0] = self.data[-1]
        self.data.pop()
        if (self.data):
            self.heapify(0)
        return item

    def is_empty(self):
        return len(self.data) == 0


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
        queue = Heap(True)
        queue.insert((0.0, pit_x, pit_y))
        cost[pit_x, pit_y] = 0.0

        while not queue.is_empty():
            current_cost = 0.0
            current_cost, x, y = queue.pop()
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
                    queue.insert((new_cost, nx, ny))

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
                                pit_elevation + (target_elevation - pit_elevation) * i / len(breach_path) * 0.00001)

    return dem


def Lindsay(dem_orig: np.ndarray) -> np.ndarray:
    rows, cols = dem_orig.shape
    dem = dem_orig.copy()
    NO_BACK_LINK = -1
    UNVISITED = 0
    EDGE = 1
    VISITED = 2
    backlinks = np.full((rows, cols, 2), -1, dtype=np.int16)
    visited = np.zeros_like(dem, dtype=np.uint8)
    pits = np.zeros_like(dem, dtype=bool)
    flood = []

    pq = Heap()

    for r in range(rows):
        for c in range(cols):
            if (r == 0 or r == rows - 1 or c == 0 or c == cols - 1):
                pq.insert((dem[r, c], r, c))
                visited[r, c] = EDGE
                continue

            lowest_neighbour = np.inf
            for d in range(8):
                nr, nc = r + d_row[d], c + d_col[d]
                if (0 <= nr < rows and 0 <= nc < cols):
                    lowest_neighbour = min(lowest_neighbour, dem[nr, nc])
            if dem[r, c] < lowest_neighbour:
                dem[r, c] = np.nextafter(lowest_neighbour, -np.inf)
                
            if dem[r, c] <= lowest_neighbour:
                pits[r, c] = True
    
    while not pq.is_empty():
        h, r, c = pq.pop()
        if pits[r, c]:
            cc = (r, c)
            target_height = dem[r, c]

            while (cc) != (-1, -1) and dem[cc[0], cc[1]] >= target_height:
                dem[cc[0], cc[1]] = target_height
                cc = tuple(backlinks[cc[0], cc[1], :])
                target_height = np.nextafter(target_height, -np.inf)
        
        for d in range(8):
            nr, nc = r + d_row[d], c + d_col[d]
            if (0 <= nr < rows and 0 <= nc < cols and visited[nr, nc] == UNVISITED):
                pq.insert((dem[nr, nc], nr, nc))
                visited[nr, nc] = VISITED
                backlinks[nr, nc, :] = r, c
                flood.append((nr, nc))
    
    for nr, nc in flood:
        pr, pc = backlinks[nr, nc, :]
        if (pr, pc) != (-1, -1) and dem[nr, nc] <= dem[pr, pc]:
            dem[nr, nc] = np.nextafter(dem[pr, pc], np.inf)
        
    return dem




def fill_depressions(dem: np.ndarray) -> np.ndarray:
    """Алгоритм заполнения впадин ЦМР (priority flood)"""
    rows, cols = dem.shape
    filled_dem = dem.copy()
    pq = Heap(True)
    pits: list[tuple] = []
    processed: np.ndarray = np.zeros_like(dem, dtype=bool)
    # Добавляем границы в pq
    for r in range(rows):
        for c in [0, cols - 1]:
            pq.insert((dem[r, c], r, c))
            processed[r, c] = True
    for c in range(1, cols - 2):
        for r in [0, rows - 1]:
            pq.insert((dem[r, c], r, c))
            processed[r, c] = True
    h: np.float64 = np.float64(0)
    while not pq.is_empty() or pits:
        if (pits):
            h, r, c = pits.pop(0)
        else:
            h, r, c = pq.pop()
        for i in range(8):
            nr, nc = r + d_row[i], c + d_col[i]
            if (0 <= nr < rows and 0 <= nc < cols and
                    not processed[nr, nc]):
                if (filled_dem[nr, nc] <= h):
                    filled_dem[nr, nc] = h
                    pits.append((filled_dem[nr, nc], nr, nc))
                else:
                    pq.insert((filled_dem[nr, nc], nr, nc))
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


def calc_flow_accumulation(dem: np.ndarray, flow: np.ndarray) -> np.ndarray:
    """Алгоритм вычисления накопления потока"""
    rows, cols = dem.shape
    # Изначально в каждой клетке есть единица воды
    accumulation = np.ones((rows, cols))
    pq = Heap(False)
    for r in range(rows):
        for c in range(cols):
            pq.insert((dem[r, c], r, c))

    while not pq.is_empty():
        h, r, c = pq.pop()
        s = np.float64(1)
        for d in range(8):
            nr, nc = r + d_row[d], c + d_col[d]
            if (nr < 0 or nr >= rows or nc < 0 or nc >= cols):
                continue
            if (h > dem[nr, nc]):
                continue
            s += accumulation[nr, nc] * flow[nr, nc, (d + 4) % 8]
        accumulation[r, c] += s

    return accumulation


def get_streams(accumulation: np.ndarray, quantile: float) -> np.ndarray:
    """Исключаем данные по заданному квантилю"""
    threshold = np.float64(np.quantile(accumulation, quantile))
    streams: np.ndarray = np.where(accumulation > threshold,
                                               accumulation, 0)
    return streams
