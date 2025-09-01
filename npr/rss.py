# rss.py

import datetime
import re

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, make_response
)

bp = Blueprint('rss', __name__, url_prefix='/npr')
#bp = Blueprint('rss', __name__)

from flask import current_app, g

from . import scan
from . import cache


import logging
log = logging.getLogger(__name__)


@bp.route('/morning-edition', endpoint='morning-edition')
@bp.route('/all-things-considered', endpoint='all-things-considered')
@bp.route('/weekend-edition-saturday', endpoint='weekend-edition-saturday')
@bp.route('/weekend-edition-sunday', endpoint='weekend-edition-sunday')
@cache.cached()
def rss_request():
    endpoint = request.endpoint.replace('rss.', '')
    rss = scan.scrape_by_program(endpoint);

    response = make_response(rss)
    response.headers.set('Content-type', 'application/rss-xml')
    return response


def init_app(app):
    app.register_blueprint(bp)
