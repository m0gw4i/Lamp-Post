import datetime
import urllib
import urllib2
import json
from flask import Flask, render_template
import ConfigParser
import sys
from werkzeug.contrib.cache import SimpleCache
import forecastio
import praw
import datetime
import time
cache = SimpleCache()


config = ConfigParser.ConfigParser()
config.readfp(open(r'config.cfg'))

app = Flask(__name__)

def get_times(api, stop):
    h_times = list()
    url = "http://realtime.mbta.com/developer/api/v2/predictionsbystop"
    opener = urllib2.build_opener()
    urllib2.install_opener(opener)
    params = {'api_key': api, 'stop': stop, 'format': "json"}
    data = urllib.urlencode(params)
    try:
        response = urllib2.urlopen("%s?%s" %(url, data)).read()
        parsed = json.loads(response)
        predictions = dict()
        for i in parsed['mode']:
            for r in i['route']:
                for d in r['direction']:
                    if d['direction_id'] == "0":
                        for p in d['trip']:
                            heading = p['trip_headsign']
                            mins, secs = str(datetime.timedelta(seconds=int(p['pre_away']))).split(":")[1:]
                            pre_time = "%s:%s" %(mins, secs)
                            times = predictions.setdefault(heading, list())
                            times.append(mins)
        if predictions:
            return predictions
            '''for heading, times in predictions.iteritems():
                mins = [str(x) for x in times][0:2]
                h_times.append("%s: %s" %(heading, " & ".join(mins)))
            return h_times'''
        else:
            return ["No Predictions"]
    except urllib2.HTTPError:
        return ["No Predictions"]

def get_alerts(api, stop):
    alerts = {}
    alert_headers = []
    url = "http://realtime.mbta.com/developer/api/v2/alertheadersbystop"
    opener = urllib2.build_opener()
    urllib2.install_opener(opener)
    params = {'api_key': api, 'stop': stop, 'format': "json", 'include_access_alerts': "false"}
    data = urllib.urlencode(params)
    try:
        response = urllib2.urlopen("%s?%s" %(url, data)).read()
        parsed = json.loads(response)
        alerts = parsed
        if alerts.has_key('alert_headers'):
            alert_headers = [i['header_text'] for i in alerts['alert_headers'] if i.has_key('header_text')]
        return alert_headers
    except urllib2.HTTPError:
        return [""]

def get_weather(api_key, lat, lng):
    w = forecastio.load_forecast(api_key, lat, lng)
    cat = "{0:.0f}".format(w.currently().d['apparentTemperature'])
    ci = w.currently().d['icon']
    cp = w.currently().d['precipProbability']
    cc = {'app_temp': cat, 'icon': ci, 'pp': "{0:.0f}%".format(cp * 100)}
    week = list()
    for d in w.daily().data:
        ds = dict()
        ds = {'day': "%s" %(d.time.strftime("%A")), 'date': "%s" %(d.time.strftime("%b %d")), 'max_temp': "{0:.0f}".format(d.d['temperatureMax']), 'min_temp': "{0:.0f}".format(d.d['temperatureMin']), 'icon': d.d['icon'], 'pp': "{0:.0f}%".format(d.d['precipProbability'] * 100)}
        week.append(ds)
    return cc, week

def get_nyt(api_key):
    nyt = list()
    url = "http://api.nytimes.com/svc/topstories/v1/home.json"
    params = {'api-key': api_key}
    data = urllib.urlencode(params)
    opener = urllib2.build_opener()
    urllib2.install_opener(opener)
    response = urllib2.urlopen("%s?%s" %(url, data)).read()
    parsed = json.loads(response)
    for r in parsed['results'][0:10]:
        title = r['title']
        url = r['url']
        abstract = r['abstract']
        byline = r['byline']
        nyt.append({'title': title, 'url': url, 'abstract': abstract, 'byline': byline})
    return nyt

def get_reddit_fp():
    r = praw.Reddit(user_agent='lamp_post')
    fp = r.get_front_page(limit=10)
    fp = [(x.score, x.title, x.url, x.permalink, x.thumbnail) for x in fp]
    return fp
@app.route("/_getText")
def getText():
    return time.strftime("%H:%M:%S")
@app.route("/")
def display():
    h_times = []
    mbta_api = config.get('MBTA', 'api')
    stop = config.get('MBTA', 'stop')
    
    forecastio_api = config.get('Forecast', 'api')
    lat = config.get('Forecast', 'lat')
    lng = config.get('Forecast', 'lng')

    nyt_api = config.get('NYT', 'api')

    predictions = cache.get('predictions')
    if predictions is None:
        predictions = get_times(mbta_api, stop)
        cache.set('predictions', predictions, timeout=20)
    
    
    alerts = cache.get('alerts')
    if alerts is None:
        alerts = get_alerts(mbta_api, stop)
        cache.set('alerts', alerts, timeout=30*60)
    weather = cache.get('weather')
    if weather is None:
        weather = get_weather(forecastio_api, lat, lng)
        cache.set('weather', weather, timeout=60*60)
    cc, week = weather

    
    news = cache.get('news')
    if news is None:
        news = get_nyt(nyt_api)
        cache.set('news', news, timeout=60*60)

    front_page = cache.get('reddit_front_page')
    if front_page is None:
        front_page = get_reddit_fp()
        cache.set('reddit_front_page', front_page, timeout=60*60)

    return render_template('new-index.html', predictions=predictions, cc=cc, week=week, news=news, alerts=alerts, front_page=front_page)

if __name__ == "__main__":
	app.run(host='0.0.0.0', debug=True)
