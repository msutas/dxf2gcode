# -*- coding: utf-8 -*-

############################################################################
#
#   Copyright (C) 2014-2015
#    Robert Lichtenberger
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

from PyQt4 import QtCore

from Core.LineGeo import LineGeo
from Core.ArcGeo import ArcGeo
from Core.BreakGeo import BreakGeo
from Core.Point import Point
from math import sqrt, copysign

import logging
logger = logging.getLogger("PostPro.Breaks")

class Breaks(QtCore.QObject):
    """
    The Breaks Class includes the functions for processing shapes on layers named BREAKS: to break closed shapes so that
    the resulting G-Code will contain rests for the workpiece.
    """
    def __init__(self, layerContents):
        self.layerContents = layerContents

    def process(self):
        """
        Process layerContents: Each non-BREAKS: layers shapes are checked against all the shapes in all BREAKS: layers.
        If a shape is intersected twice by a break-shape, the shape will be broken.
        """
        breakLayers = []
        processLayers = []
        for layerContent in self.layerContents:
            if layerContent.isBreakLayer():
                breakLayers.append(layerContent)
            elif not layerContent.should_ignore():
                processLayers.append(layerContent)

        logger.debug("Found %d break layers and %d processing layers" % (len(breakLayers), len(processLayers)) )
        if (len(breakLayers) > 0 and len(processLayers) > 0):
            self.doProcess(breakLayers, processLayers)

    def doProcess(self, breakLayers, processLayers):
        for layer in processLayers:
            for shape in layer.shapes:
                self.breakShape(shape, breakLayers)

    def breakShape(self, shape, breakLayers):
        newGeos = []
        for geo in shape.geos:
            if (isinstance(geo, LineGeo)):
                newGeos.extend(self.breakLineGeo(geo, breakLayers))
            elif isinstance(geo, ArcGeo):
                newGeos.extend(self.breakArcGeo(geo, breakLayers))
            else:
                newGeos.append(geo)
        shape.geos = newGeos

    def breakLineGeo(self, lineGeo, breakLayers):
        """
        Try to break passed lineGeo with any of the shapes on a break layers.
        Will break lineGeos recursively.
        @return: The list of geometries after breaking (lineGeo itself if no breaking happened)
        """
        newGeos = []
        for breakLayer in breakLayers:
            for breakShape in breakLayer.shapes:
                intersections = self.intersectLineGeometry(lineGeo, breakShape)
                if len(intersections) == 2:
                    (near, far) = self.classifyIntersections(lineGeo, intersections)
                    logger.debug("Line %s broken from (%f, %f) to (%f, %f)" % (lineGeo.toShortString(), near.x, near.y, far.x, far.y))
                    newGeos.extend(self.breakLineGeo(LineGeo(lineGeo.Pa, near), breakLayers))
                    newGeos.append(BreakGeo(LineGeo(near, far), breakLayer.axis3_mill_depth, breakLayer.f_g1_plane, breakLayer.f_g1_depth))
                    newGeos.extend(self.breakLineGeo(LineGeo(far, lineGeo.Pe), breakLayers))
                    return newGeos
        return [lineGeo]

    def breakArcGeo(self, arcGeo, breakLayers):
        """
        Try to break passed arcGeo with any of the shapes on a break layers.
        Will break arcGeos recursively.
        @return: The list of geometries after breaking (arcGeo itself if no breaking happened)
        """
        newGeos = []
        for breakLayer in breakLayers:
            for breakShape in breakLayer.shapes:
                intersections = self.intersectArcGeometry(arcGeo, breakShape)
                if len(intersections) == 2:
                    (near, far) = self.classifyIntersections(arcGeo, intersections)
                    logger.debug("Arc %s broken from (%f, %f) to (%f, %f)" % (arcGeo.toShortString(), near.x, near.y, far.x, far.y))
                    newGeos.extend(self.breakArcGeo(ArcGeo(Pa=arcGeo.Pa, Pe=near, O=arcGeo.O, r=arcGeo.r, s_ang=arcGeo.s_ang, direction=arcGeo.ext), breakLayers))
                    newGeos.append(BreakGeo(LineGeo(near, far), breakLayer.axis3_mill_depth, breakLayer.f_g1_plane, breakLayer.f_g1_depth))
                    newGeos.extend(self.breakArcGeo(ArcGeo(Pa=far, Pe=arcGeo.Pe, O=arcGeo.O, r=arcGeo.r, e_ang=arcGeo.e_ang, direction=arcGeo.ext), breakLayers))
                    return newGeos
        return [arcGeo]

    def intersectLineGeometry(self, lineGeo, breakShape):
        """
        Try to break lineGeo with the given breakShape. Will return the intersection points of lineGeo with breakShape.
        """
        intersections = []
        line = QtCore.QLineF(lineGeo.Pa.x, lineGeo.Pa.y, lineGeo.Pe.x, lineGeo.Pe.y)
        for breakGeo in breakShape.geos:
            if isinstance(breakGeo, LineGeo):
                breakLine = QtCore.QLineF(breakGeo.Pa.x, breakGeo.Pa.y, breakGeo.Pe.x, breakGeo.Pe.y)
                intersection = QtCore.QPointF(0, 0)  # values do not matter
                res = line.intersect(breakLine, intersection)
                if res == QtCore.QLineF.BoundedIntersection:
                    intersections.append(Point(intersection.x(), intersection.y()))
        return intersections

    def intersectArcGeometry(self, arcGeo, breakShape):
        """
        Get the intersections between the finite line and arc.
        Algorithm based on http://vvvv.org/contribution/2d-circle-line-intersections
        """
        intersections = []
        for breakGeo in breakShape.geos:
            if isinstance(breakGeo, LineGeo):
                dxy = breakGeo.Pe - breakGeo.Pa
                a = dxy.x**2 + dxy.y**2
                b = 2 * (dxy.x * (breakGeo.Pa.x - arcGeo.O.x) + dxy.y * (breakGeo.Pa.y - arcGeo.O.y))
                c = breakGeo.Pa.x**2 + breakGeo.Pa.y**2 + arcGeo.O.x**2 + arcGeo.O.y**2\
                    - 2 * (arcGeo.O.x * breakGeo.Pa.x + arcGeo.O.y * breakGeo.Pa.y)\
                    - arcGeo.r**2
                bb4ac = b * b - 4 * a * c

                if bb4ac > 0:
                    mu1 = (-b + sqrt(bb4ac)) / (2*a)
                    mu2 = (-b - sqrt(bb4ac)) / (2*a)
                    p1 = breakGeo.Pa + mu1 * dxy
                    p2 = breakGeo.Pa + mu2 * dxy

                    # Points belong to the finite line?
                    if not\
                        (p1.x < breakGeo.Pa.x and p2.x < breakGeo.Pa.x and p1.x < breakGeo.Pe.x and p2.x < breakGeo.Pe.x or
                         p1.y < breakGeo.Pa.y and p2.y < breakGeo.Pa.y and p1.y < breakGeo.Pe.y and p2.y < breakGeo.Pe.y or
                         p1.x > breakGeo.Pa.x and p2.x > breakGeo.Pa.x and p1.x > breakGeo.Pe.x and p2.x > breakGeo.Pe.x or
                         p1.y > breakGeo.Pa.y and p2.y > breakGeo.Pa.y and p1.y > breakGeo.Pe.y and p2.y > breakGeo.Pe.y):

                        if arcGeo.O.distance(breakGeo.Pa) >= arcGeo.r and self.point_belongs_to_arc(p2, arcGeo):
                            intersections.append(p2)
                        if arcGeo.O.distance(breakGeo.Pe) >= arcGeo.r and self.point_belongs_to_arc(p1, arcGeo):
                            intersections.append(p1)
        return intersections

    def point_belongs_to_arc(self, point, arcGeo):
        ang = arcGeo.dif_ang(arcGeo.Pa, point, arcGeo.ext)
        return arcGeo.ext >= ang if arcGeo.ext > 0 else arcGeo.ext <= ang

    def classifyIntersections(self, geo, intersection):
        """
        Investigate the array intersection (which contains exactly two Point instances) and return (near, far) tuple, depending on the distance of the points to the start point of the geometry geo.
        """
        if geo.Pa.distance(intersection[0]) < geo.Pa.distance(intersection[1]):
            return (intersection[0], intersection[1])
        else:
            return (intersection[1], intersection[0])
