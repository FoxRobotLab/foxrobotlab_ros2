"""--------------------------------------------------------------------------------
VIVITransformer.py

Created: June 2026
Authors: Susan Fox, Jana Abu-Subha

VIVITransformer implements a Video Vision Transformer based on Arnab et. al, and with
reference to the keras tutroial implementation of VIVIT. This file contains four classes,
TubeletEmbedding, which divides the video in spatio temporal tubes for processing, PositionalEncoder,
which injects 3D spatiotemporal context into the sequence, VideoAugmentation which adds three layers of
preprocessing data augmentation, and CellPredictModelVIVIT which creates, builds, and trains the
Video Vision Transformer.

--------------------------------------------------------------------------------"""
import os
import cv2
import numpy as np
import keras
import time
from pathlib import Path
import tensorflow as tf
from keras import layers
from match_seeker.scripts.olri_classifier.DataGeneratorVIVIT import *
from match_seeker.scripts.olri_classifier.paths import *

myPath = Path("/home/macalester/PycharmProjects/catkin_ws/src/match_seeker/res/classifier2022Data/DATA/")

@keras.saving.register_keras_serializable()
class TubeletEmbedding(layers.Layer):
    def __init__(self, embed_dim, patch_size, **kwargs):
        super().__init__(**kwargs)
        self.projection = layers.Conv3D(
            filters=embed_dim,
            kernel_size=patch_size,
            strides=patch_size,
            padding="VALID",
        )
        self.embed_dim = embed_dim
        self.patch_size = patch_size
        self.flatten = layers.Reshape(target_shape=(-1, embed_dim))

    def call(self, videos):
        projected_patches = self.projection(videos)
        flattened_patches = self.flatten(projected_patches)
        return flattened_patches

    def get_config(self):
        config = super().get_config()
        config.update({
            "embed_dim": self.embed_dim,
            "patch_size": self.patch_size,
        })
        return config


@keras.saving.register_keras_serializable()
class PositionalEncoder(layers.Layer):
    def __init__(self, embed_dim, **kwargs):
        super().__init__(**kwargs)
        self.embed_dim = embed_dim

    def build(self, input_shape):
        _, num_tokens, _ = input_shape
        self.position_embedding = layers.Embedding(
            input_dim=num_tokens, output_dim=self.embed_dim
        )
        self.positions = tf.range(0, num_tokens, 1)

    def call(self, encoded_tokens):
        # Encode the positions and add it to the encoded tokens
        encoded_positions = self.position_embedding(self.positions)
        encoded_tokens = encoded_tokens + encoded_positions
        return encoded_tokens

    def get_config(self):
        config = super().get_config()
        config.update({
            "embed_dim": self.embed_dim,
        })
        return config

@keras.saving.register_keras_serializable()
class VideoAugmentation(layers.Layer):
    def __init__(self, input_shape, **kwargs):
        super().__init__(**kwargs)
        self.input_shape_5d = input_shape
        self.frames, self.height, self.width, self.channels = input_shape

        self.probs = {
            "brightness": 0.25,
            "contrast": 0.25,
            "erasing": 0.25,
            "translation": 0.25,
            "noise": 0.25
        }

        # self.brightness_layer = layers.RandomBrightness(factor=0.25, value_range=(0.0, 1.0))
        # self.contrast_layer = layers.RandomContrast(factor=0.25)
        # self.erasing_layer = layers.RandomErasing(factor=0.4, scale=(0.02, 0.2), value_range=(0.0, 1.0))
        # self.noise_layer = layers.GaussianNoise(stddev=0.05)
        # self.translation_layer = layers.RandomTranslation(height_factor=0.1, width_factor=0.1, fill_mode='constant')

    # def _apply_conditionally(self, x, layer, probability, training):
    #     """Helper method to conditionally execute a layer based on a probability threshold."""
    #     random_val = tf.random.uniform(shape=[], minval=0.0, maxval=1.0)
    #     return tf.cond( #using cond in place of an if statement
    #         random_val < probability,
    #         lambda: layer(x, training=training),  # Apply layer if true
    #         lambda: x  # Pass through unchanged if false
    #     )

    def _augment_single_video(self, video):
        """Applies identical random transforms across all frames of ONE video clip using XLA-safe logic."""
        # 1. Generate symbolic boolean conditions
        do_brightness = tf.random.uniform([]) < self.probs["brightness"]
        do_contrast = tf.random.uniform([]) < self.probs["contrast"]
        do_translation = tf.random.uniform([]) < self.probs["translation"]
        do_erasing = tf.random.uniform([]) < self.probs["erasing"]
        do_noise = tf.random.uniform([]) < self.probs["noise"]

        # 2. Generate unified parameters for this video clip
        b_factor = tf.random.uniform([], -0.25, 0.25)
        c_factor = tf.random.uniform([], 0.75, 1.25)

        t_height = tf.cast(tf.random.uniform([], -0.1, 0.1) * tf.cast(self.height, tf.float32), tf.int32)
        t_width = tf.cast(tf.random.uniform([], -0.1, 0.1) * tf.cast(self.width, tf.float32), tf.int32)

        e_h = tf.cast(tf.random.uniform([], 0.02, 0.2) * tf.cast(self.height, tf.float32), tf.int32)
        e_w = tf.cast(tf.random.uniform([], 0.02, 0.2) * tf.cast(self.width, tf.float32), tf.int32)
        e_y = tf.random.uniform([], 0, self.height - e_h, dtype=tf.int32)
        e_x = tf.random.uniform([], 0, self.width - e_w, dtype=tf.int32)

        # 3. Apply changes vectorially across all frames using tf.cond
        video = tf.cond(do_brightness, lambda: video + b_factor, lambda: video)
        video = tf.cond(do_contrast, lambda: (video - 0.5) * c_factor + 0.5, lambda: video)

        # Axis [1, 2] corresponds to (height, width), applying shifts identically over axis 0 (frames)
        video = tf.cond(
            do_translation,
            lambda: tf.roll(video, shift=[t_height, t_width], axis=[1, 2]),
            lambda: video
        )

        def apply_erasing():
            # XLA-COMPLIANT: Generate coordinate meshes of a completely static size
            rows = tf.range(self.height)
            cols = tf.range(self.width)
            cols_grid, rows_grid = tf.meshgrid(cols, rows)

            # Use conditional comparison instead of variable tensor initialization
            in_x = (cols_grid >= e_x) & (cols_grid < e_x + e_w)
            in_y = (rows_grid >= e_y) & (rows_grid < e_y + e_h)
            in_box = in_x & in_y

            # Wherever we are inside the box, fill with 0.0, otherwise keep 1.0
            mask = tf.where(in_box, 0.0, 1.0)
            mask = tf.expand_dims(mask, axis=-1)  # Shape: (height, width, 1)
            mask = tf.cast(mask, dtype=video.dtype)

            # Broadcasts across all frames seamlessly
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

        # Use tf.map_fn to iterate cleanly through the batch elements
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


