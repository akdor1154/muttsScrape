#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

from datetime import date,timedelta,time,datetime
from copy import deepcopy
from operator import attrgetter,itemgetter
import collections

import urllib.request
import urllib.parse

from bs4 import BeautifulSoup
import requests

import json

import sys
import os
sys.path.append(os.path.dirname(__file__))

import muttsScrapeCredentials
import itertools

print('hellooo')

class ActivityJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if (o.__class__ is Activity):
            return o.__dict__()
        elif (o.__class__ is datetime):
            return o.timestamp()
        elif (o.__class__ is set):
            return list(o)
        else:
            return super().default(o)

encoder = ActivityJSONEncoder()

class Activity:
    
    friendlyNames = {
        'CL_MUV_':'Monash Venues',
        'CL_ENGINEERING':'Eng Faculty',
    }
    
    friendlyLocations = {
        'CL_23Col/G11':'G11',
        'CL_23Col/G14':'G14',
        'CL_23Col/G14^G15':['G14','G15'],
        'CL_23Col/G15':'G15',
        'CL_23Col/G16':'G16',
        'CL_23Col/G18':'G18',
        'CL_23Col/G19':'G19',
        'CL_23Col/G18^G19':['G18','G19'],
        'CL_23Col/G20':'G20',
        'CL_23Col/G21':'G21',
        'CL_23Col/G21A':'G21a'
    }
    
    def __init__(self, activityNameString, startTime=None, endTime=None, locations=None):
        self.name = ''
        self.type = ''
        self.startTime = startTime
        self.endTime = endTime
        self.weekDay = startTime.weekday() if (startTime is not None) else None
        self.locations = set(flatten(
                    [(self.friendlyLocations[l] if (l in self.friendlyLocations) else l)
                        for l in locations.split(', ')]
                ))
        self.parseName(activityNameString)
        
    def __str__(self):
        outString = [self.name,' ',self.type,': ',self.timespanToString()]
        if self.locations:
            outString += [' in ', ', '.join(self.locations)]
        return ''.join(outString)
    def __dict__(self):
        return {
            'name': self.name,
            'type': self.type,
            'startTime': self.startTime,
            'endTime': self.endTime,
            'weekDay': self.weekDay,
            'locations': self.locations
        }
    
    def timespanToString(self):
        if self.startTime is None or self.endTime is None:
            return '';
        timeFormat = '%H:%M';
        return self.startTime.strftime(timeFormat)+'—'+self.endTime.strftime(timeFormat);
    
    def parseName(self, activityNameString):
        nameSplit = activityNameString.split('/')
        if (nameSplit[1]) == 'Booking':
            bookingSource = nameSplit[0]
            self.name = next((self.friendlyNames[n] for n in self.friendlyNames.keys() if bookingSource.startswith(n)), bookingSource)
            self.type = 'Booking'
        else:
            unitSplit = nameSplit[0].split('_')
            self.name = unitSplit[0]
            self.type = nameSplit[1]
            
def isRoomTag(tag):
    return str(tag.string).startswith('Room:')
def getRoomString(tag):
    return str(tag.find(isRoomTag).next_sibling)

def flatten(l):
    for el in l:
        if isinstance(el, list):
            yield from flatten(el)
        else:
            yield el
    
def quitServing():
    status = '501 Server Error'
    start_response(status, 0)
    return [""]


def getRetardedFormValues(soup, formDict):
    retardedFormValues = {formName: getRetardedForm(soup, formName)
                            for inputName, formName in formDict.items()}

    if any(len(val) <= 0 for val in retardedFormValues.values()):
        raise Exception('Couldn\'t get needed formy stuff')
        #quitServing

    return retardedFormValues

def getRetardedForm(soup, formName):
    value = ''
    inputElement = soup.find('input',attrs={'name':formName})
    value = inputElement['value']

    return value

def expandDictKeys(d):
    l = []
    for k,v in d.items():
        if hasattr(v, '__iter__') and not isinstance(v, str):
            for vv in v:
                l.append((k, vv))
        else:
            l.append((k, v))
    return l


