import json
import os
import shutil
import sys
import time
from collections import deque
from os.path import exists
from queue import Queue

import cv2

# 自定义输入，输出，配置类
from common.config import Config
from common.input import Input
from common.output import Output

app_name = 'test'

# 读取配置
cf = Config(app_name=app_name)
task_output = Output(cf)

# 相机标号与地址
cam_info = dict()

# 调用openpose参数
mode = "-mode "
grid_square_size_mm = "-grid_square_size_mm " + str(20.0)
grid_number_inner_corners = "-grid_number_inner_corners " + "7x6"
camera_serial_number = "-camera_serial_number camera "
calibration_image_dir = "-calibration_image_dir "
cam0 = "-cam0 "
cam1 = "-cam1 "
middle_camera = "-combine_cam0_extrinsics "
camera_parameter_folder = "-camera_parameter_folder " + "D:/PythonProjects/sparkle/testimages/in/"

# 某相机与 0 号相机外参标定重合图像个数差值
extrinsic_coincidence_image = 0

# 缓冲队列 同一时刻各相机的图片读入内存
real_time_images = Queue(maxlen=480)


def test(camera_total_num):
    try:
        # TODO 关于pyopenpose文件位置
        sys.path.append('D:/PythonProjects/openpose/bin/python/openpose/Release');
        os.environ['PATH'] = os.environ['PATH'] + ';' + 'D:/PythonProjects/openpose/bin'
        import pyopenpose as op
    except ImportError as e:
        print(
            'Error: OpenPose library could not be found. Did you enable `BUILD_PYTHON` in CMake and have this Python script in the right folder?')
        raise e

    coincidence_image = [0 for i in range(camera_total_num)]
    extrinsic_camera_clib_finished = [0 for i in range(camera_total_num)]
    pic_name = 0
    corners_found = False
    calibration_start = False
    calibration_finished = False
    calibration_trigger = False

    # 标定图片处理
    while True:

        if 1 - bool(real_time_images):
            for i in range(0, camera_total_num):
                # TODO 文件读取
                img = cv2.imread("")
                real_time_images.put(img)

        for i in range(0, camera_total_num):
            gray = cv2.cvtColor(real_time_images.get(), cv2.COLOR_BGR2GRAY)
            corner_found, _, = cv2.findChessboardCorners(gray, (7, 6), None)
            corners_found = corners_found or corner_found

            if corners_found:
                coincidence_image[i] += 1
                calibration_trigger = True

            if corners_found and (i == camera_total_num - 1):
                for j in range(0, camera_total_num):
                    shutil.copy(real_time_images.get(), "D:\\result\\" + str(j) + "\\" + str(pic_name) + ".jpg")
                    shutil.copy(real_time_images.get(),
                                "D:\\result\\extrinsic\\" + str(pic_name) + "_" + str(j) + ".jpg")
                pic_name += 1

                if bool(1 - corners_found) and calibration_trigger:
                    calibration_start = True
        if calibration_start:
            break

    if calibration_start:

        for i in range(1, camera_total_num):
            coincidence_image[i] = coincidence_image[i] - coincidence_image[0]

        # 内参标定
        for i in range(0, camera_total_num):
            para = "%s %s %s %s %s %s %s" % (
                "D:\\cpp\\openpose\\build\\bin\\Calibration.exe", mode + str(1), grid_square_size_mm,
                grid_number_inner_corners,
                camera_serial_number + str(i), cam_info[i] + str(i), camera_parameter_folder)
            os.system(para)

        # 外参标定
        # 与 0 号相机重合图像个数达到阈值的相机标定
        for i in range(0, camera_total_num):
            if coincidence_image[i] > extrinsic_coincidence_image:
                para = "%s %s %s %s %s %s %s %s" % (
                    "D:\\cpp\\openpose\\build\\bin\\Calibration.exe", mode + str(2), grid_square_size_mm,
                    grid_number_inner_corners,
                    calibration_image_dir + "D:/PythonProjects/sparkle/testimages/ex/", cam0 + str(0),
                    cam1 + str(i),
                    camera_parameter_folder)
                os.system(para)
                extrinsic_camera_clib_finished[i] = 1

        # 其余相机与 0 号相机标定
        flags = []
        for i in range(0, camera_total_num):
            if i < camera_total_num / 2:
                if extrinsic_camera_clib_finished[i] < extrinsic_coincidence_image:
                    flags.append(i)
            else:
                if extrinsic_camera_clib_finished[i] > extrinsic_coincidence_image:
                    flags.append(i)

        for i in range(0, camera_total_num):
            if extrinsic_camera_clib_finished[i] == 0:
                middle_camera_num = 0
                if i < camera_total_num / 2:
                    middle_camera_num = flags[0]
                else:
                    middle_camera_num = flags[1]

                para = "%s %s %s %s %s %s %s %s %s" % (
                    "D:\\cpp\\openpose\\build\\bin\\Calibration.exe", mode + str(2), grid_square_size_mm,
                    grid_number_inner_corners,
                    calibration_image_dir + "D:/PythonProjects/sparkle/testimages/ex/",
                    cam0 + str(middle_camera_num), cam1 + str(i), middle_camera,
                    camera_parameter_folder)
                os.system(para)

        calibration_finished = True

    if calibration_finished:

        real_time_images.queue.clear()
        for i in range(0, camera_total_num):
            # TODO 文件读取实时
            img = cv2.imread("")
            real_time_images.put(img)

        # TODO openpose关键点提取

        if real_time_images:
            para = "%s %s %s %s %s" % ("poseconnect keypoints3d ", "--pose-model-name BODY_25", "--POSES_2D_PATH ",
                                       "--CAMERA_CALIBRATIONS_PATH ", "--OUTPUT_PATH ")
            os.system(para)


def handle_task(msg):
    if 'data' in msg:
        data = msg['data']
        if data is not None:
            # TODO 读取JSON
            test(len(data['cam_id']))
    # TODO 输出json
    task_output.basic_publish(json.loads())


# 定义一个回调函数来处理消息队列中的消息，这里是打印出来
def on_task_callback(ch, method, cam_info):
    handle_task(json.loads(cam_info.decode()))
    ch.basic_ack(delivery_tag=method.delivery_tag)


# 订阅任务创建消息
task_input = Input(cf, callback=on_task_callback)
task_input.start_consuming()
