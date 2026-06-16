#!/usr/bin/env python3

import os
import sys

FOXROBOTLAB_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if FOXROBOTLAB_SRC not in sys.path:
    sys.path.insert(0, FOXROBOTLAB_SRC)

from client_server.cnn_model_adapter import CnnModelAdapter


def _env(name, default=''):
    return os.environ.get(name, default)


def _bool_env(name, default=True):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in ('0', 'false', 'no', 'off')


def _workspace_dir():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))


def _resolve_path(path):
    if not path:
        return ''
    if os.path.isabs(path):
        return path
    return os.path.join(_workspace_dir(), path)


def _run_cnn_smoke_test(tf):
    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(224, 224, 3)),
        tf.keras.layers.Conv2D(4, 3, activation='relu'),
        tf.keras.layers.GlobalAveragePooling2D(),
        tf.keras.layers.Dense(2, activation='softmax'),
    ])
    x = tf.random.uniform((1, 224, 224, 3))
    y = model(x, training=False)
    print(f'TensorFlow check: cnn_smoke_output_shape={tuple(y.shape)}')
    print(f'TensorFlow check: cnn_smoke_output_device={y.device}')
    print(f'TensorFlow check: cnn_smoke_output={y.numpy().tolist()}')


def _load_project_model(tf):
    model_path = _resolve_path(_env('FOX_TENSORFLOW_MODEL_PATH'))
    if not model_path:
        print('TensorFlow check: model load skipped; FOX_TENSORFLOW_MODEL_PATH is empty')
        return 0

    print(f'TensorFlow check: loading_model={model_path}')
    if not os.path.exists(model_path):
        print('TensorFlow check: model load failed; file does not exist')
        return 1

    model = tf.keras.models.load_model(model_path, compile=False)
    print(f'TensorFlow check: model_class={type(model).__name__}')
    print(f'TensorFlow check: model_input_shape={getattr(model, "input_shape", None)}')
    print(f'TensorFlow check: model_output_shape={getattr(model, "output_shape", None)}')
    print(f'TensorFlow check: model_layers={len(model.layers)}')

    if not _bool_env('FOX_TENSORFLOW_RUN_MODEL_PREDICT', True):
        return 0

    shape = model.input_shape
    if not isinstance(shape, tuple):
        print('TensorFlow check: dummy prediction skipped; model has multiple inputs')
        return 0

    dims = [1 if dim is None else dim for dim in shape]
    x = tf.zeros(dims, dtype=tf.float32)
    y = model.predict(x, verbose=0)
    print(f'TensorFlow check: dummy_prediction_shape={getattr(y, "shape", None)}')
    print(f'TensorFlow check: dummy_prediction_dtype={getattr(y, "dtype", None)}')
    return 0


def _run_adapter_check(model_path):
    import numpy as np

    adapter = CnnModelAdapter(model_path)
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    result = adapter.predict(dummy_frame)

    print('TensorFlow check: adapter_status=ok')
    print(f"TensorFlow check: adapter_model_loaded={result['model_loaded']}")
    print(f"TensorFlow check: adapter_input_shape={result['input_shape']}")
    print(f"TensorFlow check: adapter_output_shape={result['output_shape']}")
    print(f"TensorFlow check: adapter_device={result['device']}")
    print(f"TensorFlow check: adapter_latency_ms={result['latency_ms']:.2f}")
    print(
        'TensorFlow check: adapter_sequence_length='
        f"{result['sequence_length']}/{result['sequence_target_length']}"
    )
    print(f"TensorFlow check: adapter_top_cells={result['top_cells']}")
    print(f"TensorFlow check: adapter_top_scores={result['top_scores']}")
    return 0


def main():
    print('TensorFlow check: starting')
    print(f'TensorFlow check: python={sys.executable}')

    try:
        import cv2
        print(f'TensorFlow check: opencv_version={cv2.__version__}')
    except Exception as error:
        print(f'TensorFlow check: opencv import failed: {error}')
        return 1

    try:
        import tensorflow as tf
    except Exception as error:
        print(f'TensorFlow check: import failed: {error}')
        return 1

    try:
        import numpy as np
        print(f'TensorFlow check: numpy_version={np.__version__}')
    except Exception as error:
        print(f'TensorFlow check: numpy import failed: {error}')
        return 1

    gpus = tf.config.list_physical_devices('GPU')
    logical_gpus = tf.config.list_logical_devices('GPU')
    print(f'TensorFlow check: version={tf.__version__}')
    print(f'TensorFlow check: gpu_devices={gpus}')
    print(f'TensorFlow check: logical_gpu_devices={logical_gpus}')
    print(f'TensorFlow check: LD_LIBRARY_PATH set={bool(_env("LD_LIBRARY_PATH"))}')

    if gpus:
        for index, gpu in enumerate(gpus):
            details = tf.config.experimental.get_device_details(gpu)
            print(f'TensorFlow check: gpu_{index}_name={gpu.name}')
            print(f'TensorFlow check: gpu_{index}_details={details}')
        print('TensorFlow check: GPU is available')
    else:
        print('TensorFlow check: TensorFlow imported, but no GPU was detected')

    try:
        _run_cnn_smoke_test(tf)
        model_status = _load_project_model(tf)
        adapter_status = _run_adapter_check(_resolve_path(_env('FOX_TENSORFLOW_MODEL_PATH')))
    except Exception as error:
        print(f'TensorFlow check: failed: {error}')
        return 1

    if model_status != 0:
        return model_status
    if adapter_status != 0:
        return adapter_status

    print('TensorFlow check: done')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
