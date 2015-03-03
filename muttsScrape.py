#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

from datetime import date,timedelta,time,datetime
from copy import deepcopy
from operator import attrgetter,itemgetter
import collections

import urllib.request
from bs4 import BeautifulSoup

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
	
def application(environ, start_response):
	print('hello')
	loginURL = 'https://mutts.timetable.monash.edu/MUTTS/default.aspx'
	contextPageResponse = urllib.request.urlopen(loginURL,cadefault=True)
	contextPageSoup = BeautifulSoup(contextPageResponse.read().decode())

	viewstate = ''
	viewstateInput = contextPageSoup.find('input',attrs={'name':'__VIEWSTATE'})
	viewstate = viewstateInput['value']

	sessionCookieName='ASP.NET_SessionId'
	sessionId = ''
	cookies = contextPageResponse.getheader('Set-Cookie')
	cookies = cookies.split(' ')
	for cookie in cookies:
		cookieSplit = cookie.split('=')
		if cookieSplit[0] == sessionCookieName:
			sessionId = cookieSplit[1]

	if len(sessionId) < 1 or len(viewstate) < 1:
		exit('Couldn\'t get needed formy stuff')
		#quitServing

	loginParams = urllib.parse.urlencode({
		'txtLogin':muttsScrapeCredentials.username,
		'txtPassword':muttsScrapeCredentials.password,
		'cmdLogin':'Log In',
		'__VIEWSTATE':viewstate
		}).encode('utf-8')

	loginRequest = urllib.request.Request(loginURL)
	loginRequest.add_header('Cookie',sessionCookieName+'='+sessionId)
	loginRequest.add_header('Content-Type','application/x-www-form-urlencodedcharset=utf-8')
	loginRequest.data = loginParams

	loginResponse = urllib.request.urlopen(loginRequest,cadefault=True)
	loggedInPageSoup = BeautifulSoup(loginResponse.read().decode())

	yearStartDate = date(date.today().year, 1, 1)
	yearStartDay = yearStartDate.weekday()
	week0StartDate = yearStartDate-timedelta(yearStartDay)
	weekNumber = (date.today()-week0StartDate).days//7

	weekNumberBinary = 2**(51-weekNumber)

	timetableSearchParams = urllib.parse.urlencode({
		'buildtype':'location',
		'splus_year':2015,
		'searchtype':'specific',
		'location_cd':Activity.friendlyLocations.keys(),
		'wp_decimal':weekNumberBinary,
		'startperiod':-1,
		'endperoid':-1
		},True)

	timetableURL = 'https://mutts.timetable.monash.edu/MUTTS/timetable/output/gridExcel.aspx'
	timetableRequest = urllib.request.Request(timetableURL+'?'+timetableSearchParams)
	timetableRequest.add_header('Cookie',sessionCookieName+'='+sessionId)

	timetableResponse = urllib.request.urlopen(timetableRequest, cadefault=True)
	timetableSoup = BeautifulSoup(timetableResponse.read().decode())

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
	timeMarginBackward = timedelta(minutes=7)

	#currentActivities = dict([
	#	(room, sorted([a for a in roomActivites[testTime.weekday()]
	#		if (a.startTime < testTime+timeMarginStart and testTime-timeMarginEnd < a.endTime)], key=attrgetter('startTime')))
	#	for room, roomActivites in activitiesByRoom.items()
	#])

	currentActivities = dict([
		(room, [
			('prev', next( (a for a in roomActivities[testTime.weekday()]
				  if (a.endTime > testTime-timeMarginBackward and a.endTime < testTime)
				), None)),
			('now',  next( (a for a in roomActivities[testTime.weekday()]
				  if (a.startTime < testTime and a.endTime > testTime)
				), None)),
			('next', next( (a for a in roomActivities[testTime.weekday()]
				  if (a.startTime > testTime and a.startTime < testTime+timeMarginForward)
				), None))
		])
		for room, roomActivities in activitiesByRoom.items()
	])



	response_headers = [('X-UA-Compatible', 'IE=edge'),
						('Content-type','text/html')];
	output = []
	output.append('''
	<!DOCTYPE html>
	<html>
	<head>
		<title>Current Classes</title></head>
		<meta charset="UTF-8" />
		<link rel="stylesheet" type="text/css" href="/classes.css" />
	<body>
	<ul class="roomList">
	'''
	)

	for room, roomActivities in sorted(currentActivities.items(), key=itemgetter(0)):
		hasPrev = False
		roomNameOut = '<li><span class="roomName {cssClass}">{room}: </span>'
	#	if len(roomActivities) == 0:
	#		print('<span class="classList">Free!</span>')
	#	else:
	#		print('<ul class="classList">');
	#		[print('<li>',activity.name,' ',activity.type,': ',activity.timespanToString(),'</li>',sep='')
	#			for activity in roomActivities]
	#		print('</ul>')
		classListOut = []
		classListOut.append('<ul class="classList">')
		for when,activity in roomActivities:
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
	
	outputStr = ''.join(output).encode('UTF-8')
	response_headers.append(('Content-Length', str(len(outputStr))))
	start_response('200 OK', response_headers)
	return [outputStr]
		
