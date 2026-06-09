import math
import LocalizerStringConstants as loc_const

class LocalizerOdom(object):
    def __init__(self, bot, mapGraph, logger, gui):
        self.robot = bot
        self.olin = mapGraph
        self.logger = logger
        self.gui = gui
        self.lostCount = 0
        self.closeEnough = 0.7
        self.lastKnownLoc = None
        self.confidence = 100.0
        self.odomScore = 100.0
        self.navType = "ODOM"
        
    def findLocation(self, cameraImage):
        odom_location = self.odometer()

        if self.lastKnownLoc is None:
            self.lastKnownLoc = odom_location
            self.logger.log('Last known loc: None so far')
            self.gui.updateLastKnownList([0, 0, 0, self.confidence])
        else:
            last_loc_string = 'Last known loc: ({0:4.2f}, {1:4.2f}, {2:4.2f})'
            (x, y, h) = self.lastKnownLoc
            self.logger.log(last_loc_string.format(x, y, h))
            self.gui.updateLastKnownList([x, y, h, self.confidence])

        if self.navType != "ODOM":
            self.navType = "ODOM"
        self.gui.updateNavType(self.navType)

        near_node, node_x, node_y, best_dist = self.olin.findClosestNode(odom_location)
        cell = int(self.olin.convertLocToCell(odom_location))
        node_and_pose = cell, odom_location

        if best_dist <= self.closeEnough and self.isClose(odom_location, (node_x, node_y, 0)):
            response = loc_const.at_node, node_and_pose
        else:
            response = loc_const.close, node_and_pose

        self.lastKnownLoc = odom_location
        self.gui.updateCNode(near_node)
        self.gui.updateMatchStatus("odometry only")
        
        return response

    def odometer(self):
        """
        :return: the odometry data from the robot
        """
        formStr = "Odometer loc: ({0:4.2f}, {1:4.2f}, {2:4.2f})  confidence = {3:4.2f}"
        x, y, yaw = self.robot.getOdomData()
        self.logger.log(formStr.format(x, y, yaw, self.odomScore))
        self.gui.updateOdomList([x, y, yaw, self.odomScore])
        self.odomScore = max(0.01, self.odomScore - 0.1)

        if self.robot.hasWheelDrop():
            self.odomScore = 0.01

        if not self.olin.isAllowedLocation((x, y)):
            self.odomScore = max(0.01, self.odomScore - 4) # TODO: test different out-of-bounds penalties
            cell, x, y, _ = self.olin.findClosestNode(self.robot.getOdomData())
            inbounds_loc = self.closest_bound_pt(cell, self.robot.getOdomData()[0], self.robot.getOdomData()[1])

            self.robot.updateOdomLocation(inbounds_loc[0], inbounds_loc[1], self.robot.getOdomData()[2])
            x = inbounds_loc[0]
            y = inbounds_loc[1]

        return x, y, yaw

    def closest_bound_pt(self, cell, robot_x, robot_y):
        print("Out of bounds!")

        cornerpts = self.olin.cellData[cell]
        # Add/subtract 0.2 to nudge the robot back in bounds.
        x1 = cornerpts[0] + 0.2
        x2 = cornerpts[2] - 0.2
        y1 = cornerpts[1] + 0.2
        y2 = cornerpts[3] - 0.2
        bounding_pts = [(x1, y1), (x1, y1 + .25 * (y2 - y1)), (x1, y1 + .5 * (y2 - y1)), (x1, y1 + .75 * (y2 - y1)),
                        (x1, y2), (x1 + .25 * (x2 - x1), y2), (x1 + .5 * (x2 - x1), y2), (x1 + .75 * (x2 - x1), y2),
                        (x2, y2), (x1 + .25 * (x2 - x1), y1), (x1 + .5 * (x2 - x1), y1), (x1 + .75 * (x2 - x1), y1),
                        (x2, y1), (x2, y1 + .25 * (y2 - y1)), (x2, y1 + .5 * (y2 - y1)), (x2, y1 + .75 * (y2 - y1))]
        xr = robot_x
        yr = robot_y
        best_dist = 99
        best_pt = None
        for pt in bounding_pts:
            x1 = pt[0]
            y1 = pt[1]
            dist = math.sqrt((x1 - xr)**2 + (y1 - yr)**2)
            if dist < best_dist:
                best_dist = dist
                best_pt = (x1, y1)
        return best_pt
    
    def isClose(self, odomLoc, bestLoc):
        odomX, odomY, _ = odomLoc
        bestX, bestY, _ = bestLoc
        dist = math.hypot(odomX - bestX, odomY - bestY)
        return dist <= 1 #was 5


Localizer = LocalizerOdom
