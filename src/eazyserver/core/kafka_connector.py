import logging
logger = logging.getLogger(__name__)
logger.debug("Loaded " + __name__)

import json
import time
from bson.objectid import ObjectId
from datetime import datetime

from confluent_kafka import Producer as KafkaProducer
from confluent_kafka import Consumer as KafkaConsumer
from confluent_kafka import TopicPartition

# def dict_to_binary(the_dict):
# 	binary = ' '.join(format(ord(letter), 'b') for letter in the_dict)
# 	return binary

# def binary_to_dict(the_binary):
# 	jsn = ''.join(chr(int(x, 2)) for x in the_binary.split())
# 	return jsn

def kafka_to_dict(kafka_msg):
	msg = json.loads(kafka_msg.value())
	kafka_msg_id = "{id}:{topic}:{partition}:{offset}".format(**{ "id":msg["_id"],"offset":kafka_msg.offset(), "partition": kafka_msg.partition(), "topic":kafka_msg.topic() })
	msg["_kafka__id"]= kafka_msg_id
	return msg
	
def dict_to_kafka(output,source_data):
	for data in source_data:
		if output["source_id"] == data["_id"]:
			output["_kafka_source_id"] = data["_kafka__id"]
			break
	kafka_msg = json.dumps(output)
	return kafka_msg

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

class KafkaConnector(object):
	Type = "KafkaConnector"
	def __init__(self, Behaviour, producer_topic=None, consumer_topic=None, consumer_topic2=None, kafka_broker="localhost:9092", sync_consumer=True, auto_offset_reset='largest'):
	# def __init__(self, Behaviour):
		super(KafkaConnector, self).__init__()

		self.behavior = Behaviour
		self.producer_topic = producer_topic
		self.consumer_topic = consumer_topic
		self.consumer_topic2 = consumer_topic2
		self.sync_consumer = sync_consumer
		self.kafka_api_version = (2, 12, 2)

		logger.info("=" * 20)
		logger.info("Kafka INIT Config : ")
		logger.info("Behaviour : " + str(Behaviour))
		logger.info("producer_topic : " + str(producer_topic))
		logger.info("consumer_topic : " + str(consumer_topic))
		logger.info("consumer_topic2 : " + str(consumer_topic2))
		logger.info("sync_consumer : " + str(sync_consumer))
		logger.info("auto_offset_reset : " + str(auto_offset_reset))
		logger.info("=" * 20)

		if(producer_topic):
			self.producer = KafkaProducer({'bootstrap.servers': kafka_broker, 'message.max.bytes' : 20000000})
		else:
			self.producer = None
		
		if(consumer_topic):
			self.consumer = KafkaConsumer({ 'bootstrap.servers': 'kafka', 'group.id': str(Behaviour) + str(consumer_topic) , 'auto.offset.reset': auto_offset_reset, 'max.poll.interval.ms': 86400000 }) # Check str(Behaviour) 
			self.consumer.subscribe([consumer_topic])
			self.consumer.poll()
		else:
			self.consumer = None

		if(consumer_topic2):
			self.consumer2 = KafkaConsumer({ 'bootstrap.servers': 'kafka', 'group.id': str(Behaviour) + str(consumer_topic2) , 'auto.offset.reset': auto_offset_reset, 'max.poll.interval.ms': 86400000 })
			self.consumer2.subscribe([consumer_topic2])			
			self.consumer2.poll()
		else:
			self.consumer2 = None

	def run(self):
		while True:
			if(self.consumer): # Check at least primary consumer is present
				logger.info("Consumed | {} | Topic : {}".format(self.behavior.__class__.__name__, self.consumer_topic))
				kafka_msg = self.consumer.consume(num_messages=1)[0]
				msg = kafka_to_dict(kafka_msg)
			else:
				msg = None

			if(self.consumer2): # check for two consumers		
				try:
					
					if(self.sync_consumer):
						kafka_msg = self.consumer2.consume(num_messages=1)[0]
						msg2 = kafka_to_dict(kafka_msg)
						assert msg2["_id"] == msg["source_id"]
					else:
						msg2_raw = self.consumer2.poll(timeout=0.01)

						if msg2_raw:
							msg2 = kafka_to_dict(msg2_raw)							
						else:
							msg2 = None
				except AssertionError:

					logger.info("Syncing Partition...")
					kafka_source_id = msg["_kafka_source_id"]			#"{id}:{topic}:{partition}:{offset}"
					topicName = kafka_source_id.split(":")[-3] 			# 3rd last 
					partitionName = int(kafka_source_id.split(":")[-2]) # 3rd last
					offset =  int(kafka_source_id.split(":")[-1])
					partition = TopicPartition(topic=topicName, partition=partitionName, offset=offset) 

					logger.debug("Partition : " + str(partition))

					self.consumer2.seek(partition)
					msg2 = kafka_to_dict(self.consumer2.consume(num_messages=1)[0])

				output = self.behavior.run(msg, msg2)
			elif(self.consumer): # One consumer only
				output = self.behavior.run(msg)
			else: # Not even primary consumer present, producer only behaviour
				output = self.behavior.run()
			
			# Transform output to fill missing fields
			if output:
				source_data = []
				if self.consumer: source_data.append(msg)
				if self.consumer2: source_data.append(msg2)
				output=formatOutput(output,self.behavior,source_data)

			if(self.producer_topic is not None):
				logger.info("Produced | {} | Topic : {}".format(self.behavior.__class__.__name__, self.producer_topic))
				if(output):
					value = dict_to_kafka(output,source_data)
					self.producer.produce(self.producer_topic, value)
					self.producer.poll(0)
