"""--------------------------------------------------------------------------------
VIVITPretrained.py

Created: July 2026
Author: Jana Abu-Subha

This file adapts the original VIVIT architecture to utilize a pretrained 2D Google ViT
model via Hugging Face.
--------------------------------------------------------------------------------"""
import os
os.environ["TF_USE_LEGACY_KERAS"] = "1"
from transformers import TFViTModel

import cv2
import numpy as np
import keras
import time
from pathlib import Path
import tensorflow as tf
from keras import layers
from src.foxrobotlab_ros2.src.match_seeker.scripts.olri_classifier.DataGeneratorVIVIT import *
from src.foxrobotlab_ros2.src.match_seeker.scripts.olri_classifier.paths import *

myPath = Path("/home/macalester/PycharmProjects/catkin_ws/src/match_seeker/res/classifier2022Data/DATA/")


@keras.saving.register_keras_serializable()
class VideoAugmentation(layers.Layer):
  def __init__(self, input_shape, **kwargs):
    super().__init__(**kwargs)
    self.input_shape_5d = input_shape
    self.frames, self.height, self.width, self.channels = input_shape

    self.probs = {
      "brightness": 0.35,
      "contrast": 0.35,
      "erasing": 0.30,
      "translation": 0.30,
      "noise": 0.35
    }

  def _augment_single_video(self, video):
      """Applies identical random transforms across all frames of ONE video clip using XLA-safe logic."""
      do_brightness = tf.random.uniform([]) < self.probs["brightness"]
      do_contrast = tf.random.uniform([]) < self.probs["contrast"]
      do_translation = tf.random.uniform([]) < self.probs["translation"]
      do_erasing = tf.random.uniform([]) < self.probs["erasing"]
      do_noise = tf.random.uniform([]) < self.probs["noise"]

      b_factor = tf.random.uniform([], -0.25, 0.25)
      c_factor = tf.random.uniform([], 0.75, 1.25)

      t_height = tf.cast(tf.random.uniform([], -0.1, 0.1) * tf.cast(self.height, tf.float32), tf.int32)
      t_width = tf.cast(tf.random.uniform([], -0.1, 0.1) * tf.cast(self.width, tf.float32), tf.int32)

      e_h = tf.cast(tf.random.uniform([], 0.02, 0.2) * tf.cast(self.height, tf.float32), tf.int32)
      e_w = tf.cast(tf.random.uniform([], 0.02, 0.2) * tf.cast(self.width, tf.float32), tf.int32)
      e_y = tf.random.uniform([], 0, self.height - e_h, dtype=tf.int32)
      e_x = tf.random.uniform([], 0, self.width - e_w, dtype=tf.int32)

      video = tf.cond(do_brightness, lambda: video + b_factor, lambda: video)
      video = tf.cond(do_contrast, lambda: (video - 0.5) * c_factor + 0.5, lambda: video)

      video = tf.cond(
          do_translation,
          lambda: tf.roll(video, shift=[t_height, t_width], axis=[1, 2]),
          lambda: video
      )

      def apply_erasing():
          rows = tf.range(self.height)
          cols = tf.range(self.width)
          cols_grid, rows_grid = tf.meshgrid(cols, rows)

          in_x = (cols_grid >= e_x) & (cols_grid < e_x + e_w)
          in_y = (rows_grid >= e_y) & (rows_grid < e_y + e_h)
          in_box = in_x & in_y

          mask = tf.where(in_box, 0.0, 1.0)
          mask = tf.expand_dims(mask, axis=-1)  # Shape: (height, width, 1)
          mask = tf.cast(mask, dtype=video.dtype)

          return video * mask

      video = tf.cond(do_erasing, apply_erasing, lambda: video)

      video = tf.cond(
          do_noise,
          lambda: video + tf.random.normal(shape=tf.shape(video), stddev=0.05),
          lambda: video
      )

      return tf.clip_by_value(video, 0.0, 1.0)


  def call(self, inputs, training=None):
    if not training:
      return inputs
    augmented_batch = tf.map_fn(
      fn=self._augment_single_video,
      elems=inputs,
      fn_output_signature=inputs.dtype
    )
    return augmented_batch

  def get_config(self):
    config = super().get_config()
    config.update({"input_shape": self.input_shape_5d})
    return config

@keras.saving.register_keras_serializable()
class HuggingFace2DViTWrapper(layers.Layer):
  def __init__(self, **kwargs):
    super().__init__(**kwargs)
    self.vit_base = TFViTModel.from_pretrained("google/vit-base-patch16-224-in21k", use_safetensors=False)

    for weight in self.vit_base.weights:
        if not hasattr(weight, 'regularizer'):
            weight.regularizer = None

  def call(self, inputs):
    outputs = self.vit_base(pixel_values=inputs, return_dict=False)
    return outputs[1]

  @property
  def weights(self):
    return self.vit_base.weights

  @property
  def trainable_weights(self):
    return self.vit_base.trainable_weights

  @property
  def non_trainable_weights(self):
    return self.vit_base.non_trainable_weights


