import logging
logger = logging.getLogger(__name__)
logger.debug("Loaded " + __name__)

import os
import cv2
import json
from base64 import b64encode


#################### Utility Functions ####################

def opencv_frame_to_dict(frame):
	
	_, encoded_frame = cv2.imencode('.jpg', frame)

	res = {}
	res['image'] = b64encode(encoded_frame)
	res['_type'] = "b64encoded frame"
	res['_id'] = "1"

	return(res)

###########################################################


class CV(object):

	def __init__(self, **kwargs):
		super(CV, self).__init__()

		self.video_source = kwargs.get('video_source', None)
		self.capture = cv2.VideoCapture(self.video_source)

	def read(self):
		success, frame = self.capture.read()

		if(success):
			return(frame)
		else:
			print("ERROR. Cannot read frame from : ", self.video_source)

class JSON(object):
	
	def __init__(self, **kwargs):
		super(JSON, self).__init__()

		self.json_output_file = kwargs.get('json_output_file', None)
		
	def write(self, data):

		if os.path.isfile(self.json_output_file):
			# File exists
			with open(self.json_output_file, 'a+') as outfile:
				outfile.seek(-1, os.SEEK_END)
				outfile.truncate()
				outfile.write(',')
				json.dump(data, outfile)
				outfile.write(']')
				logger.info("Results written to {} successfully".format(self.json_output_file))
		else: 
			# Create file
			with open(self.json_output_file, 'w') as outfile:
				array = []
				array.append(data)
				json.dump(array, outfile)


class LocalConnector(object):
	Type = "LocalConnector"

	''' Possible Variables 
	
		Behaviour :  
		input_source :  
		output_source :
		input_source_type :
		output_source_type :

	'''

	def __init__(self, Behaviour, **kwargs):
	
		super(LocalConnector, self).__init__()

		self.input_source = kwargs.get('input_source', None) 
		self.output_source = kwargs.get('output_source', None)

		self.output_source_type = kwargs.get('output_source_type', None)

		self.data = None
		self.reader = None
		self.writer = None

		# Create an Instance of Behaviour
		self.beh = Behaviour

		# Create the reader object
		self.reader = CV(video_source=self.input_source)

		# Determine Type of Output source and create the writer object 
		if(self.output_source_type == "json"):
			self.writer = JSON(json_output_file=self.output_source)

		print("self.writer : " , self.writer)

		for k,v in kwargs.iteritems():
			print(k, v)


	def run(self):
		while True:
			if(self.input_source): # Read Operation
				
				response = self.reader.read()
				response = opencv_frame_to_dict(response)

				self.data = self.beh.run(response)

				# Perform any data processing tasks here

			if(self.output_source): # Write Operation
				self.writer.write(self.data)



