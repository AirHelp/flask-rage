# DEPRECATED

###This is no longer supported

## Flask RAGE
[![Build Status](https://travis-ci.org/AirHelp/flask-rage.svg?branch=develop)](https://travis-ci.org/AirHelp/flask-rage)

Flask extension allowing to mimic Ruby on Rails' [lograge](https://github.com/roidrage/lograge) gem behavior

## Application setup
Enable logger for the application
```
from flask import Flask
from flask_rage import FlaskRage

app = Flask(__name__)

rage = FlaskRage()
rage.init_app(app)

```

## Logging config
To avoid multiple entries you may want to disable (e.g. send to `logging.NullHandler`) messages 
from `werkzeug` or `gunicorn`

```
[handler_stream]
class=logging.StreamHandler
formatter=flask_rage
args=()

[formatter_flask_rage]
class=flask_rage.FlaskRageFormatter
```
