Only works for Windows

### Install
```sh
conda create -n deepspeech -c conda-forge python=3.9 numpy=1.24 scipy
conda activate deepspeech
pip3 install PyAudioWPatch deepspeech webrtcvad-wheels
python install.py
```
### Usage
```python
conda activate deepspeech
python livecaptions.py
```

