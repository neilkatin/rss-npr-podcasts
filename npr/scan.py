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

import logging
log = logging.getLogger(__name__)

PARAMS_WEBTIMEOUT = "TIMEOUT"
PARAMS_MAINTEMPLATE = "MAINTEMPLATE"
PARAMS_SUBTEMPLATE = "SUBTEMPLATE"
params = {
    PARAMS_WEBTIMEOUT: 30,
    PARAMS_MAINTEMPLATE: 'https://www.npr.org/programs/{program}/archive' ,
    PARAMS_SUBTEMPLATE:  'https://www.npr.org/programs/{program}/00/00/00/{episode}' ,
}

def do_scrape():
    web_session = requests_html.HTMLSession()
    morning_edition = scrape_morning_edition(web_session, params)

class WebFormatException(Exception):
    def __init__(self, message):
        self.message = message

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
    log.debug("scrape: called")

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
        log.debug("episode id %s, episode date %s", episode_id, episode_date)
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
        
        href = audio_module_tools.find('li.audio-tool-download a', first=True).attrs['href'] 
        e_title = story.find('h3.rundown-segment__title a', first=True)
        title = e_title.text
        link = e_title.attrs['href']
        duration = audio_module.find('time', first=True).text

        log.debug(f"title { title } href { href } duration { duration }")

        pe = podcast.add_episode()
        pe.title = title
        pe.link = link
        pe.media = Media(href, size=parse_size(link), type='audio/mpeg', duration=parse_duration(duration))


def parse_size(str):
    """ pull the size out of an NPR link; look for ...&size=\d+& """
    m = re.search(r'\&size=(\d+)\&', str)
    if m == None: return 0
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
