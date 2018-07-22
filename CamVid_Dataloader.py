#!/usr/bin/env python

import torch
import random
import PIL.Image
import collections
import numpy as np
import os.path as osp
from torch.utils import data
import matplotlib.pyplot as plt


class CamVidSeg(data.Dataset):

    class_names = np.array([
        'sky',
        'building',
        'column-pole',
        'road',
        'sidewalk',
        'tree',
        'sign',
        'fence',
        'car',
        'pedestrian',
        'bicyclist',
        'void',
    ])

    class_weights = np.array([
        0.58872014284134,
        0.51052379608154,
        2.6966278553009,
        0.45021694898605,
        1.1785038709641,
        0.77028578519821,
        2.4782588481903,
        2.5273461341858,
        1.0122526884079,
        3.2375309467316,
        4.1312313079834,
        0,
    ])

    class_colors = np.array([
        (128, 128, 128),
        (128, 0, 0),
        (192, 192, 128),
        (128, 64, 128),
        (0, 0, 192),
        (128, 128, 0),
        (192, 128, 128),
        (64, 64, 128),
        (64, 0, 128),
        (64, 64, 0),
        (0, 128, 192),
        (0, 0, 0),
    ])
    # TODO: Need to check if this is bgr or rgb: current is BGR
    mean_bgr = np.array([0.4326707089857, 0.4251328133025, 0.41189489566336])*255
    #TODO: Need to check if std is used.
    std_bgr = np.array([0.28284674400252, 0.28506257482912, 0.27413549931506])*255

    def __init__(self, root, split='train', dataset='o', transform=False):
        self.root = root
        self.split = split
        self._transform = transform
        self.datasets = collections.defaultdict()

        self.datasets['o'] = osp.join(self.root, 'Original_Images')
        self.datasets['dbg1'] = osp.join(self.root, 'Degraded_Images', 'Blur_Gaussian', 'degraded_parameter_1')
        self.datasets['dbm1'] = osp.join(self.root, 'Degraded_Images', 'Blur_Motion', 'degraded_parameter_1')
        self.datasets['hi1'] = osp.join(self.root, 'Degraded_Images', 'Haze_I', 'degraded_parameter_1')
        self.datasets['ho1'] = osp.join(self.root, 'Degraded_Images', 'Haze_O', 'degraded_parameter_1')
        self.datasets['np1'] = osp.join(self.root, 'Degraded_Images', 'Noise_Poisson', 'degraded_parameter_1')
        self.datasets['nsp1'] = osp.join(self.root, 'Degraded_Images', 'Noise_Salt_Pepper', 'degraded_parameter_1')

        img_dataset_dir = osp.join(self.root, self.datasets[dataset])

        self.files = collections.defaultdict(list)
        for split in ['train', 'val']:
            imgsets_file = osp.join(root, '%s.txt' % split)
            for did in open(imgsets_file):
                did = did.strip()
                img_file = osp.join(img_dataset_dir, 'CamVid_train_images/%s.png' % did)
                lbl_file = osp.join(root, 'CamVid_train_gt/%s.png' % did)
                self.files[split].append({
                    'img': img_file,
                    'lbl': lbl_file,
                })
        imgsets_file = osp.join(root, 'test.txt')
        for did in open(imgsets_file):
            did = did.strip()
            img_file = osp.join(img_dataset_dir, 'CamVid_test_images/%s.png' % did)
            lbl_file = osp.join(root, 'CamVid_test_gt/%s.png' % did)
            self.files['test'].append({
                'img': img_file,
                'lbl': lbl_file,
            })

    def __len__(self):
        return len(self.files[self.split])

    def __getitem__(self, index):
        data_file = self.files[self.split][index]
        # load image
        img_file = data_file['img']
        img = PIL.Image.open(img_file)
        img = np.array(img, dtype=np.uint8)
        # load label
        lbl_file = data_file['lbl']
        lbl = PIL.Image.open(lbl_file)
        lbl = np.array(lbl, dtype=np.int32)
        lbl[lbl == 255] = -1
        if self._transform:
            return self.transform(img, lbl)
        else:
            return img, lbl

    def transform(self, img, lbl):
        random_crop = False
        if random_crop:
            size = (np.array(lbl.shape)*0.8).astype(np.uint32)
            img, lbl = self.random_crop(img, lbl, size)
        random_flip = False
        if random_flip:
            img, lbl = self.random_flip(img, lbl)

        img = img[:, :, ::-1]  # RGB -> BGR
        img = img.astype(np.float64)
        img -= self.mean_bgr
        img /= self.std_bgr
        img = img.transpose(2, 0, 1)
        img = torch.from_numpy(img).float()
        lbl = torch.from_numpy(lbl).long()
        return img, lbl

    def untransform(self, img, lbl):
        img = img.numpy()
        img = img.transpose(1, 2, 0)
        img *= self.std_bgr
        img += self.mean_bgr
        img = img.astype(np.uint8)
        img = img[:, :, ::-1]
        lbl = self.label_to_pil_image(lbl)
        return img, lbl

    def label_to_pil_image(self, lbl):
        color_lbl = torch.zeros(3, lbl.size(0), lbl.size(1)).byte()
        for i, color in enumerate(self.class_colors):
            mask = lbl.eq(i)
            for j in range(3):
                color_lbl[j].masked_fill_(mask, color[j])
        npimg = color_lbl.numpy()
        npimg = np.transpose(npimg, (1, 2, 0))
        return npimg

    def random_crop(self, img, lbl, size):
        h, w = lbl.shape
        th, tw = size
        if w == tw and h == th:
            return img, lbl
        x1 = random.randint(0, w-tw)
        y1 = random.randint(0, h-th)
        img = img[y1:y1+th, x1:x1+tw, :]
        lbl = lbl[y1:y1+th, x1:x1+tw]
        return img, lbl

    def random_flip(self, img, lbl):
        if random.random() < 0.5:
            return np.flip(img, 1).copy(), np.flip(lbl, 1).copy()
        return img, lbl


# For code testing
if __name__ == "__main__":
    root = '/home/dg/Dropbox/Datasets/CamVid'
    dataset = CamVidSeg(root, split='train', dataset='o', transform=True)
    img, lbl = dataset.__getitem__(1)
    img, lbl = dataset.untransform(img, lbl)
    plt.subplot(211)
    plt.imshow(img)
    plt.subplot(212)
    plt.imshow(lbl)
    plt.show()

    # dataset = CamVidSeg(root, split='train', dataset='o', transform=False)
    # mean_img = np.zeros((360, 480, 3))
    # for i in range(dataset.__len__()):
    #     img, lbl = dataset.__getitem__(i)
    #     mean_img += img
    # mean_img.transpose(2, 0, 1)
    # print (np.mean(mean_img[0]/dataset.__len__()))
    # print (np.mean(mean_img[1]/dataset.__len__()))
    # print (np.mean(mean_img[2]/dataset.__len__()))
