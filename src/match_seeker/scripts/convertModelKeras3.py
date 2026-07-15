import os
import json
import zipfile
import shutil

checkptPath = "/media/macalester/Data/PycharmProjects/catkin_ws/src/match_seeker/res/classifier2022Data/DATA/CHECKPOINTS/"
OLD_MODEL_PATH = checkptPath + "2024CellPredictLSTM_checkpoint-0802241319/CellPredAdam224-74-1.26.keras"
NEW_MODEL_PATH = 'newCellPredAdam224-74-1.26.keras'

# 1. Clean up legacy configuration keys
os.environ["TF_USE_LEGACY_KERAS"] = "1"
import tensorflow as tf

print("Forcing clean structure extraction...")
# Load using the legacy bridge engine
legacy_model = tf.keras.models.load_model(OLD_MODEL_PATH)

# Save to a staging path
staging_path = "staging_model.keras"
legacy_model.save(staging_path)

# 2. Extract and precisely repair the JSON structure
print("Parsing and cleaning layer arguments precisely...")
temp_dir = "extracted_keras_model"
with zipfile.ZipFile(staging_path, 'r') as zip_ref:
    zip_ref.extractall(temp_dir)

config_json_path = os.path.join(temp_dir, "config.json")

if os.path.exists(config_json_path):
    with open(config_json_path, 'r') as f:
        config_data = json.load(f)

    # Function to recursively scrub problematic keys out of nested layers
    def scrub_layer_configs(layer_list):
        for layer in layer_list:
            # Check the actual config parameters of this layer
            if "config" in layer:
                cfg = layer["config"]

                # A. Handle LSTM / Recurrent legacy properties
                if layer.get("class_name") in ["LSTM", "GRU", "SimpleRNN"]:
                    cfg.pop("time_major", None)  # Clean the Keras 3 syntax break
                
                # 1. If it's a TimeDistributed or wrapper layer, strip batch indicators completely
                if layer.get("class_name") in ["TimeDistributed", "Bidirectional"]:
                    cfg.pop("batch_input_shape", None)
                    cfg.pop("batch_shape", None)
                    
                    # Also clean the inner layer wrapped inside it
                    if "layer" in cfg:
                        inner = cfg["layer"]
                        if "config" in inner:
                            inner["config"].pop("batch_input_shape", None)
                            inner["config"].pop("batch_shape", None)
                            if inner.get("class_name") in ["LSTM", "GRU"]:
                                inner["config"].pop("time_major", None)
                
                # 2. For any normal layer, update the key layout to Keras 3 standards
                else:
                    if "batch_input_shape" in cfg:
                        cfg["batch_shape"] = cfg.pop("batch_input_shape")
            
           # Recurse if the layer has internal sub-layers (Functional APIs)
            if "config" in layer and "layers" in layer["config"]:
                scrub_layer_configs(layer["config"]["layers"])

    # Traverse sequential or functional layout blocks
    if "config" in config_data:
        root_cfg = config_data["config"]
        if "layers" in root_cfg:
            scrub_layer_configs(root_cfg["layers"])
            
    # Save the polished JSON configuration
    with open(config_json_path, 'w') as f:
        json.dump(config_data, f, indent=2)


# 3. Package back into clean Keras 3 file
shutil.make_archive("final_output", 'zip', temp_dir)
os.rename("final_output.zip", NEW_MODEL_PATH)

# Clean temporary footprints
shutil.rmtree(temp_dir)
os.remove(staging_path)

print(f"Successfully patched! New model saved cleanly at: {NEW_MODEL_PATH}")
