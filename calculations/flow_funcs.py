import numpy as np
import heapq

SQRT = np.sqrt(2)
d_row = [-1, -1, -1, 0, 1, 1, 1, 0]
d_col = [-1, 0, 1, 1, 1, 0, -1, -1]

# В алгоритмах используется и minheap, и maxheap,
# поэтому используем собственную реализацию


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
        if (left(pos) < len(self.data) and self.prior(self.data[left(pos)],
                                                      self.data[pos])):
            pr = left(pos)
        if (right(pos) < len(self.data) and self.prior(self.data[right(pos)],
                                                       self.data[pr])):
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

    def clear(self):
        while not self.is_empty():
            self.pop()


def breach_depressions_pit_cells(dem: np.ndarray, max_dist: int) -> np.ndarray:
    """LEGACY METHOD DON'T USE!"""
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
        if (not all(dem[pit_x, pit_y] <= dem[nx, ny]
                    for nx, ny in get_neighbors(pit_x, pit_y))):
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
                                  pit_elevation +
                                  (target_elevation - pit_elevation) * i
                                  / len(breach_path) * 0.00001)

    return dem


def fill_depressions(dem: np.ndarray) -> np.ndarray:
    """Depression filling algorythm (priority-flood)

    Args:
        dem (np.ndarray): original DEM

    Returns:
        np.ndarray: Filled DEM
    """
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


def get_distance(n):
    if n in [0, 2, 4, 6]:
        return 1
    else:
        return np.sqrt(2)


def breach_depressions_least_cost(dem: np.ndarray, max_dist=20,
                                  max_cost: float = np.inf,
                                  flat_increment=None) -> np.ndarray:
    """Breach DEM depressions

    Args:
        dem (np.ndarray): original DEM
        max_dist (int, optional): maximum search distance. Defaults to 20.
        max_cost (float, optional): maximum path cost. Defaults to np.inf.
        flat_increment (float, optional): how much to increment
        flat along the way. Defaults to None.

    Returns:
        np.ndarray: breached DEM
    """
    rows, cols = dem.shape
    nodata = np.nan
    minimize_dist = True

    if flat_increment is None or flat_increment == 0:
        elev_range = np.max(dem) - np.min(dem)
        small_num = 1.0 / (10 ** (9 - len(str(int(elev_range))))) * np.sqrt(2)
    else:
        small_num = flat_increment

    output = dem.copy().astype(np.float64)

    dx = [1, 1, 1, 0, -1, -1, -1, 0]
    dy = [-1, 0, 1, 1, 1, 0, -1, -1]
    diag_dist = np.sqrt(2)
    cost_dist = [diag_dist, 1, diag_dist, 1, diag_dist, 1, diag_dist, 1]
    pits = []
    for row in range(1, rows-1):
        for col in range(1, cols-1):
            z = output[row, col]
            if z == nodata:
                continue

            # проверка на яму
            is_pit = True
            min_zn = np.inf
            for n in range(8):
                zn = output[row + dy[n], col + dx[n]]
                if zn == nodata:
                    is_pit = False
                    break
                if zn < z:
                    is_pit = False
                    break
                if zn < min_zn:
                    min_zn = zn

            if is_pit:
                output[row, col] = min_zn - small_num
                pits.append((row, col, z))

    # Сортируем ямы
    pits.sort(key=lambda x: -x[2])

    # Инициализация массивов
    backlink = -np.ones((rows, cols), dtype=np.int8)
    encountered = np.zeros((rows, cols), dtype=np.int8)
    path_length = np.zeros((rows, cols), dtype=np.int16)

    # Отслеживание
    num_solved = 0
    num_unsolved = 0
    unsolved_pits = []

    # Обрабатываем каждую яму
    while pits:
        row, col, z = pits.pop()

        # Проверка, сохранилась ли яма
        is_still_pit = True
        for n in range(8):
            zn = output[row + dy[n], col + dx[n]]
            if zn < z and zn != nodata:
                is_still_pit = False
                num_solved += 1
                break

        if is_still_pit:
            # Вычисляем стоимость пути
            encountered[row, col] = 1
            heap = []
            heapq.heappush(heap, (0.0, row, col))
            scanned_cells = [(row, col)]
            found_solution = False
            # Ищем путь минимальной стоимости
            while heap and not found_solution:
                accum, r, c = heapq.heappop(heap)
                if accum > max_cost:
                    unsolved_pits.append((row, col, z))
                    num_unsolved += 1
                    break
                length = path_length[r, c]
                zn = output[r, c]
                cost1 = zn - z + length * small_num
                for n in range(8):
                    rn = r + dy[n]
                    cn = c + dx[n]
                    if (0 <= rn < rows and 0 <= cn < cols and
                       encountered[rn, cn] != 1 and output[rn, cn] != nodata):

                        scanned_cells.append((rn, cn))
                        length_n = length + 1
                        path_length[rn, cn] = length_n
                        backlink[rn, cn] = (n + 4) % 8

                        zn = output[rn, cn]
                        zout = z - (length_n * small_num)

                        if zn > zout:
                            cost2 = zn - zout
                            new_cost = (accum + (cost1 + cost2)/2
                                        * cost_dist[n]
                                        if minimize_dist else accum + cost2)

                            encountered[rn, cn] = 1
                            if length_n <= max_dist:
                                heapq.heappush(heap, (new_cost, rn, cn))
                        else:
                            # Нашли точку перелива
                            r_breach, c_breach = rn, cn
                            while True:
                                if backlink[r_breach, c_breach] > -1:
                                    b = backlink[r_breach, c_breach]
                                    r_breach += dy[b]
                                    c_breach += dx[b]
                                    zn = output[r_breach, c_breach]
                                    length = path_length[r_breach, c_breach]
                                    zout = z - (length * small_num)
                                    if zn > zout:
                                        output[r_breach, c_breach] = zout
                                else:
                                    break

                            num_solved += 1
                            found_solution = True
                            break

        # Востанавливаем начальные условия
        for r, c in scanned_cells:
            backlink[r, c] = -1
            encountered[r, c] = 0
            path_length[r, c] = 0
    return output


def calc_flow(dem: np.ndarray, cell_sz: float,
              exponent: float = 1.1) -> np.ndarray:
    """Calculate flow diractions using MFD-md

    Args:
        dem (np.ndarray): original DEM (cell values in meters)
        cell_sz (float): size of original DEM (in meters)
        exponent (float, optional): modifier. Defaults to 1.1.

    Returns:
        np.ndarray: matrix of flow in 8 directions for each cell
    """
    rows, cols = dem.shape
    flow = np.zeros((rows, cols, 8))
    slopes = np.zeros((rows, cols, 8))
    for r in range(1, rows - 1):
        for c in range(1, cols - 1):
            z0: np.float64 = dem[r, c]  # Высота тек. клетки
            total_weight: np.float64 = np.float64(0)  # Общий вес по
#                                                   направлениям для нормировки

            for d in range(8):  # Перебираем все доступные направления
                nr, nc = r + d_row[d], c + d_col[d]
                dz: np.float64 = z0 - dem[nr, nc]  # Перепад высот
#                                                    по направлению
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
    """Calculate flow accumulation along found directions

    Args:
        dem (np.ndarray): original DEM
        flow (np.ndarray): flow matrix

    Returns:
        np.ndarray: accumulation mask for DEM
    """
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
