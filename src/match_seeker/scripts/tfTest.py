
#import os
#os.environ['TF_USE_LEGACY_KERAS'] = '1'

import time
import tensorflow as tf
#import tf_keras

print("Starting...")

#time.sleep(2)

#print("ANother print statement")

#checkptPath = "/media/macalester/Data/PycharmProjects/catkin_ws/src/match_seeker/res/classifier2022Data/DATA/CHECKPOINTS"
#testModelPath = "2024CellPredictLSTM_checkpoint-0802241319/CellPredAdam224-74-1.26.keras"
#model = tf_keras.models.load_model(checkptPath + "/" + testModelPath)
#model.save('newCellPredAdam224-74-1.26.keras')

print(tf.__version__)

print("Done")
