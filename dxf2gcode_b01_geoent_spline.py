#!/usr/bin/python
# -*- coding: cp1252 -*-
#
#dxf2gcode_b01_ent_polyline
#Programmer: Christian Kohl�ffel
#E-mail:     n/A
#
#Copyright 2008 Christian Kohl�ffel
#
#Distributed under the terms of the GPL (GNU Public License)
#
#dxf2gcode is free software; you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation; either version 2 of the License, or
#(at your option) any later version.
#
#This program is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.
#
#You should have received a copy of the GNU General Public License
#along with this program; if not, write to the Free Software
#Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

from Canvas import Arc
from math import sqrt, sin, cos, atan2, radians, degrees
from dxf2gcode_b01_nurbs_calc import Spline2Arcs
from dxf2gcode_b01_point import PointClass, PointsClass, ContourClass

class SplineClass:
    def __init__(self,Nr=0,caller=None):
        self.Typ='Spline'
        self.Nr = Nr

        #Initialisieren der Werte        
        self.Layer_Nr = 0
        self.Spline_flag=[]
        self.degree=1
        self.Knots=[]
        self.Weights=[]
        self.CPoints=[]
        self.ArcSpline=[]
        self.length= 0

        #Lesen der Geometrie
        self.Read(caller)

        #Umwandeln zu einem ArcSpline

        Spline2ArcsClass=Spline2Arcs(degree=self.degree,Knots=self.Knots,\
                                Weights=self.Weights,CPoints=self.CPoints,tol=0.01)

        #print self
        self.ArcSpline=Spline2ArcsClass.Curve


        
    def __str__(self):
        # how to print the object
        s= ('\nTyp: Spline \nNr -> %i' %self.Nr)+\
           ('\nLayer Nr -> %i' %self.Layer_Nr)+\
           ('\nSpline flag -> %i' %self.Spline_flag)+\
           ('\ndegree -> %i' %self.degree)+\
           ('\nKnots -> %s' %self.Knots)+\
           ('\nWeights -> %s' %self.Weights)+\
           ('\nCPoints ->')
           
        for point in self.CPoints:
            s=s+"\n"+str(point)
        s+='\nArcSpline: ->'
        for geo in self.ArcSpline:
            s=s+str(geo)
        s=s+'\nLength ->'+str(self.length)
        return s

    def App_Cont_or_Calc_IntPts(self, cont, points, i, tol):
        #Hinzuf�gen falls es keine geschlossener Spline ist CPOINST??
        if self.CPoints[0].isintol(self.CPoints[-1],tol):
            self.analyse_and_opt()
            cont.append(ContourClass(len(cont),1,[[i,0]],self.length)) 
        else:
            points.append(PointsClass(point_nr=len(points),geo_nr=i,\
                                      Layer_Nr=self.Layer_Nr,\
                                      be=self.ArcSpline[0].Pa,\
                                      en=self.ArcSpline[-1].Pe,\
                                      be_cp=[],en_cp=[]))      

    def Read(self, caller):
        Old_Point=PointClass(0,0)

        #K�rzere Namen zuweisen        
        lp=caller.line_pairs
        e=lp.index_code(0,caller.start+1)

        #Layer zuweisen        
        s=lp.index_code(8,caller.start+1)
        self.Layer_Nr=caller.Get_Layer_Nr(lp.line_pair[s].value)

        #Spline Flap zuweisen
        s=lp.index_code(70,s+1)
        self.Spline_flag=int(lp.line_pair[s].value) 

        #Spline Ordnung zuweisen
        s=lp.index_code(71,s+1)
        self.degree=int(lp.line_pair[s].value)

        #Number of CPts
        s=lp.index_code(73,s+1)
        nCPts=int(lp.line_pair[s].value)          


        #Lesen der Knoten
        while 1:
            #Knoten Wert
            sk=lp.index_code(40,s+1,e)
            if sk==None:
                break
            self.Knots.append(float(lp.line_pair[sk].value))
            s=sk

        #Lesen der Gewichtungen
        while 1:
            #Knoten Gewichtungen
            sg=lp.index_code(41,s+1,e)
            if sg==None:
                break
            self.Weights.append(float(lp.line_pair[sg].value))
            s=sg
            
        if len(self.Weights)==0:
            for nr in range(nCPts):
                self.Weights.append(1)
                
        #Lesen der Kontrollpunkte
        while 1:  
            #XWert
            s=lp.index_code(10,s+1,e)
            #Wenn kein neuer Punkt mehr gefunden wurde abbrechen ...
            if s==None:
                break
            
            x=float(lp.line_pair[s].value)
            #YWert
            s=lp.index_code(20,s+1,e)
            y=float(lp.line_pair[s].value)

            self.CPoints.append(PointClass(x,y))             

            if (Old_Point==self.CPoints[-1]):
               # add to boundary if not zero-length segment
               Old_Point=self.CPoints[-1]
               if len(self.CPoints)>1:
                   self.length+=self.CPoints[-2].distance(self.CPoints[-1])            

        caller.start=e

   
    

    def analyse_and_opt(self):     
        summe=0
        #Berechnung der Fl�ch nach Gau�-Elling Positive Wert bedeutet CW
        #negativer Wert bedeutet CCW geschlossenes Polygon    !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!        
        for p_nr in range(1,len(self.CPoints)):
            summe+=(self.CPoints[p_nr-1].x*self.CPoints[p_nr].y-self.CPoints[p_nr].x*self.CPoints[p_nr-1].y)/2
            
    def plot2can(self,canvas,p0,sca,tag):
        hdl=[]
        for geo in self.ArcSpline:
            hdl+=(geo.plot2can(canvas,p0,sca,tag))
       
        return hdl
##        #if summe>0.0:
##        #   self.CPoints.reverse()
##
##        #Suchen des kleinsten Startpunkts von unten Links X zuerst (Muss neue Schleife sein!)
##        min_point=self.Points[0]
##        min_p_nr=0
##        del(self.Points[-1])
##        for p_nr in range(1,len(self.Points)):
##            #Geringster Abstand nach unten Unten Links
##            if (min_point.x+min_point.y)>=(self.Points[p_nr].x+self.Points[p_nr].y):
##                min_point=self.Points[p_nr]
##                min_p_nr=p_nr
##        #Kontur so anordnen das neuer Startpunkt am Anfang liegt
##        self.Points=self.Points[min_p_nr:len(self.Points)]+self.Points[0:min_p_nr]+[self.Points[min_p_nr]]
##

##    
    def get_start_end_points(self,direction=0):
        if direction==0:
            punkt, angle=self.ArcSpline[0].get_start_end_points(direction)
        elif direction==1:
            punkt, angle=self.ArcSpline[-1].get_start_end_points(direction)

        return punkt,angle
    
    def Write_GCode(self,string,paras,sca,p0,dir,axis1,axis2):
        for geo in self.ArcSpline:
            string+=geo.Write_GCode(paras,sca,p0,dir,axis1,axis2)
        return string   