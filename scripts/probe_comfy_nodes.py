import requests
import json

r = requests.get('http://127.0.0.1:8188/object_info')
data = r.json()
targets = [
    '4c314f31-ecda-4b08-ae98-faaba1bf613f',
    'MiniMaxH3ImageToVideo',
    'MiniMaxH3ReferenceToVideo',
    'MiniMaxH3SigmaShift',
    'ResolutionSelector',
    'ComfyMathExpression',
    'PrimitiveFloat',
    'PrimitiveStringMultiline',
    'LoadImage',
    'SaveVideo',
    'VAEDecode',
    'VAEDecodeAudio',
    'VAELoader',
    'KSampler',
    'KSamplerSelect',
    'BasicScheduler',
    'BasicGuider',
    'SamplerCustomAdvanced',
    'RandomNoise',
    'UNETLoader',
    'CLIPLoader',
    'CreateVideo',
]
for k in targets:
    print(f'{k:55s} {"YES" if k in data else "NO"}')
