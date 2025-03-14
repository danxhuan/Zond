import os
import rasterio
from rasterio.enums import ColorInterp
import numpy as np
import matplotlib.pyplot as plt
if __name__ == '__main__':
    import flow_funcs as fl
else:
    from . import flow_funcs as fl

# CONST


class FlowCalc:
    def __init__(self, input_file: str, cell_size: int):
        self.save_path = input_file
        self.cell_size = cell_size
        print("Starting flow calculation initialization!")
        try:
            file = rasterio.open(input_file, 'r')
        except Exception:
            print("Не могу загрузить входной файл!")
            raise FileNotFoundError
        self.dem = file.read(1, out_dtype=np.float64)
        print("Data read.")
        self.geodata = file.meta
        self.geodata['dtype'] = 'float64'
        print("Metadata read.")
        self.results = None
        file.close()

    def find_results(self):
        dem = self.dem
        print("Starting calculation...")
        print("Filling depressions...")
        filled_dem = fl.fill_depressions(dem)
        print("Calculating flow...")
        breached = fl.Lindsay(dem)
        flow = fl.calc_flow(breached,
                            self.cell_size)
        print("Calculating flow accumulation...")
        acc = fl.calc_flow_accumulation(breached, flow)
        self.results = (filled_dem, flow, acc, breached)
        print("Calculations are finished!")

    def visualise_result(self):
        if self.results is None:
            print("Nothing to visualise")
        fig, axes = plt.subplots(2, 2, figsize=(10, 10))
        im1 = axes[0, 0].imshow(self.dem, cmap='gray')
        fig.colorbar(im1, ax=axes[0, 0])
        axes[0, 0].set_title(f'Исходная карта (Разрешение: {self.cell_size} метров)')

        im2 = axes[0, 1].imshow(self.results[0], cmap='gray')
        fig.colorbar(im2, ax=axes[0, 1])
        axes[0, 1].set_title('Карта с заполненными впадинами')

        im3 = axes[1, 0].imshow(fl.get_streams(self.results[2], 0.9), cmap='Blues')
        fig.colorbar(im3, ax=axes[1, 0])
        axes[1, 0].set_title('Накопление потока (в условных единицах)')

        im4 = axes[1, 1].imshow(self.results[0] - self.dem, cmap='Blues')
        fig.colorbar(im4, ax=axes[1, 1])
        axes[1, 1].set_title('Заполненные впадины')
        plt.tight_layout()
        plt.show()

    def save_results(self):
        path = os.path.split(self.save_path)
        orig_name = path[1].split('.')[0]
        res_path = os.path.join(path[0], orig_name + '_result')
        self.geodata.update(count=1)
        names = ["filled", "accum", "depressions", "breached"]
        descs = ["DEM with filled depressions", "Flow accumulation",
                 "Filled depressions", "Breached DEM"]
        data = [self.results[0], self.results[2], self.results[0] - self.dem, self.results[3]]
        types = ["float64", "float64", "int16", "float64"]
        colormaps = [[ColorInterp.gray],
                     [ColorInterp.blue],
                     [ColorInterp.blue],
                     [ColorInterp.gray]]
        if not os.path.exists(res_path):
            os.mkdir(os.path.join(res_path))
        for i in range(4):
            self.geodata['dtype'] = types[i]
            try:
                file = rasterio.open(os.path.join(
                    res_path,
                    names[i] + '.tif'),
                    'w', **self.geodata)
            except Exception:
                raise FileNotFoundError
            file.colorinterp = colormaps[i]
            file.write(data[i], 1)
            file.close()
            print(f'{descs[i]}: {names[i]}')
    



# FUNC

if __name__ == '__main__':
    app = FlowCalc('/home/egor/dev/IT/Zond/calculations/0127.tif', 30)
    app.find_results()
    app.save_results()
