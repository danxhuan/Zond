import os
import time
import rasterio
import numpy as np
import tensorflow as tf
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from tensorflow.keras.utils import Sequence
from tensorflow.keras.callbacks import ModelCheckpoint, EarlyStopping, CSVLogger

# Конфигурация
BLOCK_SIZE = 4096
PATCH_SIZE = 64
SCALE_FACTOR = 6
BATCH_SIZE = 4
EPOCHS = 20
MIN_SAMPLES = 100
NODATA = -9999
VIZ_INTERVAL = 3
LEARNING_RATE = 1e-5  # Увеличена скорость обучения

class TileDataGenerator(Sequence):
    def __init__(self, file_path, blocks, batch_size=BATCH_SIZE, shuffle=True):
        super().__init__()
        self.file_path = file_path
        self.blocks = blocks.copy()
        self.batch_size = batch_size
        self.shuffle = shuffle
        self.current_epoch = 0
        self.skipped_blocks = 0
        self.on_epoch_end()

    def __len__(self):
        return len(self.blocks) // self.batch_size

    def __getitem__(self, index):
        X, y = [], []
        for _ in range(self.batch_size):
            lr, hr = self._get_valid_pair()
            if lr is not None and hr is not None:
                X.append(lr)
                y.append(hr)
        return np.array(X), np.array(y)

    def _get_valid_pair(self):
        while len(self.blocks) > 0:
            block_idx = np.random.choice(len(self.blocks))
            y_start, x_start, h, w = self.blocks[block_idx]

            try:
                with rasterio.open(self.file_path) as src:
                    data = src.read(
                        1,
                        window=((y_start, y_start + h), (x_start, x_start + w)),
                        masked=True
                    ).astype(np.float32)

                data = np.ma.filled(data, np.nan)

                if self._is_invalid_data(data):
                    self._remove_block(block_idx)
                    continue

                lr = data[::60, ::60]
                hr = data[::10, ::10]

                if not self._validate_shapes(lr, hr):
                    self._remove_block(block_idx)
                    continue

                lr_patch, hr_patch = self._create_patches(lr, hr)
                lr_norm = self._normalize(lr_patch)
                hr_norm = self._normalize(hr_patch)

                if np.isnan(lr_norm).any() or np.isnan(hr_norm).any():
                    raise ValueError("Обнаружены NaN после нормализации")
                print(f"Блок {block_idx} обработан успешно ")
                return lr_norm[..., np.newaxis], hr_norm[..., np.newaxis]

            except Exception as e:
                self._remove_block(block_idx)
                print(f"Ошибка в блоке {block_idx}: {str(e)}")

        return None, None

    def _is_invalid_data(self, data):
        if np.all(np.isnan(data)):
            return True
        if np.nanstd(data) < 1e-4:
            return True
        return False

    def _validate_shapes(self, lr, hr):
        return (lr.shape[0] >= PATCH_SIZE and
                lr.shape[1] >= PATCH_SIZE and
                hr.shape[0] >= PATCH_SIZE * SCALE_FACTOR and
                hr.shape[1] >= PATCH_SIZE * SCALE_FACTOR)

    def _create_patches(self, lr, hr):
        h_start = np.random.randint(0, lr.shape[0] - PATCH_SIZE)
        w_start = np.random.randint(0, lr.shape[1] - PATCH_SIZE)
        return (
            lr[h_start:h_start + PATCH_SIZE, w_start:w_start + PATCH_SIZE],
            hr[h_start * SCALE_FACTOR:(h_start + PATCH_SIZE) * SCALE_FACTOR,
            w_start * SCALE_FACTOR:(w_start + PATCH_SIZE) * SCALE_FACTOR]
        )

    def _normalize(self, data):
        valid_data = data[~np.isnan(data)]
        if valid_data.size == 0:
            return np.zeros_like(data)
        mean = np.mean(valid_data)
        std = np.std(valid_data)
        if std == 0:
            std = 1e-7  # Избегаем деления на ноль
        normalized = (data - mean) / std
        normalized[np.isnan(normalized)] = 0  # Замена NaN на 0
        return normalized

    def _remove_block(self, block_idx):
        del self.blocks[block_idx]
        self.skipped_blocks += 1

    def on_epoch_end(self):
        self.current_epoch += 1
        if self.shuffle:
            np.random.shuffle(self.blocks)
        print(f"Пропущено блоков: {self.skipped_blocks}")
        self.skipped_blocks = 0

