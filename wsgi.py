import os
import sys

dirPath = os.path.dirname(os.path.realpath(__file__))

sys.path.insert(0, dirPath)

import muttsScrape
from  muttsScrapeCache import getCurrentActivities
import json
import datetime

class ActivityJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if (o.__class__ is muttsScrape.Activity):
            return o.__dict__()
        elif (o.__class__ is datetime.Datetime):
            return o.timestamp()
        elif (o.__class__ is set):
            return list(o)
        else:
            return super().default(o)

encoder = ActivityJSONEncoder()

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
