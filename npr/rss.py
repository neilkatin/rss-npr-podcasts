# rss.py

import datetime
import re

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, make_response
)

bp = Blueprint('rss', __name__, url_prefix='/rss')

from flask import current_app, g

from . import scan


import logging
log = logging.getLogger(__name__)


@bp.route('/morning-edition')
def morning_edition():
    rss = scan.scrape_morning_edition();

    response = make_response(rss)
    response.headers.set('Content-type', 'application/rss-xml')
    return response


def init_app(app):
    app.register_blueprint(bp)
