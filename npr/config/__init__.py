

class Config(object):
    pass

class DevelopmentConfig(Config):
    CACHE_TYPE='null'
    CACHE_NO_NULL_WARNING=True

class ProductionConfig(Config):
    CACHE_TYPE='simple'
    CACHE_DEFAULT_TIMEOUT=600
