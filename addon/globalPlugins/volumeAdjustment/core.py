#core.py
from ctypes import cast, POINTER
from comtypes import CoCreateInstance, CLSCTX_ALL, CLSCTX_INPROC_SERVER
from .pycaw import AudioUtilities, IAudioEndpointVolume, CLSID_MMDeviceEnumerator, IMMDeviceEnumerator, EDataFlow, ERole


class ExtendedAudioUtilities(AudioUtilities):

	@staticmethod
	def GetSpeaker(id=None):
		device_enumerator = CoCreateInstance(
			CLSID_MMDeviceEnumerator,
			IMMDeviceEnumerator,
			CLSCTX_INPROC_SERVER)
		if id is not None:
			speakers = device_enumerator.GetDevice(id)
		else:
			speakers = device_enumerator.GetDefaultAudioEndpoint(EDataFlow.eRender.value, ERole.eMultimedia.value)
		return speakers

class AudioDevice(object):
	def __init__(self, id='', name='', volume=None):
		self._id = id
		self._name = name
		self._volume = volume
		self._default = False

	id = lambda self: self._id
	name = lambda self: self._name
	volume = lambda self: self._volume
	default = lambda self: self._default

	id = property(id)
	name = property(name)
	volume = property(volume)
	default = property(default)

class AudioDevices(object):

	def __init__(self):
		self._defaultDevice = AudioDevice()
		self._devices = []

	def initialize(self):
		self._defaultDevice = AudioUtilities.GetSpeakers()
		try:
			mixers = ExtendedAudioUtilities.GetAllDevices()
		except Exception as e:
			mixers = []
		for mixer in mixers:
			device = ExtendedAudioUtilities.GetSpeaker(mixer.id)
			try:
				interface = device.Activate(
					IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
			except Exception as e:
				continue
			device = AudioDevice(
				id = mixer.id,
				name = mixer.FriendlyName,
				volume = cast(interface, POINTER(IAudioEndpointVolume))
			)
			if device.id==self._defaultDevice.GetId():
				device._default = True
				self._devices.insert(0, device)
			else:
				self._devices.append(device)

	def __len__(self):
		return len(self._devices)

	def __getitem__(self, index):
		return self._devices[index]


class AudioSession(object):

	def __init__(self, name):
		self._name = name
		self._volume = None

	@property
	def name(self):
		return self._name

	@property
	def title(self):
		return ' '.join(self.name.split('.')[:-1])

	@property
	def volume(self):
		if not self._volume:
			for session in AudioUtilities.GetAllSessions():
				if session.Process and session.Process.name()==self.name:
					self._volume = session.SimpleAudioVolume
		return self._volume
