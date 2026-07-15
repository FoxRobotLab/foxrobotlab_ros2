import os
import time
from collections import deque


FOXROBOTLAB_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
MATCH_SEEKER_SCRIPTS = os.path.join(FOXROBOTLAB_SRC, 'match_seeker', 'scripts')
MATCH_SEEKER_MODELS = os.path.join(FOXROBOTLAB_SRC, 'match_seeker', 'res', 'models')


def resolve_model_path(model_path):
    raw_path = str(model_path or '').strip()
    if not raw_path:
        return raw_path

    candidates = [raw_path]
    if not os.path.isabs(raw_path):
        candidates.extend([
            os.path.abspath(raw_path),
            os.path.join(FOXROBOTLAB_SRC, raw_path),
        ])

    basename = os.path.basename(raw_path)
    if basename:
        candidates.append(os.path.join(MATCH_SEEKER_MODELS, basename))

    for candidate in candidates:
        candidate = os.path.abspath(candidate)
        if os.path.exists(candidate):
            return candidate
    return os.path.abspath(raw_path)


class CnnModelAdapter:
    def __init__(
        self,
        model_path,
        sequence_length=10,
        image_size=224,
        top_k=3,
    ):
        self.model_path = resolve_model_path(model_path)
        self.sequence_length = int(sequence_length)
        self.image_size = int(image_size)
        self.top_k = int(top_k)
        self.frames = deque(maxlen=self.sequence_length)
        self.model = None
        self.model_loaded = False
        import tensorflow as tf
        self.tf = tf
        self.tensorflow_version = tf.__version__
        self.last_latency_ms = None
        self.last_device = ''

    def _device_names(self, device_type):
        return [
            device.name
            for device in self.tf.config.list_physical_devices(device_type)
        ]

    def _logical_device_names(self, device_type):
        return [
            device.name
            for device in self.tf.config.list_logical_devices(device_type)
        ]

    def load(self):
        if self.model_loaded:
            return
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(self.model_path)

        self.model = self.tf.keras.models.load_model(self.model_path, compile=False)
        self.model_loaded = True

    @property
    def input_shape(self):
        if self.model is None:
            return None
        return getattr(self.model, 'input_shape', None)

    @property
    def output_shape(self):
        if self.model is None:
            return None
        return getattr(self.model, 'output_shape', None)

    @property
    def layer_count(self):
        if self.model is None:
            return 0
        return len(self.model.layers)

    def preprocess_frame(self, frame):
        import cv2
        import numpy as np

        resized = cv2.resize(frame, (self.image_size, self.image_size))
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        return rgb.astype(np.float32) / 255.0

    def add_frame(self, frame):
        processed = self.preprocess_frame(frame)
        self.frames.append(processed)
        return processed

    def build_sequence(self, frame=None):
        import numpy as np

        if frame is not None:
            current = self.add_frame(frame)
        elif self.frames:
            current = self.frames[-1]
        else:
            current = np.zeros(
                (self.image_size, self.image_size, 3),
                dtype=np.float32,
            )

        sequence = list(self.frames)
        while len(sequence) < self.sequence_length:
            sequence.insert(0, current)

        sequence = sequence[-self.sequence_length:]
        return np.expand_dims(np.asarray(sequence, dtype=np.float32), axis=0)

    def predict(self, frame):
        import numpy as np

        self.load()
        sequence = self.build_sequence(frame)

        start = time.perf_counter()
        input_tensor = self.tf.convert_to_tensor(sequence, dtype=self.tf.float32)
        output_tensor = self.model(input_tensor, training=False)
        self.last_latency_ms = (time.perf_counter() - start) * 1000.0
        self.last_device = output_tensor.device

        output = output_tensor.numpy()
        if output.ndim != 2 or output.shape[0] != 1:
            raise ValueError(f'Expected model output shape (1, n), got {output.shape}')

        scores = output[0]
        top_count = min(self.top_k, len(scores))
        top_indices = np.argsort(scores)[-top_count:][::-1]
        top_scores = [float(scores[index] * 100.0) for index in top_indices]
        top_cells = [int(index) for index in top_indices]

        return {
            'top_cells': top_cells,
            'top_scores': top_scores,
            'latency_ms': self.last_latency_ms,
            'device': self.last_device,
            'sequence_length': len(self.frames),
            'sequence_target_length': self.sequence_length,
            'model_path': self.model_path,
            'tensorflow_version': self.tensorflow_version,
            'gpu_devices': self._device_names('GPU'),
            'logical_gpu_devices': self._logical_device_names('GPU'),
            'input_shape': self.input_shape,
            'output_shape': self.output_shape,
            'model_loaded': self.model_loaded,
        }
