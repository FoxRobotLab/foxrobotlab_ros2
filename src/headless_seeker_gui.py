#!/usr/bin/env python3


class HeadlessSeekerGUI:
    def __init__(self, match_planner, turtle_bot):
        self.matchPlanner = match_planner
        self.turtleBot = turtle_bot
        self._start_location = ''
        self._start_yaw = ''
        self._destination = ''

    def popupStart(self):
        pass

    def inputStartLoc(self):
        return self._start_location

    def inputStartYaw(self):
        return self._start_yaw

    def popupDest(self):
        pass

    def inputDes(self):
        return self._destination

    def updateMessageText(self, text):
        print(text)

    def updateOdomList(self, loc):
        pass

    def updateLastKnownList(self, loc):
        pass

    def updateMCLList(self, loc):
        pass

    def updatePicLocs(self, loc1, loc2, loc3):
        pass

    def updatePicConf(self, scores):
        pass

    def updateTurnState(self, statement):
        pass

    def updateTurnInfo(self, turnData):
        pass

    def endTurn(self):
        pass

    def toggleMotors(self):
        if self.turtleBot.movement_paused:
            self.turtleBot.unpauseMovement()
        else:
            self.turtleBot.pauseMovement()

    def quitProgram(self):
        self.matchPlanner.shutdown()

    def updateTDist(self, dist):
        pass

    def updateCNode(self, closestNode):
        pass

    def updateNextNode(self, node):
        pass

    def updateRadius(self, radius):
        pass

    def updateMatchStatus(self, status):
        pass

    def updateNavType(self, nav_type):
        pass

    def navigatingMode(self):
        pass

    def localizingMode(self):
        pass

    def tilePrediction(self):
        pass

    def carpetPrediction(self):
        pass

    def stop(self):
        pass

    def update(self):
        pass
