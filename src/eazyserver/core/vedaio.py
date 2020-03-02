import socketio
import logging
logger = logging.getLogger(__name__)
logger.info("Loaded " + __name__)
import os
from bson import json_util

import json
import requests
from requests.auth import HTTPBasicAuth
from flask import jsonify, Response

from threading import Event
from .utils import threaded,is_main_thread_active
from time import sleep


class VedaSocketIO():
    def __init__(self,api_config=None, subscriptions=[]):
        print("---------------------------veda socketio init called!------------------------")
        # 
        # #TODO: Generalise AUTH config: change VedaUser to User and so on.
        if api_config is None:
            from flask import current_app as app
            self.config = app.config
        else:
            self.config=api_config

        self.oneTimeLoginCalled = False
        self.LoggedinSuccess = Event()
        self.subscriptions=subscriptions
        self.userid=""
        self.loginCreds= {
            "auth": {
                "username": self.config['VEDA_USER'],
                "password": self.config['VEDA_PASSWORD']
            },
            "roomno":""
        }

        self.authHeader = {
           "sessionid" : ""
        }
        self.sio = socketio.Client()


        @self.sio.event
        def connect():
            print('-----------------------------------------connection established------------------------------------------')
            print ('connection established',self.sio.sid)
            if self.oneTimeLoginCalled==False :
                self.callOneTimeLogin()
            for topic in self.subscriptions:
                self.subscribe(topic, remember=False)

        @self.sio.on('loggedIn')
        def on_loggedIn(data):
            print ('logged in successfully',data)
            self.authHeader['sessionid'] = data['sessionid']
            self.LoggedinSuccess.set()

        @self.sio.event
        def error(data):
            print('VedaIO: ERROR:', data)

        @self.sio.event
        def my_message(data):
            print('message received with ', data)
            self.sio.emit('my response', {'response': 'my response'})

        @self.sio.event
        def disconnect():
            print('disconnected from server')


        socketioServer = os.environ.get('SOCKETIO_SERVER', self.config.get("VEDA_SERVER_URL","localhost"))
        print(socketioServer)
        threaded(self.connect_with_retry,socketioServer)

    # Connect to socket server with retries, use utils.threaded for background connection
    def connect_with_retry(self, url, retry=0, retry_interval=5, *args, **kwargs):
        while (is_main_thread_active()):
            try:
                self.sio.connect(url)
                break
            except socketio.exceptions.ConnectionError as e:
                logger.error("VEDAIO Connection failure: retrying again.{}".format(retry))
                continue
            except Exception as e:
                logger.error("VEDAIO Connection failure: {}".format(e))
                break
            finally:
                if retry == 1: break
                elif retry >1 :
                    retry -= 1
                
                sleep(retry_interval)
                

    def subscribe(self,topic, timeout=5, remember=True, remember_on_failure=True):
        # check for login status
        if not self.LoggedinSuccess.is_set():
            success=self.LoggedinSuccess.wait(timeout=timeout)
            if not success:
                if remember_on_failure:
                    self.subscriptions.append(topic)
                    return
                else:
                    raise RuntimeError("Log in timed out")
        
        # Subscribe
        print("Subscribing............")
        data = {
            "topicFilters" : topic,
            'sessionid': self.authHeader['sessionid'],
            "consumer" : self.userid
        }
        print(data)
        self.sio.emit("subscribe",data)

        # remember to auto subscribe on connect and disconnets events
        if remember:
            self.subscriptions.append(topic)

    def send(self,data,topic="resourceUpdate", timeout=5):
        if not self.LoggedinSuccess.is_set():
            self.LoggedinSuccess.wait(timeout=timeout)
        print("Sending............")
        data['sessionid'] = self.authHeader['sessionid']
        self.sio.emit(topic, data)
        
    def callOneTimeLogin(self):
        print("one time login called!")
        self.oneTimeLoginCalled = True
        try:
            #TODO use username
            # with app.app_context():
                # usersCol = app.data.driver.db['users']
                # query = { "username": self.loginCreds['auth']['username'] }
                # user = usersCol.find_one(query)

                url = self.config.get("VEDA_SERVER_URL","localhost")+"/v1/rest/login"
                data = self.loginCreds["auth"]
                auth = HTTPBasicAuth(self.config['VEDA_USER'], self.config['VEDA_PASSWORD'])
                response = requests.request("POST", url, json=data, auth=auth, timeout=10)
                response.raise_for_status()
                user=response.json()

                # print 'user:',user['_id'], type(user['_id'])
                if user:
                    # userJson = json.loads(user, default=json_util.default)
                    # print 'user in json format',userJson
                    self.userid = str(user['_id'])
                    # print self.userid,type(self.userid)
                    self.loginCreds['roomno']=self.userid
                    print (self.loginCreds)
                    self.sio.emit('join',self.loginCreds)
                else:
                    print( "user not found!!")

        except Exception as er:
            print("error happened while making call",er)

        if self.userid:
            print('userid:',self.userid)
        else:
            print("no valid userid")
        print("one time login ends")

# socketClient = VedaSocketIO()

