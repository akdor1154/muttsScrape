import muttsScrape
import os.path

import time
from datetime import timedelta as Timedelta

from pickle import load, dump

activitiesFileName = 'savedActivities.pickle'
activitiesByRoomFileName = 'savedActivitiesByRoom.pickle'


maxAgeBeforeRegen = Timedelta(hours=6).total_seconds()

import threading

thread = None

def getCurrentActivities():
    try:
        print('attempting to load saved activities...')
        with open(activitiesFileName, 'rb') as savedActivitiesFile:
            activities = load(savedActivitiesFile)
        with open(activitiesByRoomFileName, 'rb') as savedActivitiesByRoomFile:
            activitiesByRoom = load(savedActivitiesByRoomFile)

        currentTime = time.time()
        modifiedTimestamp = os.path.getatime(activitiesFileName)

        if currentTime - modifiedTimestamp > maxAgeBeforeRegen:
            getFreshActivitiesInBackground()

        print('loaded saved activities')

    except Exception as e:
        print('loading failed, rescraping')
        print(e)
        print(e.args)
        activities, activitiesByRoom = getFreshActivities()

    return activitiesByRoom


def getFreshActivitiesInBackground():
    global thread
    if thread is not None and thread.isAlive():
        return

    thread = threading.Thread(target=getFreshActivities)
    thread.start()

def getFreshActivities():
    s = muttsScrape.Scraper()
    s.login()
    soup = s.getTimetableSoup()
    activities, roomActivities = s.getActivities(soup)
    saveActivities(activities, roomActivities)
    return activities, roomActivities

def saveActivities(activities, roomActivities):
    with open(activitiesFileName+'.temp', 'wb') as savedActivitiesFile:
        dump(activities, savedActivitiesFile)
    os.replace(activitiesFileName+'.temp', activitiesFileName)

    with open(activitiesByRoomFileName+'.temp', 'wb') as savedActivitiesByRoomFile:
        dump(roomActivities, savedActivitiesByRoomFile)
    os.replace(activitiesByRoomFileName+'.temp', activitiesByRoomFileName)
