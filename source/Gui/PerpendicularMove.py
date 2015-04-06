# -*- coding: utf-8 -*-

############################################################################
#   
#   Copyright (C) 2015
#    Christian Kohlöffel
#    Vinzenz Schulz
#    Jean-Paul Schouwstra
#    Robert Lichtenberger
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

from Core.LineGeo import LineGeo
from Core.Point import Point
from Core.EntitieContent import EntitieContentClass

from math import pi

import logging
from Gui.EntryExitMoveBase import EntryExitMoveBase
logger = logging.getLogger('Gui.PerpendicularMove')

from PyQt4 import QtCore

# Length of the cross.
dl = 0.2
DEBUG = 1

class PerpendicularMove(EntryExitMoveBase):
    def __init__(self, startp, angle,
                 pencolor=QtCore.Qt.green,
                 shape=None, parent=None, isStartMove=True):
        self.isStartMove = isStartMove
        super(PerpendicularMove, self).__init__(startp, angle, pencolor, shape, parent)

    def do_make_start_moves(self):
        # BaseEntitie created to add the StartMoves etc. This Entitie must not
        # be offset or rotated etc.
        BaseEntitie = EntitieContentClass(Nr=-1, Name='BaseEntitie',
                                          parent=None,
                                          children=[],
                                          p0=Point(x=0.0, y=0.0),
                                          pb=Point(x=0.0, y=0.0),
                                          sca=[1, 1, 1],
                                          rot=0.0)
        
        self.parent = BaseEntitie
        

        # Get the start rad. and the length of the line segment at begin. 
        start_rad = self.shape.LayerContent.start_radius

        # Get tool radius based on tool diameter.   
        tool_rad = self.shape.LayerContent.tool_diameter / 2
        
        # Calculate the starting point with and without compensation.        
        start = self.startp
        angle = self.angle
      
        Oein = start;

        if (self.shape.cut_cor == 41 or self.shape.cut_cor == 42):
            if self.shape.cut_cor == 41:     
                Oein = start.get_arc_point(angle + pi / 2, start_rad + tool_rad)
            else:
                Oein = start.get_arc_point(angle - pi / 2, start_rad + tool_rad)
            if self.isStartMove:
                self.geos.append(Oein)                    
                start_line = LineGeo(Oein, start)
                self.geos.append(start_line)
            else:
                start_line = LineGeo(start, Oein)
                self.geos.append(start_line)
        else:
            self.geos.append(start)                    
    
