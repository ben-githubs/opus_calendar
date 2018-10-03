# -*- coding: utf-8 -*-
"""
Created on Mon Oct  1 20:55:45 2018

@author: Ben
"""

import datetime as dt
import logging
import urllib.request
import os # For removing old description files
import glob

# Create Logger
logging.getLogger().setLevel(logging.DEBUG)

# Important constants
DESC_DIR = os.path.join(os.getcwd(),"descriptions")
CALENDAR_DATA_URL = "https://calendar.google.com/calendar/ical/opustutoring%40gmail.com/public/basic.ics"


# -----------------------------------------------------------------------------
# ---------------------------------------------------------------- Event Class
# -----------------------------------------------------------------------------

class Event:
    def __init__(self, properties): # ......................... Event.__init__
        self.summary = properties.get("SUMMARY", "None")
        self.dtStart = properties.get("DTSTART", "20000101T000000")
        self.dtEnd = properties.get("DTEND", "20000101T000000")
        self.uid = properties.get("UID", 0)
        self.description = properties.get("DESCRIPTION", "")
        self.location = properties.get("LOCATION", "")
        self.rrule = properties.get("RRULE", "")
        self.exdate = properties.get("EXDATE", "")
        
        # Format variables
        self.dtStart = IcalParser.Str2Datetime(self.dtStart)
        self.dtEnd = IcalParser.Str2Datetime(self.dtEnd)
        self.rrule = Event.ParseRRule(self.rrule)
        self.exdate = [IcalParser.Str2Datetime(date).date() 
                        for date in self.exdate]
        
    
    def CheckDate(self, date): # ............................. Event.CheckDate
        """This function check's if this event is on the given date.  Returns
        a boolean value.  Also checks any repititions of this event."""
        # Check if this is the correct type
        if type(date) != dt.date:
            if type(date) == dt.datetime:
                date = date.date()
            else:
                logging.error("Invalid date object.")
                return False
        
        # Check assuming no repeats 
        if self.dtStart.date() == date:
            return True
        elif self.dtStart.date() > date:
            return False
        
        # Check if this event repeats
        r = self.rrule # Just keeps things simple
        if r:
            # Is this date in the excluded dates?
            if self.exdate and date in self.exdate:
                return False
            if "UNTIL" in r.keys() and r["UNTIL"].date() < date:
                return False
            if "FREQ" in r.keys() and r["FREQ"] == "WEEKLY":
                if "BYDAY" in r.keys():
                    weekday = {"MO":0, "TU":1, "WE":2, "TH":3, "FR":4}.get(
                            r["BYDAY"].strip())
                    return weekday == date.weekday()
        return False
    
    def ParseRRule(rrule): # ................................ Event.ParseRRule
        """Parses the string for the repetition rule as found in an ICal file.
        Should possibly move this to thr IcalParser class... """
        if rrule == "":
            return dict()
        parts = rrule.split(';')
        rrule = dict()
        for part in parts:
            [key, val] = part.split('=')
            rrule[key] = val
        # Special cases
        if "UNTIL" in rrule.keys():
            rrule["UNTIL"] = IcalParser.Str2Datetime(rrule["UNTIL"])
        
        return rrule

# -----------------------------------------------------------------------------
# ------------------------------------------------------------- Calendar Class
# -----------------------------------------------------------------------------

class Calendar:
    def __init__(self): # .................................. Calendar.__init__
        self.events = list()
    
    def AddEvents(self,eventList): # ...................... Calendar.AddEvents
        self.events += eventList
    
    def GetEvents(self, date): # .......................... Calendar.GetEvents
        returnlist = list()
        logging.debug("Retrieving events on {}".format(date.strftime("%c")))
        for event in self.events:
            if event.CheckDate(date):
                returnlist.append(event)
        logging.debug("There are {0:} events occuring on {1:s}".format(
                len(returnlist), date.strftime("%b %d, %y")))
        return self.SortEventsByTime(returnlist)
    
    def SortEventsByTime(self, eventList): # ....... Calendar.SortEventsByTime
        dts = [event.dtStart.time() for event in eventList]
        orig = [event.dtStart.time() for event in eventList]
        dts.sort()
        indices = [orig.index(dt) for dt in dts]
        return [eventList[index] for index in indices]


# -----------------------------------------------------------------------------
# ----------------------------------------------------------- ICalParser Class
# -----------------------------------------------------------------------------

