#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

from datetime import date,timedelta as Timedelta,time,datetime as Datetime
from copy import deepcopy
from operator import attrgetter,itemgetter
import collections

import urllib.request
import urllib.parse

from bs4 import BeautifulSoup, NavigableString
import requests

import json

import sys
import os
sys.path.append(os.path.dirname(__file__))

import muttsScrapeCredentials
import itertools

print('hellooo')


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
    
    def __init__(self, activityNameString : str, startTime:Datetime = None, endTime:Datetime=None, locations:list=None):
        self.name = ''
        self.type = ''
        self.startTime = startTime
        self.endTime = endTime
        self.weekDay = startTime.weekday() if (startTime is not None) else None
        self.locations = set(flatten(
                    [(self.friendlyLocations[l] if (l in self.friendlyLocations) else l)
                        for l in locations]
                ))
        self.parseName(activityNameString)

    def __repr__(self):
        return self.__str__()
        
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
    def __setstate__(self, state):
        self.name = state['name']
        self.type = state['type']
        self.startTime = state['startTime']
        self.endTime = state['endTime']
        self.weekDay = state['weekDay']
        self.locations = state['locations']
    
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

def getString(soup):
    return ''.join(s for s in soup.contents if isinstance(s, NavigableString))


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

        return timetableSoup


    def getActivities(self, soup):

        days = {'Monday':0,'Tuesday':1,'Wednesday':2,'Thursday':3,'Friday':4,'Saturday':5,'Sunday':6}
        activities = [[],[],[],[],[],[],[]]
        activitiesByRoom = dict((room, deepcopy(activities)) for room in flatten(Activity.friendlyLocations.values()))

        today = Datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)

        currentTime = None

        for tr in soup.find('table', class_='cyon_table').find('tbody').find_all('tr'):
            tds = tr.find_all('td')
            activityName = str(tds[0].string)
            activityUnitFullName = str(tds[1].string)
            activityUnitDescription = str(tds[2].string)
            activityDayName = str(tds[3].string)
            activityStartTimeStr = getString(tds[4])
            activityDurationStr = getString(tds[5])
            activityTeachingWeeks = str(tds[6].string)

            locationsTd = tds[7]

            #try:
            activityTime = Datetime.strptime(activityStartTimeStr, '%I:%M%p')
            activityDurationHours, activityDurationMinutes = tuple(map(int, activityDurationStr.split(':', maxsplit=2)))
            activityDuration = Timedelta(hours=activityDurationHours, minutes=activityDurationMinutes)
            activityStartDay = (
                  today
                - Timedelta(days = today.weekday())
                + Timedelta(days = days[activityDayName])
            )
            activityStartTime = activityStartDay.replace(hour=activityTime.hour, minute=activityTime.minute)
            activityEndTime = activityStartTime+activityDuration
            #except Exception as e:
            #    print('error getting time for activity:')
            #    print('name: %s' % activityName)
            #    print('startTimeStr: %s' % activityStartTimeStr)
            #    print('durationStr: %s' % activityDurationStr)
            #    continue

            activityRooms = []
            for aElement in locationsTd.find_all('a'):
                room = aElement['href'].split('Location=')[1]
                activityRooms.append(room)

            a = Activity(
                activityName,
                startTime=activityStartTime,
                endTime=activityEndTime,
                locations=activityRooms
            )

            activities[a.weekDay].append(a)
            [activitiesByRoom[room][a.weekDay].append(a) for room in a.locations if room in Activity.friendlyLocations.values()]

        self.activities = activities
        self.activitiesByRoom = activitiesByRoom

        return activities, activitiesByRoom

    @staticmethod
    def getCurrentActivities(activitiesByRoom):


        #testTime = datetime.today().replace(hour=11,minute=0,second=0,microsecond=0)
        testTime = Datetime.today()
        timeMarginForward = Timedelta(hours=6)
        timeMarginBackward = Timedelta(hours=6)

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





from pickle import load, dump

if __name__ == '__main__':
    s = Scraper()

    try:
        raise Exception('asdf')
        print('attempting to load saved activities...')
        with open('savedActivities.pickle', 'rb') as savedActivitiesFile:
            activities = load(savedActivitiesFile)
        with open('savedActivitiesByRoom.pickle', 'rb') as savedActivitiesByRoomFile:
            activitiesByRoom = load(savedActivitiesByRoomFile)
        print('loaded saved activities')

    except Exception as e:
        print('loading failed, rescraping')
        print(e)
        print(e.args)
        s.login()
        ts = s.getTimetableSoup()
        activities, activitiesByRoom = s.getActivities(ts)
        with open('savedActivities.pickle', 'wb') as savedActivitiesFile:
            dump(activities, savedActivitiesFile)
        with open('savedActivitiesByRoom.pickle', 'wb') as savedActivitiesByRoomFile:
            dump(activitiesByRoom, savedActivitiesByRoomFile)
        print('saved activities')

    currentActivities = Scraper.getCurrentActivities(activitiesByRoom)
    print(currentActivities)