class CellPredictModelVIVIT(object):
  def __init__(self, check_point_folder=myPath / "CHECKPOINTS", loaded_checkpoint="2026PretrainedCellPredict_0707261308/ViT2D_Temporal-10-2.16.weights.h5",
               framePath=myPath / "FrameData", annotPath=myPath / "AnnotData",
               data_name="ViT2D_Temporal", output_size=271, image_size=224, seq_length=16, skip_size=16,
               batch_size=8, learning_rate=1e-5, epochs=30, input_shape=(16, 224, 224, 3)):

    # run_id = time.strftime("%m%d%y%H%M")
    # self.checkpoint_dir = os.path.join(check_point_folder, f"2026PretrainedCellPredict_{run_id}/")
    # os.makedirs(self.checkpoint_dir, exist_ok=True)

    # For loading a previous model
    self.checkpoint_dir = os.path.join(check_point_folder, "2026PretrainedCellPredict_0707261308/")

    self.framePath = framePath
    self.annotPath = annotPath
    self.data_name = data_name

    self.outputSize = output_size
    self.image_size = image_size
    self.seqLength = seq_length
    self.skipSize = skip_size

    self.batch_size = batch_size
    self.learning_rate = learning_rate
    self.epochs = epochs
    self.input_shape = input_shape

    self.train_ds = None
    self.val_ds = None
    self.model = None

    self.custom_objects = {
      "VideoAugmentation": VideoAugmentation,
      "HuggingFace2DViTWrapper": HuggingFace2DViTWrapper
    }

    if loaded_checkpoint is not None:
      self.loaded_checkpoint = os.path.join(check_point_folder, loaded_checkpoint)
    else:
      self.loaded_checkpoint = None

  def prepDatasets(self):
    self.train_ds = DataGeneratorVIVIT(framePath=self.framePath, annotPath=self.annotPath, skipSize=self.skipSize,
                                       seqLength=self.seqLength, batch_size=self.batch_size, train=True,
                                       generateForCellPred=True)
    self.val_ds = DataGeneratorVIVIT(framePath=self.framePath, annotPath=self.annotPath, skipSize=self.skipSize,
                                     seqLength=self.seqLength, batch_size=self.batch_size, train=False,
                                     generateForCellPred=True)

  def create_vivit_classifier(self):
    """
    Builds the 2D ViT temporal fusion model using the weight-forwarding wrapper.
    """
    inputs = layers.Input(shape=self.input_shape)

    x = VideoAugmentation(input_shape=self.input_shape)(inputs)

    x_2d = layers.Lambda(lambda t: tf.reshape(t, [-1, self.image_size, self.image_size, 3]))(x)
    x_2d = layers.Lambda(lambda tensor: (tensor - 0.5) / 0.5)(x_2d)
    x_2d = layers.Lambda(lambda tensor: tf.transpose(tensor, perm=[0, 3, 1, 2]))(x_2d)

    features_2d = HuggingFace2DViTWrapper()(x_2d)

    temporal_features = layers.Lambda(lambda t: tf.reshape(t, [-1, self.seqLength, 768]))(features_2d)

    video_representation = layers.GlobalAveragePooling1D()(temporal_features)

    video_representation = layers.Dropout(0.5)(video_representation)
    outputs = layers.Dense(self.outputSize, activation="softmax")(video_representation)

    model = keras.Model(inputs=inputs, outputs=outputs)
    return model

  def buildNetwork(self):
    print(tf.__version__)
    self.model = self.create_vivit_classifier()

    if self.loaded_checkpoint is not None:
      try:
          self.model.load_weights(self.loaded_checkpoint, skip_mismatch=True)
          print("Successfully loaded Dense classification head weights.")
      except Exception as e:
          print(f"Notice: Initializing clean weights or handling partial checkpoint map: {e}")

    optimizer = keras.optimizers.AdamW(learning_rate=self.learning_rate, weight_decay=1e-4)
    self.model.compile(
      optimizer=optimizer,
      loss="sparse_categorical_crossentropy",
      metrics=[
        keras.metrics.SparseCategoricalAccuracy(name="accuracy"),
        keras.metrics.SparseTopKCategoricalAccuracy(5, name="top-5-accuracy"),
      ],
    )
    print("\n--- MODEL TRAINABILITY VERIFICATION ---")
    self.model.summary(show_trainable=True)

  def train(self, epochs=30):
    self.model.fit(
      self.train_ds,
      epochs=epochs,
      verbose=1,
      validation_data=self.val_ds,
      callbacks=[
        keras.callbacks.History(),
        keras.callbacks.ModelCheckpoint(
          self.checkpoint_dir + self.data_name + "-{epoch:02d}-{val_loss:.2f}.weights.h5",
          save_weights_only=True,
          save_freq="epoch"
        ),
        keras.callbacks.TensorBoard(
          log_dir=self.checkpoint_dir,
          write_images=False
        ),
        keras.callbacks.TerminateOnNaN()
      ]
    )


  def cleanImage(self, image, imageSize=224):
    shrunkenIm = cv2.resize(image, (imageSize, imageSize))
    recoloredIm = cv2.cvtColor(shrunkenIm, cv2.COLOR_BGR2RGB)
    processedIm = recoloredIm / 255.0
    return processedIm

  def predictSingleImageBatchAllData(self, images):
    cleanImages = []
    for image in images:
      cleanImage = self.cleanImage(image, 224)
      cleanImages.append(cleanImage)
    listed = np.asarray([cleanImages])
    modelPredict = self.model.predict(listed)
    maxIndex = np.argmax(modelPredict)
    return maxIndex, modelPredict[0]

  def findTopX(self, x, numList):
    topXInd = np.argsort(numList)[-x:][::-1]
    topXPercs = numList[topXInd]
    return topXPercs, topXInd


if __name__ == "__main__":
  print("Executing fine-tuning of Pretrained ViViT")
  runner = CellPredictModelVIVIT()
  runner.prepDatasets()
  runner.buildNetwork()
  runner.train()
  print("Training complete!")