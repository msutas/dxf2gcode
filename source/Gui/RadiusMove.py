# -*- coding: utf-8 -*-

############################################################################
#   
#   Copyright (C) 2008-2015
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

from math import pi

import Core.Globals as g
from Core.LineGeo import LineGeo
from Core.ArcGeo import ArcGeo
from Core.Point import Point
from Core.EntitieContent import EntitieContentClass

import logging
from Gui.EntryExitMoveBase import EntryExitMoveBase
logger = logging.getLogger('Gui.RadiusMove')

from PyQt4 import QtCore

# Length of the cross.
dl = 0.2
DEBUG = 1

class RadiusMove(EntryExitMoveBase):
    """
    This Function generates the StartMove for each shape. It
    also performs the Plotting and Export of this moves. It is linked
    to the shape as its parent
    """
    def __init__(self, startp, angle,
                 pencolor=QtCore.Qt.green,
                 shape=None, parent=None):
        super(RadiusMove, self).__init__(startp, angle, pencolor, shape, parent)

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
        start_ver = start_rad

        # Get tool radius based on tool diameter.   
        tool_rad = self.shape.LayerContent.tool_diameter / 2
        
        # Calculate the starting point with and without compensation.        
        start = self.startp
        angle = self.angle
      
        if self.shape.cut_cor == 40:              
            self.geos.append(start)    
        # Cutting Compensation Left    
        elif (self.shape.cut_cor == 41  and
              ((g.config.vars.General['lead_in_move'] == "radius") or
               (g.config.vars.General['lead_in_move'] == "radius2"))):
        # elif self.shape.cut_cor == 41:
            # Center of the Starting Radius.
            Oein = start.get_arc_point(angle + pi / 2, start_rad + tool_rad)
            # Start Point of the Radius
            Pa_ein = Oein.get_arc_point(angle + pi, start_rad + tool_rad)
            # Start Point of the straight line segment at begin.
            Pg_ein = Pa_ein.get_arc_point(angle + pi / 2, start_ver)
            
            # Get the dive point for the starting contour and append it.
            start_ein = Pg_ein.get_arc_point(angle, tool_rad)
            self.geos.append(start_ein)

            # generate the Start Line and append it including the compensation. 
            start_line = LineGeo(Pg_ein, Pa_ein)
            self.geos.append(start_line)

            # generate the start rad. and append it.
            start_rad = ArcGeo(Pa=Pa_ein, Pe=start, O=Oein,
                               r=start_rad + tool_rad, direction=1)
            self.geos.append(start_rad)
            
        # Cutting Compensation Right            
        elif (self.shape.cut_cor == 42  and
              ((g.config.vars.General['lead_in_move'] == "radius") or
               (g.config.vars.General['lead_in_move'] == "radius2"))):
            
            # closed shape & G42 => create exit move: redo first geo (https://sourceforge.net/p/dxf2gcode/tickets/61/)
            if (g.config.vars.General['lead_in_move'] == "radius2"):
                angle = angle + pi / 2
            
            # Center of the Starting Radius.
            Oein = start.get_arc_point(angle - pi / 2, start_rad + tool_rad)
            # Start Point of the Radius
            Pa_ein = Oein.get_arc_point(angle + pi, start_rad + tool_rad)
            # Start Point of the straight line segment at begin.
            Pg_ein = Pa_ein.get_arc_point(angle - pi / 2, start_ver)
            
            # Get the dive point for the starting contour and append it.
            start_ein = Pg_ein.get_arc_point(angle, tool_rad)
            self.geos.append(start_ein)

            # generate the Start Line and append it including the compensation.
            start_line = LineGeo(Pg_ein, Pa_ein)
            self.geos.append(start_line)

            # generate the start rad. and append it.
            start_rad = ArcGeo(Pa=Pa_ein, Pe=start, O=Oein,
                               r=start_rad + tool_rad, direction=0)
            self.geos.append(start_rad)
            