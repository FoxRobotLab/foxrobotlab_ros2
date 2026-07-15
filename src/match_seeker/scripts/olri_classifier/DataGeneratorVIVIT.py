"""--------------------------------------------------------------------------------
DataGenerator based on previous versions  (DataGeneratorLSTM) but with changed train/validation split mechanism, as well
as cropped images as opposed to downsized
Created Summer 2026
Edited by Jana Abu Subha

--------------------------------------------------------------------------------"""
import os
import math
from pathlib import Path
import cv2
import re
import numpy as np
import keras

myPath = Path("/home/macalester/PycharmProjects/catkin_ws/src/match_seeker/res/classifier2022Data/DATA/")
textDataPath = myPath / "AnnotData/"
framesDataPath = myPath / "FrameData/"
checkPts = myPath / "CHECKPOINTS/"

class DataGeneratorVIVIT(keras.utils.Sequence):
    def __init__(self, framePath, annotPath, skipSize, seqLength,
                 batch_size, shuffle=True, randSeed=12342, train_perc=0.8,
                 img_size=224, train=True, generateForCellPred = True):
        self.train = train
        self.batch_size = batch_size
        self.framePath = framePath
        self.annotPath = annotPath
        self.skipSize = skipSize
        self.seqLength = seqLength
        self.num_locs = 271

        self.shuffle = shuffle
        self.img_size = img_size

        self.runData = self._collectRunData()
        allSequences = self._enumerateSequences()

        self.val_perc = 1.0 - train_perc
        self.train_perc = train_perc
        np.random.seed(randSeed)

        self.generateForCellPred = generateForCellPred
        self.potentialHeadings = [0, 45, 90, 135, 180, 225, 270, 315]

        trainSequences, valSequences = self.traintestsplit(allSequences)
        self.active_sequences = trainSequences if self.train else valSequences

        print(self.train_perc, len(trainSequences) / len(allSequences), len(valSequences) / len(allSequences))

    def __len__(self):
      'Denotes the number of batches per epoch'
      return int(np.floor(len(self.active_sequences) / self.batch_size))

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

    def on_epoch_end(self):
        'Reshuffles after each epoch'
        if self.shuffle and self.train:
            np.random.shuffle(self.active_sequences)

    def __getitem__(self, index):
        """Generate one batch of data"""
        X, Y = self.__data_generation(index * self.batch_size)
        return X, Y

    def cleanImage(self, image):
        """Preprocessing the images into the correct input form."""
        # img2 = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        # shrunkenIm = cv2.resize(img2, (self.img_size, self.img_size))
        # processedIm = shrunkenIm / 255.0
        # return processedIm
        img_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        h, w = img_rgb.shape[:2]

        new_h = int(self.img_size / (w / h))
        shrunken = cv2.resize(img_rgb, (self.img_size, new_h))

        total_padding = self.img_size - new_h
        top_pad = total_padding // 2
        bottom_pad = total_padding - top_pad

        padded_image = cv2.copyMakeBorder(
            shrunken,
            top_pad, bottom_pad, 0, 0,
            borderType=cv2.BORDER_CONSTANT,
            value=[0, 0, 0]
        )
        return padded_image / 255.0

    def __data_generation(self, startIndex):
        """Generates and returns one batch of data, a batch of sequences, and their corresponding labels.
        Note the shape of the data here: one row for each sequence, and the second dimension is the length
        of the sequence (each element is an image), and the third, fourth, and fifth dimensions are the image size
        (height, width, channels)."""

        X = np.zeros((self.batch_size, self.seqLength, self.img_size, self.img_size, 3), dtype=float)
        Y = np.zeros((self.batch_size), dtype=int)

        for bInd in range(self.batch_size):
            actInd = startIndex + bInd
            [runInd, seqInd] = self.active_sequences[actInd]
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


    def traintestsplit(self, all_sequences):
        """
        Extracts locations from parsed VideoRunData objects, runs a pure
        presence-based stratified split on entire runs, and groups frame sequences.
        """
        num_runs = len(self.runData)
        run_location_matrix = np.zeros((num_runs, self.num_locs))

        for run_idx, runObj in enumerate(self.runData):
            cells_in_run = {annot['cell'] for annot in runObj.annotData.values()}
            for cell_id in cells_in_run:
                if 0 <= cell_id < self.num_locs:
                    run_location_matrix[run_idx, cell_id] = 1

        train_run_indices = []
        train_presence = np.zeros(self.num_locs)
        val_presence = np.zeros(self.num_locs)

        run_rarity = np.sum(run_location_matrix, axis=1)
        sorted_run_indices = np.argsort(-run_rarity)

        train_size = 1.0 - self.val_perc
        expected_ratio = train_size / self.val_perc

        for idx in sorted_run_indices:
            run_profile = run_location_matrix[idx]

            train_score = np.sum(run_profile * (train_presence == 0))
            val_score = np.sum(run_profile * (val_presence == 0))

            if train_score == val_score:
                if len(train_run_indices) <= len(sorted_run_indices) * train_size:
                    train_run_indices.append(idx)
                    train_presence = np.maximum(train_presence, run_profile)
                else:
                    val_presence = np.maximum(val_presence, run_profile)
            elif train_score > val_score:
                train_run_indices.append(idx)
                train_presence = np.maximum(train_presence, run_profile)
            else:
                val_presence = np.maximum(val_presence, run_profile)

        train_sequences = []
        val_sequences = []
        for seq in all_sequences:
            runInd, seqInd = seq
            if runInd in train_run_indices:
                train_sequences.append(seq)
            else:
                val_sequences.append(seq)

        np.random.shuffle(train_sequences)
        np.random.shuffle(val_sequences)

        return train_sequences, val_sequences