class Scraper:

    def __init__(self):
        self.session = requests.Session()


    def login(self):
        loginUrl = 'https://classtimetable.monash.edu/2016Staff/Login.aspx'
        contextPageResponse = self.session.get(loginUrl)
        contextPageSoup = BeautifulSoup(contextPageResponse.text)

        retardedFormInputs = {
            'viewState': '__VIEWSTATE',
            'viewstateGenerator': '__VIEWSTATEGENERATOR',
            'eventValidation': '__EVENTVALIDATION'
        }

        retardedFormValues = getRetardedFormValues(contextPageSoup, retardedFormInputs)

        loginParams = {
            'tUserName':muttsScrapeCredentials.username,
            'tPassword':muttsScrapeCredentials.password,
            'bLogin':'Login'
        }

        loginParams.update(retardedFormValues)

        loginResponse = self.session.post(
            loginUrl,
            data    = loginParams
        )



        self.loggedInPageSoup = BeautifulSoup(loginResponse.text)

        #print(loginResponse.text)


    def getTimetableSoup(self):

        #yearStartDate = date(date.today().year, 1, 1)
        #yearStartDay = yearStartDate.weekday()
        
        #week0StartDate = yearStartDate-timedelta(yearStartDay)
        #weekNumber = (date.today()-week0StartDate).days//7
        #weekNumberBinary = 2**(51-weekNumber)

        searchPageUrl = 'https://classtimetable.monash.edu/2016Staff/default.aspx'

        retardedFormInputs = {
            'viewState': '__VIEWSTATE',
            'viewstateGenerator': '__VIEWSTATEGENERATOR',
            'eventValidation': '__EVENTVALIDATION'
        }

        retardedFormValues = getRetardedFormValues(self.loggedInPageSoup, retardedFormInputs)

        searchParams = {
            '__EVENTTARGET': 'LinkBtn_locations',
            'tLinkType': 'information'
        }

        searchParams.update(retardedFormValues)

        searchResponse = self.session.post(searchPageUrl, data=searchParams)
        searchResponseSoup = BeautifulSoup(searchResponse.text)


        timetableSearchParams = {
            'tLinkType' : 'locations',
            'dlObject'  : Activity.friendlyLocations.keys(),
            'lbWeeks'   : 't', # this week, 'n' # next week, '2' # 2nd week of year, '3;4;51' # 3rd, 4th, 51st week of year,
            'lbDays'    : '1;2;3;4;5;6;7',
            'RadioType' : 'location_list;cyon_reports_list_url;dummy',
            'bGetTimetable': 'View+Timetable'
        }

        retardedFormInputs = {
            'viewState': '__VIEWSTATE',
            'viewstateGenerator': '__VIEWSTATEGENERATOR',
            'eventValidation': '__EVENTVALIDATION'
        }
        retardedFormValues = getRetardedFormValues(searchResponseSoup, retardedFormInputs)
        timetableSearchParams.update(retardedFormValues)

        timetableSearchQuery = expandDictKeys(timetableSearchParams)

        timetableURL = 'https://classtimetable.monash.edu/2016Staff/default.aspx'
        timetableResponse = self.session.post(timetableURL, data=timetableSearchQuery)

        timetableSoup = BeautifulSoup(timetableResponse.text)

        print(timetableResponse.text)

        return timetableResponse


