import os
import json
import rasterio
from rasterio.enums import ColorInterp
import numpy as np
import matplotlib.pyplot as plt
import rasterio.features
if __name__ == '__main__':
    import flow_funcs as fl
else:
    from . import flow_funcs as fl

# CONST

def extract_streams(acc: np.ndarray,
                    transform: rasterio.Affine,
                    crs: rasterio.crs.CRS):
    geojson = {
        "type": "FeatureCollection",
        # "crs": {
        #    "type": "name",
        #    "properties": {
        #        "name": f"EPSG:{crs['init'].split(':')[1]}"
        #    }
        #},
        "features": []
    }
    
    treshold = max(acc.shape[0], acc.shape[1])
    streams = (acc >= 100).astype(np.uint8)

    for shape, value in rasterio.features.shapes(streams, transform=transform):
        if value == 1:
            if shape['type'] == 'Polygon':
                ins_feature = {
                            "type": "Feature",
                            "geometry": {
                                "type": "LineString",
                                "coordinates": []
                            },
                            "properties": {}
                        }
                line_coords = shape['coordinates'][0]
                enhanced = []
                for coord in line_coords:
                    col, row = ~transform * (coord[0], coord[1])
                    if 0 <= row < acc.shape[0] and 0 <= col < acc.shape[1]:
                        accumulation = acc[int(row), int(col)]
                        enhanced.append([coord[0], coord[1], accumulation])
                ins_feature['geometry']['coordinates'] = enhanced
                geojson['features'].append(ins_feature)
    
    return geojson



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
        self.transform = file.transform
        self.crs = file.crs
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
        breached = fl.breach_depressions_least_cost(dem, 100, 10,
                                                    fill_deps=False)
        flow = fl.calc_flow(breached,
                            self.cell_size)
        print("Calculating flow accumulation...")
        acc = fl.calc_flow_accumulation(breached, flow)
        geo = extract_streams(acc, self.transform, self.crs)
        self.results = (filled_dem, flow, acc, breached, geo)
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
        data = [self.results[0],
                self.results[2],
                self.results[0] - self.dem,
                self.results[3]]
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
        try:
            with open(os.path.join(res_path, "streams.json"), "w") as file:
                file.write(json.dumps(self.results[4], indent=0))
        except Exception:
            raise FileNotFoundError


# FUNC

if __name__ == '__main__':
    app = FlowCalc('/home/egor/dev/IT/Zond/calculations/0127.tif', 30)
    app.find_results()
    app.save_results()
