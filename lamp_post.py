import datetime
import urllib
import urllib2
import json
from flask import Flask, render_template
import ConfigParser
import sys
from werkzeug.contrib.cache import SimpleCache
import forecastio
cache = SimpleCache()


config = ConfigParser.ConfigParser()
config.readfp(open(r'config.cfg'))

app = Flask(__name__)

def get_times(api, stop):
    url = "http://realtime.mbta.com/developer/api/v2/predictionsbystop"
    opener = urllib2.build_opener()
    urllib2.install_opener(opener)

    params = {'api_key': api, 'stop': stop, 'format': "json"}

    data = urllib.urlencode(params)
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
                        times.append(pre_time)
    return predictions

def get_alerts(api, route):
    url = "http://realtime.mbta.com/developer/api/v2/alertsbyroute"
    opener = urllib2.build_opener()
    urllib2.install_opener(opener)

    params = {'api_key': api, 'route': route, 'format': "json", 'include_access_alerts': "false"}

    data = urllib.urlencode(params)
    response = urllib2.urlopen("%s?%s" %(url, data)).read()
    parsed = json.loads(response)
    alerts = parsed['alerts']
    return alerts

def get_weather(api_key, lat, lng):
    w = forecastio.load_forecast(api_key, lat, lng)
    ct = w.currently().d['apparentTemperature']
    ct = "%s" %(ct)
    hs = w.hourly().summary
    wd = w.daily().summary
    
    return ct, hs , wd

@app.route("/")
def display():
    h_times = []
    mbta_api = config.get('MBTA', 'api')
    stop = config.get('MBTA', 'stop')
    
    forecastio_api = config.get('Forecast', 'api')
    lat = config.get('Forecast', 'lat')
    lng = config.get('Forecast', 'lng')

    predictions = cache.get('predictions')
    if predictions is None:
        predictions = get_times(mbta_api, stop)
        cache.set('predictions', predictions, timeout=20)
    
    alerts_931 = get_alerts(mbta_api, "931_")
    alerts_933 = get_alerts(mbta_api, "933_")

    weather = cache.get('weather')
    if weather is None:
        weather = get_weather(forecastio_api, lat, lng)
        cache.set('weather', weather, timeout=60*60)
    ct, hs, wd = weather

    for heading, times in predictions.iteritems():
        mins = [str(x) for x in times][0:2]
        h_times.append("%s: %s" %(heading, " & ".join(mins)))
    
    return render_template('index.html', h_times=h_times, ct=ct, hs=hs, wd=wd)

if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True)