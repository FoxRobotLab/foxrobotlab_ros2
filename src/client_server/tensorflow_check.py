#!/usr/bin/env python3

import os
import sys


def main():
    os.environ.setdefault('TF_ENABLE_ONEDNN_OPTS', '0')
    os.environ.setdefault('TF_NUM_INTRAOP_THREADS', '1')
    os.environ.setdefault('TF_NUM_INTEROP_THREADS', '1')
    os.environ.setdefault('OMP_NUM_THREADS', '1')

    print('TensorFlow check: starting')
    print(f'TensorFlow check: python={sys.executable}')
    print(f"TensorFlow check: TF_ENABLE_ONEDNN_OPTS={os.environ.get('TF_ENABLE_ONEDNN_OPTS')}")
    print(f"TensorFlow check: TF_NUM_INTRAOP_THREADS={os.environ.get('TF_NUM_INTRAOP_THREADS')}")
    print(f"TensorFlow check: TF_NUM_INTEROP_THREADS={os.environ.get('TF_NUM_INTEROP_THREADS')}")

    try:
        import tensorflow as tf
    except Exception as error:
        print(f'TensorFlow check: import failed: {error}')
        return 1

    gpus = tf.config.list_physical_devices('GPU')
    print(f'TensorFlow check: version={tf.__version__}')
    print(f'TensorFlow check: gpu_devices={gpus}')
    print(f"TensorFlow check: LD_LIBRARY_PATH set={bool(os.environ.get('LD_LIBRARY_PATH'))}")

    if gpus:
        print('TensorFlow check: GPU is available')
    else:
        print('TensorFlow check: TensorFlow imported, but no GPU was detected')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
