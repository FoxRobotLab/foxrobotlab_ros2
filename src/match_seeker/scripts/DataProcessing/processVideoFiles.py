"""--------------------------------------------------------------------------------
processVideoFiles.py
Authors: Susan Fox
Date: Summer 2026

This program reads in saved AVI files and compares them to the previously saved and processed
frame data. It determines a time stamp for each frame, and then writes out every frameSkip frames
to a folder. The key variables to control this program are:
* videoPath, the path to the AVI file you want to process
* oldFramePath, the path to the folder of frames already created for this video
* oldAnnotFile, the path to the annotations file containing info about location and heading for the robot
* newFramePath, the path to a folder to save the new frames into
* newsAnnotFile, the path to the new annotations file, based on the old one
* frameSkip, how many frames to skip, if frameSkip = 1, take every frame, if it = 2, every other, etc.

Why compare with old frames?

In 2022 and 2024 when we collected the dataset, we also ran a separate program where
we recorded the robots locations and headings, determined manually by a person accompanying the
robot, at various timestamps. We then painstakingly coordinated timestamps and locations with existing
frames. We then checked each sequence of frames manually. Now, we would like to leverage that information
to relabel new frames, which might be closer together than the old ones.

Algorithm:
1. read in the filenames for a particular run, and sort them in order, set an index into the list
2. read in the current save frame
3. read in the annotations folder, set an index into it, and check that it is referring to the same image as step 1
4. set up an accumulator variable framesBetween, that will hold the frames that don't match saved frames
5. set up a counter for keeping track of which video frames to save to files
6. open the video file for reading, and start a loop through its frames
7.     compare the current video frame with the current saved frame
8.     if they are identical then
9.         call helper to process this frame and frames between, assigning them timestamps, locations, and headings
10.        save the right frames to the file, and write corresponding entries in the new annotation file
11.        update counter and set framesBetween to empty
11.    else
12.        add video frame to framesBetween
13. if there are leftover frames, then process them based on frame rate, or report to user
--------------------------------------------------------------------------------"""

from pathlib import Path
import cv2
import numpy as np

# Global variables
# dataRoot = Path("/Volumes/T7/macalester/")
dataRoot = Path("/Users/susan/PycharmProjects/foxrobotlab_ros2/src/match_seeker/res")
aviRootPath = dataRoot / "classifierData2026/AVI2022Backup"
oldFramesRootPath = dataRoot / "classifierData2026/FrameData"
oldAnnotRootPath = dataRoot / "classifierData2026/AnnotData"
newFramesRootPath = dataRoot / "classifierData2026/NewFrameData"
newFramesRootPath.mkdir(parents=True, exist_ok=True)
newAnnotRootPath = dataRoot / "classifier2026/NewAnnotData"
newAnnotRootPath.mkdir(parents=True, exist_ok=True)

# Variables to change to process different files
origTimeStamp = "20220705-1616"
videoPath = aviRootPath / (origTimeStamp + ".avi")
oldFramePath = oldFramesRootPath / (origTimeStamp + "frames")
oldAnnotFile = oldAnnotRootPath / ("FrameDataReviewed" + origTimeStamp + "frames.txt")
newFramePath = newFramesRootPath / oldFramePath.name
newAnnotFile = newAnnotRootPath / ("FrameData" + origTimeStamp + "frames.txt")
frameSkip = 4


def readAnnotations(annotFile):
    """Given a Path object pointing to an annotation file, read in its contents and save them as a dictionary of
    dictionaries: the outer level keys are the image filenames, and the value associated with a filename is
    a dictionary labeling x, y, cell, and heading"""
    if not annotFile.exists():
      raise FileNotFoundError

    with open(annotFile, 'r') as fil:
        annotData = {}
        for line in fil:
            parts = line.split()
            if len(parts) > 1:  # Checks if the line is not empty
                imgName = parts[0]
                x = float(parts[1])
                y = float(parts[2])
                cell = int(parts[3])
                head = int(parts[4])
                annotData[imgName] = {'x': x, 'y': y, 'cell': cell, 'head': head}
    return annotData

