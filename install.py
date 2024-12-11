from urllib.request import urlretrieve as download
import os

print("downloading...")
os.makedirs('models',exist_ok=True)
download(r'https://github.com/mozilla/DeepSpeech/releases/download/v0.9.3/deepspeech-0.9.3-models.pbmm', r'models/deepspeech-0.9.3-models.pbmm')
download(r'https://github.com/mozilla/DeepSpeech/releases/download/v0.9.3/deepspeech-0.9.3-models.scorer', r'models/deepspeech-0.9.3-models.scorer')
print("download finished")