def getCurrentActivities():
    print('hello')

    self.login()


    days = {'Mon':0,'Tue':1,'Wed':2,'Thu':3,'Fri':4,'Sat':5,'Sun':6}
    activities = [[],[],[],[],[],[],[]]
    activitiesByRoom = dict((room, deepcopy(activities)) for room in flatten(Activity.friendlyLocations.values()))

    currentDay = 0
    startTimeString = timetableSoup.find(id='tblTimetable').tr.td.next_sibling.get_text()
    startTime = datetime.strptime(startTimeString, '%H:%M')
    
    currentTime = None
    for tr in timetableSoup.find(id='tblTimetable').find_all('tr'):
        currentTime = datetime.today().replace(hour=startTime.hour,minute=startTime.minute,second=0,microsecond=0)
        columnDelta = timedelta(minutes=30)
        
        maybeDay = tr.td.get_text()
        if maybeDay in days:
            currentDay = days[maybeDay]
            
        currentTime = (currentTime
            - timedelta(days=currentTime.weekday())
            + timedelta(days=currentDay) )
        if 'rowspan' in tr.td.attrs and int(tr.td['rowspan']) > 1:
            currentTime -= columnDelta
            
        for td in tr.find_all('td'):
            tdSpan = 1
            if 'span' in td.attrs:
                tdSpan = int(td['span'])
                tdSpan = tdSpan if (tdSpan > 1) else 1
            if 'activity_name' in td.attrs and len(td['activity_name']) > 1:
                rooms = getRoomString(td)
                a = Activity(
                    td['activity_name'],
                    startTime=currentTime,
                    endTime=currentTime+(tdSpan*columnDelta),
                    locations=rooms
                    )
                print('found activity: '+str(a))
                activities[currentTime.weekday()].append(a)
                [activitiesByRoom[room][a.weekDay].append(a) for room in a.locations]
            currentTime += tdSpan*columnDelta


    #testTime = datetime.today().replace(hour=11,minute=0,second=0,microsecond=0)
    testTime = datetime.today()
    timeMarginForward = timedelta(hours=6)
    timeMarginBackward = timedelta(hours=6)

    #currentActivities = dict([
    #   (room, sorted([a for a in roomActivites[testTime.weekday()]
    #       if (a.startTime < testTime+timeMarginStart and testTime-timeMarginEnd < a.endTime)], key=attrgetter('startTime')))
    #   for room, roomActivites in activitiesByRoom.items()
    #])

    currentActivities = dict([
        (room, {
            'prev': next( (a for a in roomActivities[testTime.weekday()]
                  if (a.endTime > testTime-timeMarginBackward and a.endTime < testTime)
                ), None),
            'now': next( (a for a in roomActivities[testTime.weekday()]
                  if (a.startTime < testTime and a.endTime > testTime)
                ), None),
            'next': next( (a for a in roomActivities[testTime.weekday()]
                  if (a.startTime > testTime and a.startTime < testTime+timeMarginForward)
                ), None)
        })
        for room, roomActivities in activitiesByRoom.items()
    ])

    return currentActivities

def serveHtml():
    currentActivities = getCurrentActivities()
    response_headers = {'X-UA-Compatible':'IE=edge',
                        'Content-type':'text/html'};
    output = []
    output.append('''<!DOCTYPE html>
    <html>
    <head>
        <title>Current Classes</title></head>
        <meta charset="UTF-8" />
        <link rel="stylesheet" type="text/css" href="/static/classes.css" />
    <body>
    <ul class="roomList">
    '''
    )
    for room, roomActivities in sorted(currentActivities.items(), key=itemgetter(0)):
        hasPrev = False
        roomNameOut = '<li><span class="roomName {cssClass}">{room}: </span>'
    #   if len(roomActivities) == 0:
    #       print('<span class="classList">Free!</span>')
    #   else:
    #       print('<ul class="classList">');
    #       [print('<li>',activity.name,' ',activity.type,': ',activity.timespanToString(),'</li>',sep='')
    #           for activity in roomActivities]
    #       print('</ul>')
        classListOut = []
        classListOut.append('<ul class="classList">')
        for when,activity in roomActivities.items():
            if activity is not None:
                classListOut.append('<li class="{cssClass}">{when:s}{name:s} {type:s}: {time:s}</li>'.format(
                    cssClass=when,
                    when=''.join([when.title(),': ']) if when != 'now' else '',
                    name=activity.name,
                    type=activity.type,
                    time=activity.timespanToString()))
                if when == 'prev':
                    hasPrev = True
            elif when != 'prev':
                classListOut.append('<li class="{cssClass:s} free">{when:s}Free!</li>'.format(
                    cssClass=when,
                    when=''.join([when.title(),': ']) if when != 'now' else ''))
        classListOut.append('</ul>')
        classListOut.append('</li>')
        output.append(roomNameOut.format(cssClass = "roomWithPrev" if hasPrev else "", room=room))
        output.append('\n'.join(classListOut))
    output.append('''</ul>
    </body>
    </html>
    ''');
    
    outputStr = ''.join(output)
    return (response_headers, outputStr)
        
def serveJson():
    response_headers = {'Content-type':'application/json', 'Access-Control-Allow-Origin': '*'}
    print('json hello')
    return (response_headers, encoder.encode(getCurrentActivities()))
    
def application(environ, start_response):
    getParams = urllib.parse.parse_qs(environ['QUERY_STRING'], keep_blank_values=True)
    (response_headers, outputStr) = serveHtml() if ('json' not in getParams) else serveJson()
    outputBytes = outputStr.encode('UTF-8')
    response_headers['Content-Length'] = str(len(outputBytes))
    if (response_headers['Content-type']):
        response_headers['Content-type'] += '; charset=utf-8'
    start_response('200 OK', list(response_headers.items()))
    return [outputBytes]


if __name__ == '__main__':
    s = Scraper()
    s.login()
    ts = s.getTimetableSoup()