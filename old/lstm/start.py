import __init__
import pygame
import pygame.camera
import time
import random
import os
import zipfile
from imutils import face_utils
import dlib
import cv2
import numpy as np
import imutils
import json
import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import transforms
import train
import utility
import lstm
from collections import deque
import pygame

pygame.init()

camera_port = 0
camera = cv2.VideoCapture(camera_port)

device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')

pretrained_face_landmark = "shape_predictor_68_face_landmarks.dat"
# http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2
detector = dlib.get_frontal_face_detector()
predictor = dlib.shape_predictor(pretrained_face_landmark)

inst = pygame.image.load('inst.png')

infoObject = pygame.display.Info()
print(infoObject)
# screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
screen = pygame.display.set_mode((0, 0))
# Костыли так как фуллскрине нельзя alt+tab ,но и открыть окно на весь экрано просто нельзя там рамка(
time.sleep(0.1)

max_w, max_h = pygame.display.get_surface().get_size()

isFullscreen = False

_quit = False
dir = "data"
last_image = ''

x = random.randint(0, max_w)  # infoObject.current_w
y = random.randint(0, max_h)  # infoObject.current_h

face_detector = utility.FaceDetector()


# Check folder for data
if not os.path.exists(dir):
    os.makedirs(dir)

batch_size = 1
seq_len = 5

model = utility.load_model('./lstm/model.pth', device, lstm.model.TwoEyesWithLSTM(2, batch_size, seq_len))


eyes_left = deque()
eyes_right = deque()
faces = deque()
points = deque()

while not _quit:
    time.sleep(1 / 30)

    eyes = None
    shape = None

    return_value, frame = camera.read()

    frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)

    img = pygame.image.frombuffer(frame.tostring(), frame.shape[1::-1], "RGB")

    screen.fill((255, 255, 255))
    screen.blit(img, (0, 0))
    screen.blit(inst, (600, 0))

    rects = detector(frame, 0)

    for (i, rect) in enumerate(rects):
        shape = predictor(frame, rect)
        shape = face_utils.shape_to_np(shape)

        for (x_, y_) in shape:  # 36 42 43 48
            pygame.draw.circle(screen, (0, 255, 0), (x_, y_), 2)

        (x_, y_, w_, h_) = cv2.boundingRect(np.array([shape[36:42]]))
        eye_left = frame[y_ - 3:y_ + h_ + 3, x_ - 5:x_ + w_ + 5]

        (x_, y_, w_, h_) = cv2.boundingRect(np.array([shape[43:48]]))
        eye_right = frame[y_ - 3:y_ + h_ + 3, x_ - 5:x_ + w_ + 5]

        if eye_right is not None and eyes_left is not None:
            eyes_left.append(cv2.resize(eye_left, (32, 32)))
            eyes_right.append(cv2.resize(eye_right, (32, 32)))
            faces.append(shape)
            points.append([x, y])

            if len(eyes_left) > seq_len:
                eyes_left.popleft()
                eyes_right.popleft()
                faces.popleft()
                points.popleft()

    # Predict
    if len(eyes_left) == seq_len and model is not None:

        _eyes_left = np.array(eyes_left).reshape((1, seq_len, 3, 32, 32))
        _eyes_right = np.array(eyes_right).reshape((1, seq_len, 3, 32, 32))
        _faces = np.array(faces).reshape((1, seq_len, 68, 2))
        print(_eyes_left)
        print(_eyes_right)
        print(_faces)
        eyes_left_torch = torch.from_numpy(_eyes_left).float().to(device)
        eyes_right_torch = torch.from_numpy(_eyes_right).float().to(device)
        faces_torch = torch.from_numpy(_faces).float().to(device)
        out = model(eyes_left_torch, eyes_right_torch, faces_torch)

        out = out.cpu().data.numpy()[0]
        print(out)
        x_pred = out[0]
        y_pred = out[1]

        if x_pred < 0:
            x_pred = 0
        if y_pred < 0:
            y_pred = 0
        if x_pred > max_w:
            x_pred = max_w
        if y_pred > max_h:
            y_pred = max_h

        pygame.draw.circle(screen, (0, 255, 0), (x_pred, y_pred), 12)

    x, y = pygame.mouse.get_pos()
    print("{} {}".format(x, y))
    pygame.draw.circle(screen, (255, 0, 0), (x, y), 12)

    pygame.display.flip()

    events = pygame.event.get()
    for event in events:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                _quit = True
            if event.key == pygame.K_SPACE and len(eyes_left) == seq_len:
                lstm.dataset.save_data(seq_len, list(eyes_left), list(eyes_right), list(faces), list(points))
        if event.type == pygame.QUIT:
            _quit = True

# cam.stop()
pygame.quit()