class IcalParser:
    def Parse(filename): # .................................. ICalParser.Parse
        file = urllib.request.urlopen(filename)
        content = file.read().decode()
        logging.info("Opening file.")
        events = list()
        readingEvent = False # Flag for if we're reading an event
        eventProp = dict() # Create a dict for the properties of the event
        lastProp = ""
        logging.debug("Commencing line search.")
        for line in content.split('\n'):
            # Is this the start of a new event?
            if line.strip() == "BEGIN:VEVENT":
                if readingEvent:
                    # Shouldn't happen, this is a problem
                    logging.error("""Tried to read a new calendar event while 
                              already reading one. Aborting function.""")
                    return
                readingEvent = True
                eventProp = dict()
            elif line.strip() == "END:VEVENT":
                if not readingEvent:
                    #Also shouldn't be happending
                    logging.error("""Reached the end of an unknown event. File
                              structure us likely wrong. Aborting 
                              function.""")
                    return
                # Else, add the event
                readingEvent = False
                events.append(Event(eventProp))
            elif readingEvent:
                props = line.split(':',1)
                if len(props) > 1:
                    lastProp = props[0].split(';')[0]
                    if lastProp == "EXDATE":
                        if lastProp in eventProp.keys():
                            eventProp[lastProp].append(props[1].strip())
                        else:
                            eventProp[lastProp] = [props[1].strip()]
                    else: eventProp[lastProp] = props[1]
                else: # Just add the content here to the previous prop
                    eventProp[lastProp] += line
        logging.info("Found {} events.".format(len(events)))
        return events
    
    def Str2Datetime(string): # ...................... IcalParser.Str2Datetime
        year = int(string[:4])
        month = int(string[4:6])
        day = int(string[6:8])
        hour = int(string[9:11])
        min = int(string[11:13])
        sec = int(string[13:15])
        return dt.datetime(year, month, day, hour, min, sec)

# -----------------------------------------------------------------------------
# ----------------------------------------------------------- HTMLExport Class
# -----------------------------------------------------------------------------

class HTMLExport:
    def __init__(self, template):
        """ Creates the HTMLExport object. Template is the filename of (or path
        to) the html template for this object to use."""
        self.template = template
        
        with open(template) as f:
            logging.info("HTMLExport has opened the file {}".format(template))
            self.text = f.read()
    
    def PlaceAtTag(self, tag, newText):
        """Looks for a specific tag within the file and places newText as a 
        string at that position. Tags are denotes by <!--tag:{}--> in the 
        file."""
        
        index = self.text.find("<!--tag:{}-->".format(tag))
        if index > -1:
            newStr = self.text[:index]
            newStr += newText
            newStr += self.text[index:]
            self.text = newStr
            logging.debug("Succesfully placed string in file.")
        else:
            logging.debug("Could not find tag {0} in {1}".format(tag, 
                          self.template))
    
    def ExportFile(self, fname):
        with open(fname, 'w') as f:
            f.write(self.text)
            logging.info("Wrote contents to html file.")
    
    def ExportString(self):
        return self.text
    
    

# -----------------------------------------------------------------------------
# -------------------------------------------------------------- Main Function
# -----------------------------------------------------------------------------

def main():
    # Create new calendar object
    cal = Calendar();
    cal.AddEvents(IcalParser.Parse(CALENDAR_DATA_URL))
    
    #  Figure out which dates we should display on the calendar
    today = dt.datetime.today()
    monday = today+dt.timedelta((0-today.weekday())%7)
    tuesday = today+dt.timedelta((1-today.weekday())%7)
    wednesday = today+dt.timedelta((2-today.weekday())%7)
    thursday = today+dt.timedelta((3-today.weekday())%7)
    friday = today+dt.timedelta((4-today.weekday())%7)
    
    # Clean description directory
    logging.debug("{0} files in {1}.".format(len(os.listdir(DESC_DIR)),DESC_DIR))
    for file in os.listdir(DESC_DIR):
        os.remove(os.path.join(DESC_DIR, file))
    
    html = HTMLExport("temp.html")
    
    for weekday in [monday, tuesday, wednesday, thursday, friday]:
        datestr = weekday.strftime("%a %b %d")
        tag = weekday.strftime("%A").lower()
        newContent = """
            <div class="top-info"><span>{0}</span></div>
            <ul>
                <!--tag:{1}-events-->
            </ul>""".format(datestr, tag)
        html.PlaceAtTag(tag, newContent)
        
        # Now, add individual events
        for event in cal.GetEvents(weekday):
            htmlContent = HTMLExport("description_template.html")
            htmlContent.PlaceAtTag("description", event.description)
            fname = "desc{}.html".format(len(os.listdir(DESC_DIR)))
            fname = os.path.join(DESC_DIR, fname)
            htmlContent.ExportFile(fname)
            
            htmlEvent = HTMLExport("event_template.html")
            htmlEvent.PlaceAtTag("start", event.dtStart.strftime("%H:%M"))
            htmlEvent.PlaceAtTag("end", event.dtEnd.strftime("%H:%M"))
            htmlEvent.PlaceAtTag("content", fname)
            htmlEvent.PlaceAtTag("name", event.summary)
            html.PlaceAtTag("{0}-events".format(tag), htmlEvent.text)
    
    html.ExportFile("index.html")
        

        
main()