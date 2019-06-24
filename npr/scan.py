# scan.py

import functools
import datetime
import re

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)

bp = Blueprint('scan', __name__, url_prefix='/scan')

import click
from flask import current_app, g
from flask.cli import with_appcontext

from podgen import Podcast, Episode, Media

import requests
import requests_html
import pytz

import logging
log = logging.getLogger(__name__)

PARAMS_WEBTIMEOUT = "TIMEOUT"
PARAMS_BASEURL = "BASEURL"
PARAMS_MAINTEMPLATE = "MAINTEMPLATE"
PARAMS_SUBTEMPLATE = "SUBTEMPLATE"
params = {
    PARAMS_WEBTIMEOUT: 30,
    PARAMS_BASEURL:      'https://www.npr.org/programs/{program}/',
    PARAMS_MAINTEMPLATE: 'https://www.npr.org/programs/{program}/archive',
    PARAMS_SUBTEMPLATE:  'https://www.npr.org/programs/{program}/00/00/00/{episode}',
}

# NPR runs on eastern time
pod_tz = pytz.timezone('America/New_York')

def do_scrape():
    web_session = requests_html.HTMLSession()
    morning_edition = scrape_by_program('morning-edition')

class WebFormatException(Exception):
    def __init__(self, message):
        self.message = message

def scrape_by_program(program, web_session=requests_html.HTMLSession(), params=params):
    podcast = Podcast()
    podcast.explicit = False
    podcast.website = params[PARAMS_BASEURL].format(program=program)

    if program == 'morning-edition':
        podcast.name = "NPR Morning Edition"
        podcast.description = \
            """Every weekday for over three decades, Morning Edition has taken
            listeners around the country and the world with two hours of multi-faceted
            stories and commentaries that inform, challenge and occasionally amuse.
            Morning Edition is the most listened-to news radio program in the country."""
        podcast.image = 'https://media.npr.org/assets/img/2018/08/06/npr_me_podcasttile_sq-4036eb96471eeed96c37dfba404bb48ea798e78c-s200-c85.jpg'

    elif program == 'all-things-considered':
        podcast.name = "NPR All Things Considered"
        podcast.description = \
            """NPR's afternoon news show"""
        podcast.image = 'https://media.npr.org/assets/img/2018/08/06/npr_atc_podcasttile_sq-bcc33a301405d37aa6bdcc090f43d29264915f4a-s200-c85.jpg'

    elif program == 'weekend-edition-saturday':
        podcast.name = "NPR Weekend Edition Saturday"
        podcast.description = \
            """NPR morning news on Saturday"""
        podcast.image = 'https://media.npr.org/assets/img/2019/02/26/we_otherentitiestemplatesat_sq-cbde87a2fa31b01047441e6f34d2769b0287bcd4-s200-c85.png'

    elif program == 'weekend-edition-sunday':
        podcast.name = "NPR Weekend Edition Sunday"
        podcast.description = \
            """NPR morning news show on Sunday"""
        podcast.image = 'https://media.npr.org/assets/img/2019/02/26/we_otherentitiestemplatesun_sq-4a03b35e7e5adfa446aec374523a578d54dc9bf5-s200-c85.png'

    else:
        raise WebFormatException(f"program { program } not found")

    scrape(web_session, params, program, podcast)

    rssfeed = podcast.rss_str(minimize=False)
    #log.debug(f"\n\nfeed { rssfeed }")

    return rssfeed


def scrape_morning_edition(web_session=requests_html.HTMLSession(), params=params):

    podcast = Podcast()
    podcast.name = "NPR Morning Edition"
    podcast.description = \
        """Every weekday for over three decades, Morning Edition has taken
        listeners around the country and the world with two hours of multi-faceted
        stories and commentaries that inform, challenge and occasionally amuse.
        Morning Edition is the most listened-to news radio program in the country."""
    podcast.website = "https://www.npr.org/programs/morning-edition"
    podcast.explicit = False

    scrape(web_session, params, 'morning-edition', podcast)

    rssfeed = podcast.rss_str(minimize=False)
    #log.debug(f"\n\nfeed { rssfeed }")

    return rssfeed




