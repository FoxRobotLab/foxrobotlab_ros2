import os
os.environ["TF_USE_LEGACY_KERAS"] = "1"
import tensorflow as tf

# Step A: Extract the naked weight arrays from the old architecture
legacy_model = tf.keras.models.load_model("path/to/your/old_model_tf215")
old_weights = legacy_model.get_weights()

# Step B: Turn off the legacy environment switch
del os.environ["TF_USE_LEGACY_KERAS"]
import importlib
importlib.reload(tf) # Reload to pull clean native Keras 3

# Step C: Re-build your modern structural design function block
def build_modern_model():
    # Replace old InputLayer styles with the clean standard Keras 3 style
    inputs = tf.keras.Input(shape=(your_input_dimension,)) 
    x = tf.keras.layers.Dense(64, activation='relu')(inputs)
    outputs = tf.keras.layers.Dense(10, activation='softmax')(x)
    return tf.keras.Model(inputs=inputs, outputs=outputs)

modern_model = build_modern_model()

# Step D: Align structural layout and load weights cleanly
modern_model.set_weights(old_weights)
modern_model.save("path/to/your/new_model_tf218.keras")
print("Weights extracted and mapped directly to clean modern framework.")
