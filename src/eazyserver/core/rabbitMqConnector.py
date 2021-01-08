import logging
logger = logging.getLogger(__name__)
logger.debug("Loaded " + __name__)

import os
import json
import time
import sys
import traceback
from prettyprinter import pprint
from bson.objectid import ObjectId
from datetime import datetime

import rabbitMqConnector as Connector


# TODO: Move/Add formatOutput to behaviour base class 
# Created following fields in output dict if missing:
# _id,_created,_updated,source_id,_type,_producer
def formatOutput(output,behavior,source_data=None): 
    if "_id" not in output: output["_id"] = str(ObjectId())
    if "_updated" not in output: output["_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if "_type" not in output: output["_type"] = "BEHAVIOUR"		#TODO take from behavior object
    if "_producer" not in output: output["_producer"] = "{}:{}:{}".format(behavior.__class__.__name__,"1.0",behavior.id) #name:version:id #TODO take version from behaviour

    # Source chaining for stream
    if "source_id" not in output: 
        if source_data: # Select rightmost consumer
            output["source_id"] = source_data[-1]["_id"]
        else:  # This is Producer
            output["source_id"] = output["_id"]

    # source_config chaining for stream
    if source_data: # Select rightmost consumer
        output_source_config = source_data[-1]["source_config"]
    else:
        # init from behaviour config values 
        output_source_config ={
            "organization":behavior.config.get("organization", ""),
            "hub":behavior.config.get("hub", ""),
            "camera":behavior.config.get("camera", behavior.config.get("_id", "")),
            "behaviourType":behavior.config.get("behaviourType", ""),
            "behaviour":behavior.config.get("_id", ""),
        }
        # Handle embedded=true case
        for key,value in output_source_config.items():
            if type(value) ==dict:
                output_source_config[key] = value.get("_id","")
        # Handle camera type
        if output_source_config["behaviour"] == output_source_config["camera"]:
            output_source_config["behaviour"] = ""
            output_source_config["behaviourType"] = "camera"

    output_source_config.update(output.get("source_config",{}))
    output["source_config"]=output_source_config

    if "_created" not in output: 
        if output["source_id"] is None or output["source_id"] == output["_id"]:
            output["_created"] = output["_updated"]
        else:
            # Propagate _created from input data which is source (_id of input specified as source_id of output)
            if source_data:
                for data in source_data:
                    if output["source_id"] == data["_id"]:
                        output["_created"] = data["_created"]
                        break
                # Propagate _created time based upon same source_id of input data
                for data in source_data:
                    if output["source_id"] == data["source_id"]:
                        output["_created"] = data["_created"]
                        break
                    
    if "_created" not in output: 		
        logger.info("{} | source_id  {} not found for id {}".format(output["_producer"],output["source_id"],output["_id"]))
        output["_created"] = output["_updated"]
        
    return output

#############################
## Main Connector Class
#############################

class RabbitMqConnector(object):
    Type = "RabbitMqConnector"

    def __init__(self, Behaviour, client_type="rabbitMq", on_exit=None, **kwargs):
        self.should_stop =False
        self.client = None
        self.behavior = Behaviour

        self.client_type = client_type
        self.client_config = kwargs
        self.exit_callbacks=[]
        if on_exit: self.exit_callbacks.append(on_exit)
        
        # TODO : Validate **kwargs
        
        RABBIT_SERVER_CONFIG=self.client_config.get("rabbitServerConfig",{
            'host':"queue.vedalabs.in",
            'user':'guest',
            'password':'guest',
            'port':5672
        })
        
        REST_API_CONFIG=self.client_config.get("restApiConfig",None)
        
        self.consumerTopics=self.client_config.get("consumerTopics",None)
        self.producerTopic=self.client_config.get("producerTopic",None)
        self.consumerSubscriptions=self.client_config.get("consumerSubscriptions",None)
        self.producerSubscriptions=self.client_config.get("producerSubscriptions",None)
        self.consumerSyncTopics=self.client_config.get("consumerSyncTopics",None)
        self.consumerSyncMode=self.client_config.get("consumerSyncMode",False)
        self.sender_rabbit_server_config=self.client_config.get("sender_rabbit_server_config",None)
        self.receiver_rabbit_server_config=self.client_config.get("receiver_rabbit_server_config",None)
        
        print("="*50)
        print("Printing kwargs...")
        for k,v in kwargs.items():
            print(k, v)
        print("="*50)

        # Create client based on type of Kafka Client specified
        queueId=self.behavior.config.get("_id","")
        self.asyncLock=False
        
        self.client=Connector.RabbitMqConnector(rabbit_server_config=RABBIT_SERVER_CONFIG,        
                                                topicCallback=self.consume,
                                                subscriptionCallback=self.update,
                                                consumerTopics=self.consumerTopics,
                                                consumerSubscriptions=self.consumerSubscriptions,
                                                consumerSyncTopics=self.consumerSyncTopics,
                                                producerTopic=self.producerTopic,
                                                rest_api_config=REST_API_CONFIG,
                                                sender_exchange="BEHAVIOUR_EVENTS",
                                                receiver_exchange="BEHAVIOUR_EVENTS",
                                                sender_rabbit_server_config=self.sender_rabbit_server_config,
                                                receiver_rabbit_server_config=self.receiver_rabbit_server_config,
                                                queueId=queueId)
        
        # Add rabbit mq client to the behaviour object as well
        self.behavior.connector_client=self.client
        
    def stop(self):
        self.should_stop=True
        logger.info("Behaviour is schedule for shutdown.")
        self.client.stop()
        
    def send(self,output,source_data=None):
        output = formatOutput(output, self.behavior,source_data)
        self.client.send(producerTopic=self.producerTopic,message=output)
        

    ###### Update Related Functions
    # Topics to be subscribed
    def subscriptionTopics(self,subscriptions=[]):
        subscriptions = self.behavior.subscriptionTopics(subscriptions)
        return subscriptions

    # update event callback
    def update(self, data,props=None,methods=None):
        logger.debug("KafkaConnector: Update triggered with data:{}".format(data))
        UpdateSuccess = self.behavior.update(data)
        logger.debug("KafkaConnector: Hot update status:{}".format(UpdateSuccess))
        
        return UpdateSuccess
           
                
    def consume(self,message,props=None,methods=None):
        print ("consume called for msg")
        try:
            while(self.asyncLock==True):
                time.sleep(0.1)
                print("waiting for async lock")
            self.asyncLock=True
            consumerTopic=methods.routing_key
            output=self.behavior.run(message)   
            if output:
                self.send(output,[message])
            self.asyncLock=False
        except Exception as e:
            self.asyncLock=False
            logger.error("Exception in Behaviour code:{}".format(str(e)))
            self.client.stop()
            print("-"*60)
            traceback.print_exc(file=sys.stdout)
            self.on_exit(101)
            print("-"*60)
            exit(101) 
            
            
        
    def run(self,app):
        app.app_context().push()
        while(not self.should_stop):
            try:
                if (self.consumerTopics ==None and self.consumerSyncTopics ==None):
                        output=self.behavior.run()
                        if output:
                            self.send(output)    
                            
                if self.consumerSyncTopics:
                    if self.consumerSyncMode !=True:
                        for topic in self.consumerSyncTopics:
                            message=self.client.consume_sync(topic)
                            if message:
                                output=self.behavior.run(message)
                                if output:
                                    self.send(output,[message])
                                
                    else:
                        message=self.client.consume_sync_all()
                        if message:
                            output=self.behavior.run(message)
                            if output:
                                self.send(output,[message])
                            
            except Exception as e:
                logger.error("Exception in Behaviour code:{}".format(str(e)))
                self.client.stop()
                print("-"*60)
                traceback.print_exc(file=sys.stdout)
                self.on_exit(101)
                print("-"*60)
                exit(101)
            time.sleep(0.01)
                

    def on_exit(self,exit_code):
        for callback in self.exit_callbacks:
            callback(exit_code)
