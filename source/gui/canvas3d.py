############################################################################
#
#   Copyright (C) 2015
#    Jean-Paul Schouwstra
#
#   This file is part of DXF2GCODE.
#
#   DXF2GCODE is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   DXF2GCODE is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with DXF2GCODE.  If not, see <http://www.gnu.org/licenses/>.
#
############################################################################

from __future__ import absolute_import
from __future__ import division

from math import pi, cos, sin, radians
import logging

from PyQt5.QtCore import QPoint, Qt, QCoreApplication
from PyQt5.QtGui import QColor, QOpenGLVersionProfile

from core.layercontent import Shapes
from core.point import Point
from core.point3d import Point3D
from core.stmove import StMove
import globals.globals as g
from gui.canvas import CanvasBase, MyDropDownMenu


logger = logging.getLogger("Gui.Canvas")


class GLWidget(CanvasBase):
    CAM_LEFT_X = -0.5
    CAM_RIGHT_X = 0.5
    CAM_BOTTOM_Y = 0.5
    CAM_TOP_Y = -0.5
    CAM_NEAR_Z = -14.0
    CAM_FAR_Z = 14.0

    COLOR_BACKGROUND = QColor.fromHsl(160, 0, 255, 255)
    COLOR_NORMAL = QColor.fromCmykF(1.0, 0.5, 0.0, 0.0, 1.0)
    COLOR_SELECT = QColor.fromCmykF(0.0, 1.0, 0.9, 0.0, 1.0)
    COLOR_NORMAL_DISABLED = QColor.fromCmykF(1.0, 0.5, 0.0, 0.0, 0.25)
    COLOR_SELECT_DISABLED = QColor.fromCmykF(0.0, 1.0, 0.9, 0.0, 0.25)
    COLOR_ENTRY_ARROW = QColor.fromRgbF(0.0, 0.0, 1.0, 1.0)
    COLOR_EXIT_ARROW = QColor.fromRgbF(0.0, 1.0, 0.0, 1.0)
    COLOR_ROUTE = QColor.fromRgbF(0.5, 0.0, 0.0, 1.0)
    COLOR_STMOVE = QColor.fromRgbF(0.5, 0.0, 0.25, 1.0)
    COLOR_BREAK = QColor.fromRgbF(1.0, 0.0, 1.0, 0.7)
    COLOR_LEFT = QColor.fromHsl(134, 240, 130, 255)
    COLOR_RIGHT = QColor.fromHsl(186, 240, 130, 255)

    def __init__(self, parent=None):
        super(GLWidget, self).__init__(parent)

        self.shapes = Shapes([])
        self.orientation = 0
        self.wpZero = 0
        self.routearrows = []
        self.expprv = None

        self.isPanning = False
        self.isRotating = False
        self.isMultiSelect = False
        self._lastPos = QPoint()

        self.posX = 0.0
        self.posY = 0.0
        self.posZ = 0.0
        self.rotX = 0.0
        self.rotY = 0.0
        self.rotZ = 0.0
        self.scale = 1.0
        self.scaleCorr = 1.0

        self.showPathDirections = False
        self.showDisabledPaths = False

        self.topLeft = Point()
        self.bottomRight = Point()

        self.tol = 0

    def resetAll(self):
        self.gl.glDeleteLists(1, self.orientation)  # the orientation arrows are currently generated last
        self.shapes = Shapes([])
        self.wpZero = 0
        self.orientation = 0
        self.delete_opt_paths()

        self.posX = 0.0
        self.posY = 0.0
        self.posZ = 0.0
        self.rotX = 0.0
        self.rotY = 0.0
        self.rotZ = 0.0
        self.scale = 1.0

        self.topLeft = Point()
        self.bottomRight = Point()

        self.update()

    def delete_opt_paths(self):
        if len(self.routearrows) > 0:
            self.gl.glDeleteLists(self.routearrows[0][2], len(self.routearrows))
            self.routearrows = []

    def addexproutest(self):
        self.expprv = Point3D(g.config.vars.Plane_Coordinates['axis1_start_end'],
                              g.config.vars.Plane_Coordinates['axis2_start_end'],
                              0)

    def addexproute(self, exp_order, layer_nr):
        """
        This function initialises the Arrows of the export route order and its numbers.
        """
        for shape_nr in range(len(exp_order)):
            shape = self.shapes[exp_order[shape_nr]]
            st = self.expprv
            en, self.expprv = shape.get_start_end_points_physical()
            en = en.to3D(shape.axis3_start_mill_depth)
            self.expprv = self.expprv.to3D(shape.axis3_mill_depth)

            self.routearrows.append([st, en, 0])

            # TODO self.routetext.append(RouteText(text=("%s,%s" % (layer_nr, shape_nr+1)), startp=en))

    def addexprouteen(self):
        st = self.expprv
        en = Point3D(g.config.vars.Plane_Coordinates['axis1_start_end'],
                     g.config.vars.Plane_Coordinates['axis2_start_end'],
                     0)

        self.routearrows.append([st, en, 0])
        for route in self.routearrows:
            route[2] = self.makeRouteArrowHead(route[0], route[1])

    def contextMenuEvent(self, event):
        if not self.isRotating:
            clicked, offset, _ = self.getClickedDetails(event)
            MyDropDownMenu(self, event.globalPos(), clicked, offset)

    def setXRotation(self, angle):
        self.rotX = self.normalizeAngle(angle)

    def setYRotation(self, angle):
        self.rotY = self.normalizeAngle(angle)

    def setZRotation(self, angle):
        self.rotZ = self.normalizeAngle(angle)

    def normalizeAngle(self, angle):
        return (angle - 180) % -360 + 180

    def mousePressEvent(self, event):
        if self.isPanning or self.isRotating:
            self.setCursor(Qt.ClosedHandCursor)
        elif event.button() == Qt.LeftButton:
            clicked, offset, tol = self.getClickedDetails(event)
            xyForZ = {}
            for shape in self.shapes:
                hit = False
                z = shape.axis3_start_mill_depth
                if z not in xyForZ:
                    xyForZ[z] = self.determineSelectedPosition(clicked, z, offset)
                hit |= shape.isHit(xyForZ[z], tol)

                if not hit:
                    z = shape.axis3_mill_depth
                    if z not in xyForZ:
                        xyForZ[z] = self.determineSelectedPosition(clicked, z, offset)
                    hit |= shape.isHit(xyForZ[z], tol)

                if self.isMultiSelect and shape.selected:
                    hit = not hit

                if hit != shape.selected:
                    g.window.TreeHandler.updateShapeSelection(shape, hit)

                shape.selected = hit

            self.update()
        self._lastPos = event.pos()

    def getClickedDetails(self, event):
        min_side = min(self.frameSize().width(), self.frameSize().height())
        clicked = Point((event.pos().x() - self.frameSize().width() / 2),
                        (event.pos().y() - self.frameSize().height() / 2)) / min_side / self.scale
        offset = Point3D(-self.posX, -self.posY, -self.posZ) / self.scale
        tol = 4 * self.scaleCorr / min_side / self.scale
        return clicked, offset, tol

    def determineSelectedPosition(self, clicked, forZ, offset):
        angleX = -radians(self.rotX)
        angleY = -radians(self.rotY)

        zv = forZ - offset.z
        clickedZ = ((zv + clicked.x * sin(angleY)) / cos(angleY) - clicked.y * sin(angleX)) / cos(angleX)
        sx, sy, sz = self.deRotate(clicked.x, clicked.y, clickedZ)
        return Point(sx + offset.x, - sy - offset.y)  #, sz + offset.z

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton or event.button() == Qt.RightButton:
            if self.isPanning:
                self.setCursor(Qt.OpenHandCursor)
            elif self.isRotating:
                self.setCursor(Qt.PointingHandCursor)

    def mouseMoveEvent(self, event):
        dx = event.pos().x() - self._lastPos.x()
        dy = event.pos().y() - self._lastPos.y()

        if self.isRotating:
            if event.buttons() == Qt.LeftButton:
                self.setXRotation(self.rotX - dy / 2)
                self.setYRotation(self.rotY + dx / 2)
            elif event.buttons() == Qt.RightButton:
                self.setXRotation(self.rotX - dy / 2)
                self.setZRotation(self.rotZ + dx / 2)
        elif self.isPanning:
            if event.buttons() == Qt.LeftButton:
                min_side = min(self.frameSize().width(), self.frameSize().height())
                dx, dy, dz = self.deRotate(dx, dy, 0)
                self.posX += dx / min_side
                self.posY += dy / min_side
                self.posZ += dz / min_side

        self._lastPos = event.pos()
        self.update()

    def wheelEvent(self, event):
        min_side = min(self.frameSize().width(), self.frameSize().height())
        x = (event.pos().x() - self.frameSize().width() / 2) / min_side
        y = (event.pos().y() - self.frameSize().height() / 2) / min_side
        s = 1.001 ** event.angleDelta().y()

        x, y, z = self.deRotate(x, y, 0)
        self.posX = (self.posX - x) * s + x
        self.posY = (self.posY - y) * s + y
        self.posZ = (self.posZ - z) * s + z
        self.scale *= s

        self.update()

    def rotate(self, x, y, z):
        angleZ = radians(self.rotZ)
        x, y, z = x*cos(angleZ) - y*sin(angleZ), x*sin(angleZ) + y*cos(angleZ), z
        angleY = radians(self.rotY)
        x, y, z = x*cos(angleY) + z*sin(angleY), y, -x*sin(angleY) + z*cos(angleY)
        angleX = radians(self.rotX)
        return x, y*cos(angleX) - z*sin(angleX), y*sin(angleX) + z*cos(angleX)

    def deRotate(self, x, y, z):
        angleX = -radians(self.rotX)
        x, y, z = x, y*cos(angleX) - z*sin(angleX), y*sin(angleX) + z*cos(angleX)
        angleY = -radians(self.rotY)
        x, y, z = x*cos(angleY) + z*sin(angleY), y, -x*sin(angleY) + z*cos(angleY)
        angleZ = -radians(self.rotZ)
        return x*cos(angleZ) - y*sin(angleZ), x*sin(angleZ) + y*cos(angleZ), z

    def getRotationVectors(self, orgRefVector, toRefVector):
        """
        Generate a rotation matrix such that toRefVector = matrix * orgRefVector
        @param orgRefVector: A 3D unit vector
        @param toRefVector: A 3D unit vector
        @return: 3 vectors such that matrix = [vx; vy; vz]
        """
        # based on:
        # http://math.stackexchange.com/questions/180418/calculate-rotation-matrix-to-align-vector-a-to-vector-b-in-3d

        if orgRefVector == toRefVector:
            return Point3D(1, 0, 0), Point3D(0, 1, 0), Point3D(0, 0, 1)

        v = orgRefVector.cross_product(toRefVector)
        mn = (1 - orgRefVector * toRefVector) / v.length_squared()

        vx = Point3D(1, -v.z, v.y) + mn * Point3D(-v.y**2 - v.z**2, v.x * v.y, v.x * v.z)
        vy = Point3D(v.z, 1, -v.x) + mn * Point3D(v.x * v.y, -v.x**2 - v.z**2, v.y * v.z)
        vz = Point3D(-v.y, v.x, 1) + mn * Point3D(v.x * v.z, v.y * v.z, -v.x**2 - v.y**2)

        return vx, vy, vz

    def initializeGL(self):
        version = QOpenGLVersionProfile()
        version.setVersion(2, 0)
        self.gl = self.context().versionFunctions(version)
        self.gl.initializeOpenGLFunctions()

        self.setClearColor(GLWidget.COLOR_BACKGROUND)

        # self.gl.glPolygonMode(self.gl.GL_FRONT_AND_BACK, self.gl.GL_LINE )
        self.gl.glShadeModel(self.gl.GL_SMOOTH)
        self.gl.glEnable(self.gl.GL_DEPTH_TEST)
        self.gl.glEnable(self.gl.GL_CULL_FACE)
        # self.gl.glEnable(self.gl.GL_LIGHTING)
        # self.gl.glEnable(self.gl.GL_LIGHT0)
        self.gl.glEnable(self.gl.GL_MULTISAMPLE)
        self.gl.glEnable(self.gl.GL_BLEND)
        self.gl.glBlendFunc(self.gl.GL_SRC_ALPHA, self.gl.GL_ONE_MINUS_SRC_ALPHA)
        # self.gl.glLightfv(self.gl.GL_LIGHT0, self.gl.GL_POSITION, (0.5, 5.0, 7.0, 1.0))
        # self.gl.glEnable(self.gl.GL_NORMALIZE)

    def paintGL(self):
        # The last transformation you specify takes place first.
        self.gl.glClear(self.gl.GL_COLOR_BUFFER_BIT | self.gl.GL_DEPTH_BUFFER_BIT)
        self.gl.glLoadIdentity()
        self.gl.glRotatef(self.rotX, 1.0, 0.0, 0.0)
        self.gl.glRotatef(self.rotY, 0.0, 1.0, 0.0)
        self.gl.glRotatef(self.rotZ, 0.0, 0.0, 1.0)
        self.gl.glTranslatef(self.posX, self.posY, self.posZ)
        self.gl.glScalef(self.scale, self.scale, self.scale)
        for shape in self.shapes.selected_iter():
            if not shape.disabled:
                self.setColor(GLWidget.COLOR_STMOVE)
                self.gl.glCallList(shape.drawStMove)
                self.setColor(GLWidget.COLOR_SELECT)
                self.gl.glCallList(shape.drawObject)
            elif self.showDisabledPaths:
                self.setColor(GLWidget.COLOR_SELECT_DISABLED)
                self.gl.glCallList(shape.drawObject)
        for shape in self.shapes.not_selected_iter():
            if not shape.disabled:
                if shape.parentLayer.isBreakLayer():
                    self.setColor(GLWidget.COLOR_BREAK)
                elif shape.cut_cor == 41:
                    self.setColor(GLWidget.COLOR_LEFT)
                elif shape.cut_cor == 42:
                    self.setColor(GLWidget.COLOR_RIGHT)
                else:
                    self.setColor(GLWidget.COLOR_NORMAL)
                self.gl.glCallList(shape.drawObject)
                if self.showPathDirections:
                    self.setColor(GLWidget.COLOR_STMOVE)
                    self.gl.glCallList(shape.drawStMove)
            elif self.showDisabledPaths:
                self.setColor(GLWidget.COLOR_NORMAL_DISABLED)
                self.gl.glCallList(shape.drawObject)

        # optimization route arrows
        self.setColor(GLWidget.COLOR_ROUTE)
        self.gl.glBegin(self.gl.GL_LINES)
        for route in self.routearrows:
            start = route[0]
            end = route[1]
            self.gl.glVertex3f(start.x, -start.y, start.z)
            self.gl.glVertex3f(end.x, -end.y, end.z)
        self.gl.glEnd()

        self.gl.glScalef(self.scaleCorr / self.scale, self.scaleCorr / self.scale, self.scaleCorr / self.scale)
        scaleArrow = self.scale / self.scaleCorr
        for route in self.routearrows:
            end = scaleArrow * route[1]
            self.gl.glTranslatef(end.x, -end.y, end.z)
            self.gl.glCallList(route[2])
            self.gl.glTranslatef(-end.x, end.y, -end.z)

        # direction arrows
        for shape in self.shapes:
            if shape.selected and (not shape.disabled or self.showDisabledPaths) or\
               self.showPathDirections and not shape.disabled:
                start, end = shape.get_start_end_points_physical()
                start = scaleArrow * start.to3D(shape.axis3_start_mill_depth)
                end = scaleArrow * end.to3D(shape.axis3_mill_depth)
                self.gl.glTranslatef(start.x, -start.y, start.z)
                self.gl.glCallList(shape.drawArrowsDirection[0])
                self.gl.glTranslatef(-start.x, start.y, -start.z)
                self.gl.glTranslatef(end.x, -end.y, end.z)
                self.gl.glCallList(shape.drawArrowsDirection[1])
                self.gl.glTranslatef(-end.x, end.y, -end.z)

        self.gl.glCallList(self.wpZero)
        self.gl.glTranslatef(-self.posX / self.scaleCorr, -self.posY / self.scaleCorr, -self.posZ / self.scaleCorr)
        self.gl.glCallList(self.orientation)

    def resizeGL(self, width, height):
        self.gl.glViewport(0, 0, width, height)
        side = min(width, height)
        self.gl.glMatrixMode(self.gl.GL_PROJECTION)
        self.gl.glLoadIdentity()
        if width >= height:
            scale_x = width / height
            self.gl.glOrtho(GLWidget.CAM_LEFT_X * scale_x, GLWidget.CAM_RIGHT_X * scale_x,
                            GLWidget.CAM_BOTTOM_Y, GLWidget.CAM_TOP_Y,
                            GLWidget.CAM_NEAR_Z, GLWidget.CAM_FAR_Z)
        else:
            scale_y = height / width
            self.gl.glOrtho(GLWidget.CAM_LEFT_X, GLWidget.CAM_RIGHT_X,
                            GLWidget.CAM_BOTTOM_Y * scale_y, GLWidget.CAM_TOP_Y * scale_y,
                            GLWidget.CAM_NEAR_Z, GLWidget.CAM_FAR_Z)
        self.scaleCorr = 400 / side
        self.gl.glMatrixMode(self.gl.GL_MODELVIEW)

    def setClearColor(self, c):
        self.gl.glClearColor(c.redF(), c.greenF(), c.blueF(), c.alphaF())

    def setColor(self, c):
        self.setColorRGBA(c.redF(), c.greenF(), c.blueF(), c.alphaF())

    def setColorRGBA(self, r, g, b, a):
        # self.gl.glMaterialfv(self.gl.GL_FRONT, self.gl.GL_DIFFUSE, (r, g, b, a))
        self.gl.glColor4f(r, g, b, a)

    def plotAll(self, shapes):
        for shape in shapes:
            self.paint_shape(shape)
            self.shapes.append(shape)
        self.drawWpZero()
        self.drawOrientationArrows()

    def repaint_shape(self, shape):
        self.gl.glDeleteLists(shape.drawObject, 4)
        self.paint_shape(shape)

    def paint_shape(self, shape):
        shape.drawObject = self.makeShape(shape)  # 1 object
        shape.stmove = StMove(shape)
        shape.drawStMove = self.makeStMove(shape.stmove)  # 1 object
        shape.drawArrowsDirection = self.makeDirArrows(shape)  # 2 objects

    def makeShape(self, shape):
        genList = self.gl.glGenLists(1)
        self.gl.glNewList(genList, self.gl.GL_COMPILE)

        self.gl.glBegin(self.gl.GL_LINES)
        shape.make_path(self.drawHorLine, self.drawVerLine)
        self.gl.glEnd()

        self.gl.glEndList()

        self.topLeft.detTopLeft(shape.topLeft)
        self.bottomRight.detBottomRight(shape.bottomRight)

        return genList

    def makeStMove(self, stmove):
        genList = self.gl.glGenLists(1)
        self.gl.glNewList(genList, self.gl.GL_COMPILE)

        self.gl.glBegin(self.gl.GL_LINES)
        stmove.make_path(self.drawHorLine, self.drawVerLine)
        self.gl.glEnd()

        self.gl.glEndList()

        return genList

    def drawHorLine(self, caller, Ps, Pe):
        self.gl.glVertex3f(Ps.x, -Ps.y, caller.axis3_start_mill_depth)
        self.gl.glVertex3f(Pe.x, -Pe.y, caller.axis3_start_mill_depth)
        self.gl.glVertex3f(Ps.x, -Ps.y, caller.axis3_mill_depth)
        self.gl.glVertex3f(Pe.x, -Pe.y, caller.axis3_mill_depth)

    def drawVerLine(self, caller, Ps):
        self.gl.glVertex3f(Ps.x, -Ps.y, caller.axis3_start_mill_depth)
        self.gl.glVertex3f(Ps.x, -Ps.y, caller.axis3_mill_depth)

    def drawOrientationArrows(self):

        rCone = 0.01
        rCylinder = 0.004
        zTop = 0.05
        zMiddle = 0.02
        zBottom = -0.03
        segments = 20

        arrow = self.gl.glGenLists(1)
        self.gl.glNewList(arrow, self.gl.GL_COMPILE)

        self.drawCone(Point(), rCone, zTop, zMiddle, segments)
        self.drawSolidCircle(Point(), rCone, zMiddle, segments)
        self.drawCylinder(Point(), rCylinder, zMiddle, zBottom, segments)
        self.drawSolidCircle(Point(), rCylinder, zBottom, segments)

        self.gl.glEndList()

        self.orientation = self.gl.glGenLists(1)
        self.gl.glNewList(self.orientation, self.gl.GL_COMPILE)

        self.setColorRGBA(0.0, 0.0, 1.0, 0.5)
        self.gl.glCallList(arrow)

        self.gl.glRotatef(90, 0, 1, 0)
        self.setColorRGBA(1.0, 0.0, 0.0, 0.5)
        self.gl.glCallList(arrow)

        self.gl.glRotatef(90, 1, 0, 0)
        self.setColorRGBA(0.0, 1.0, 0.0, 0.5)
        self.gl.glCallList(arrow)

        self.gl.glEndList()

    def drawWpZero(self):

        r = 0.02
        segments = 20  # must be a multiple of 4

        self.wpZero = self.gl.glGenLists(1)
        self.gl.glNewList(self.wpZero, self.gl.GL_COMPILE)

        self.setColorRGBA(0.2, 0.2, 0.2, 0.7)
        self.drawSphere(r, segments, segments // 4, segments, segments // 4)

        self.gl.glBegin(self.gl.GL_TRIANGLE_FAN)
        self.gl.glVertex3f(0, 0, 0)
        for i in range(segments // 4 + 1):
            ang = -i * 2 * pi / segments
            xy2 = Point().get_arc_point(ang, r)
            # self.gl.glNormal3f(0, -1, 0)
            self.gl.glVertex3f(xy2.x, 0, xy2.y)
        for i in range(segments // 4 + 1):
            ang = -i * 2 * pi / segments
            xy2 = Point().get_arc_point(ang, r)
            # self.gl.glNormal3f(-1, 0, 0)
            self.gl.glVertex3f(0, -xy2.y, -xy2.x)
        for i in range(segments // 4 + 1):
            ang = -i * 2 * pi / segments
            xy2 = Point().get_arc_point(ang, r)
            # self.gl.glNormal3f(0, 0, 1)
            self.gl.glVertex3f(-xy2.y, xy2.x, 0)
        self.gl.glEnd()

        self.setColorRGBA(0.6, 0.6, 0.6, 0.5)
        self.drawSphere(r * 1.25, segments, segments, segments, segments)

        self.gl.glEndList()

    def drawSphere(self, r, lats, mlats, longs, mlongs):
        lats //= 2
        # based on http://www.cburch.com/cs/490/sched/feb8/index.html
        for i in range(mlats):
            lat0 = pi * (-0.5 + i / lats)
            z0 = r * sin(lat0)
            zr0 = r * cos(lat0)
            lat1 = pi * (-0.5 + (i + 1) / lats)
            z1 = r * sin(lat1)
            zr1 = r * cos(lat1)
            self.gl.glBegin(self.gl.GL_QUAD_STRIP)
            for j in range(mlongs + 1):
                lng = 2 * pi * j / longs
                x = cos(lng)
                y = sin(lng)

                self.gl.glNormal3f(x * zr0, y * zr0, z0)
                self.gl.glVertex3f(x * zr0, y * zr0, z0)
                self.gl.glNormal3f(x * zr1, y * zr1, z1)
                self.gl.glVertex3f(x * zr1, y * zr1, z1)
            self.gl.glEnd()

    def drawSolidCircle(self, origin, r, z, segments):
        self.gl.glBegin(self.gl.GL_TRIANGLE_FAN)
        # self.gl.glNormal3f(0, 0, -1)
        self.gl.glVertex3f(origin.x, -origin.y, z)
        for i in range(segments + 1):
            ang = -i * 2 * pi / segments
            xy2 = origin.get_arc_point(ang, r)
            self.gl.glVertex3f(xy2.x, -xy2.y, z)
        self.gl.glEnd()

    def drawCone(self, origin, r, zTop, zBottom, segments):
        self.gl.glBegin(self.gl.GL_TRIANGLE_FAN)
        self.gl.glVertex3f(origin.x, -origin.y, zTop)
        for i in range(segments + 1):
            ang = i * 2 * pi / segments
            xy2 = origin.get_arc_point(ang, r)

            # self.gl.glNormal3f(xy2.x, -xy2.y, zBottom)
            self.gl.glVertex3f(xy2.x, -xy2.y, zBottom)
        self.gl.glEnd()

    def drawCylinder(self, origin, r, zTop, zBottom, segments):
        self.gl.glBegin(self.gl.GL_QUAD_STRIP)
        for i in range(segments + 1):
            ang = i * 2 * pi / segments
            xy = origin.get_arc_point(ang, r)

            # self.gl.glNormal3f(xy.x, -xy.y, 0)
            self.gl.glVertex3f(xy.x, -xy.y, zTop)
            self.gl.glVertex3f(xy.x, -xy.y, zBottom)
        self.gl.glEnd()

    def makeDirArrows(self, shape):
        (start, start_dir), (end, end_dir) = shape.get_start_end_points_physical(None, False)

        startArrow = self.gl.glGenLists(1)
        self.gl.glNewList(startArrow, self.gl.GL_COMPILE)
        self.setColor(GLWidget.COLOR_ENTRY_ARROW)
        self.drawDirArrow(Point3D(), start_dir.to3D(), True)
        self.gl.glEndList()

        endArrow = self.gl.glGenLists(1)
        self.gl.glNewList(endArrow, self.gl.GL_COMPILE)
        self.setColor(GLWidget.COLOR_EXIT_ARROW)
        self.drawDirArrow(Point3D(), end_dir.to3D(), False)
        self.gl.glEndList()

        return startArrow, endArrow

    def drawDirArrow(self, origin, direction, startError):
        offset = 0.0 if startError else 0.05
        zMiddle = -0.02 + offset
        zBottom = -0.05 + offset
        rx, ry, rz = self.getRotationVectors(Point3D(0, 0, 1), direction)

        self.drawArrowHead(origin, rx, ry, rz, offset)

        self.gl.glBegin(self.gl.GL_LINES)
        zeroMiddle = Point3D(0, 0, zMiddle)
        self.gl.glVertex3f(zeroMiddle * rx + origin.x, -zeroMiddle * ry - origin.y, zeroMiddle * rz + origin.z)
        zeroBottom = Point3D(0, 0, zBottom)
        self.gl.glVertex3f(zeroBottom * rx + origin.x, -zeroBottom * ry - origin.y, zeroBottom * rz + origin.z)
        self.gl.glEnd()

    def makeRouteArrowHead(self, start, end):
        if end == start:
            direction = Point3D(0, 0, 1)
        else:
            direction = (end - start).unit_vector()
        rx, ry, rz = self.getRotationVectors(Point3D(0, 0, 1), direction)

        head = self.gl.glGenLists(1)
        self.gl.glNewList(head, self.gl.GL_COMPILE)
        self.drawArrowHead(Point3D(), rx, ry, rz, 0)
        self.gl.glEndList()
        return head

    def drawArrowHead(self, origin, rx, ry, rz, offset):
        r = 0.01
        segments = 10
        zTop = 0 + offset
        zBottom = -0.02 + offset

        self.gl.glBegin(self.gl.GL_TRIANGLE_FAN)
        zeroTop = Point3D(0, 0, zTop)
        self.gl.glVertex3f(zeroTop * rx + origin.x, -zeroTop * ry - origin.y, zeroTop * rz + origin.z)
        for i in range(segments + 1):
            ang = i * 2 * pi / segments
            xy2 = Point().get_arc_point(ang, r).to3D(zBottom)
            self.gl.glVertex3f(xy2 * rx + origin.x, -xy2 * ry - origin.y, xy2 * rz + origin.z)
        self.gl.glEnd()

        self.gl.glBegin(self.gl.GL_TRIANGLE_FAN)
        zeroBottom = Point3D(0, 0, zBottom)
        self.gl.glVertex3f(zeroBottom * rx + origin.x, -zeroBottom * ry - origin.y, zeroBottom * rz + origin.z)
        for i in range(segments + 1):
            ang = -i * 2 * pi / segments
            xy2 = Point().get_arc_point(ang, r).to3D(zBottom)
            self.gl.glVertex3f(xy2 * rx + origin.x, -xy2 * ry - origin.y, xy2 * rz + origin.z)
        self.gl.glEnd()

    def setShowPathDirections(self, flag):
        self.showPathDirections = flag

    def setShowDisabledPaths(self, flag=True):
        self.showDisabledPaths = flag

    def autoscale(self):
        # TODO currently only works correctly when object is not rotated
        if self.frameSize().width() >= self.frameSize().height():
            aspect_scale_x = self.frameSize().width() / self.frameSize().height()
            aspect_scale_y = 1
        else:
            aspect_scale_x = 1
            aspect_scale_y = self.frameSize().height() / self.frameSize().width()
        scaleX = (GLWidget.CAM_RIGHT_X - GLWidget.CAM_LEFT_X) * aspect_scale_x / (self.bottomRight.x - self.topLeft.x)
        scaleY = (GLWidget.CAM_BOTTOM_Y - GLWidget.CAM_TOP_Y) * aspect_scale_y / (self.topLeft.y - self.bottomRight.y)
        self.scale = min(scaleX, scaleY) * 0.95
        self.posX = ((GLWidget.CAM_LEFT_X + GLWidget.CAM_RIGHT_X) * 0.95 * aspect_scale_x
                     - (self.topLeft.x + self.bottomRight.x) * self.scale) / 2
        self.posY = -((GLWidget.CAM_TOP_Y + GLWidget.CAM_BOTTOM_Y) * 0.95 * aspect_scale_y
                      - (self.topLeft.y + self.bottomRight.y) * self.scale) / 2
        self.posZ = 0
        self.update()

    def topView(self):
        self.rotX = 0
        self.rotY = 0
        self.rotZ = 0
        self.update()

    def isometricView(self):
        self.rotX = -22
        self.rotY = -22
        self.rotZ = 0
        self.update()
