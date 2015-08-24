#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Originally file located here:
# http://bugs.foocorp.net/projects/librefm/wiki/LastToLibre
# I have modified this file to export Last.fm library to .scrobble.log file.
# You can use qtscrob or scrobble-cli to push it to your account

"""
Script for exporting tracks through audioscrobbler API.
Usage: lastexport.py -u USER [-o OUTFILE] [-p STARTPAGE] [-s SERVER]
"""

import re
import sys
import time
import urllib
import urllib2
import xml.etree.ElementTree as ET
from optparse import OptionParser
from random import randint

__version__ = '0.0.4'

day = 86400
counter = 0
date = 1391602932


def get_options(parser):
    """ Define command line options."""
    parser.add_option("-u", "--user", dest="username", default=None,
                      help="User name.")
    parser.add_option("-o", "--outfile", dest="outfile",
                      default=".scrobbler.log",
                      help="Output file, default is .scrobbler.log")
    parser.add_option("-p", "--page", dest="startpage", type="int",
                      default="1",
                      help="Page to start fetching tracks from, default is 1")
    parser.add_option("-s", "--server", dest="server", default="last.fm",
                      help="Server to fetch track info from, "
                           "default is last.fm")
    parser.add_option("-t", "--type", dest="infotype", default="scrobbles",
                      help="Type of information to export, "
                           "scrobbles|loved|banned, default is scrobbles")
    parser.add_option("-d", "--day", dest="tracksperday", default=None,
                      help="Tracks per day.")
    options, args = parser.parse_args()

    if not options.username:
        sys.exit("User name not specified, see --help")

    if options.infotype == "loved":
        infotype = "lovedtracks"
    elif options.infotype == "banned":
        infotype = "bannedtracks"
    else:
        infotype = "recenttracks"

    return options.username, options.outfile, options.startpage, options.server, infotype, options.tracksperday


def connect_server(server, username, startpage, sleep_func=time.sleep,
                   tracktype='recenttracks'):
    """ Connect to server and get a XML page."""
    if server == "libre.fm":
        baseurl = 'http://alpha.libre.fm/2.0/?'
        urlvars = dict(method='user.get%s' % tracktype,
                       api_key=('lastexport.py-%s' % __version__).ljust(32, '-'),
                       user=username,
                       page=startpage,
                       limit=200)

    elif server == "last.fm":
        baseurl = 'http://ws.audioscrobbler.com/2.0/?'
        urlvars = dict(method='user.get%s' % tracktype,
                       api_key='e38cc7822bd7476fe4083e36ee69748e',
                       user=username,
                       page=startpage,
                       limit=50)
    else:
        if server[:7] != 'http://':
            server = 'http://%s' % server
        baseurl = server + '/2.0/?'
        urlvars = dict(method='user.get%s' % tracktype,
                       api_key=('lastexport.py-%s' % __version__).ljust(32, '-'),
                       user=username,
                       page=startpage,
                       limit=200)

    url = baseurl + urllib.urlencode(urlvars)
    for interval in (1, 5, 10, 62):
        try:
            f = urllib2.urlopen(url)
            break
        except Exception, e:
            last_exc = e
            print "Exception occured, retrying in %ds: %s" % (interval, e)
            sleep_func(interval)
    else:
        print "Failed to open page %s" % urlvars['page']
        raise last_exc

    response = f.read()
    f.close()

    # bad hack to fix bad xml
    response = re.sub('\xef\xbf\xbe', '', response)
    # Unbelievably, some people have ASCII control characters
    # in their scrobbles: I ran across a \x04 (end of transmission).
    # Remove all of those except \n and \t
    response = re.sub('[\0-\x08\x0b-\x1f]', '', response)
    return response


def get_pageinfo(response, tracktype='recenttracks'):
    """Check how many pages of tracks the user have."""
    xmlpage = ET.fromstring(response)
    totalpages = xmlpage.find(tracktype).attrib.get('totalPages')
    return int(totalpages)


def get_tracklist(response):
    """Read XML page and get a list of tracks and their info."""
    xmlpage = ET.fromstring(response)
    tracklist = xmlpage.getiterator('track')
    return tracklist


def parse_track(trackelement):
    """Extract info from every track entry and output to list."""
    if trackelement.find('artist').getchildren():
        # artist info is nested in loved/banned tracks xml
        artistname = trackelement.find('artist').find('name').text
        artistmbid = trackelement.find('artist').find('mbid').text
    else:
        artistname = trackelement.find('artist').text
        artistmbid = trackelement.find('artist').get('mbid')

    if trackelement.find('album') is None:
        # no album info for loved/banned tracks
        albumname = ''
        albummbid = ''
    else:
        albumname = trackelement.find('album').text
        albummbid = trackelement.find('album').get('mbid')

    trackname = trackelement.find('name').text
    trackmbid = trackelement.find('mbid').text

    delay = randint(3, 200)
    time = randint(160, 480)
    tracknum = randint(1, 8)

    global counter, date, day, trackdict

    output = [artistname, albumname, trackname, str(tracknum), str(time), 'L',
              str(date), '']

    if counter >= tracksperday:
        counter = 0
        date = date - day
    else:
        counter = counter + 1
        date = date - time

    for i, v in enumerate(output):
        if v is None:
            output[i] = ''

    with open(outfile, 'a') as outfileobj:
        outfileobj.write(("\t".join(output) + "\r\n").encode('utf-8'))
    return output


def get_tracks(server, username, startpage=1, sleep_func=time.sleep,
               tracktype='recenttracks'):
    page = startpage
    response = connect_server(server, username, page, sleep_func, tracktype)
    totalpages = get_pageinfo(response, tracktype)

    if startpage > totalpages:
        raise ValueError("First page (%s) is higher than total pages (%s)." %
                         (startpage, totalpages))

    while page <= totalpages:
        # Skip connect if on first page, already have that one stored.

        if page > startpage:
            response = connect_server(server, username, page, sleep_func,
                                      tracktype)

        tracklist = get_tracklist(response)

        tracks = []
        for trackelement in tracklist:
            # do not export the currently playing track.
            if not trackelement.attrib.has_key("nowplaying") or not trackelement.attrib["nowplaying"]:
                tracks.append(parse_track(trackelement))

        yield page, totalpages, tracks

        page += 1
        sleep_func(.4)


def main(server, username, startpage, outfile, infotype='recenttracks',
         tracksperdayarg=100):
    trackdict = dict()
    global tracksperday
    tracksperday = tracksperdayarg

    page = startpage  # for case of exception
    totalpages = -1  # ditto
    n = 0
    try:
        for page, totalpages, tracks in get_tracks(server, username, startpage,
                                                   tracktype=infotype):
            print "Got page %s of %s.." % (page, totalpages)
            for track in tracks:
                n += 1
                trackdict.setdefault(n, track)
    except ValueError, e:
        exit(e)
    except Exception:
        raise

if __name__ == "__main__":
    parser = OptionParser()
    username, outfile, startpage, server, infotype, tracksperday = get_options(parser)
    with open(outfile, 'a') as outfileobj:
        outfileobj.write(("#AUDIOSCROBBLER/1.1\r\n#TZ/UTC\r\n#CLIENT/Rockbox h3xx 1.2\r\n").encode('utf-8'))
    main(server, username, startpage, outfile, infotype, tracksperday)
