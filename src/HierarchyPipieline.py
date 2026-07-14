import numpy as np

from VIVITPretrained import CellPredictModelVIVIT
# from VIVITRegionPretrained import RegionPredictModelVIVIT


class MaskedVIVITPipeline:
  def __init__(self, region_runner, cell_runner, region_to_cell_map):
    """
    Takes instantiated and loaded ViViT model runners and links them.
    """
    self.region_runner = region_runner
    self.cell_runner = cell_runner
    self.region_to_cell_map = region_to_cell_map

  def locate_robot(self, frame_sequence):
    """
    Takes a sequence of raw images (e.g., 16 frames from the robot's camera),
    runs them through both models, applies the mask, and returns the final localization.
    """

    pred_region_idx, region_probs = self.region_runner.predictSingleImageBatchAllData(frame_sequence)

    raw_cell_idx, all_cell_probs = self.cell_runner.predictSingleImageBatchAllData(frame_sequence)

    valid_cell_indices = self.region_to_cell_map[pred_region_idx]
    masked_cell_probs = np.zeros_like(all_cell_probs)

    for idx in valid_cell_indices:
      masked_cell_probs[idx] = all_cell_probs[idx]

    final_cell_idx = np.argmax(masked_cell_probs)
    final_confidence = masked_cell_probs[final_cell_idx]

    return pred_region_idx, final_cell_idx, final_confidence


if __name__ == "__main__":
  print("Initializing Hierarchical ViViT Localization...")

  # 1. Define your mapping (Region Index -> List of Cell Indices)
  # Example: Region 0 has cells 0-50, Region 1 has 51-100, etc.
  REGION_TO_CELL_MAPPING = {
    0: list(range(0, 51)),
    1: list(range(51, 101)),
    2: list(range(101, 271))
  }

  # 2. Instantiate the Region Model Runner
  # Make sure output_size matches your number of regions
  region_model = RegionPredictModelVIVIT(
    loaded_checkpoint="path_to_region_weights.h5",
    output_size=3,  # Example: 3 Regions
    data_name="ViT2D_Region"
  )
  region_model.buildNetwork()

  # 3. Instantiate the Global Cell Model Runner
  # Output size is 271 based on your generator
  cell_model = CellPredictModelVIVIT(
    loaded_checkpoint="2026PretrainedCellPredict_0707261308/ViT2D_Temporal-10-3.09.weights.h5",
    output_size=271,
    data_name="ViT2D_Cell"
  )
  cell_model.buildNetwork()

  # 4. Create the Pipeline
  robot_locator = MaskedVIVITPipeline(
    region_runner=region_model,
    cell_runner=cell_model,
    region_to_cell_map=REGION_TO_CELL_MAPPING
  )

  print("Pipeline Ready. Waiting for camera feed...")

  # 5. Process a live sequence (Simulated here)
  # This should be a list/array of 16 raw cv2 images coming from your robot
  import cv2

  dummy_sequence = [np.zeros((480, 640, 3), dtype=np.uint8) for _ in range(16)]

  # Run localization
  predicted_region, predicted_cell, confidence = robot_locator.locate_robot(dummy_sequence)

  print("-" * 30)
  print("LOCALIZATION RESULTS")
  print("-" * 30)
  print(f"Predicted Region Index : {predicted_region}")
  print(f"Predicted Cell Index   : {predicted_cell}")
  print(f"Cell Confidence        : {confidence * 100:.2f}%")