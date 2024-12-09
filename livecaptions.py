import deepspeech
import numpy as np
import webrtcvad
import pyaudiowpatch as pyaudio
from scipy import signal
import queue
from halo import Halo
from collections import deque


class VADAudio:
    """Filter & segment audio with voice activity detection."""

    frame_duration_ms = 30 # must be 10, 20, or 30
    sample_rate = 16000 # must be 16000
    
    def __init__(self):
        def callback(in_data, frame_count, time_info, status):
            self.buffer_queue.put(in_data)
            return (None, pyaudio.paContinue)
        self.buffer_queue = queue.Queue()
        self.pa = pyaudio.PyAudio()
        self.device = self.getLoopbackDevice()
        self.input_rate = int(self.device["defaultSampleRate"])
        self.frame_per_buffer=int(self.frame_duration_ms*self.device["defaultSampleRate"]/1000)
        self.channels=self.device["maxInputChannels"]
        self.vad = webrtcvad.Vad(mode=3) # mode can be 1, 2 or 3, higher value means it's stricter
        self.pa.open(
            format=pyaudio.paInt16,
            channels= self.channels,
            rate= self.input_rate,
            input= True,
            input_device_index=self.device["index"],
            frames_per_buffer= self.frame_per_buffer,
            stream_callback= callback,
        ).start_stream()

        print(self.input_rate) # 48000
        print(self.frame_per_buffer) # 1440
        print(self.channels) # 2
        
    def getLoopbackDevice(self):
        try:
            # Get default WASAPI info
            wasapi_info = self.pa.get_host_api_info_by_type(pyaudio.paWASAPI)
        except OSError:
            print("Looks like WASAPI is not available on the system. Exiting...")
            exit()
        
        # Get default WASAPI speakers
        default_speakers = self.pa.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
        
        if not default_speakers["isLoopbackDevice"]:
            for loopback in self.pa.get_loopback_device_info_generator():
                """
                Try to find loopback device with same name(and [Loopback suffix]).
                Unfortunately, this is the most adequate way at the moment.
                """
                if default_speakers["name"] in loopback["name"]:
                    default_speakers = loopback
                    return default_speakers
            else:
                print("Default loopback output device not found.\n\nRun `python -m pyaudiowpatch` to check available devices.\nExiting...\n")
                exit()

    def read_resampled(self):
        """Return a block of audio data resampled to 16000hz, blocking if necessary."""
        data16 = np.frombuffer(self.buffer_queue.get(), dtype=np.int16)
        data16=data16[::self.channels] # select only one channel
        resample_size = int(len(data16) / self.input_rate * self.sample_rate)
        result = signal.resample(data16, resample_size).astype(np.int16).tobytes()
        return result
 
    def read(self):
        """Return a block of audio data, blocking if necessary."""
        return self.buffer_queue.get()

    def frame_generator(self):
        """Generator that yields all audio frames from speaker/headphones."""
        if self.input_rate == self.sample_rate:
            while True:
                yield self.read()
        else:
            while True:
                yield self.read_resampled()

    def vad_collector(self, padding_ms=300, ratio=0.75):
       """Generator that yields series of consecutive audio frames comprising each utterence, separated by yielding a single None.
           Determines voice activity by ratio of frames in padding_ms. Uses a buffer to include padding_ms prior to being triggered.
           Example: (frame, ..., frame, None, frame, ..., frame, None, ...)
                     |---utterence---|        |---utterence---|
       """
       frames = self.frame_generator()
       num_padding_frames = padding_ms // self.frame_duration_ms
       ring_buffer = deque(maxlen=num_padding_frames)
       triggered = False
 
       for frame in frames:
           if len(frame) < 640: # it means, sample_rate * frame_duration_ms / 1000 * 2 must be larger than 640
               print(len(frame))
               print(self.frame_per_buffer)
               return

           is_speech = self.vad.is_speech(frame, self.sample_rate)
 
           if not triggered:
               ring_buffer.append((frame, is_speech))
               num_voiced = len([f for f, speech in ring_buffer if speech])
               if num_voiced > ratio * ring_buffer.maxlen:
                   triggered = True
                   for f, s in ring_buffer:
                       yield f
                   ring_buffer.clear()
 
           else:
               yield frame
               ring_buffer.append((frame, is_speech))
               num_unvoiced = len([f for f, speech in ring_buffer if not speech])
               if num_unvoiced > ratio * ring_buffer.maxlen:
                   triggered = False
                   yield None
                   ring_buffer.clear()
model = deepspeech.Model('models/deepspeech-0.9.3-models.pbmm')
model.enableExternalScorer('models/deepspeech-0.9.3-models.scorer')
stream = model.createStream()

vad_audio = VADAudio()
frames = vad_audio.vad_collector()
spinner = Halo(spinner='line')

for frame in frames:
    if frame is not None:
        if spinner: spinner.start()
        stream.feedAudioContent(np.frombuffer(frame, np.int16))
    else:
        if spinner: spinner.stop()
        print("end utterence")
        text = stream.finishStream()
        print("Recognized: %s" % text)
        stream = model.createStream()
# todo 显示字幕