import os
import sys
import logging
import logging.config

from flask import Flask
from flask_caching import Cache
#from flask_reverse_proxy_fix.middleware import ReverseProxyPrefixFix
from werkzeug.middleware.proxy_fix import ProxyFix

import dotenv


def create_app(test_config=None):
    global log

    dotenv.load_dotenv('.env')

    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    init_logging(__name__, app)
    app.wsgi_app = ProxyFix(
        app.wsgi_app, x_for=1, x_proto=1, x_prefix=1
        )

    app.config.from_prefixed_env()

    log.info(f"os.getenv[FLASK_DEBUG] { os.getenv('FLASK_DEBUG') }")
    app.config['DEBUG'] = os.getenv('FLASK_DEBUG')
    log.info(f"debug { app.config['DEBUG'] } app.debug { app.debug }")
    #app.config.from_mapping(
        # taken from .flaskenv and .env
        #SECRET_KEY='dev',
        #DATABASE=os.path.join(app.instance_path, 'flaskr.sqlite'),
    #)

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
        #app.config.from_object(f".config.{ app.config['ENV'].capitalize() }Config")
        app.config.from_object(f"{ __name__ }.config.{ app.config['ENV'].capitalize() }Config")
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass


    #log.debug(f"app.config: { app.config }")
    log.debug(f"app.config['ENV'] = { app.config['ENV'] }, __name__ = { __name__ }")

    #ReverseProxyPrefixFix(app)

    global cache
    if app.config['DEBUG']:
        #cache = Cache(config={'CACHE_TYPE': 'null', 'CACHE_NO_NULL_WARNING': True })
        #cache = Cache(config={'CACHE_TYPE': 'simple', 'CACHE_DEFAULT_TIMEOUT': 5 })
        cache = Cache(config=app.config)
    else:
        cache = Cache(config={'CACHE_TYPE': 'simple'})

    cache.init_app(app)

    # a simple page that says hello
    @app.route('/hello')
    def hello():
        return 'Hello, World!'

    @app.route('/')
    def root():
        return """
            <p>This app returns RSS feeds for NPR programs that don\'t return it themselves.</p>

            <p>Supported URLs are:</p>

            <ul>
                <li><a href='/npr/morning-edition'>/npr/morning-edition</a></li>
                <li><a href='/npr/all-things-considered'>/npr/all-things-considered</a></li>
                <li><a href='/npr/weekend-edition-saturday'>/npr/weekend-edition-saturday</a></li>
                <li><a href='/npr/weekend-edition-sunday'>/npr/weekend-edition-sunday</a></li>
            </ul>
            """

    from . import scan
    scan.init_app(app)

    from . import rss
    rss.init_app(app)

    return app


def init_logging(app_name, app):
    logging_config = {
        'version': 1,
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'default',
                'level': 'DEBUG',
                'stream': 'ext://sys.stderr'
            },
            'wsgi': {
                'class': 'logging.StreamHandler',
                'formatter': 'default',
                'level': 'DEBUG',
                'stream': 'ext://flask.logging.wsgi_errors_stream'
            },
        },
        'formatters': {
            'default': {
                'format': '%(asctime)s %(levelname)-5s %(name)-10s %(funcName)-.15s:%(lineno)d %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S',
            },
        },
        'root': {
            'level': 'DEBUG' if app.config['DEBUG'] else 'INFO',
            #'handlers': [ 'console', 'wsgi' ],
            'handlers': [ 'wsgi' ],
        },
        'loggers': {
            'urllib3': {
                'level': 'INFO',
            },
            'selenium': {
                'level': 'INFO',
            },
            'pyexcel': {
                'level': 'INFO',
            },
            'pyexcel_io': {
                'level': 'INFO',
            },
            'lml': {
                'level': 'INFO',
            },
            'watchdog': {
                'level': 'INFO',
            },
        },
    }

    logging.config.dictConfig(logging_config)
    global log
    log = logging.getLogger(app_name)


