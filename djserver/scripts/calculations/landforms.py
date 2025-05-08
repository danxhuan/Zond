import os
import rasterio
from rasterio.enums import ColorInterp
import numpy as np
import rasterio.features
if __name__ == '__main__':
    import calculations.landform_funcs as lnd
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
        # Получаем имя файла без расширения (например, "dem" из "dem.tif")
        input_filename = os.path.splitext(os.path.basename(self.save_path))[0]
        
        # Создаём путь к папке results (на том же уровне, что и enhanced)
        parent_dir = os.path.dirname(os.path.dirname(self.save_path))  # .../ (родитель enhanced)
        res_dir = os.path.join(parent_dir, "results")  # .../results/
        
        # Создаём уникальную подпапку (например, .../results/dem/)
        unique_res_dir = os.path.join(res_dir, input_filename)

        self.geodata.update(count=1)
        self.geodata['dtype'] = np.int8
        self.geodata['nodata'] = -1
        names = ["landforms", "slope_classified", "aspect_classified",
                 "segments", "slope_degrees", "aspect_degrees"]
        data = self.results
        if not os.path.exists(unique_res_dir):
            os.mkdir(os.path.join(unique_res_dir))

        for i in range(6):
            try:
                file = rasterio.open(os.path.join(
                    unique_res_dir,
                    names[i] + '.tif'),
                    'w', **self.geodata)
            except Exception:
                raise FileNotFoundError
            file.write(data[i], 1)
            file.colorintepr = ColorInterp.palette
            file.close()
            print(f'{names[i]}')
