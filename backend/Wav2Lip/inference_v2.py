
'''
ultralytics
'''
import sys
sys.path.append('./')

import argparse
import copy
import math
import os
import platform
import subprocess
import sys
import tempfile
import time
import uuid
import warnings
from collections import defaultdict
import time

import cv2
import numpy as np
import torch
from PIL import Image
from tqdm import tqdm
from models import Wav2Lip as wav2lip_model
import audio

import face_detection

# os.environ['YOLO_VERBOSE'] = 'False'
# from ultralytics import YOLO


# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# from src.torchalign import FacialLandmarkDetector
# from src.utils.utils import decompose_tfm, img_warp, img_warp_back_inv_m, metrix_M
# from src.utils.utils import laplacianSmooth


torch.manual_seed(1234)
device = 'cuda' if torch.cuda.is_available() else 'cpu'
print('Using {} for inference.'.format(device))

def _load(checkpoint_path):
    if device == 'cuda':
        checkpoint = torch.load(checkpoint_path)
    else:
        checkpoint = torch.load(checkpoint_path, map_location=lambda storage, loc: storage)
    return checkpoint


def load_model(path):
    model = wav2lip_model()
    print("Load checkpoint from: {}".format(path))
    checkpoint = _load(path)
    s = checkpoint["state_dict"]
    new_s = {}
    for k, v in s.items():
        new_s[k.replace('module.', '')] = v
    model.load_state_dict(new_s)

    model = model.to(device)
    return model.eval()


def get_video_fps(vfile):
    cap = cv2.VideoCapture(vfile)
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.release()
    return fps

class Wav2Lipv2Wrapper:
    """
    A simplified wrapper for Wav2Lipv2 inference that matches the interface expected by main.py
    but implements the logic from the user provided code snippet.
    """
    def __init__(self, checkpoint_path, ffmpeg_path):
        self.checkpoint_path = checkpoint_path
        self.ffmpeg_path = ffmpeg_path
        self.device = device
        self.model = load_model(self.checkpoint_path)
        self.img_size = 96 # Wav2Lip standard
        self.mel_step_size = 16
        print("Wav2Lipv2 Model loaded")

    def inference(self, face_path, audio_path, outfile):
        # This implements the core inference loop adapted for single image + audio
        
        # 1. Load Audio
        if not audio_path.endswith('.wav'):
             print('Extracting raw audio...')
             temp_wav = 'temp/temp.wav'
             command = '{} -y -i {} -strict -2 {}'.format(self.ffmpeg_path, audio_path, temp_wav)
             subprocess.call(command, shell=True)
             audio_path = temp_wav

        wav = audio.load_wav(audio_path, 16000)
        mel = audio.melspectrogram(wav)
        
        # 2. Load Face (Image)
        if face_path.split('.')[1] in ['jpg', 'png', 'jpeg']:
             frame = cv2.imread(face_path)
             fps = 25.0 # Default for image
             
             # Face Detection
             detector = face_detection.FaceAlignment(face_detection.LandmarksType._2D, flip_input=False, device=device)
             
             # Detect face
             batch_size = 1 # Simple batch
             predictions = detector.get_detections_for_batch(np.array([frame]))
             rect = predictions[0]
             
             if rect is None:
                 raise ValueError('Face not detected!')

             # Crop Face
             pady1, pady2, padx1, padx2 = [0, 10, 0, 0] # Default pads
             y1 = max(0, rect[1] - pady1)
             y2 = min(frame.shape[0], rect[3] + pady2)
             x1 = max(0, rect[0] - padx1)
             x2 = min(frame.shape[1], rect[2] + padx2)
             
             face_crop = frame[y1:y2, x1:x2]
             coords = (y1, y2, x1, x2)
             
             # Resize to model input
             face_resized = cv2.resize(face_crop, (self.img_size, self.img_size))
             
             # Generate Frames
             mel_idx_multiplier = 80./fps
             i = 0
             mel_chunks = []
             while 1:
                 start_idx = int(i * mel_idx_multiplier)
                 if start_idx + self.mel_step_size > len(mel[0]):
                     mel_chunks.append(mel[:, len(mel[0]) - self.mel_step_size:])
                     break
                 mel_chunks.append(mel[:, start_idx : start_idx + self.mel_step_size])
                 i += 1
             
             print(f"Generating {len(mel_chunks)} frames...")
             
             # Inference Loop
             batch_size = 128
             gen_frames = []
             
             # Prepare Batches
             img_batch = []
             mel_batch_list = []
             
             for m in mel_chunks:
                 img_batch.append(face_resized)
                 mel_batch_list.append(m)
             
             img_batch = np.asarray(img_batch)
             mel_batch_list = np.asarray(mel_batch_list)
             
             # Masking (Wav2Lip specific: mask lower half)
             img_masked = img_batch.copy()
             img_masked[:, self.img_size//2:] = 0
             img_batch = np.concatenate((img_masked, img_batch), axis=3) / 255.
             mel_batch_list = np.reshape(mel_batch_list, [len(mel_batch_list), mel_batch_list.shape[1], mel_batch_list.shape[2], 1])
             
             # Predict
             pred_batches = []
             for i in tqdm(range(0, len(img_batch), batch_size)):
                 img_b = torch.FloatTensor(np.transpose(img_batch[i:i+batch_size], (0, 3, 1, 2))).to(device)
                 mel_b = torch.FloatTensor(np.transpose(mel_batch_list[i:i+batch_size], (0, 3, 1, 2))).to(device)
                 
                 with torch.no_grad():
                     pred = self.model(mel_b, img_b)
                 
                 pred = pred.cpu().numpy().transpose(0, 2, 3, 1) * 255.
                 pred_batches.append(pred)
                 
             pred_all = np.concatenate(pred_batches, axis=0)
             
             # Reconstruct Video
             temp_video = 'temp/result.avi'
             frame_h, frame_w = frame.shape[:-1]
             out = cv2.VideoWriter(temp_video, cv2.VideoWriter_fourcc(*'DIVX'), fps, (frame_w, frame_h))
             
             for p in pred_all:
                 p = cv2.resize(p.astype(np.uint8), (x2 - x1, y2 - y1))
                 
                 f = frame.copy()
                 f[y1:y2, x1:x2] = p
                 out.write(f)
                 
             out.release()
             
             # Merge Audio
             command = '{} -y -i {} -i {} -strict -2 -q:v 1 {}'.format(self.ffmpeg_path, audio_path, temp_video, outfile)
             subprocess.call(command, shell=True)
             
             return outfile

if __name__ == '__main__':
    # Standalone test
    import sys
    # Example usage
    pass
