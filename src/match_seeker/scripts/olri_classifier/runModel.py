#!/usr/bin/env python3.12
"""--------------------------------------------------------------------------------
runModel.py
Authors: Susan Fox, Bea Bautista, Shosuke Noma, Yifan Wu
Based on olin_cnn_predictor.py

This provides a couple simple classes that match_seeker can use to run the models
that have been trained. It runs both the cell prediction model and the heading prediction
model, and combines the results, providing the top three cell predictions.

Updated: 2024. Added the CNN-LSTM and CNN-Transformer models
Updated: 2026. Added VIVIT and Pretrained ViT models and Hierarchical prediction class
--------------------------------------------------------------------------------"""
import os
import numpy as np
from src.foxrobotlab_ros2.src.match_seeker.scripts.olri_classifier.paths import DATA, checkPts, textDataPath

# 2019
# from olri_classifier.cnn_cell_model_2019 import CellPredictModel2019
# from src.match_seeker.scripts.olri_classifier.cnn_heading_model_2019 import HeadingPredictModel

# CNN - RGB
# from src.match_seeker.scripts.olri_classifier.cnn_cell_model_RGBinput import CellPredictModelRGB
from src.foxrobotlab_ros2.src.match_seeker.scripts.olri_classifier.cnn_heading_model_RGBinput import HeadingPredictModelRGB

# CNN - LSTM
# from olri_classifier.cnn_lstm_cell_model_2024 import CellPredictModelLSTM
# from olri_classifier.cnn_lstm_heading_model_2024 import HeadingPredictModelLSTM

# CNN-Transformer
# from src.match_seeker.scripts.olri_classifier.cnn_transformer_cell_model_2024 import CellPredictModelCNNTransformer
# from olri_classifier.cnn_transformer_heading_model_2024 import HeadingPredictModelCNNTransformer

# ViViT model
# from src.foxrobotlab_ros2.src.VIVITransformer import CellPredictModelVIVIT

# Pretrained ViT model
os.environ["TF_USE_LEGACY_KERAS"] = "1"
from src.foxrobotlab_ros2.src.VIVITPretrained import CellPredictModelVIVIT as CellPredictModelVIVITPretrained

# Hierarchical model
from src.foxrobotlab_ros2.src.RegionPredict import RegionPredictModelVIVIT

# Comment above and uncomment below if needed
# sys.path.append('/home/macalester/PycharmProjects/catkin_ws/src/match_seeker/scripts') # handles weird import errors
# from paths import *
# from cnn_cell_model_2019 import CellPredictModel2019
# from cnn_cell_model_RGBinput import CellPredictModelRGB
# from cnn_heading_model_2019 import HeadingPredictModel
# from cnn_heading_model_RGBinput import HeadingPredictModelRGB
# from cnn_lstm_cell_model_2024 import CellPredictModelLSTM
# from cnn_lstm_heading_model_2024 import HeadingPredictModelLSTM

# uncomment to use CPU
# os.environ['CUDA_VISIBLE_DEVICES'] = ''

class ModelRunHierarchy(object):
    """
    This builds the hierarchical model pipeline, using a region predictor
    to mask out invalid cell predictions before finding the top 3 cells.
    """

    def __init__(self):
        REGION_CHECKPOINT = "2026PretrainedRegionPredict_0710261334/ViT2D_Region-10-0.09.weights.h5"
        CELL_CHECKPOINT = "2026PretrainedCellPredict_0707261308/ViT2D_Temporal-30-2.34.weights.h5"

        region_to_cell_map = {
            # 0: Green_Floor_Hallway
            0: list(range(20, 66)) + list(range(142, 166)) + list(range(221, 230)),

            # 1: Brick_Hallway
            1: list(range(230, 271)) + list(range(166, 176)),

            # 2: West_Faculty_Offices
            2: list(range(176, 221)),

            # 3: East_Faculty_Offices
            3: list(range(0, 20)),

            # 4: Smail
            4: list(range(66, 142))
        }

        self.region_to_cell_map = region_to_cell_map

        self.regionModel = RegionPredictModelVIVIT(
            check_point_folder=checkPts,
            loaded_checkpoint=REGION_CHECKPOINT
        )
        self.regionModel.buildNetwork()

        self.cellModel = CellPredictModelVIVITPretrained(
            check_point_folder=checkPts,
            loaded_checkpoint=CELL_CHECKPOINT
        )
        self.cellModel.buildNetwork()
        #
        # self.headingModel = HeadingPredictModelRGB(
        #     checkPointFolder=checkPts,
        #     loaded_checkpoint="2026HeadingPredictTransformer_checkpoint-0623261432/VIVIT-20-0.17.keras"
        # )
        # self.headingModel.buildNetwork()

    def getPrediction(self, images, mapGraph):
        potentialHeadings = [0, 45, 90, 135, 180, 225, 270, 315, 360]


        seq_len = getattr(self.cellModel, 'seqLength', 16)
        frames = images[-seq_len:]
        bestHead = "None"

        # # # --- 1. Predict Heading ---
        # lastHeading, headOutputPercs = self.headingModel.predictSingleImageBatchAllData(frames)
        # bestHead = potentialHeadings[lastHeading]

        # --- 2. Predict Region & Cell ---
        pred_region_idx, region_probs = self.regionModel.predictSingleImageBatchAllData(frames)
        raw_cell_idx, all_cell_probs = self.cellModel.predictSingleImageBatchAllData(frames)

        # --- 3. Apply the Hierarchy Mask ---
        valid_cell_indices = self.region_to_cell_map.get(pred_region_idx, [])
        masked_cell_probs = np.zeros_like(all_cell_probs)

        for idx in valid_cell_indices:
            masked_cell_probs[idx] = all_cell_probs[idx]

        bestThreePercs, bestThreeInd = self.cellModel.findTopX(3, masked_cell_probs)

        best_cells_xy = []
        for i, pred_cell in enumerate(bestThreeInd):
            pred_cell = int(pred_cell)
            if bestThreePercs[i] >= 0.00:
                predXY = mapGraph.getLocation(pred_cell)
                pred_xyh = (predXY[0], predXY[1], bestHead)
                best_cells_xy.append(pred_xyh)

        best_scores = [s * 100 for s in bestThreePercs]

        return best_scores, best_cells_xy

