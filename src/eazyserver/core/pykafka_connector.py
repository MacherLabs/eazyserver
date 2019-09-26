import logging
logger = logging.getLogger(__name__)
logger.debug("Loaded " + __name__)

import json
import time
import sys
import pprint

from pykafka import KafkaClient
from pykafka.common import OffsetType

#############################
## Helper Methods
#############################

mapnonprint = {
	'\0':'^@',
	'\1':'^A',
	'\2':'^B',
	'\3':'^C',
	'\4':'^D',
	'\5':'^E',
	'\6':'^F',
	'\a':'^G',
	'\b':'^H',
	'\t':'^I',
	'\n':'^J',
	'\v':'^K',
	'\f':'^L',
	'\r':'^M',
	'\x00':'^@',
	'\x01':'^A',
	'\x02':'^B',
	'\x03':'^C',
	'\x04':'^D',
	'\x05':'^E',
	'\x06':'^F',
	'\x07':'^G',
	'\x08':'^H',
	'\x09':'^I',
	'\x0a':'^J',
	'\x0b':'^K',
	'\x0c':'^L',
	'\x0d':'^M',
	'\x0e':'^N',
	'\x0f':'^O',
	'\x10':'^P',
	'\x11':'^Q',
	'\x12':'^R',
	'\x13':'^S',
	'\x14':'^T',
	'\x15':'^U',
	'\x16':'^V',
	'\x17':'^W',
	'\x18':'^X',
	'\x19':'^Y',
	'\x1a':'^Z',
	'\x1b':'^[',
	'\x1c':'^\\',
	'\x1d':'^]',
	'\x1e':'^^',
	'\x1f':'^-',
}

def replacecontrolchar(text):
	for a,b in mapnonprint.items():
		if a in text:
			logger.warning("Json Decode replacecontrolchar:{} with {}".format(a,b))
			text = text.replace(a,b)
	return text

def kafka_to_dict(kafka_msg):
	try:
		try:
			msg = json.loads(kafka_msg.value)
		except:
			msg = json.loads(replacecontrolchar(kafka_msg.value))
		kafka_msg_id = "{id}:{topic}:{partition}:{offset}".format(**{ "id":msg["_id"], "offset":kafka_msg.offset, "partition": kafka_msg.partitions[0], "topic":kafka_msg.topic })
		msg["_kafka__id"]= kafka_msg_id
	except Exception as e:
		logger.error("Json Decode Error:offset {}:{}".format(kafka_msg.offset,e))
		filename = "/LFS/dump/"+str(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
		
		# If path does not exists, create it
		if(not os.path.exists("/LFS/dump")):
			os.makedirs("/LFS/dump")
		
		with open(filename,"wb") as f: f.write(kafka_msg.value)
		msg=None
	return msg
	
def dict_to_kafka(output,source_data):
	for data in source_data:
		if output["source_id"] == data["_id"]:
			output["_kafka_source_id"] = data["_kafka__id"]
			break
	kafka_msg = json.dumps(output)
	return kafka_msg

class Kafka_PyKafka(object):
	Type = "PyKafka Wrapper Class"
	def __init__(self, kafka_client_config):

		# Get Config Params
		self.broker = kafka_client_config["broker"]
		self.producer_topic = kafka_client_config.get("producer_topic")
		self.consumer_1_topic = kafka_client_config.get("consumer_1_topic")
		self.consumer_2_topic = kafka_client_config.get("consumer_2_topic")

		# Create global (sort of) PyKafka client
		self.pykafka_client = KafkaClient("kafka:9092")

		# Create Producer
		if(self.producer_topic):
			topic = self.pykafka_client.topics[kafka_client_config["producer_topic"]]
			self.producer = topic.get_producer(kafka_client_config["producer_params"])


		# Create Consumer 1
		if(self.consumer_1_topic):
			topic = self.pykafka_client.topics[self.consumer_1_topic]
			self.consumer_1 = topic.get_simple_consumer(kafka_client_config["consumer_1_params"])

		# Create Consumer 2
		if(self.consumer_2_topic):
			topic = self.pykafka_client.topics[self.consumer_2_topic]
			self.consumer_2 = topic.get_simple_consumer(kafka_client_config["consumer_2_params"])

		# Print Complete config

	def produce(self, message):
		self.producer.produce(message)

	def consume1(self):
		message_kafka = self.consumer_1.consume()
		if(message_kafka is not None):
			
			print("="*50)
			print("Consumed 1 PyKafka")
			print("Message Size = ".format(str(len(message_kafka))))
			print("="*50)

			message_kafka = message_kafka.value
			message_dict = kafka_to_dict(message_kafka)
			return(message_dict)
		else:
			logger.info("Empty message received from consumer")
			return(None)

	def consume2(self, block=True):
		message_kafka = self.consumer_2.consume(block=block)
		if(message_kafka is not None):
			
			print("="*50)
			print("Consumed 2 PyKafka")
			print("Message Size = ".format(str(len(message_kafka))))
			print("="*50)

			message_kafka = message_kafka.value
			message_dict = kafka_to_dict(message_kafka)
			return(message_dict)
		else:
			logger.info("Empty message received from consumer")
			return(None)


	def sync_consumers(self):

		m1 = self.consumer_1.consume()
		m2 = self.consumer_2.consume()

		m1_dict, m2_dict = kafka_to_dict(m1.value, kafka_to_dict(m2.value))

		try:
			assert(m2_dict["_id"] == m1_dict["source_id"])

		except AssertionError:
			logger.info("Consumers not synced. Syncing now...")


			kafka_source_id = m1_dict["_kafka_source_id"]                   #"{id}:{topic}:{partition}:{offset}"
			consumer_2_partition = int(kafka_source_id.split(":")[-2])      # 3rd last
			consumer_2_offset =  int(kafka_source_id.split(":")[-1])

			# Sync Consumer 2
			self.consumer_2.reset_offsets([(consumer_2_partition, consumer_2_offset)])
			self.consumer_2.stop()
			self.consumer_2.start()

			m2 = self.consumer_2.consume()
			m2_dict = kafka_to_dict(m2.value)

		try:
			assert(m2_dict["_id"] == m1_dict["source_id"]) 
			return(m1_dict, m2_dict)
		except AssertionError:
			logger.info("Consumers not synced. Unknown error.")
			sys.exit(0)
