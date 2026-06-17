#!/usr/bin/env python

""" ========================================================================
matchPlanner.py
Created: June 2017

This file borrows code from the qrPlanner.py in qr_seeker.
It manages the robot, from low-level motion control (using PotentialFieldBrain)
to higher level path planning, plus matching camera images to a database of images
in order to localize the robot.

Team Summer 2019 did not make a lot of changes here, however now the GUI doesn't
always accurately reflect what is happening. Fix what is being logged to the
GUI here and in SeekerGUI2.py

Team Summer 2026 started to refactor for ROS2. Changes made:
- Now using TurtleControlProcessor to replace turtleControl.py
- 

Note: Do not start matchPlanner unless the robot is on the ground, otherwise the odometry
will be off.

======================================================================== """

import math

import cv2
import numpy as np
# from espeak import espeak
# import MovementHandler
import PotentialFieldThread
import FieldBehaviors
import Localizer2
import PathLocation
import OutputLogger
import OlinWorldMap
import SeekerGUI2
# from DataPaths import basePath, graphMapData
import time
import LocalizerStringConstants as loc_const
import sys
import os

FOXROBOTLAB_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if FOXROBOTLAB_SRC not in sys.path:
    sys.path.insert(0, FOXROBOTLAB_SRC)

# Server - Client Setup
from turtle_control_processor import TurtleControlProcessor
from client_server.localizer_remote import RemoteLocalizer
from client_server.gui_status_bridge import GuiStatusBridge
from client_server.gui_headless import HeadlessSeekerGUI


USE_REMOTE_LOCALIZER = os.environ.get('FOX_REMOTE_LOCALIZER', '1') != '0'
REMOTE_LOCALIZER_IP = os.environ.get('FOX_LOCALIZER_SERVER_IP', '10.22.21.57')
REMOTE_LOCALIZER_PORT = int(os.environ.get('FOX_LOCALIZER_SERVER_PORT', '62027'))
REMOTE_LOCALIZER_TIMEOUT = float(os.environ.get('FOX_LOCALIZER_TIMEOUT', '2.0'))
USE_GUI_STATUS_BRIDGE = os.environ.get('FOX_GUI_STATUS_BRIDGE', '1') != '0'
GUI_STATUS_SERVER_IP = os.environ.get('FOX_GUI_STATUS_SERVER_IP', REMOTE_LOCALIZER_IP)
GUI_STATUS_SERVER_PORT = int(os.environ.get('FOX_GUI_STATUS_SERVER_PORT', '62029'))
USE_GUI_COMMAND_SERVER = os.environ.get('FOX_GUI_COMMAND_SERVER', '1') != '0'
GUI_COMMAND_SERVER_HOST = os.environ.get('FOX_GUI_COMMAND_SERVER_HOST', '0.0.0.0')
GUI_COMMAND_SERVER_PORT = int(os.environ.get('FOX_GUI_COMMAND_SERVER_PORT', '62030'))
MATCH_LOOP_SLEEP = float(os.environ.get('FOX_MATCH_LOOP_SLEEP', '0.03'))
DISPLAY_WINDOWS = os.environ.get('FOX_DISPLAY_WINDOWS', '0') == '1'
USE_LEGACY_GUI = os.environ.get('FOX_USE_LEGACY_GUI', '0') == '1'


