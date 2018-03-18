from __future__ import print_function

import warnings

from flask import Flask

import requests
import requests_toolbelt.adapters.appengine
import urllib3.contrib.appengine
from routes import routes

requests.packages.urllib3.disable_warnings(
    requests.packages.urllib3.contrib.appengine.AppEnginePlatformWarning
)

requests_toolbelt.adapters.appengine.monkeypatch()

app = Flask(__name__)
app.config.from_object('config')
app.register_blueprint(routes)

if __name__ == '__main__':
    app.run()
