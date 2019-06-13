from local_connector import LocalConnector

d = {'bbox' : {'a' : 1, 'b': 2}}

class Behaviour(object):

	def __init__(self):
		pass

	def run(self, input):
		return(d)


input_source = {}

LC = LocalConnector(
	Behaviour=Behaviour,
	input_source="video.mp4",
	output_source="logs.json",
	output_source_type="json"
	)

LC.run()