def scrape(web_session, params, program, podcast):
    log.debug(f"scrape: processing { program }")

    url = params[PARAMS_MAINTEMPLATE].format(program=program)

    response = web_session.get(url, timeout=params[PARAMS_WEBTIMEOUT])
    response.raise_for_status()

    episode = response.html.find('#episode-list', first=True)
    if episode == None:
        raise WebFormatException(f"no episodes found on page { url }")

    articles = episode.find('article.program-show')
    for article in articles:
        if 'data-episode-id' not in article.attrs:
            raise WebFormatException(f"could not find data-episode-id in article on page { url }")

        episode_id = article.attrs['data-episode-id']
        episode_date = article.attrs['data-episode-date']
        #log.debug("episode id %s, episode date %s", episode_id, episode_date)
        podgen_episode = scrape_episode(web_session, params, program, episode_id, episode_date, podcast)
    
    
def scrape_episode(web_session, params, program, episode, date, podcast):
    url = params[PARAMS_SUBTEMPLATE].format(program=program, episode=episode)

    log.debug(f"url is { url }")
    
    response = web_session.get(url, timeout=params[PARAMS_WEBTIMEOUT])
    response.raise_for_status()

    episode = response.html.find('#story-list', first=True)
    if episode == None:
        raise WebFormatException(f"no episodes found on page { url }")

    stories = episode.find("article.rundown-segment")
    for story in stories:
        audio_module = story.find("div.audio-module", first=True)
        if audio_module == None:
            raise WebFormatException(f"no div.audio-module found on page { url }")
        audio_module_tools = audio_module.find("div.audio-module-tools", first=True)
        if audio_module_tools == None:
            raise WebFormatException(f"no div.audio-module-tools found on page { url }")
        
        download_element = audio_module_tools.find('li.audio-tool-download a', first=True)
        if download_element == None:
            # sometimes articles don't have download enabled.  Ignore them
            log.debug("No download link for article")
            continue
        href = download_element.attrs['href'] 
        e_title = story.find('h3.rundown-segment__title a', first=True)
        title = e_title.text
        link = e_title.attrs['href']
        duration = audio_module.find('time', first=True).text

        #log.debug(f"title { title } href { href } duration { duration }")

        pe = podcast.add_episode()
        pe.title = title
        pe.link = link

        pubdate = parse_date(href)
        if pubdate != None:
            pe.publication_date = pubdate

        filesize = parse_size(href)
        #log.debug(f"media filesize { filesize } href { href }")
        pe.media = Media(href, size=parse_size(href), type='audio/mpeg', duration=parse_duration(duration))

def parse_date(str):
    """ pull the date out of an NPR download link.
    Ideally this would be date + time, but time doesn't seem
    to be present anywhere in the interface

    Final component of the URL seems to be .../YYYYMMDD_slug.mp3?...
    Search for that and parse the results
    """
    m = re.search('/(\d{4})(\d{2})(\d{2})_[^/]+.mp3\?', str)
    if m == None:
        log.debug(f"No date found in url { str }")
        return None
    year = int(m.group(1))
    month = int(m.group(2))
    day = int(m.group(3))
    dt = datetime.datetime(year, month, day, tzinfo=pod_tz)
    #log.debug(f"found a date: { m.group(1) }-{ m.group(2) }-{ m.group(3) } / { dt }")
    return dt

def parse_size(str):
    """ pull the size out of an NPR link; look for ...&size=\d+& """
    m = re.search('&size=(\d+)&', str)
    if m == None:
        log.debug("no size found in url { str }")
        return 0
    return m.group(1)

def parse_duration(str):
    """ parse an NPR duration ([h:m:s]) into a datetime.timedelta """
    times = str.split(':')

    if len(times) >= 3:
        return datetime.timedelta(hours=int(times[0]), minutes=int(times[1]), seconds=int(times[2]))
    elif len(times) >= 2:
        return datetime.timedelta(minutes=int(times[0]), seconds=int(times[1]))
    else:
        return datetime.timedelta(seconds=int(times[0]))



@click.command('scan')
@with_appcontext
def click_scan():
    """ Scan the NPR site for updated feeds """
    do_scrape()
    click.echo('performed scrape')


def init_app(app):
    app.cli.add_command(click_scan)
    app.register_blueprint(bp)
