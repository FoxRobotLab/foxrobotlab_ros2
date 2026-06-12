#!/usr/bin/env python3

import os
import sys


def main():
    print('TensorFlow check: starting')
    print(f'TensorFlow check: python={sys.executable}')

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