#
# class ModelRunVIVIT(object):
#     """This builds the VIVIT model, where only the image is an input """
#     def __init__(self):
#         VIVIT_2026_HEADING_CHECKPOINT = "2026CellPredictTransformer_checkpoint-0624260941/VIVIT-10-0.08.keras"
#         VIVIT_2026_CELL_CHECKPOINT = "2026ActualCellPredictTransformer_checkpoint-0626261616/VIVIT-50-0.10.keras"
#
#         self.cellModel = CellPredictModelVIVIT(
#             check_point_folder=checkPts,
#             # Change this as needed
#             loaded_checkpoint=VIVIT_2026_CELL_CHECKPOINT
#         )
#         self.cellModel.buildNetwork()
#
#         self.headingModel = CellPredictModelVIVIT(
#             check_point_folder=checkPts,
#             # Change this as needed
#             loaded_checkpoint=VIVIT_2026_HEADING_CHECKPOINT
#         )
#         self.headingModel.buildNetwork()
#
#
#     def getPrediction(self, images, mapGraph):
#         potentialHeadings = [0, 45, 90, 135, 180, 225, 270, 315, 360]
#
#
#         lastHeading, headOutputPercs = self.headingModel.predictSingleImageBatchAllData(images[-10:])
#         bestHead = potentialHeadings[lastHeading]
#         newCell, cellOutPercs = self.cellModel.predictSingleImageBatchAllData(images)
#         # print(f"New cell: {newCell}")
#         # print(f"Last heading: {lastHeading}")
#
#         bestThreePercs, bestThreeInd = self.cellModel.findTopX(3, cellOutPercs)
#         # print(bestThreePercs, bestThreeInd, type(bestThreeInd), bestThreeInd.shape, bestThreeInd.dtype)
#         best_cells_xy = []
#         for i, pred_cell in enumerate(bestThreeInd):
#             pred_cell = int(pred_cell)
#             if bestThreePercs[i] >= 0.00:
#                 predXY = mapGraph.getLocation(pred_cell)
#                 # print(predXY)
#                 pred_xyh = (predXY[0], predXY[1], bestHead)
#                 best_cells_xy.append(pred_xyh)
#
#         best_scores = [s * 100 for s in bestThreePercs]
#
#         return best_scores, best_cells_xy
#
#
# class ModelRunVIVITPretrained(object):
#     """This builds the Pretrained 2D ViT with average pooling model (Hugging Face Base)"""
#
#     def __init__(self):
#         # Update these
#         PRETRAINED_2026_CELL_CHECKPOINT = "2026PretrainedCellPredict_0707261308/ViT2D_Temporal-10-2.16.weights.h5"
#         PRETRAINED_2026_HEADING_CHECKPOINT = "2026ActualCellPredictTransformer_checkpoint-0626261616/VIVIT-50-0.10.keras"
#
#         self.cellModel = CellPredictModelVIVITPretrained(
#             check_point_folder=checkPts,
#             loaded_checkpoint=PRETRAINED_2026_CELL_CHECKPOINT
#         )
#         self.cellModel.buildNetwork()
#
#         self.headingModel = CellPredictModelVIVITPretrained(
#             check_point_folder=checkPts,
#             loaded_checkpoint=PRETRAINED_2026_HEADING_CHECKPOINT
#         )
#         self.headingModel.buildNetwork()
#
#     def getPrediction(self, images, mapGraph):
#         potentialHeadings = [0, 45, 90, 135, 180, 225, 270, 315, 360]
#
#         # Slices sequence to match the configured seqLength (typically 16)
#         seq_len = getattr(self.headingModel, 'seqLength', 16)
#         lastHeading, headOutputPercs = self.headingModel.predictSingleImageBatchAllData(images[-seq_len:])
#         bestHead = potentialHeadings[lastHeading]
#
#         newCell, cellOutPercs = self.cellModel.predictSingleImageBatchAllData(images[-seq_len:])
#
#         bestThreePercs, bestThreeInd = self.cellModel.findTopX(3, cellOutPercs)
#         best_cells_xy = []
#         for i, pred_cell in enumerate(bestThreeInd):
#             pred_cell = int(pred_cell)
#             if bestThreePercs[i] >= 0.00:
#                 predXY = mapGraph.getLocation(pred_cell)
#                 pred_xyh = (predXY[0], predXY[1], bestHead)
#                 best_cells_xy.append(pred_xyh)
#
#         best_scores = [s * 100 for s in bestThreePercs]
#         return best_scores, best_cells_xy
#
# class ModelRun2019(object):
#     """This builds the 2019 style of model, where the cell prediction model takes in the current heading
#     as input, and vice versa"""
#
#     def __init__(self):
#         self.cellModel =  CellPredictModel2019(
#             loaded_checkpoint =checkPts + "cell_acc9705_headingInput_155epochs_95k_NEW.hdf5",
#             testData = DATA)
#         self.headingModel = HeadingPredictModel(
#             loaded_checkpoint=checkPts + "heading_acc9517_cellInput_250epochs_95k_NEW.hdf5",
#             testData = DATA)
#
#     def getPrediction(self, image, mapGraph, odomLoc):
#         potentialHeadings = [0, 45, 90, 135, 180, 225, 270, 315, 360]
#
#         lastCell = mapGraph.convertLocToCell(odomLoc)
#
#         lastHeading, headOutputPercs = self.headingModel.predictSingleImageAllData(image, lastCell)
#         bestHead = potentialHeadings[lastHeading]
#
#         newCell, cellOutPercs = self.cellModel.predictSingleImageAllData(image, bestHead)
#         bestThreeInd, bestThreePercs = self.cellModel.findTopX(3, cellOutPercs[0])
#
#         best_cells_xy = []
#         for i, pred_cell in enumerate(bestThreeInd):
#             if bestThreePercs[i] >= 0.20:
#                 predXY = mapGraph.getLocation(pred_cell)
#                 print(pred_cell)
#                 pred_xyh = (predXY[0], predXY[1], bestHead)
#                 best_cells_xy.append(pred_xyh)
#
#         best_scores = [s * 100 for s in bestThreePercs]
#
#         # cell = mapGraph.convertLocToCell(best_cells_xy[0])
#
#         return best_scores, best_cells_xy
#
#
# class ModelRunRGB(object):
#     """This builds the 2022 RGB style of model, where the input is just the image"""
#
#     def __init__(self):
#         self.cellModel = CellPredictModelRGB(
#             checkPointFolder=checkPts,
#             # Change this as needed
#             loaded_checkpoint="2022CellPredict_checkpoint-0624221612/FullData-30-0.21.hdf5"
#         )
#         self.cellModel.buildNetwork()
#
#         self.headingModel = HeadingPredictModelRGB(
#             checkPointFolder=checkPts,
#             # Change this as needed
#             loaded_checkpoint="2022HeadingPredict_checkpoint-0627221032/FullData-30-0.24.hdf5"
#         )
#         self.headingModel.buildNetwork()
#
#
#     def getPrediction(self, image, mapGraph):
#         potentialHeadings = [0, 45, 90, 135, 180, 225, 270, 315, 360]
#
#         lastHeading, headOutputPercs = self.headingModel.predictSingleImageAllData(image)
#         bestHead = potentialHeadings[lastHeading]
#         newCell, cellOutPercs = self.cellModel.predictSingleImageAllData(image)
#         bestThreePercs, bestThreeInd = self.cellModel.findTopX(3, cellOutPercs)
#
#
#         best_cells_xy = []
#         for i, pred_cell in enumerate(bestThreeInd):
#             if bestThreePercs[i] >= 0.20:
#                 predXY = mapGraph.getLocation(pred_cell)
#                 pred_xyh = (predXY[0], predXY[1], bestHead)
#                 best_cells_xy.append(pred_xyh)
#
#         best_scores = [s * 100 for s in bestThreePercs]
#
#         # cell = mapGraph.convertLocToCell(best_cells_xy[0])
#
#         return best_scores, best_cells_xy
#
#
# class ModelRunLSTM(object):
#     """This builds the 2024 Lstm style of model"""
#     def __init__(self):
#         LSTM_2024_CELL_CHECKPOINT = "2024CellPredictLSTM_checkpoint-0802241319/CellPredAdam224-74-1.26.keras"
#         LSTM_2024_HEADING_CHECKPOINT = "2024HeadingPredict_checkpoint-0717241135/TestHeadingInCellPredAdam224Corrected-61-0.07.keras"
#
#         self.cellModel = CellPredictModelLSTM(
#             check_point_folder=checkPts,
#             # Change this as needed
#             loaded_checkpoint=LSTM_2024_CELL_CHECKPOINT
#         )
#         self.cellModel.buildNetwork()
#
#         self.headingModel = HeadingPredictModelLSTM(
#             checkpoint_folder=checkPts,
#             # Change this as needed
#             loaded_checkpoint=LSTM_2024_HEADING_CHECKPOINT
#         )
#         self.headingModel.buildNetwork()
#
#
#     def getPrediction(self, images, mapGraph):
#         potentialHeadings = [0, 45, 90, 135, 180, 225, 270, 315, 360]
#
#
#         lastHeading, headOutputPercs = self.headingModel.predictSingleImageBatchAllData(images)
#         bestHead = potentialHeadings[lastHeading]
#         newCell, cellOutPercs = self.cellModel.predictSingleImageBatchAllData(images)
#         # print(f"New cell: {newCell}")
#         # print(f"Last heading: {lastHeading}")
#
#         bestThreePercs, bestThreeInd = self.cellModel.findTopX(3, cellOutPercs)
#
#
#         best_cells_xy = []
#         for i, pred_cell in enumerate(bestThreeInd):
#             if bestThreePercs[i] >= 0.00:
#                 predXY = mapGraph.getLocation(pred_cell)
#                 pred_xyh = (predXY[0], predXY[1], bestHead)
#                 best_cells_xy.append(pred_xyh)
#
#         best_scores = [s * 100 for s in bestThreePercs]
#
#         # cell = mapGraph.convertLocToCell(best_cells_xy[0])
#
#         return best_scores, best_cells_xy