class MatchPlanner(object):

    def __init__(self):

        self.robot = TurtleControlProcessor(spin_in_background=True)
        # print("MatchPlanner: Robot ::: Pause Movement")
        self.robot.pauseMovement()
        self.fHeight, self.fWidth, self.fDepth = self.robot.getImage()[0].shape

        self.brain = None
        self.goalSeeker = None
        self.whichBrain = ""

        if DISPLAY_WINDOWS:
            cv2.namedWindow("MCL Display")
            cv2.moveWindow("MCL Display", 1300, 25)

        self.logger = OutputLogger.OutputLogger(True, False)

        self.olinMap = OlinWorldMap.WorldMap()
        # self.moveHandle = MovementHandler.MovementHandler(self.robot, self.logger)
        self.pathLoc = PathLocation.PathLocation(self.olinMap, self.logger)

        # use x, y, yaw instead of node, yaw because updating odometer offsets require those
        self.startX = None
        self.startY = None
        self.startYaw = None

        self.destinationNode = None

        self.locator = None

        self.ignoreLocationCount = 0

        if USE_LEGACY_GUI:
            legacy_gui = SeekerGUI2.SeekerGUI2(self, self.robot)
        else:
            legacy_gui = HeadlessSeekerGUI(self, self.robot)
        self.gui = GuiStatusBridge(
            legacy_gui,
            GUI_STATUS_SERVER_IP,
            GUI_STATUS_SERVER_PORT,
            enabled=USE_GUI_STATUS_BRIDGE,
            command_host=GUI_COMMAND_SERVER_HOST,
            command_port=GUI_COMMAND_SERVER_PORT,
            command_enabled=USE_GUI_COMMAND_SERVER,
        )
        self.gui.update()

    def run(self):
        """Runs the program for the duration of 'runtime'"""

        iterationCount = 0
        self.setupNavBrain()
        self.brain.pause()
        self.locator = self._createLocator()
        self.gui.updateMessageText('Image localization active; waiting for navigation goal')

        while not self.robot.is_shutdown():
            self.gui.update()
            image = self.robot.getImage()[0]
            if DISPLAY_WINDOWS:
                cv2.imshow("Turtlebot View", image)
                cv_image = self.robot.getDepth()
                cv_image = cv_image.astype(np.uint8)
                im = cv2.normalize(cv_image, None, 0, 255, cv2.NORM_MINMAX)
                ret, im = cv2.threshold(cv_image, 1, 255, cv2.THRESH_BINARY)
                cv2.imshow("Depth View", im)
                cv2.waitKey(20)

            self.logger.log("-------------- New Match ---------------")
            time.sleep(MATCH_LOOP_SLEEP)
            status, nodeAndPose = self.locator.findLocation(image)
            iterationCount += 1

            self._apply_pending_navigation_inputs(nodeAndPose)
            if not self._navigation_ready():
                self.brain.pause()
                self.goalSeeker.setGoal(None, None, None)
                continue

            self._run_navigation_step(status, nodeAndPose)
        self.shutdown()

    def _run_navigation_step(self, status, nodeAndPose):
        """React to the current localization result only after navigation is configured."""

        self.brain.unpause()
        if nodeAndPose is None:
            self.goalSeeker.setGoal(None, None, None)
            return

        """------------------------------------------------------------------------------------------------
        Team Summer 2019 more or less made no changes here and now the behavior in this while loop is out
        of date. Start here to make changes to reactionary behavior.

        lookAround() is currently not utilized. However in some cases it may be helpful i.e. when the
        robot has decided to stare at a wall and not move because it doesn't know where it is.

        Perhaps experiment with ways to reincorporate this behavior.
        ---------------------------------------------------------------------------------------------------"""
        if self.whichBrain == "loc":
            self.lookAround()

        if status == loc_const.temp_lost:  # bestMatch score < 5 but lostCount < 10
            self.goalSeeker.setGoal(None, None, None)
            # self.logger.log("======Goal seeker off")
        elif status == loc_const.keep_going:  # LookAround found a match
            if self.whichBrain != "nav":
                # self.speak("Navigating...")
                self.gui.navigatingMode()
                # self.robot.turnByAngle(35)  # turn back 35 degrees bc the behavior is faster than the matching
                self.brain.unpause()
                self.checkCoordinates(nodeAndPose)  # react to the location data of the match
                self.whichBrain = "nav"
        elif status == loc_const.look:  # enter LookAround behavior
            if self.whichBrain != "loc":
                # self.speak("Localizing...")
                self.gui.localizingMode()
                self.brain.pause()
                self.whichBrain = "loc"
            self.goalSeeker.setGoal(None, None, None)
            self.lookAround()
        else:  # found a node
            if self.whichBrain == "loc":
                self.whichBrain = "nav"
                # self.speak("Navigating...")
                self.gui.navigatingMode()
                self.brain.unpause()
            if status == loc_const.at_node:
                # self.logger.log("Found a good enough match: " + str(matchInfo))
                self.respondToLocation(nodeAndPose)

                if self.pathLoc.atDestination(nodeAndPose[0]):
                    # reached destination. wait for the next destination while localization continues
                    # self.speak("Destination reached")
                    self.robot.stop()
                    self.robot.updateOdomLocation(nodeAndPose[1][0], nodeAndPose[1][1], nodeAndPose[1][2])
                    self.destinationNode = None
                    self.goalSeeker.setGoal(None, None, None)
                    self.gui.updateMessageText('Destination reached; waiting for next goal')
                    # self.logger.log("======Goal seeker off")
                else:
                    h = self.pathLoc.getTargetAngle()
                    currHead = nodeAndPose[1][-1]  # yaw
                    self.goalSeeker.setGoal(self.pathLoc.getCurrentPath()[1], h, currHead)
                    self.checkCoordinates(nodeAndPose)
                    # self.logger.log("=====Updating goalSeeker: " + str(self.pathLoc.getCurrentPath()[1]) + " " +
                    #                 str(h) + " " + str(currHead))

            elif status == loc_const.close:
                self.checkCoordinates(nodeAndPose)
            self.brain.unpause()

    def _createLocator(self):
        if USE_REMOTE_LOCALIZER:
            self.logger.log(
                "Using remote localizer at {0}:{1}".format(
                    REMOTE_LOCALIZER_IP,
                    REMOTE_LOCALIZER_PORT,
                )
            )
            return RemoteLocalizer(
                self.robot,
                REMOTE_LOCALIZER_IP,
                REMOTE_LOCALIZER_PORT,
                timeout=REMOTE_LOCALIZER_TIMEOUT,
                gui=self.gui,
            )

        self.logger.log("Using local odometry localizer")
        return Localizer2.LocalizerOdom(self.robot, self.olinMap, self.logger, self.gui)

    def _apply_pending_navigation_inputs(self, nodeAndPose):
        start_fields = self._pop_pending_start()
        if start_fields is not None:
            self._set_start_from_fields(start_fields, nodeAndPose)

        goal_fields = self._pop_pending_goal()
        if goal_fields is not None:
            self._set_goal_from_fields(goal_fields, nodeAndPose)

    def _pop_pending_start(self):
        if hasattr(self.gui, 'popPendingStart'):
            return self.gui.popPendingStart()
        return None

    def _pop_pending_goal(self):
        if hasattr(self.gui, 'popPendingGoal'):
            return self.gui.popPendingGoal()
        return None

    def _set_start_from_fields(self, fields, nodeAndPose):
        pose = self._parse_start_pose(
            str(fields.get('location', '')).strip(),
            str(fields.get('yaw', '')).strip(),
            nodeAndPose,
        )
        if pose is None:
            self.gui.updateMessageText('Invalid start input; localization continues')
            return False

        self.startX, self.startY, self.startYaw = pose
        self.robot.updateOdomLocation(x=self.startX, y=self.startY, yaw=self.startYaw)
        self.gui.updateMessageText(
            'Start set to ({0:.2f}, {1:.2f}, {2:.2f})'.format(
                self.startX,
                self.startY,
                self.startYaw,
            )
        )
        if self.destinationNode is not None:
            self.pathLoc.beginJourney(self.destinationNode)
        return True

    def _set_goal_from_fields(self, fields, nodeAndPose):
        destination = self._parse_destination(str(fields.get('destination', '')).strip())
        if destination is None:
            self.gui.updateMessageText('Invalid destination input; localization continues')
            return False
        if destination == -1:
            self.shutdown()
            return False

        if self.startYaw is None:
            self._use_current_pose_as_start(nodeAndPose)
        if self.startYaw is None:
            self.gui.updateMessageText('Waiting for a valid localized pose before starting navigation')
            return False

        self.destinationNode = destination
        self.pathLoc.beginJourney(self.destinationNode)
        self.robot.unpauseMovement()
        self.gui.updateMessageText('Goal set to {0}; navigation enabled'.format(self.destinationNode))
        return True

    def _parse_start_pose(self, location_text, yaw_text, nodeAndPose):
        current_pose = nodeAndPose[1] if nodeAndPose is not None else None
        if not location_text:
            if current_pose is None:
                return None
            userX, userY = current_pose[0], current_pose[1]
        else:
            location_parts = location_text.split()
            try:
                if len(location_parts) == 1:
                    userNode = int(location_parts[0])
                    if not self.olinMap.isValidNode(userNode):
                        return None
                    userX, userY = self.olinMap._nodeToCoord(userNode)
                elif len(location_parts) == 2:
                    userX = float(location_parts[0])
                    userY = float(location_parts[1])
                else:
                    return None
            except (TypeError, ValueError):
                return None

        try:
            userYaw = float(yaw_text) if yaw_text else current_pose[2]
        except (TypeError, ValueError, IndexError):
            return None
        return userX, userY, userYaw

    def _parse_destination(self, destination_text):
        try:
            destination = int(destination_text)
        except (TypeError, ValueError):
            return None
        if destination == -1 or self.olinMap.isValidNode(destination):
            return destination
        return None

    def _use_current_pose_as_start(self, nodeAndPose):
        if nodeAndPose is None:
            return
        pose = nodeAndPose[1]
        self.startX, self.startY, self.startYaw = pose[0], pose[1], pose[2]
        self.gui.updateMessageText(
            'Using current localized pose as start: ({0:.2f}, {1:.2f}, {2:.2f})'.format(
                self.startX,
                self.startY,
                self.startYaw,
            )
        )

    def _navigation_ready(self):
        return self.startYaw is not None and self.destinationNode is not None

    def getStartLocation(self, nextDest=False):
        #self.brain.pause()
        if nextDest:
            self.startX, self.startY, self.startYaw = self.robot.getOdomData()
        else:
            self.startX, self.startY, self.startYaw = self._userStartLoc()
        if self.startYaw == -1 or self.startYaw is None:
            return False, None
        self.robot.updateOdomLocation(x=self.startX, y=self.startY, yaw=self.startYaw)

        return True, loc_const.at_node

    def getNextGoalDestination(self):
        """Gets goal from user and sets up path location tracker etc. Returns False if
        the user wants to quit."""
        self.brain.pause()
        self.destinationNode = self._userGoalDest()
        if self.destinationNode == -1:
            return False
        self.pathLoc.beginJourney(self.destinationNode)
        # self.speak("Heading to " + str(self.destinationNode))
        self.brain.unpause()
        return True

    def _userStartLoc(self):
        self.gui.popupStart()
        userInputLoc = self.gui.inputStartLoc()
        userInputYaw = self.gui.inputStartYaw()
        # #where it is a choice to pick node or loc pop ups
        # self.gui.askWhich()
        # userInputX = self.gui.userInputStartX
        # userInputY = self.gui.userInputStartY

        self.logger.log("User input: {0} {1}".format(userInputLoc, userInputYaw))

        userLocList = userInputLoc.split()

        # node
        if len(userLocList) == 1:
            userNode = int(userLocList[0])
            self.logger.log("User node: " + str(userNode))
            if self.olinMap.isValidNode(userNode) or userNode != -1:
                userX, userY = self.olinMap._nodeToCoord(userNode)
                self.logger.log("User x, y: {0}, {1}".format(userX, userY))
            else:
                return -1,-1,-1
        # x y
        elif len(userLocList) == 2:
            userX = float(userLocList[0])
            userY = float(userLocList[1])

        return userX, userY, float(userInputYaw)

    def _userGoalDest(self):
        """Asks the user for a goal destination or -1 to cause the robot to shut down."""
        # while True:
        #     userInp = raw_input("Enter destination index (-1 to quit): ")
        #     if userInp.isdigit():
        #         userNum = int(userInp)
        #         if self.olinMap.isValidNode(userNum) or userNum == -1:
        #             return userNum
        self.gui.popupDest()
        userInput = self.gui.inputDes()
        userNum = int(userInput)
        if self.olinMap.isValidNode(userNum) or userNum == -1:
            return userNum

    def setupNavBrain(self):
        """Sets up the potential field brain with access to the robot's sensors and motors, and add the
        KeepMoving, BumperReact, and CliffReact behaviors, along with ObstacleForce behaviors for six regions
        of the depth data. TODO: Figure out how to add a positive pull toward the next location?"""
        self.whichBrain = "nav"
        # self.speak("matchPlanner.setupNavBrain: Navigating Brain Activated")
        self.brain = PotentialFieldThread.PotentialFieldBrain(self.robot)
        self.brain.pause()
        self.brain.add(FieldBehaviors.KeepMoving())
        self.brain.add(FieldBehaviors.BumperReact())
        self.brain.add(FieldBehaviors.CliffReact())
        self.goalSeeker = FieldBehaviors.seekGoal()
        self.brain.add(self.goalSeeker)
        numPieces = 6
        widthPieces = int(math.floor(self.fWidth / float(numPieces)))
        speedMultiplier = 50
        for i in range(0, numPieces):
            obstBehavior = FieldBehaviors.ObstacleForce(i * widthPieces,
                                                        widthPieces / 2,
                                                        speedMultiplier,
                                                        self.fWidth,
                                                        self.fHeight)
            self.brain.add(obstBehavior)
            # The way these pieces are made leads to the being slightly more responsive to its left side
            # further investigation into this could lead to a more uniform obstacle reacting
        self.brain.start()
        self.brain.pause()

    def respondToLocation(self, matchInfo):
        """Given information about a location that matches this one "enough". Uses the heading data from the match
        to determine how to turn to face the next node it should head to.
        Returns True if the robot has arrived at its final goal location, otherwise, False.
        First: gets the last node in the path the robot has traveled. If that node is different from the new
        match information, OR if they are the same but a long time has passed, then record that the robot
        has reached this location, determine which direction the robot should go next, and turn toward that
        direction.
        matchInfo format = [nearNode, (x, y), heading)]"""

        assert matchInfo is not None

        # self.logger.log("*******")
        # self.logger.log("Responding to Location Reached")
        self.ignoreLocationCount += 1  # Incrementing time counter to avoid responding to location for a while

        nearNode = matchInfo[0]

        if self.pathLoc.visitNewNode(nearNode) or self.ignoreLocationCount > 50:
            self.ignoreLocationCount = 0
            self.pathLoc.continueJourney(nearNode)

            # speakStr = "At node " + str(nearNode)
            # self.speak(speakStr)

    def checkCoordinates(self, localizePose):
        """Check the current match information to see if we should change headings. If node that is
        confidently "not close enough" is what we expect, then make sure heading is right. Otherwise,
        if it is a neighbor of one of the expected nodes, then turn to move toward that node.
        If it is further in the path, should do something, but not doing it now.
        MatchInfo format: (nearNode, location of x, y, and heading)"""
        currPath = self.pathLoc.getCurrentPath()
        if currPath is None or currPath == []:
            return

        (nearNode, currLoc) = localizePose
        justVisitedNode = currPath[0]
        immediateGoalNode = currPath[1]
        self.logger.log("------------- matchPlanner.checkCoordinates: Checking coordinates -----")

        # if nearNode == currPath[-1]:
        #     self.respondToLocation(localizePose)

        if nearNode == justVisitedNode or nearNode == immediateGoalNode:
            nextNode = immediateGoalNode
            self.logger.log("Nearest node is previous node or current goal")
        elif nearNode in currPath:
            self.logger.log(
                "Nearest node is on current path, may have missed current goal")  # TODO: What is best response here
            pathInd = currPath.index(nearNode)
            if len(currPath) > pathInd + 1 and self.olinMap.calcAngle(currLoc, currPath[pathInd + 1]) < 20:
                nextNode = currPath[pathInd + 1]
            else:
                nextNode = nearNode
        elif self.olinMap.areNeighbors(nearNode, immediateGoalNode):
            self.logger.log("Nearest node is adjacent to current goal but not in path")
            nextNode = immediateGoalNode
        elif self.olinMap.areNeighbors(nearNode, justVisitedNode):
            # If near node just visited, but not near next goal, and not in path already, return to just visited
            self.logger.log("Nearest node is adjacent to previous node but not in path")
            nextNode = justVisitedNode
        else:  # near a node but you don't need to be there!
            self.logger.log("Nearest node is not on/near path")
            if type(nearNode) == str:  # when node is x or y
                nextNode = immediateGoalNode
            else:
                nextNode = nearNode

        targetAngle = self.olinMap.calcAngle(currLoc, nextNode)
        tDist = self.olinMap.straightDist2d(currLoc, nextNode)
        self.gui.updateNextNode(nextNode)
        if tDist >= 1.5:
            self.turn(nextNode, currLoc[2], targetAngle, tDist)
        else:
            self.logger.log("Not Turning. TDist = " + str(tDist))

    def turn(self, node, heading, targetHeading, tDist):
        # adjust heading based on previous if statement
        targetHeading = targetHeading % 360
        angle1 = abs(heading - targetHeading)
        angle2 = 360 - angle1

        if min(angle1, angle2) >= 90:
            self.gui.updateTurnState("Turning to node " + str(node))
            # self.speak("Adjusting heading to node " + str(node))
            self.turnToNextTarget(heading, targetHeading)
            self.goalSeeker.setGoal(None, None, None)
            self.gui.endTurn()
        elif min(angle1, angle2) >= 30:
            self.gui.updateTurnState("Turning to node " + str(node))
            self.turnToNextTarget(heading, targetHeading)
            self.gui.endTurn()
        else:
            # self.goalSeeker.setGoal(tDist, targetHeading, heading)
            self.goalSeeker.setGoal(None, None, None)
            formSt = "Angle1 = {0:4.2f}     Angle2 = {1:4.2f}"  #: target distance = {0:4.2f}  target heading = {1:4.2f}  current heading = {2:4.2f}"
            self.logger.log(formSt.format(angle1, angle2))  # .format(tDist, targetHeading, heading) )

        self.logger.log("  targetDistance = " + str(tDist))
        self.gui.updateTDist(tDist)

    def lookAround(self):
        """turns. stops. waits."""
        self.robot.turnByAngle(-35)
        self.robot.stop()

    def turnToNextTarget(self, currHeading, targetAngle):
        """Takes in the currentHeading, which comes from the heading attached to the current best matching picture,
        given in global coordinates. Also takes in the target angle, also in global coordinates. This function computes
        the angle the robot should turn.
        NOTE: Could try to use depth data to modify angle if facing a wall well enough..."""

        angleToTurn = targetAngle - (currHeading % 360)
        if angleToTurn < -180:
            angleToTurn += 360
        elif 180 < angleToTurn:
            angleToTurn -= 360

        self.logger.log("Turning to next target...")
        self.logger.log("  currHeading = " + str(currHeading))
        self.logger.log("  targetAngle = " + str(targetAngle))
        self.logger.log("  angleToTurn = " + str(angleToTurn))

        self.gui.updateTurnInfo([currHeading, targetAngle, angleToTurn])
        self.gui.update()

        self.brain.pause()
        self.robot.turnByAngle(angleToTurn)
        self.brain.unpause()

    # def speak(self, speakStr):
    #     """Takes in a string and "speaks" it to the base station and also to the  robot's computer."""
    #     espeak.set_voice("english-us", gender=2, age=60)
    #     espeak.synth(speakStr)  # nodeNum, nodeCoord, heading = matchInfo
    #     self.pub.publish(speakStr)
    #     self.gui.updateMessageText(speakStr)
    #     self.logger.log(speakStr)

    def shutdown(self):
        # TODO: This doesn't actually shut down all the way
        self.logger.log("Quitting...")
        self.logger.close()
        self.robot.stop()
        self.gui.stop()
        self.brain.stop()  # was stopAll
        if DISPLAY_WINDOWS:
            cv2.destroyAllWindows()
        if self.locator is not None and hasattr(self.locator, 'close'):
            self.locator.close()
        self.robot.shutdown()
        sys.exit(0)

if __name__ == "__main__":
    plan = MatchPlanner()
    plan.run()