def annotateFrames(prevImgName, currImgName, framesBetween, currAnnots):
    """framesBetween is a list of frames, all of which need to be annotated.
    ASSERT: the first frame in framesBetween should match prevImgName and the last frame should match currImgName
    ASSERT: this updates the given newAnnots dictionary
    Compute the difference in milliseconds between prevImg and currImg, divide into subsections, use that to build
    new frame names. Do the same to compute the x and y based on the difference between the x values and the y values.
    And also for headings.
    From the olinmap convert (x,y) coordinates to corresponding cells,
    """
    return [], {}


def saveFrames(frameList, newFrameNames, counter):
    """Given a list of frames, and their corresponding timestamped names, save every Nth, using the current
    counter, so that N is determined by frameSkip. Build and return a list of the names that were actually saved."""
    global frameSkip
    savedFrames = []
    for name, img in zip(newFrameNames, frameList):
        if counter == 0:
            pathAndName = newFramePath / name
            cv2.imwrite(pathAndName, img)
            savedFrames.append(name)
        counter = (counter + 1) % frameSkip
    return counter, savedFrames


def updateNewAnnotations(saveImgList, temps, full):
    """Given the list of actually saved frames, and temporary annotations that include those frames as well as
    others that were not saved, and the full annotation list, this copies the annotations of the images from the
    saved list into the full dictionary"""
    for savedIm in saveImgList:
        full[savedIm] = temps[savedIm]


if __name__ == '__main__':
    print('Frames at', oldFramePath)
    print('Annots at', oldAnnotFile)
    # 1. Read in old frame filenames
    oldFrameNames = clean_files = [f for f in oldFramePath.glob("*.jpg") if not f.name.startswith("._")]

    oldFrameNames.sort()
    oldFrameIndex = 0

    # 2. Read in first frame
    print(oldFrameNames[oldFrameIndex])
    prevOldName = None
    currOldName = oldFrameNames[oldFrameIndex]
    currOldImg = cv2.imread(currOldName)

    cv2.imshow("OLD FRAME", currOldImg)

    # 3. Read in old annotations, a dictionary of dictionaries
    oldAnnotations = readAnnotations(oldAnnotFile)
    assert currOldName.name in oldAnnotations
    currAnnots = oldAnnotations[currOldName.name]

    # 4. Set up new annotation dictionary
    newAnnots = {}

    # 5. Set up an accumulators for the loop
    framesBetween = []
    counter = 0

    # 6. Open the video file for reading, and start a loop through its frames
    vidcap = cv2.VideoCapture(videoPath)
    cv2.namedWindow("Video frame")
    cv2.moveWindow("Video frame", 680, 0)
    cv2.namedWindow("Diffs")
    cv2.moveWindow("Diffs", 340, 500)
    stop = False
    while True:
        gotFrame, frame = vidcap.read()
        if not gotFrame:
            print("No frame")
            break

        # Compare frame to current from old
        diff = cv2.absdiff(frame, currOldImg)

        nonzero = np.sum(diff > 0)
        totalDiff = diff.sum()
        maxDiff = diff.max()
        print(totalDiff, nonzero, maxDiff)
        _, diffImg = cv2.threshold(diff, 1, 255, cv2.THRESH_BINARY)
        cv2.imshow("Diffs", diffImg)
        if totalDiff < 1100000 and nonzero < 1000000 and maxDiff < 25:
            print("Same!")
            stop = True
            newFrameNames, tempAnnots = annotateFrames(prevOldName, currOldName, framesBetween, currAnnots)
            counter, savedNames = saveFrames(framesBetween, newFrameNames, counter)
            updateNewAnnotations(savedNames, tempAnnots, newAnnots)
            # Reset for next round
            prevOldName = currOldName
            framesBetween = [framesBetween[-1]]
        else: # skip this frame
            framesBetween.append(frame)


        cv2.imshow("Video frame", frame)
        if stop:
            cv2.waitKey(0)
            stop = False
        else:
            x = cv2.waitKey(10)
        if x == ord('q'):
            break
