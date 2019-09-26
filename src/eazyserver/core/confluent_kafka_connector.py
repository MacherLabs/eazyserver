import logging
logger = logging.getLogger(__name__)
logger.debug("Loaded " + __name__)

import json
import time
import sys
import pprint

from confluent_kafka import Producer as KafkaProducer
from confluent_kafka import Consumer as KafkaConsumer
from confluent_kafka import TopicPartition

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
			msg = json.loads(kafka_msg.value())
		except:
			msg = json.loads(replacecontrolchar(kafka_msg.value()))
		kafka_msg_id = "{id}:{topic}:{partition}:{offset}".format(**{ "id":msg["_id"],"offset":kafka_msg.offset(), "partition": kafka_msg.partition(), "topic":kafka_msg.topic() })
		msg["_kafka__id"]= kafka_msg_id
	except Exception as e:
		# import pdb; pdb.set_trace()
		logger.error("Json Decode Error:offset {}:{}".format(kafka_msg.offset(),e))
		filename = "/LFS/dump/"+str(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
		
		# If path does not exists, create it
		if(not os.path.exists("/LFS/dump")):
			os.makedirs("/LFS/dump")
		
		with open(filename,"wb") as f: f.write(kafka_msg.value())
		msg=None
	return msg
	
def dict_to_kafka(output,source_data):
	for data in source_data:
		if output["source_id"] == data["_id"]:
			output["_kafka_source_id"] = data["_kafka__id"]
			break
	kafka_msg = json.dumps(output)
	return kafka_msg

class Kafka_Confluent(object):
	Type = "Confluent-Kafka Wrapper Class"
	def __init__(self, kafka_client_config):

		print("="*50)
		print("Printing Kafka_Confluent kwargs...")
		import pprint
		pp = pprint.PrettyPrinter(indent=4)
		pp.pprint(kafka_client_config)
		print("="*50)

		self.broker = kafka_client_config["broker"]
		self.producer_params = kafka_client_config["producer_params"]
		self.consumer_1_params = kafka_client_config["consumer_1_params"]
		self.consumer_2_params = kafka_client_config["consumer_2_params"]

		self.producer_topic = kafka_client_config.get('producer_topic')
		self.consumer_1_topic = kafka_client_config.get('consumer_1_topic')
		self.consumer_2_topic = kafka_client_config.get('consumer_2_topic')

		self.producer = None
		self.consumer_1 = None
		self.consumer_2 = None

		# Create Producer
		if(self.producer_topic):
			self.producer_params['bootstrap.servers'] = kafka_client_config["broker"]
			self.producer = KafkaProducer(self.producer_params)
			print("Producer created successfully...")

		# Create Consumer 1
		if(self.consumer_1_topic):
			self.consumer_1_params['bootstrap.servers'] = kafka_client_config["broker"]
			self.consumer_1 = KafkaConsumer(self.consumer_1_params)
			self.consumer_1.subscribe([self.consumer_1_topic])
			self.consumer_1.poll(timeout=0.01)
			print("Consumer 1 created successfully...")

		# Create Consumer 2
		if(self.consumer_2_topic):
			self.consumer_2_params['bootstrap.servers'] = kafka_client_config["broker"]
			self.consumer_2 = KafkaConsumer(self.consumer_2_params)
			self.consumer_2.subscribe([self.consumer_2_topic])
			self.consumer_2.poll(timeout=0.01)
			print("Consumer 1 created successfully...")

		# TODO : Print Complete config


	def produce(self, output, source_data):
		value = dict_to_kafka(output, source_data)

		print("="*50)
		print("Producing Message")
		print("self.producer_topic", self.producer_topic)
		print("message size, ", str(len(value)))
		print("="*50)

		self.producer.produce(self.producer_topic, value)
		self.producer.poll(0)
		return(True)

	def consume1(self):
		print("="*50)
		print("Consuming Message")
		print("self.consumer_1_topic", self.consumer_1_topic)
		print("="*50)
		message_kafka = self.consumer_1.consume(num_messages=1)[0]
		message_dict = kafka_to_dict(message_kafka)
		return(message_dict)

	def consume2(self, block=True):

		print("="*50)
		print("Consuming Message")
		print("self.consumer_2_topic", self.consumer_2_topic)
		print("="*50)

		if(block):
			message_kafka = self.consumer_2.consume(num_messages=1)[0]
		else:
			message_kafka = self.consumer_2.poll(timeout=0.01)

		if(message_kafka):
			message_dict = kafka_to_dict(message_kafka)
		else:
			message_dict = None
		
		return(message_dict)

		
	def sync_consumers(self):

		m1 = self.consumer_1.consume(num_messages=1)[0]
		m2 = self.consumer_2.consume(num_messages=1)[0]

		m1_dict, m2_dict = kafka_to_dict(m1), kafka_to_dict(m2)

		try:
			assert(m2_dict["_id"] == m1_dict["source_id"])

		except AssertionError:
			logger.info("Consumers not synced. Syncing now...")

			kafka_source_id = m1_dict["_kafka_source_id"]                   #"{id}:{topic}:{partition}:{offset}"
			consumer_2_topic_name = kafka_source_id.split(":")[-3] 			# 3rd last 
			consumer_2_partition = int(kafka_source_id.split(":")[-2])      # 3rd last
			consumer_2_offset =  int(kafka_source_id.split(":")[-1])
			consumer_2_topic_partition = TopicPartition(topic=consumer_2_topic_name, partition=consumer_2_partition, offset=consumer_2_offset)

			# Sync Consumer 2
			self.consumer_2.seek(consumer_2_topic_partition)
			m2 = self.consumer_2.consume(num_messages=1)[0]
			m2_dict = kafka_to_dict(m2)

		try:
			assert(m2_dict["_id"] == m1_dict["source_id"]) 
			return(m1_dict, m2_dict)
		except AssertionError:
			logger.info("Consumers not synced. Unknown error.")
			sys.exit(0)



