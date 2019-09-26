import logging
logger = logging.getLogger(__name__)
logger.debug("Loaded " + __name__)

import os
import sys
import signal

from kafka_connector import KafkaConnector
import threading

class Manager(object):
	Type = "Manager"

	def __init__(self, **kwargs):
		super(Manager, self).__init__()

		self.behaviour = kwargs.get('behaviour')
		self.connector_type = kwargs.get('connector_type')
		self.kafka_client_type = kwargs.get('kafka_client_type')
		self.kafka_client_config = kwargs.get('kafka_client_config')

		self.connected_behaviour = KafkaConnector(
			self.behaviour, 
			kafka_client_type=self.kafka_client_type, 
			**self.kafka_client_config)
		
		self.signal_map = kwargs.get('signal_map', {})

		# Set Kafka Enable/Disable on SIGUSR2 (12)
		signal.signal(10, self.receiveSignal)
		signal.signal(12, self.receiveSignal)


	def run(self):
		logger.info("Manager run() called.")
		main_connector_thread = threading.Thread(target=self.connected_behaviour.run)
		main_connector_thread.start()
		

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


	def onSignal(self):
		logger.info("Manager Signal Handler Initialized.")
		logger.info('My PID is:{}'.format(str(os.getpid())))

		# Register signals
		for k,v in self.signal_map.items():
			print("Registering Signal = {}".format(k))
			signal.signal(k, self.receiveSignal)






