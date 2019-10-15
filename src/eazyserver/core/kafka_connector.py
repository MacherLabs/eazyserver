import logging
logger = logging.getLogger(__name__)
logger.debug("Loaded " + __name__)

import os
import json
import time
import sys
import pprint
from bson.objectid import ObjectId
from datetime import datetime

from pykafka_connector import Kafka_PyKafka
from confluent_kafka_connector import Kafka_Confluent


# TODO: Move/Add formatOutput to behaviour base class 
# Created following fields in output dict if missing:
# _id,_created,_updated,source_id,_type,_producer
def formatOutput(output,behavior,source_data): 
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
	if "_created" not in output: 
		if output["source_id"] is None or output["source_id"] == output["_id"]:
			output["_created"] = output["_updated"]
		else:
            # Propagate _created from input data which is source (_id of input specified as source_id of output)
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

class KafkaConnector(object):
	Type = "KafkaConnector"

	def __init__(self, Behaviour, kafka_client_type="confluent", **kwargs):

		self.kafka_should_run = True
		self.client = None
		self.behavior = Behaviour

		self.kafka_client_type = kafka_client_type
		self.kafka_client_config = kwargs
		
		# TODO : Validate **kwargs

		print("="*50)
		print("Printing kwargs...")
		for k,v in kwargs.items():
			print(k, v)
		print("="*50)

		# Create client based on type of Kafka Client specified
		if(self.kafka_client_type == "pykafka"):
			self.client = Kafka_PyKafka(kafka_client_config=self.kafka_client_config)

		if(self.kafka_client_type == "confluent"):
			self.client = Kafka_Confluent(kafka_client_config=self.kafka_client_config)

	def enable_kafka(self):
		logger.info("Enabling Kafka")
		self.kafka_should_run = True

	def disable_kafka(self):
		logger.info("Disbaling Kafka")
		self.kafka_should_run = False

	def run(self):

		while(True):
			if(self.kafka_should_run):
				source_data = []

				############################
				# Consume
				############################

				message_1 = None
				message_2 = None
				output = None

				# if both consumers are specified
				if(self.client.consumer_2_topic):
					# print("BOTH CONSUMER PRESENT")

					if(self.kafka_client_config['sync_consumers']):
						# sync_consumer = True
						message_1, message_2 = self.client.sync_consumers()

					else:
						# sync_consumer = False
						message_2 = self.client.consume2(block=False)
						message_1 = self.client.consume1()
					
					# Received both messages
					source_data.append(message_2)
					source_data.append(message_1)
					output = self.behavior.run(message_1, message_2)

				elif(self.client.consumer_1_topic):
					message_1 = self.client.consume1()
					source_data.append(message_1)
					output = self.behavior.run(message_1)
				else:
					output = self.behavior.run()

				# Transform output to fill missing fields
				if output:
					output = formatOutput(output, self.behavior, source_data)

				############################
				# Produce
				############################

				if(self.client.producer_topic):
					if(output):
						producer_response = self.client.produce(output, source_data)

			else:
				logger.info("Kafka Connector paused (self.kafka_should_run = False). Sleeping for 30 secs...")
				time.sleep(30)