# This class is not currently in use
#
# class ModelRunCNNTransformer(object):
#     """This builds the 2024 CNN-Transformer style of model"""
#
#     def __init__(self):
#         self.cellModel = CellPredictModelCNNTransformer(
#             checkpoint_folder=checkPts,
#             annot_path=textDataPath,
#             # Change this as needed
#             # loaded_checkpoint="cnn_transformer.weights.h5"
#         )
#         self.cellModel.buildNetwork()
#
#         self.headingModel = HeadingPredictModelCNNTransformer(
#             checkpoint_folder=checkPts,
#             # Change this as needed
#             loaded_checkpoint="2024HeadingPredict_checkpoint-0717241135/TestHeadingInCellPredAdam224Corrected-61-0.07.keras"
#         )
#         self.headingModel.buildNetwork()

    # TODO: Implement the getPrediction method
    # def getPrediction(self, images, mapGraph):
    #     potentialHeadings = [0, 45, 90, 135, 180, 225, 270, 315, 360]
    #
    #
    #     lastHeading, headOutputPercs = self.headingModel.predictSingleImageBatchAllData(images)
    #     bestHead = potentialHeadings[lastHeading]
    #     newCell, cellOutPercs = self.cellModel.predictSingleImageBatchAllData(images)
    #     # print(f"New cell: {newCell}")
    #     # print(f"Last heading: {lastHeading}")
    #
    #     bestThreePercs, bestThreeInd = self.cellModel.findTopX(3, cellOutPercs)
    #
    #
    #     best_cells_xy = []
    #     for i, pred_cell in enumerate(bestThreeInd):
    #         if bestThreePercs[i] >= 0.00:
    #             predXY = mapGraph.getLocation(pred_cell)
    #             pred_xyh = (predXY[0], predXY[1], bestHead)
    #             best_cells_xy.append(pred_xyh)
    #
    #     best_scores = [s * 100 for s in bestThreePercs]
    #
    #     # cell = mapGraph.convertLocToCell(best_cells_xy[0])
    #
    #     return best_scores, best_cells_xy


if __name__ == "__main__":
    # modelRunner2019 = ModelRun2019()
    # modelRunner2022 = ModelRunRGB()
    # modelRunner2024 = ModelRunLSTM()
    # modelRunnerCNNTransformer = ModelRunCNNTransformer()
    modelRunner2026 = ModelRunHierarchy()

