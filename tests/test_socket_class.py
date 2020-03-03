from eazyserver.core.vedaio import VedaSocketIO
from time import sleep

api_config ={
    'VEDA_USER': "tempuser",
    'VEDA_PASSWORD': "tempuser",
    'VEDA_API_VERSION' : 'v1/rest',
    'VEDA_DEVICE_ID' : '5a609e3ffc94243786cc9ba9',
    'VEDA_SERVER_URL' : 'https://api.staging.vedalabs.in',
}


socketClient=VedaSocketIO(api_config)

print("Initialisation Completed!!")

class ABC():
    def __init__(self):
        print("initialising ABC!!!")
        self.subscription=[]
        self.updateHandler()

    def updateHandler(self):
        @socketClient.sio.on("message")
        def my_message(data):
            self.update(data)
    
    def update(self,data):
        print('message received in class ABC, Object: {} with data:{}'.format(self,data))


print("Subscribing")
subscribe_topic= {
    "organization" : "59bf87d978ada0d6df4e29f6",
    "hub": "5d9c5158f78f95b45dc6a58f",
    "_id": "5d9c5563c943900991530054",
    'topic':'behaviours',
    # 'eventType': 'cReAtED',
    'eventType': 'Updated'
}
print(subscribe_topic)
socketClient.subscribe(subscribe_topic)

subscribe_topic= {
    "organization" : "59bf87d978ada0d6df4e29f6",
    "hub": "5d9c5158f78f95b45dc6a58f",
    "_id": "5d9c5210f78f95b45dc6a590",
    'topic':'cameras',
    'eventType': 'Updated'
}

print(subscribe_topic)
socketClient.subscribe(subscribe_topic)

print("Chandler Bing")

sleep(30)
print("How are you doin!!")
bc=ABC()

while True: sleep(100)