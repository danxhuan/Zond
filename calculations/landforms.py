import os
import json
import rasterio
from rasterio.enums import ColorInterp
import numpy as np
import rasterio.features
if __name__ == '__main__':
    import landform_funcs as lnd
else:
    from . import landform_funcs as lnd


class LandformCalc():
    """Class that performs landform calculations"""
    def __init__(self, input_file: str, cell_size: int):
        self.save_path = input_file
        self.cell_size = cell_size
        print("Starting landform calculation initialization!")
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

    def find_results(self) -> None:
        """Perform calculations of geomorphons, aspect and slope"""
        print("Calculating geomorphons...")
        geom = lnd.find_geomorphons(self.dem, self.cell_size, 50, 1)
        print("Finding slope and aspect...")
        slope, aspect = lnd.calculate_slope_aspect(self.dem, self.cell_size)
        print("Classifying results...")
        self.results = [geom, lnd.classify_slope(slope),
                        lnd.classify_aspect(aspect),
                        lnd.classify_slope_segments(geom),
                        slope,
                        aspect]

    def save_results(self):
        "Save results of landform calculations"
        path = os.path.split(self.save_path)
        orig_name = path[1].split('.')[0]
        res_path = os.path.join(path[0], orig_name + '_result')
        self.geodata.update(count=1)
        self.geodata['dtype'] = np.int8
        self.geodata['nodata'] = -1
        names = ["landforms", "slope_classified", "aspect_classified",
                 "segments", "slope_degrees", "aspect_degrees"]
        data = self.results
        if not os.path.exists(res_path):
            os.mkdir(os.path.join(res_path))

        for i in range(6):
            try:
                file = rasterio.open(os.path.join(
                    res_path,
                    names[i] + '.tif'),
                    'w', **self.geodata)
            except Exception:
                raise FileNotFoundError
            file.write(data[i], 1)
            file.colorintepr = ColorInterp.palette
            file.close()
            print(f'{names[i]}')


if __name__ == '__main__':
    app = LandformCalc('/home/egor/dev/IT/Zond/calculations/0127.tif', 30)
    app.find_results()
    app.save_results()
