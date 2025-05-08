import os
import json
import rasterio
from rasterio.enums import ColorInterp
import numpy as np
import rasterio.features
if __name__ == '__main__':
    import calculations.flow_funcs as fl
else:
    from . import flow_funcs as fl


def extract_streams(acc: np.ndarray,
                    transform: rasterio.Affine) -> dict:
    """Extract cells with most flow accumulation (0.85 quantile)

    Args:
        acc (np.ndarray): flow accumulation matrix
        transform (rasterio.Affine): transform from original DEM

    Returns:
        dict: geojson of selected features
    """
    geojson = {
        "type": "FeatureCollection",
        "features": []
    }

    threshold = np.float64(np.quantile(acc, 0.85))
    streams = (acc > threshold).astype(np.uint8)

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
            print("Can't load input file!")
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
        """Perform calculations of breached DEM,
        flow accumulation and depressions"""
        dem = self.dem
        print("Starting calculation...")
        print("Filling depressions...")
        filled_dem = fl.fill_depressions(dem)
        print("Calculating flow...")
        breached = fl.breach_depressions_least_cost(dem, 100, 20)
        flow = fl.calc_flow(breached,
                            self.cell_size)
        print("Calculating flow accumulation...")
        acc = fl.calc_flow_accumulation(breached, flow)
        geo = extract_streams(acc, self.transform)
        self.results = (filled_dem, flow, acc, breached, geo)
        print("Calculations are finished!")

    def save_results(self):
        """Save results of flow calculations"""
        # Получаем имя файла без расширения (например, "dem" из "dem.tif")
        input_filename = os.path.splitext(os.path.basename(self.save_path))[0]
        
        # Создаём путь к папке results (на том же уровне, что и enhanced)
        parent_dir = os.path.dirname(os.path.dirname(self.save_path))  # .../ (родитель enhanced)
        res_dir = os.path.join(parent_dir, "results")  # .../results/
        
        # Создаём уникальную подпапку (например, .../results/dem/)
        unique_res_dir = os.path.join(res_dir, input_filename)

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
        if not os.path.exists(unique_res_dir):
            os.mkdir(os.path.join(unique_res_dir))
        for i in range(4):
            self.geodata['dtype'] = types[i]
            try:
                file = rasterio.open(os.path.join(
                    unique_res_dir,
                    names[i] + '.tif'),
                    'w', **self.geodata)
            except Exception:
                raise FileNotFoundError
            file.colorinterp = colormaps[i]
            file.write(data[i], 1)
            file.close()
            print(f'{descs[i]}: {names[i]}')
        try:
            with open(os.path.join(unique_res_dir, "streams.json"), "w") as file:
                file.write(json.dumps(self.results[4], indent=0))
        except Exception:
            raise FileNotFoundError
