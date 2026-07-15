

import tensorflow as tf
import keras

print("Starting...")

print(tf.config.list_physical_devices('GPU'))

new_model = keras.models.load_model('../res/models/newCellPredAdam224-74-1.26.keras', compile=False)

new_model.compile(optimizer="adam", loss="categorical_crossentropy", metrics=['accuracy'])

print("Done")