class VideoRunData(object):
    """Represents the data for one "run" (essentially one video) including the annotations and the frames themselves,
    without reading in the image data. It can be used to retrieve a sequence of image names and their annotations
    of a given length and starting point."""
    def __init__(self, annotFile, annotPath, dataPath, skipSize, seqLength):
        """Sets up the data for a single run, given the annotation filename and the path to the folder of images.
        It also takes optionally the number of frames to skip between starts of sequences, and the length of the
        sequence to produce."""
        self.skipSize = skipSize
        self.seqLength = seqLength

        results = re.findall("FrameDataReviewed(\d+)-(\d+)frames.txt", annotFile)
        [date, recTime] = results[0]
        self.date = date
        self.recTime = recTime

        self.folderPath = dataPath / (str(date) + "-" + str(recTime) + "frames")

        if not os.path.exists(self.folderPath):
            print( "THERE IS NO " + str(self.folderPath) + ("!!!"))
            raise FileNotFoundError
        self.imageNames = [f for f in os.listdir(self.folderPath) if f.endswith(".jpg")]
        self.imageNames.sort()
        self.frameCount = len(self.imageNames)
        self.numSequences = math.ceil((self.frameCount - self.seqLength + 1) / self.skipSize)

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

if __name__ == "__main__":
    import sys

    print("=" * 60)
    print("STARTING PIPELINE FUNCTIONALITY TEST")
    print("=" * 60)

    # 1. Verify Directories Exist Before Running
    if not textDataPath.exists() or not framesDataPath.exists():
        print(f"[ERROR] Data paths not found!\nText: {textDataPath}\nFrames: {framesDataPath}")
        sys.exit(1)

    # 2. Instantiate Training Generator
    print("\n[STEP 1] Initializing Training Data Generator...")
    try:
        train_gen = DataGeneratorVIVIT(
            framePath=framesDataPath,
            annotPath=textDataPath,
            skipSize=16,
            seqLength=16,
            batch_size=8,
            train_perc=0.8,
            train=True,
            shuffle=True
        )
        print(f"--> Training generator ready. Total batches: {len(train_gen)}")
    except Exception as e:
        print(f"[FAIL] Training initialization failed: {e}")
        sys.exit(1)

    # 3. Instantiate Validation Generator
    print("\n[STEP 2] Initializing Validation Data Generator...")
    try:
        val_gen = DataGeneratorVIVIT(
            framePath=framesDataPath,
            annotPath=textDataPath,
            skipSize=16,
            seqLength=16,
            batch_size=8,
            train_perc=0.8,
            train=False,  # Crucial: test the validation fork
            shuffle=False
        )
        print(f"--> Validation generator ready. Total batches: {len(val_gen)}")
    except Exception as e:
        print(f"[FAIL] Validation initialization failed: {e}")
        sys.exit(1)

    # 4. Pull a Sample Batch (Tests data generation, cv2 image loading, and resizing)
    print("\n[STEP 3] Fetching Batch 0 from Training Generator...")
    try:
        X, Y = train_gen[0]
        print("[SUCCESS] Batch generation complete!")
        print(f"--> X (Input Features) Shape : {X.shape} (Expected: (8, 16, 224, 224, 3))")
        print(f"--> Y (Target Labels) Shape  : {Y.shape} (Expected: (8,))")
        print(f"--> Data Range Verification  : Min={X.min():.2f}, Max={X.max():.2f} (Expected: 0.0 to 1.0)")
    except IndexError as e:
        print(f"[FAIL] Batch fetching triggered an index/scope error: {e}")
    except FileNotFoundError as e:
        print(f"[FAIL] Image or annotation file missing during runtime generation: {e}")
    except Exception as e:
        print(f"[FAIL] Unexpected crash during batch generation: {e}")

    print("\n" + "=" * 60)
    print("TEST EXECUTION COMPLETED")
    print("=" * 60)