class TrainingMonitor(tf.keras.callbacks.Callback):
    def __init__(self, train_gen, val_gen):
        super().__init__()
        self.train_gen = train_gen
        self.val_gen = val_gen
        self.start_time = None
        self.batch_times = []

    def on_train_begin(self, logs=None):
        self.start_time = time.time()
        print("Начало обучения")

    def on_train_batch_end(self, batch, logs=None):
        batch_time = time.time() - self.start_time
        self.batch_times.append(batch_time)
        avg_time = np.mean(self.batch_times[-10:]) if self.batch_times else 0
        eta = avg_time * (EPOCHS * len(self.train_gen) - batch) if avg_time else 0

        print(f"\rBatch {batch} | Loss: {logs['loss']:.4f} | MAE: {logs['mae']:.4f} | "
              f"Скорость: {1 / avg_time:.1f} batches/s | ETA: {eta // 3600:.0f}h {eta % 3600 // 60:.0f}m")

    def on_epoch_end(self, epoch, logs=None):
        if (epoch + 1) % VIZ_INTERVAL == 0:
            self.visualize_prediction()

    def visualize_prediction(self):
        idx = np.random.choice(len(self.val_gen))
        lr, hr_true = self.val_gen[idx]
        hr_pred = self.model.predict(lr, verbose=0)

        plt.figure(figsize=(15, 5))
        plt.subplot(131), plt.imshow(lr[0, ..., 0], cmap='terrain'), plt.title('LR Input')
        plt.subplot(132), plt.imshow(hr_true[0, ..., 0], cmap='terrain'), plt.title('HR True')
        plt.subplot(133), plt.imshow(hr_pred[0, ..., 0], cmap='terrain'), plt.title('Prediction')
        plt.suptitle(f"Пример интерполяции (эпоха {self.model.current_epoch})")
        plt.tight_layout()
        plt.show(block=False)
        plt.pause(5)
        plt.close()

def prepare_blocks(file_path):
    blocks = []

    with rasterio.open(file_path) as src:
        height, width = src.shape
        block_size = (min(BLOCK_SIZE, height // 2, width // 2) // 60) * 60

        for y in range(0, height - block_size, block_size // 2):
            for x in range(0, width - block_size, block_size // 2):
                try:
                    data = src.read(1, window=((y, y + block_size), (x, x + block_size)), masked=True)
                    if np.ma.count(data) > 0.1 * data.size:
                        blocks.append((y, x, block_size, block_size))
                except:
                    continue

    if len(blocks) < MIN_SAMPLES:
        raise ValueError(f"Недостаточно блоков: {len(blocks)} < {MIN_SAMPLES}")
    return blocks

def build_model():
    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(PATCH_SIZE, PATCH_SIZE, 1)),
        tf.keras.layers.UpSampling2D(SCALE_FACTOR, interpolation='bilinear'),
        tf.keras.layers.Conv2D(32, 3, activation='relu', padding='same',
                               kernel_initializer='he_normal'),
        tf.keras.layers.BatchNormalization(),
        tf.keras.layers.Conv2D(16, 3, activation='relu', padding='same'),
        tf.keras.layers.Conv2D(1, 3, padding='same')
    ])
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=LEARNING_RATE),
        loss='mse',
        metrics=['mae']
    )
    return model

def train_model(file_path):
    blocks = prepare_blocks(file_path)
    train_blocks, val_blocks = train_test_split(blocks, test_size=0.2, random_state=42)

    train_gen = TileDataGenerator(file_path, train_blocks)
    val_gen = TileDataGenerator(file_path, val_blocks, shuffle=False)

    model = build_model()
    model.summary()

    callbacks = [
        TrainingMonitor(train_gen, val_gen),
        ModelCheckpoint('0_model.h5', save_best_only=True),
        EarlyStopping(patience=5, restore_best_weights=True),
        CSVLogger('training_log.csv'),
        tf.keras.callbacks.TerminateOnNaN()
    ]

    history = model.fit(
        train_gen,
        validation_data=val_gen,
        epochs=EPOCHS,
        callbacks=callbacks,
        verbose=0
    )

    model.save("terrain_interpolator.h5")
    return model

if __name__ == "__main__":
    tf.keras.utils.disable_interactive_logging()
    tf.get_logger().setLevel('ERROR')
    np.random.seed(42)

    TIFF_FILE =  r"C:\Users\vova\Desktop\data\MDS_sampa-ZSTD.tif"

    if not os.path.isfile(TIFF_FILE):
        raise FileNotFoundError(f"Файл {TIFF_FILE} не найден")

    model = train_model(TIFF_FILE)
