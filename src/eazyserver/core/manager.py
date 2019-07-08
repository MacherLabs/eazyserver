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
		self.behaviour.run()

	def onStart(self):
		print("Method called before running Behaviour")

	def onExit(self):
		print("Method called when on exiting the Behaviour")

	def onSignal(self):
		print("Handling Signal")

