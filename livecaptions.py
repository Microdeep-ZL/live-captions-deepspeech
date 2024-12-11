import json
import deepspeech
import numpy as np
import webrtcvad
import pyaudiowpatch as pyaudio
from scipy import signal
import queue
from collections import deque
import tkinter as tk
from threading import Thread


class VADAudio:
    """Filter & segment audio with voice activity detection."""

    frame_duration_ms = 30 # must be 10, 20, or 30
    sample_rate = 16000 # must be 16000
    buffer_queue = queue.Queue()
    
    def __init__(self):
        def callback(in_data, frame_count, time_info, status):
            self.buffer_queue.put(in_data)
            return (None, pyaudio.paContinue)
        VADAudio.timeout=config["idle_endurance"]
        self.pa = pyaudio.PyAudio()
        self.device = self.getLoopbackDevice()
        self.input_rate = int(self.device["defaultSampleRate"])
        self.frame_per_buffer=int(self.frame_duration_ms*self.device["defaultSampleRate"]/1000)
        self.channels=self.device["maxInputChannels"]
        self.vad = webrtcvad.Vad(mode=3) # mode (aka aggressiveness) can be 1, 2 or 3, higher value means it's stricter
        self.pa.open(
            format=pyaudio.paInt16,
            channels= self.channels,
            rate= self.input_rate,
            input= True,
            input_device_index=self.device["index"],
            frames_per_buffer= self.frame_per_buffer,
            stream_callback= callback,
        ).start_stream()

        # print(self.input_rate) # 48000
        # print(self.frame_per_buffer) # 1440
        # print(self.channels) # 2
        
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
        data16 = np.frombuffer(self.read(), dtype=np.int16)
        data16=data16[::self.channels] # select only one channel
        resample_size = int(len(data16) / self.input_rate * self.sample_rate)
        result = signal.resample(data16, resample_size).astype(np.int16).tobytes()
        return result
 
    def read(self):
        """Return a block of audio data, blocking if necessary."""
        return self.buffer_queue.get(timeout=VADAudio.timeout)

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

        while 1:
            try:
                frame=next(frames)
            except queue.Empty:
                root.withdraw()
                VADAudio.timeout=None
                frames = self.frame_generator()
                frame=next(frames)
                root.deiconify()
                VADAudio.timeout=config["idle_endurance"] # after there being no sound for a few seconds, hide the window
            if len(frame) < 640: # it means, sample_rate * frame_duration_ms / 1000 * 2 must be larger than 640
                # print(len(frame))
                # print(self.frame_per_buffer) # should be equal to len(frame)
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

def splitLines(text):
    '''if longer than one line, split into two lines'''
    lines=[]
    array=text.split()
    length=0
    j=0
    for i in range(len(array)):
        length+=1+len(array[i])
        if length>config["maxlen"]:
            lines.append(" ".join(array[j:i]))
            j=i
            length=0
    lines.append(" ".join(array[j:]))
    return "\n".join(lines[-2:])

def setCaption(text,flag):
    global string_buffer
    temp=splitLines(string_buffer+" "+text)
    if flag=="finish":
        string_buffer=temp
    caption.replace("1.0","2.end",temp)

def transcribe():
    model = deepspeech.Model('models/deepspeech-0.9.3-models.pbmm')
    model.enableExternalScorer('models/deepspeech-0.9.3-models.scorer')
    stream = model.createStream()
    frames = VADAudio().vad_collector()
    count=0
    try:
        while 1:
            frame=next(frames)
            if frame is not None:
                count+=1
                stream.feedAudioContent(np.frombuffer(frame, np.int16))
                if count*VADAudio.frame_duration_ms/1000>0.5: # update every 0.5 seconds
                    count=0
                    setCaption(stream.intermediateDecode(),"intermediate")
            else:
                count=0
                setCaption(stream.finishStream(),"finish")
                stream = model.createStream()
    except Exception:
        pass

def create_window():
    root = tk.Tk()
    root.overrideredirect(True) # remove title bar
    root.configure(bg="black")
    root.attributes('-alpha', config["opacity"])
    root.wm_attributes('-topmost', True)
    
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    window_width = config["window_width"]
    window_height = config["window_height"]
    x = (screen_width - window_width) //2
    y = int((screen_height - window_height) *.8)
    root.geometry(f"{window_width}x{window_height}+{x}+{y}")

    font={
        "font":(config["font_type"],config["font_size"]),
        "fg":config["fg"],
        "bg":config["bg"],
        "cursor":"arrow",
        "height":config["rows"], # number of rows
    }
    caption = tk.Text(root,**font)
    caption.insert(tk.END,"Live Caption")
    caption.pack(fill="both")

    def start_move(event):
        root.x = event.x
        root.y = event.y

    def on_motion(event):
        delta_x = event.x - root.x
        delta_y = event.y - root.y
        root.geometry(f"+{root.winfo_x() + delta_x}+{root.winfo_y() + delta_y}")

    root.bind('<Button-1>', start_move)
    root.bind('<B1-Motion>', on_motion)

    return root, caption

# todo 降低延迟
# todo 美化界面

if __name__ == "__main__":
    with open("config.json") as f:
        config=json.loads(f.read())
    try:
        root, caption=create_window()
        string_buffer=""
        t=Thread(target=transcribe)
        t.start()
        root.mainloop()
    except KeyboardInterrupt:
        VADAudio.buffer_queue.put(None)
        t.join()
        root.destroy()