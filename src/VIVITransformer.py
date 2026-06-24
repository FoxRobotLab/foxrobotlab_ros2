import os
import time
from pathlib import Path
import math
import cv2
import re
import numpy as np
import tensorflow as tf
import keras
from keras import layers

# Paths for the Precision Towers
myPath = Path("/home/macalester/PycharmProjects/catkin_ws/src/match_seeker/res/classifier2022Data/DATA/")
textDataPath = myPath / "AnnotData/"
framesDataPath = myPath / "FrameData/"
checkPts = myPath / "CHECKPOINTS/"

run_id = time.strftime("%m%d%y%H%M")
checkpoint_dir = str(checkPts) + f"/2026CellPredictTransformer_checkpoint-{run_id}/"
data_name = "VIVIT"

outputSize = 271 #ie number of classes
image_size = 224
seqLength = 10
skipSize = 5

batch_size = 8
learning_rate = 1e-4
epochs = 10
train_perc = 0.8
randSeed = 4359

eval_ratio = 11.0 / 61.0
image_depth = 4
dataSize = 0

# TUBELET EMBEDDING
INPUT_SHAPE = (10, 224, 224, 3)
PATCH_SIZE = (4, 16, 16)
NUM_PATCHES = (INPUT_SHAPE[0] // PATCH_SIZE[0]) ** 2

# ViViT ARCHITECTURE
LAYER_NORM_EPS = 1e-6
PROJECTION_DIM = 128
NUM_HEADS = 8
NUM_LAYERS = 8

loaded_checkpoint_raw = "2026CellPredictTransformer_checkpoint-0623261432/VIVIT-20-0.17.keras"
if loaded_checkpoint_raw is not None:
    loaded_checkpoint = checkPts / loaded_checkpoint_raw
else:
    loaded_checkpoint = loaded_checkpoint_raw

train_ds = None
val_ds = None
model = None

"""
Data generator based on DataGenerator2022.py that produces data suitable for use by a CNN-LSTM model. It
produces sequences of a fixed length, made from overlapping segments of each video/run frames.

Created Summer 2024
Authors: Susan Fox, Marcus Wallace, Elisa Avalos, Oscar Reza Bautista
"""

class DataGeneratorLSTM(keras.utils.Sequence):
    def __init__(self, framePath, annotPath, skipSize, seqLength,
                 batch_size, shuffle=True, randSeed=12342, train_perc=0.8,
                 img_size=224, train=True, generateForCellPred = True,
                 cellPredWithHeadingIn = False, headingPredWithCellIn = False):

        self.batch_size = batch_size
        self.framePath = framePath
        self.annotPath = annotPath
        self.skipSize = skipSize
        self.seqLength = seqLength

        self.shuffle = shuffle
        self.img_size = img_size
        self.image_path = framesDataPath

        self.runData = self._collectRunData()
        self.allSequences = self._enumerateSequences()

        self.train_perc = train_perc
        np.random.seed(randSeed)  # set random generator to

        self.trainSequences, self.valSequences = self.traintestsplit(self.allSequences, self.train_perc)
        print(self.train_perc, len(self.trainSequences) / len(self.allSequences), len(self.valSequences) / len(self.allSequences))

        self.generateForCellPred = generateForCellPred
        self.cellPredWithHeadingIn = cellPredWithHeadingIn
        self.headingPredWithCellIn = headingPredWithCellIn

        self.potentialHeadings = [0, 45, 90, 135, 180, 225, 270, 315]
        if not train:
            self.allSequences = self.valSequences

    def __len__(self):
      'Denotes the number of batches per epoch'
      return int(np.floor(len(self.trainSequences) / self.batch_size))

    def _collectRunData(self):
        """Iterates over the annotation files in the input folder, and builds a run data object for each."""
        if not os.path.exists(self.annotPath):
            raise FileNotFoundError
        annotFiles = [f for f in os.listdir(self.annotPath) if f.startswith("FrameDataReviewed") and f.endswith(".txt")]
        annotFiles.sort()
        runData = []
        for file in annotFiles:
            nextRunInfo = VideoRunData(file, self.annotPath, self.framePath, self.skipSize, self.seqLength)
            runData.append(nextRunInfo)
        return runData

    def _enumerateSequences(self):
        """Iterates over the self.runData objects, and collects up how many sequences each run has. It makes a list of all
        possible sequences, which can be reordered to produce sequences in random orders."""
        allSequences = []
        for (runIndex, rData) in enumerate(self.runData):
            numSeqs = rData.getNumSequences()
            for seqInd in range(numSeqs):
                allSequences.append([runIndex, seqInd])
        return allSequences

    def makeFilename(path, fileNum):
        """Makes a filename for reading or writing image files"""
        formStr = "{0:s}{1:s}{2:0>4d}.{3:s}"
        name = formStr.format(path, 'frame', fileNum, "jpg")
        return name

    def on_epoch_end(self):
        'Reshuffles after each epoch'
        if self.shuffle:
            np.random.shuffle(self.trainSequences)

    def __getitem__(self, index):
      """Generate one batch of data"""

      # Generate data
      X, Y = self.__data_generation(index * self.batch_size)
      return X, Y

    def cleanImage(self, image):
        """Preprocessing the images into the correct input form."""
        img2 = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        shrunkenIm = cv2.resize(img2, (self.img_size, self.img_size))
        processedIm = shrunkenIm / 255.0
        return processedIm

    def __data_generation(self, startIndex):
        """Generates and returns one batch of data, a batch of sequences, and their corresponding labels.
        Note the shape of the data here: one row for each sequence, and the second dimension is the length
        of the sequence (each element is an image), and the third, fourth, and fifth dimensions are the image size
        (height, width, channels)."""
        # TODO: Need to determine here if we have one output per sequence? I think that is so, will write the code that way

        # # Initialization
        X = np.zeros((self.batch_size, self.seqLength, self.img_size, self.img_size, 3), dtype=float)
        Y = np.zeros((self.batch_size), dtype=int)

        for bInd in range(self.batch_size):
            actInd = startIndex + bInd
            [runInd, seqInd] = self.trainSequences[actInd]
            runObj = self.runData[runInd]
            frameList, annotList = runObj.retrieveSequence(seqInd)
            for (i, imgName) in enumerate(frameList):
                img = cv2.imread(imgName)
                finalIm = self.cleanImage(img)
                X[bInd,i,:,:,:] = finalIm
            if self.generateForCellPred:
                Y[bInd] = annotList[-1]['cell']
            else:
                headVal = annotList[-1]['head']
                headInd = self.potentialHeadings.index(headVal)
                Y[bInd] = headInd
        return X, Y

    def traintestsplit(self, sequences, train_perc):
        '''Split the data passed in based on the evaluation ratio into
        training and testing datasets, assuming it's already randomized'''
        np.random.shuffle(sequences)
        num_eval = int((train_perc * len(sequences)))
        train_images = sequences[:num_eval]
        eval_images = sequences[num_eval:]
        return train_images, eval_images


class VideoRunData(object):
    """Represents the data for one "run" (essentially one video) including the annotations and the frames themselves,
    without reading in the image data. It can be used to retrieve a sequence of image names and their annotations
    of a given length and starting point."""
    def __init__(self, annotFile, annotPath, dataPath, skipSize, seqLength):
        """Sets up the data for a single run, given the annotation filename and the path to the folder of images.
        It also takes optionally the number of frames to skip between starts of sequences, and the length of the
        sequence to produce."""
        # Sequence basics
        self.skipSize = skipSize
        self.seqLength = seqLength

        # identifying timestamp information
        results = re.findall("FrameDataReviewed(\d+)-(\d+)frames.txt", annotFile)
        [date, recTime] = results[0]
        self.date = date
        self.recTime = recTime

        # Set up information about images and their filenames
        self.folderPath = dataPath / (str(date) + "-" + str(recTime) + "frames")

        if not os.path.exists(self.folderPath):
            print( "THERE IS NO " + str(self.folderPath) + ("!!!"))
            raise FileNotFoundError
        self.imageNames = [f for f in os.listdir(self.folderPath) if f.endswith(".jpg")]
        self.imageNames.sort()
        self.frameCount = len(self.imageNames)
        self.numSequences = math.ceil((self.frameCount - self.seqLength + 1) / self.skipSize)

        # Set up information about locations and cells from the annotation file
        self.annotationsFile = annotPath / annotFile
        if not os.path.exists(self.annotationsFile):
            raise FileNotFoundError
        with open(self.annotationsFile, 'r') as fil:
            rawLines = fil.readlines()
        self.annotData = {}
        for line in rawLines:
            parts = line.split()
            if len(parts) > 1:  # Checks if the line is not empty
                imgName = parts[0]
                x = float(parts[1])
                y = float(parts[2])
                cell = int(parts[3])
                head = int(parts[4])
                self.annotData[imgName] = {'x': x, 'y': y, 'cell': cell, 'head': head}

    def getFrameCount(self):
        """Returns the number of frames in this run"""
        return self.frameCount

    def getNumSequences(self):
        """Calculates the number of sequences, given the number of frames, the skip size, and the length of the sequence"""
        return self.numSequences

    def retrieveSequence(self, seqInd):
        """This takes in a number, which is NOT the index of the frame, but rather which sequence to retrieve. For
        example, with a skip size of 2, 0 would start with frame 0, but sequence index 1 would start with frame 2.
        It returns a list of the image filenames for this sequence, and the corresponding annotations
        (x, y, cell, head)."""
        startIndex = seqInd * self.skipSize
        seqFramePaths = []
        seqAnnotations = []
        for i in range(self.seqLength):
            imName = self.imageNames[startIndex + i]
            annot = self.annotData[imName]
            seqFramePaths.append(self.folderPath / imName)
            seqAnnotations.append(annot)
        return seqFramePaths, seqAnnotations



def prepDatasets():
    """Finds the cell labels associated with the files in the frames folder, and then sets up two
    data generators to preprocess data and produce the data in batches."""
    global train_ds, val_ds
    train_ds = DataGeneratorLSTM(framePath = framesDataPath, annotPath = textDataPath, skipSize=skipSize, seqLength=seqLength, batch_size = batch_size, generateForCellPred = False)
    val_ds = DataGeneratorLSTM(framePath = framesDataPath, annotPath = textDataPath, skipSize=skipSize, seqLength=seqLength, batch_size = batch_size, train = False, generateForCellPred = False)

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

def create_vivit_classifier(
    tubelet_embedder,
    positional_encoder,
    input_shape=INPUT_SHAPE,
    transformer_layers=NUM_LAYERS,
    num_heads=NUM_HEADS,
    embed_dim=PROJECTION_DIM,
    layer_norm_eps=LAYER_NORM_EPS,
    num_classes=outputSize,
):
    # Get the input layer
    inputs = layers.Input(shape=input_shape)
    # Create patches.
    patches = tubelet_embedder(inputs)
    # Encode patches.
    encoded_patches = positional_encoder(patches)

    # Create multiple layers of the Transformer block.
    for _ in range(transformer_layers):
        # Layer normalization and MHSA
        x1 = layers.LayerNormalization(epsilon=1e-6)(encoded_patches)
        attention_output = layers.MultiHeadAttention(
            num_heads=num_heads, key_dim=embed_dim // num_heads, dropout=0.1
        )(x1, x1)

        # Skip connection
        x2 = layers.Add()([attention_output, encoded_patches])

        # Layer Normalization and MLP
        x3 = layers.LayerNormalization(epsilon=1e-6)(x2)
        x3 = keras.Sequential(
            [
                layers.Dense(units=embed_dim * 4, activation="gelu"),
                layers.Dense(units=embed_dim, activation="gelu"),
            ]
        )(x3)

        # Skip connection
        encoded_patches = layers.Add()([x3, x2])

    # Layer normalization and Global average pooling.
    representation = layers.LayerNormalization(epsilon=layer_norm_eps)(encoded_patches)
    representation = layers.GlobalAvgPool1D()(representation)

    # Classify outputs.
    outputs = layers.Dense(units=num_classes, activation="softmax")(representation)

    # Create the Keras model.
    model = keras.Model(inputs=inputs, outputs=outputs)
    return model


def buildNetwork():
    """Builds the network, saving it to self.model."""
    global model
    print (tf.__version__)
    print ("Calling buildNetwork", loaded_checkpoint)
    if loaded_checkpoint is not None:
        model = keras.models.load_model(loaded_checkpoint, compile=False, custom_objects={"TubeletEmbedding": TubeletEmbedding, "PositionalEncoder": PositionalEncoder})         #TODO: change what checkpoint is being loaded
        print ("Got past the model loading")
    else:
        model = create_vivit_classifier(
            tubelet_embedder=TubeletEmbedding(
                embed_dim=PROJECTION_DIM, patch_size=PATCH_SIZE
            ),
            positional_encoder=PositionalEncoder(embed_dim=PROJECTION_DIM),
        )
    # Compile the model with the optimizer, loss function
    # and the metrics.
    optimizer = keras.optimizers.Adam(learning_rate=learning_rate)
    model.compile(
        optimizer=optimizer,
        loss="sparse_categorical_crossentropy",
        metrics=[
            keras.metrics.SparseCategoricalAccuracy(name="accuracy"),
            keras.metrics.SparseTopKCategoricalAccuracy(5, name="top-5-accuracy"),
        ],
    )

def train(epochs = 10):
    """Sets up the loss function and optimizer, and then trains the model on the current training data. Quits if no
    training data is set up yet."""
    # balancer = DataBalancer()
    # weights = balancer.getClassWeightCells()
    model.fit(
        train_ds,
        epochs=epochs,
        verbose=1,
        validation_data=val_ds,
        # class_weight = weights,
        callbacks=[
            keras.callbacks.History(),
            keras.callbacks.ModelCheckpoint(
                checkpoint_dir + data_name + "-{epoch:02d}-{val_loss:.2f}.keras",
                save_freq="epoch"  # save every epoch
            ),
            keras.callbacks.TensorBoard(
                log_dir=checkpoint_dir,
                write_images=False
            ),
            keras.callbacks.TerminateOnNaN()
        ]
    )



if __name__ == "__main__":
    print("Starting pipeline...")

    # 1. Prepare the data generators
    prepDatasets()
    print("Datasets prepped successfully.")

    # 2. Build the MoViNet model
    buildNetwork()
    print("Network built and compiled.")

    # 3. Start training
    train(epochs=epochs)
    print("Training complete!")

