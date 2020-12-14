import logging
logger = logging.getLogger(__name__)
logger.debug("Loaded " + __name__)

import os
import sys
import signal

from .kafka_connector import KafkaConnector
from .rabbitMqConnector import RabbitMqConnector
import threading
from .vedaio import VedaSocketIO

class Manager(object):
	Type = "Manager"

	def __init__(self, **kwargs):
		super(Manager, self).__init__()

		self.behaviour = kwargs.get('behaviour')
		self.connector_type = kwargs.get('connector_type','kafka')
		self.kafka_client_type = kwargs.get('kafka_client_type',None)
		self.kafka_client_config = kwargs.get('kafka_client_config',None)
		self.client_config=kwargs.get('client_config',None)

		
		self.pid = os.getpid()
		self.exit_code = 0

		if self.connector_type == 'kafka':
			self.connected_behaviour = KafkaConnector(
				self.behaviour, 
				kafka_client_type=self.kafka_client_type, 
				on_exit=self.stop,
				**self.kafka_client_config)
   
		if self.connector_type == 'rabbitMq':
			self.rabbit_client_config = kwargs.get('rabbit_client_config')
			self.connected_behaviour = RabbitMqConnector(
				self.behaviour, 
				on_exit=self.stop,
				**self.client_config)
			
		self.signal_map = kwargs.get('signal_map', {})

		# Set Kafka Enable/Disable on SIGUSR2 (12)
		signal.signal(10, self.receiveSignal)
		signal.signal(12, self.receiveSignal)
		signal.signal(signal.SIGTERM, self.receiveSignal)

		# Socket IO based Live updates
		if not self.connected_behaviour.behavior.offlineMode:
			self.socketClient=VedaSocketIO(subscriptions=self.subscriptionTopics())
			self.registerUpdateHandler()
	
	
	###### Update Related Functions
	def subscriptionTopics(self,subscriptions=[]):
		subscriptions = self.connected_behaviour.subscriptionTopics(subscriptions)
		logger.info("Manager: Subscription Topics: {}".format(subscriptions))
		return subscriptions

	# update event callback
	def update(self, data):
		logger.info("Manager: Update triggered with data:{}".format(data))
		UpdateSuccess = self.connected_behaviour.update(data)
		logger.info("Manager: Hot update status:{}".format(UpdateSuccess))

		# Handle update if not handled already
		if not UpdateSuccess:
			self.stop(exit_code=100)

	# register update event callback
	def registerUpdateHandler(self):
		@self.socketClient.sio.on("message")
		def my_message(data):
			self.update(data)


	###### Run Method
	def run(self):
		logger.info("Manager run() called.")
		from flask import current_app as app
		self.connected_behaviour_thread = threading.Thread(target=self.connected_behaviour.run, args=(app._get_current_object(),))
		self.connected_behaviour_thread.start()
		

	def onStart(self):
		logger.info("Manager onStart() called.")

	def onExit(self):
		logger.info("Manager onExit() called.")

	# Handling Signals
	def receiveSignal(self, signal_number, frame):  
		print('Received:', signal_number)
			
		if(signal_number in self.signal_map):
			f = self.signal_map[signal_number]
			f['func'](*f['args'], **f['kwargs'])

		# Set Kafka Enable/Disable on SIGUSR2 (12)
		if(signal_number == 10):
			logger.info("Enaling Kafka")
			self.connected_behaviour.enable_kafka()

		if(signal_number == 12):
			logger.info("Disabling Kafka")
			self.connected_behaviour.disable_kafka()

		if (signal_number == signal.SIGTERM):
			logger.info("Stopping Everything")
			self.cleanup()

	def onSignal(self):
		logger.info("Manager Signal Handler Initialized.")
		logger.info('My PID is:{}'.format(str(os.getpid())))

		# Register signals
		for k,v in self.signal_map.items():
			print("Registering Signal = {}".format(k))
			signal.signal(k, self.receiveSignal)

	def stop(self, exit_code=0):
		logger.info("Stopping function triggered with exit_code:{}".format(exit_code))
		self.exit_code=exit_code
		os.kill(self.pid, signal.SIGTERM)
	
	def cleanup(self):
		if not self.connected_behaviour.behavior.offlineMode:
			self.socketClient.sio.disconnect()
		self.connected_behaviour.stop()
		self.connected_behaviour_thread.join(timeout=10)
		exit(self.exit_code)





