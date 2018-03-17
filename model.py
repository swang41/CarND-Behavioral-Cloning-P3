import os
import csv
import cv2
import numpy as np
from random import shuffle
import sklearn


def augment_shear(image, steering_angle, shear_range=200):
    """
    Sources:
    https://medium.com/@ksakmann/behavioral-cloning-make-a-car-drive-like-yourself-dc6021152713#.7k8vfppvk
    https://github.com/ksakmann/CarND-BehavioralCloning/blob/master/model.py
    :param image:
        Source image on which the shear operation will be applied
    :param steering_angle:
        The steering angle of the image
    :param shear_range:
        Random shear between [-shear_range, shear_range + 1] will be applied
    :return:
        The image generated by applying random shear on the source image
    """
    rows, cols, ch = image.shape
    dx = np.random.randint(-shear_range, shear_range + 1)
    random_point = [cols / 2 + dx, rows / 2]
    pts1 = np.float32([[0, rows], [cols, rows], [cols / 2, rows / 2]])
    pts2 = np.float32([[0, rows], [cols, rows], random_point])
    dsteering = dx / (rows / 2) * 360 / (2 * np.pi * 25.0) / 6.0
    M = cv2.getAffineTransform(pts1, pts2)
    image = cv2.warpAffine(image, M, (cols, rows), borderMode=1)
    steering_angle += dsteering

    return image, steering_angle

def augment_brightness(image):
	image1 = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
	image1 = np.array(image1, dtype = np.float32)
	random_bright_ratio = 0.5 + np.random.uniform()
	image1[:,:,2] = image1[:,:,2] * random_bright_ratio
	image1[:,:,2][image1[:,:,2] > 255] = 255
	image1 = np.array(image1, dtype = np.uint8)
	image = cv2.cvtColor(image1, cv2.COLOR_HSV2RGB)
	return image

def augment_flip(image, steer):
	ind_flip = np.random.randint(2)
	if ind_flip == 0:
		image = cv2.flip(image, 1)
		steer *= -1
	return image, steer

def preprocess_image_file_train(line_data):
    i_lrc = np.random.randint(3)
    if len(line_data[i_lrc].split('/')) == 1:
        if line_data[i_lrc].split('\\')[-3] == 'extra_data':
            path_file = './extra_data/IMG/' + line_data[i_lrc].split('\\')[-1]
        else:
            path_file = './extra_data_para_roads/IMG/' + line_data[i_lrc].split('\\')[-1]
    else:
        path_file = './data/IMG/' + line_data[i_lrc].split('/')[-1]
    if i_lrc == 0:
        shift_ang = 0
    if i_lrc == 1:
        shift_ang = .3
    if i_lrc == 2:
        shift_ang = -.3
    steer = float(line_data[3]) + shift_ang
    image = cv2.imread(path_file)
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    image, steer = augment_shear(image, steer)
    image, steer = augment_flip(image, steer)
    image = augment_brightness(image)
    image = cv2.resize(image[60: 140,: , :], (64,  64), interpolation = cv2.INTER_AREA)
    return image, steer

samples = []

with open('./data/driving_log.csv') as csvfile:
	reader = csv.reader(csvfile)
	next(reader, None)
	for line in reader:
		samples.append(line)

print("Number of Data: ", len(samples))


with open("./extra_data/driving_log.csv") as csvfile:
    reader = csv.reader(csvfile)
    next(reader, None)
    for line in reader:
        if abs(float(line[3])) < 0.01:
            continue
        samples.append(line)

print("Number of Data with extra data from track 2: ", len(samples))


from sklearn.model_selection import train_test_split
train_samples, valid_samples = train_test_split(samples, test_size=0.1)
print("Train Samples: ", len(train_samples))


def generator(samples, batch_size=32):
    shuffle(samples)
    while 1:
        images = []
        steers = []
        for i in range(batch_size):
            i_line = np.random.randint(len(samples))
            keep_pr = 0
            while keep_pr == 0:
                i_line = np.random.randint(len(samples))
                image, steer = preprocess_image_file_train(samples[i_line])
                if abs(steer) > .1:
                    keep_pr = 1
                elif np.random.uniform() > 0.7:
                    keep_pr = 1
            images.append(image)
            steers.append(steer)
        X_train = np.array(images)
        y_train = np.array(steers)
        yield sklearn.utils.shuffle(X_train, y_train)


from keras.models import Sequential
from keras.layers import Flatten, Dense, Lambda, Cropping2D, Dropout
from keras.layers import Convolution2D, MaxPooling2D, ELU
from keras.optimizers import Adam
from keras.regularizers import l2
from keras.callbacks import ModelCheckpoint
from keras import backend as K

batch_size = 64
reg = 0.001
lr = 0.001
keep_prob = 0.5
samples_per_epoch= 20032
nb_val_samples= 0.1 * samples_per_epoch
train_generator = generator(train_samples, batch_size)
valid_generator = generator(valid_samples, batch_size)

K.clear_session()
model = Sequential()
model.add(Lambda(lambda x: x/255.0 - 0.5, input_shape=(64,64,3)))
model.add(Convolution2D(24, 5, 5, subsample=(2,2), W_regularizer=l2(reg)))
model.add(ELU())
model.add(Convolution2D(36, 5, 5, subsample=(2,2), W_regularizer=l2(reg)))
model.add(ELU())
model.add(Convolution2D(48, 5, 5, subsample=(2,2), W_regularizer=l2(reg)))
model.add(ELU())
model.add(Convolution2D(64, 3, 3, W_regularizer=l2(reg)))
model.add(ELU())
model.add(Convolution2D(64, 3, 3, W_regularizer=l2(reg)))
model.add(ELU())
model.add(Flatten())
model.add(Dropout(keep_prob))
model.add(Dense(100, W_regularizer=l2(reg)))
model.add(Dense(50, W_regularizer=l2(reg)))
model.add(Dense(10))
model.add(Dense(1))

adam_opt = Adam(lr)

model.compile(loss='mse', optimizer=adam_opt)
model.summary()

###Saving Model and Weights###
model_json = model.to_json()
with open("model.json", "w") as json_file:
	json_file.write(model_json)

filepath = "./models_extra_data_5/model2-{epoch:02d}-{val_loss:.2f}.h5"
checkpoint = ModelCheckpoint(filepath, period = 1)
model.fit_generator(train_generator,
	samples_per_epoch=samples_per_epoch,
	validation_data=valid_generator,
	nb_val_samples=nb_val_samples,
	nb_epoch=20,
	verbose=1,
	callbacks=[checkpoint])

