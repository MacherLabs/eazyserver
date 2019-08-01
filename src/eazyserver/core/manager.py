import logging
logger = logging.getLogger(__name__)
logger.debug("Loaded " + __name__)

import os
import sys
import signal

class Manager(object):
	Type = "Manager"

	def __init__(self, Behaviour, **kwargs):
		super(Manager, self).__init__()

		self.behaviour = Behaviour

	def run(self):
		logger.info("Manager run() called.")
		self.behaviour.run()

	def onStart(self):
		logger.info("Manager onStart() called.")

	def onExit(self):
		logger.info("Manager onExit() called.")

	# Handling Signals

	def receiveSignal(self, signalNumber, frame):  
	    print('Received:', signalNumber)

	    # SIGUSR1
	    if(signalNumber == 10):
	    	logger.info("Signal - SIGUSR1")

	    # SIGUSR2
	    if(signalNumber == 12):
	    	logger.info("Signal - SIGUSR2")

	    # SIGTERM
	    if(signalNumber == 15):
	    	logger.info("Terminating...")
	    	self.onExit()
	    

	def onSignal(self):
		logger.info("Manager Signal Handler Initialized.")
		logger.info('My PID is:', str(os.getpid()))

		signal.signal(signal.SIGUSR1, self.receiveSignal)
		signal.signal(signal.SIGUSR2, self.receiveSignal)
		signal.signal(signal.SIGTERM, self.receiveSignal)




