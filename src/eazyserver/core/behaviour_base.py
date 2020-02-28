import logging
logger = logging.getLogger(__name__)
logger.debug("Loaded " + __name__)

# Import app to get api_config
def get_beh_config(behaviour_type, behaviour_id):
    import requests
    from requests.auth import HTTPBasicAuth
    from flask import current_app as app

    #TODO: Generalise AUTH config: change VedaUser to User and so on.
    api_config = app.config['VEDA_AUTH']
    Veda_auth = HTTPBasicAuth(api_config['VedaUser'], api_config['VedaPassword'])

    final_url = "{}/{}/{}/{}".format(api_config['ServerUrl'], api_config['API_VERSION'], behaviour_type, behaviour_id)     
    logging.info("Fetching Behaviour config: {}".format(final_url))

    resp = {}
    try:
        resp = requests.get(final_url, auth=Veda_auth, timeout=10)
        resp.raise_for_status()
        resp = resp.json()
    except Exception as e:
        logging.error("getConfig Failed:{}".format(e))
        resp = None
    if resp is None:
        raise RuntimeError("Failed to fetch cloud config for behaviour {}".format(behaviour_id))

    if(behaviour_type is "cameras"):
        resp['enabled'] = resp.get("isEnabled",True)
    else:
        resp['enabled'] = resp.get("params",{}).get("enable",True)
        
    return resp

class Behaviour(object):
    def __init__(self, config, behaviour_id=None, behaviour_type="behaviours"):
        
        if behaviour_id:
            config = get_beh_config(behaviour_type=behaviour_type, behaviour_id=behaviour_id)
        
        self.id = config["_id"]
        self.config  = config
        self.enabled = config.get("enabled",True)

    ###### Update Related Functions
    # Topics to be subscribed
    def subscriptionTopics(self,subscriptions=[]):
        if "camera" in self.config:
            # Behaviour update subscription
            subscriptions.append(
                {
                    "_id": self.id,
                    'topic':'behaviours',
                    'eventType': 'Updated'
                }
            )        
            subscriptions.append(
                {
                    "_id": self.id,
                    'topic':'behaviours',
                    'eventType': 'Replaced'
                }
            )
        # Camera update subscription
        # if type is behaviour
        if "camera" in self.config:
            camera_id = self.config["camera"]
             # Handle embedded=True case
            if type(camera_id) == dict:    
                camera_id = camera_id["_id"]
        else:
            camera_id = self.id
        
        subscriptions.append(
            {
                "_id": camera_id,
                'topic':'cameras',
                'eventType': 'Updated'
            }
        ) 
        subscriptions.append(
            {
                "_id": camera_id,
                'topic':'cameras',
                'eventType': 'Replaced'
            }
        ) 

        return subscriptions

    # update event callback
    def update(self, data):
        logger.info("Behaviour: hot updates not handled by behaviour: {}. It will be handled via restart policy".format(self))
        UpdateSuccess = False
        return UpdateSuccess

    def run(self, data):
        return(data)