class CellPredictModelVIVIT(object):
    def __init__(self, check_point_folder=myPath / "CHECKPOINTS", loaded_checkpoint="2026ActualCellPredictTransformer_checkpoint-0706261533/VIVIT-20-4.47.keras",
                 framePath=myPath / "FrameData", annotPath=myPath / "AnnotData",
                 data_name="VIVIT", output_size=271, image_size=224, seq_length=16, skip_size=16,
                 batch_size=8, learning_rate=1e-4, epochs=100, input_shape= (16, 224, 224, 3)):

        # File System
        run_id = time.strftime("%m%d%y%H%M")
        # For starting a new model
        # self.checkpoint_dir = os.path.join(check_point_folder, f"2026ActualCellPredictTransformer_checkpoint-{run_id}/")

        # For loading a previous model
        self.checkpoint_dir = os.path.join(check_point_folder, "2026ActualCellPredictTransformer_checkpoint-0706261533/")

        self.framePath = framePath
        self.annotPath = annotPath
        self.data_name = data_name

        # Model Hyperparameters
        self.outputSize = output_size
        self.image_size = image_size
        self.seqLength = seq_length
        self.skipSize = skip_size
        self.batch_size = batch_size
        self.learning_rate = learning_rate
        self.epochs = epochs
        self.input_shape= input_shape

        # ViViT Network Transformer Architecture
        self.layer_norm_eps = 1e-6
        self.embed_dim = 256 # previously 128
        self.num_heads = 4 # previously 8
        self.num_layers = 8
        self.patch_size = (4, 16, 16)

        # Datasets & Central Graph Components
        self.train_ds = None
        self.val_ds = None
        self.model = None

        # Custom Layer Serializers mapping configuration
        self.custom_objects = {
            "TubeletEmbedding": TubeletEmbedding,
            "PositionalEncoder": PositionalEncoder,
            "VideoAugmentation": VideoAugmentation
        }

        # Handle file paths if loading active weights
        if loaded_checkpoint is not None:
            self.loaded_checkpoint = os.path.join(check_point_folder, loaded_checkpoint)
        else:
            self.loaded_checkpoint = None


    def prepDatasets(self):
        """Finds the cell labels associated with the files in the frames folder, and then sets up two
        data generators to preprocess data and produce the data in batches."""
        self.train_ds = DataGeneratorVIVIT(framePath=self.framePath, annotPath=self.annotPath, skipSize=self.skipSize,
                                      seqLength=self.seqLength, batch_size=self.batch_size, train=True, generateForCellPred=True)
        self.val_ds = DataGeneratorVIVIT(framePath=self.framePath, annotPath=self.annotPath, skipSize=self.skipSize,
                                    seqLength=self.seqLength, batch_size=self.batch_size, train=False, generateForCellPred=True)

    def create_vivit_classifier(self):
        """
        Builds a Video Vision Transformer (ViViT) model with spatio-temporal tubelet embeddings.
        Features a data augmentation layer.
        Includes dropout to prevent overfitting.
        """
        inputs = layers.Input(shape=self.input_shape)
        augment = VideoAugmentation(input_shape=self.input_shape)(inputs)

        tubelet_embedder = TubeletEmbedding(embed_dim=self.embed_dim, patch_size=self.patch_size)
        positional_encoder = PositionalEncoder(embed_dim=self.embed_dim)

        patches = tubelet_embedder(augment)
        encoded_patches = positional_encoder(patches)

        encoded_patches = layers.Dropout(0.3)(encoded_patches)

        for _ in range(self.num_layers):
            x1 = layers.LayerNormalization(epsilon=1e-6)(encoded_patches)
            attention_output = layers.MultiHeadAttention(
                num_heads=self.num_heads, key_dim=self.embed_dim // self.num_heads, dropout=0.2
            )(x1, x1)

            x2 = layers.Add()([attention_output, encoded_patches])

            x3 = layers.LayerNormalization(epsilon=1e-6)(x2)
            x3 = keras.Sequential(
                [
                    layers.Dense(units=self.embed_dim * 4, activation="gelu"),
                    layers.Dropout(0.2),
                    layers.Dense(units=self.embed_dim, activation="gelu"),
                    layers.Dropout(0.2),
                ]
            )(x3)

            encoded_patches = layers.Add()([x3, x2])

        representation = layers.LayerNormalization(epsilon=self.layer_norm_eps)(encoded_patches)
        representation = layers.GlobalAvgPool1D()(representation)

        representation = layers.Dropout(0.5)(representation)

        outputs = layers.Dense(units=self.outputSize, activation="softmax")(representation)

        model = keras.Model(inputs=inputs, outputs=outputs)
        return model

    def buildNetwork(self):
        """Builds the network, saving it to self.model."""
        print(tf.__version__)
        print("Calling buildNetwork", self.loaded_checkpoint)
        if self.loaded_checkpoint is not None:
            self.model = keras.models.load_model(self.loaded_checkpoint, compile=False,
                                            custom_objects=self.custom_objects)
            print("Got past the model loading")
        else:
            self.model = self.create_vivit_classifier()
        # Compile the model with the optimizer, loss function
        # and the metrics.
        optimizer = keras.optimizers.AdamW(learning_rate=self.learning_rate, weight_decay=1e-4)
        self.model.compile(
            optimizer=optimizer,
            loss="sparse_categorical_crossentropy",
            metrics=[
                keras.metrics.SparseCategoricalAccuracy(name="accuracy"),
                keras.metrics.SparseTopKCategoricalAccuracy(5, name="top-5-accuracy"),
            ],
        )

    def train(self, epochs=100):
        """Sets up the loss function and optimizer, and then trains the model on the current training data. Quits if no
        training data is set up yet."""
        # balancer = DataBalancer()
        # weights = balancer.getClassWeightCells()
        self.model.fit(
            self.train_ds,
            epochs=epochs,
            verbose=1,
            validation_data=self.val_ds,
            # class_weight = weights,
            callbacks=[
                keras.callbacks.History(),
                keras.callbacks.ModelCheckpoint(
                    self.checkpoint_dir + self.data_name + "-{epoch:02d}-{val_loss:.2f}.keras",
                    save_freq="epoch"  # save every epoch
                ),
                keras.callbacks.TensorBoard(
                    log_dir=self.checkpoint_dir,
                    write_images=False
                ),
                keras.callbacks.TerminateOnNaN()
            ]
        )

    def cleanImage(self, image, imageSize=224):
        """Process a single image into the correct input form for 2020 model, mainly used for testing."""
        shrunkenIm = cv2.resize(image, (imageSize, imageSize))
        recoloredIm = cv2.cvtColor(shrunkenIm, cv2.COLOR_BGR2RGB)
        processedIm = recoloredIm / 255.0
        return processedIm

    def predictSingleImageBatchAllData(self, images):
        """Given a batch of images, converts it to be suitable for the network, then runs the model and returns
        the resulting prediction as tuples of index of prediction and list of predictions."""
        cleanImages = []
        for image in images:
            cleanImage = self.cleanImage(image, 224)
            cleanImages.append(cleanImage)
        listed = np.asarray([cleanImages])
        modelPredict = self.model.predict(listed)
        maxIndex = np.argmax(modelPredict)
        # print(f"Model Pred Shape: {modelPredict.shape}")
        return maxIndex, modelPredict[0]

    def findTopX(self, x, numList):
        """Returns the top X probabilities and their indices."""
        # print("findTopX:", numList)
        topXInd = np.argsort(numList)[-x:][::-1]
        topXPercs = numList[topXInd]
        return topXPercs, topXInd


if __name__ == "__main__":
    print("Executing training from scratch")
    runner = CellPredictModelVIVIT()
    runner.prepDatasets()
    runner.buildNetwork()
    runner.train()
    print("Training complete!")

