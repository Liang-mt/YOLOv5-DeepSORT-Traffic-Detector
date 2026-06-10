# -*- coding: utf-8 -*-

import shutil
import PyQt5.QtCore
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
import threading
import argparse
import os
import sys
from pathlib import Path
import cv2
import torch
import torch.backends.cudnn as cudnn
from AIDetector_pytorch import Detector
import imutils
import time
import sqlite3
import datetime
import numpy as np
from PIL import ImageFont, ImageDraw, Image
import re
from tools import DatabaseManager, TrackerUtils
import pandas as pd


class ImageUtils:
    """图像工具类"""

    @staticmethod
    def cv2ImgAddText(img, text, left, top, textColor=(0, 255, 0), textSize=20):
        """
        在图像上添加中文文字

        Args:
            img: 输入图像
            text: 要添加的文字
            left: 左边距
            top: 上边距
            textColor: 文字颜色
            textSize: 文字大小

        Returns:
            添加文字后的图像
        """
        if isinstance(img, np.ndarray):  # 判断是否OpenCV图片类型
            img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img)
        fontText = ImageFont.truetype(
            "./font/platech.ttf", textSize, encoding="utf-8")
        draw.text((left, top), text, textColor, font=fontText)
        return cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR)


# 窗口主类
class MainWindow(QTabWidget):
    # 基本配置不动，然后只动第三个界面
    def __init__(self, cam_id=0):
        # 初始化界面
        super().__init__()

        # 实例变量替代全局变量
        self.count = 0
        self.set_cam_id = 0
        self.cam_id_set = 0
        self.set_start_time = 0
        self.set_end_time = 0

        # 实例化依赖类
        self.db_manager = DatabaseManager()
        self.tracker_utils = TrackerUtils()
        self.image_utils = ImageUtils()

        # 初始化摄像头ID
        self.cam_id = cam_id

        self.setWindowTitle('Yolov5目标检测系统')
        self.resize(1200, 800)
        self.setWindowIcon(QIcon("images/UI/xf.jpg"))
        # 图片读取进程
        self.output_size = 480
        self.img2predict = ""
        # 初始化视频读取线程
        self.vid_source = cam_id  # 初始设置为摄像头
        self.stopEvent = threading.Event()
        self.webcam = True
        self.stopEvent.clear()
        self.det = Detector()

        self.initUI()
        self.reset_vid()

        self.location_id = ["成化大道", "枫林路", "锦溪道", "韶华路"]

    def _get_button_style(self):
        """获取按钮样式"""
        return (
            "QPushButton{color:white}"
            "QPushButton:hover{background-color: rgb(2,110,180);}"
            "QPushButton{background-color:rgb(48,124,208)}"
            "QPushButton{border:2px}"
            "QPushButton{border-radius:5px}"
            "QPushButton{padding:5px 5px}"
            "QPushButton{margin:5px 5px}"
        )

    '''
    ***界面初始化***
    '''

    def initUI(self):
        # 图片检测子界面
        font_title = QFont('楷体', 16)
        font_main = QFont('楷体', 14)

        # 图片识别界面, 两个按钮，上传图片和显示结果
        img_detection_widget = QWidget()
        img_detection_layout = QVBoxLayout()
        img_detection_title = QLabel("车流量查询功能")
        img_detection_title.setFont(font_title)
        mid_img_widget = QWidget()
        mid_img_layout = QHBoxLayout()
        self._img = QLabel()
        self._img.setPixmap(QPixmap("images/UI/up.jpeg"))
        self._img.setAlignment(Qt.AlignCenter)
        mid_img_layout.addWidget(self._img)
        mid_img_widget.setLayout(mid_img_layout)

        cam_id_button = QPushButton("摄像头id")
        time_button = QPushButton("时间段")
        up_img_button = QPushButton("车流量查询")
        det_img_button = QPushButton("摄像头序号查询")

        cam_id_button.clicked.connect(self.select_cam_id)
        time_button.clicked.connect(self.select_time_range)
        up_img_button.clicked.connect(self.traffic_volume_query)
        det_img_button.clicked.connect(self.camera_search)

        cam_id_button.setFont(font_main)
        time_button.setFont(font_main)
        up_img_button.setFont(font_main)
        det_img_button.setFont(font_main)

        button_style = self._get_button_style()
        cam_id_button.setStyleSheet(button_style)
        time_button.setStyleSheet(button_style)
        up_img_button.setStyleSheet(button_style)
        det_img_button.setStyleSheet(button_style)

        img_detection_layout.addWidget(img_detection_title, alignment=Qt.AlignCenter)
        img_detection_layout.addWidget(mid_img_widget, alignment=Qt.AlignCenter)
        img_detection_layout.addWidget(cam_id_button)
        img_detection_layout.addWidget(time_button)
        img_detection_layout.addWidget(up_img_button)
        img_detection_layout.addWidget(det_img_button)
        img_detection_widget.setLayout(img_detection_layout)

        # todo 视频识别界面
        # 视频识别界面的逻辑比较简单，基本就从上到下的逻辑
        vid_detection_widget = QWidget()
        vid_detection_layout = QVBoxLayout()
        vid_title = QLabel("视频检测功能")
        vid_title.setFont(font_title)
        self.vid_img = QLabel()
        self.vid_img.setPixmap(QPixmap("images/UI/up.jpeg"))
        vid_title.setAlignment(Qt.AlignCenter)
        self.vid_img.setAlignment(Qt.AlignCenter)
        self.webcam_id_btn = QPushButton("摄像头id设置")
        self.webcam_detection_btn = QPushButton("摄像头实时监测")
        self.mp4_detection_btn = QPushButton("视频文件检测")
        self.vid_stop_btn = QPushButton("停止检测")
        self.webcam_id_btn.setFont(font_main)
        self.webcam_detection_btn.setFont(font_main)
        self.mp4_detection_btn.setFont(font_main)
        self.vid_stop_btn.setFont(font_main)

        self.webcam_id_btn.setStyleSheet(button_style)
        self.webcam_detection_btn.setStyleSheet(button_style)
        self.mp4_detection_btn.setStyleSheet(button_style)
        self.vid_stop_btn.setStyleSheet(button_style)

        self.webcam_id_btn.clicked.connect(self.cam_id_select)
        self.webcam_detection_btn.clicked.connect(self.open_cam)
        self.mp4_detection_btn.clicked.connect(self.open_mp4)
        self.vid_stop_btn.clicked.connect(self.close_vid)
        # 添加组件到布局上
        vid_detection_layout.addWidget(vid_title)
        vid_detection_layout.addWidget(self.vid_img)
        vid_detection_layout.addWidget(self.webcam_id_btn)
        vid_detection_layout.addWidget(self.webcam_detection_btn)
        vid_detection_layout.addWidget(self.mp4_detection_btn)
        vid_detection_layout.addWidget(self.vid_stop_btn)
        vid_detection_widget.setLayout(vid_detection_layout)

        self.addTab(img_detection_widget, '车流量查询')
        self.addTab(vid_detection_widget, '视频检测')

    def select_cam_id(self):
        """选择摄像头ID"""
        dialog = QDialog()
        dialog.setWindowTitle("选择摄像头ID")
        layout = QVBoxLayout()

        combobox = QComboBox()
        combobox.addItems(["0", "1", "2", "3"])

        layout.addWidget(combobox)

        # Create a horizontal layout for buttons
        buttons_layout = QHBoxLayout()

        confirm_button = QPushButton("确认")
        cancel_button = QPushButton("取消")

        buttons_layout.addWidget(confirm_button)
        buttons_layout.addWidget(cancel_button)

        # Add button layout to the main layout
        layout.addLayout(buttons_layout)

        dialog.setLayout(layout)

        # Connect buttons to accept and reject slots
        confirm_button.clicked.connect(dialog.accept)
        cancel_button.clicked.connect(dialog.reject)

        if dialog.exec_() == QDialog.Accepted:
            self.set_cam_id = combobox.currentText()
        else:
            self.set_cam_id = "5"  # Assuming you want a string as the default value

    def select_time_range(self):
        """选择时间范围 - 带快捷时间按钮"""
        dialog = QDialog()
        dialog.setWindowTitle("设置时间段")
        dialog.setMinimumWidth(380)
        layout = QVBoxLayout()

        # ===== 快捷时间按钮 =====
        quick_group = QGroupBox("快捷选择")
        quick_layout = QGridLayout()

        now = datetime.datetime.now()
        quick_presets = [
            ("今天", 0, 0),
            ("昨天", 1, 1),
            ("最近3天", 3, 0),
            ("最近7天", 7, 0),
            ("最近30天", 30, 0),
            ("本月", "month", 0),
        ]

        def set_quick_time(days_back, end_back):
            """设置快捷时间"""
            if days_back == "month":
                start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                end = now.replace(hour=23, minute=59, second=0, microsecond=0)
            else:
                start = (now - datetime.timedelta(days=days_back)).replace(hour=0, minute=0, second=0, microsecond=0)
                if end_back > 0:
                    end = (now - datetime.timedelta(days=end_back)).replace(hour=23, minute=59, second=0, microsecond=0)
                else:
                    end = now.replace(second=0, microsecond=0)
            start_datetime_edit.setDateTime(QDateTime.fromString(start.strftime("%Y-%m-%d %H:%M"), "yyyy-MM-dd HH:mm"))
            end_datetime_edit.setDateTime(QDateTime.fromString(end.strftime("%Y-%m-%d %H:%M"), "yyyy-MM-dd HH:mm"))

        for idx, (label, days, end_back) in enumerate(quick_presets):
            btn = QPushButton(label)
            btn.setFixedHeight(32)
            btn.setStyleSheet(
                "QPushButton{background-color:#e8f4fd; color:#333; border:1px solid #b3d8f0; border-radius:4px;}"
                "QPushButton:hover{background-color:#d0ebfa;}"
            )
            btn.clicked.connect(lambda checked, d=days, e=end_back: set_quick_time(d, e))
            quick_layout.addWidget(btn, idx // 3, idx % 3)

        quick_group.setLayout(quick_layout)
        layout.addWidget(quick_group)

        # ===== 自定义时间选择 =====
        custom_group = QGroupBox("自定义时间")
        custom_layout = QVBoxLayout()

        start_datetime_edit = QDateTimeEdit()
        end_datetime_edit = QDateTimeEdit()
        start_datetime_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        end_datetime_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        start_datetime_edit.setCalendarPopup(True)
        end_datetime_edit.setCalendarPopup(True)

        custom_layout.addWidget(QLabel("开始时间:"))
        custom_layout.addWidget(start_datetime_edit)
        custom_layout.addWidget(QLabel("截止时间:"))
        custom_layout.addWidget(end_datetime_edit)

        custom_group.setLayout(custom_layout)
        layout.addWidget(custom_group)

        # ===== 确认/取消按钮 =====
        buttons_layout = QHBoxLayout()
        confirm_button = QPushButton("确认")
        cancel_button = QPushButton("取消")
        confirm_button.setStyleSheet(self._get_button_style())
        cancel_button.setStyleSheet(self._get_button_style())
        buttons_layout.addWidget(confirm_button)
        buttons_layout.addWidget(cancel_button)
        layout.addLayout(buttons_layout)

        confirm_button.clicked.connect(dialog.accept)
        cancel_button.clicked.connect(dialog.reject)

        dialog.setLayout(layout)

        if dialog.exec_() == QDialog.Accepted:
            self.set_start_time = start_datetime_edit.dateTime().toString("yyyy-MM-dd HH:mm")
            self.set_end_time = end_datetime_edit.dateTime().toString("yyyy-MM-dd HH:mm")

    def traffic_volume_query(self):
        """车流量查询"""
        camera_id = int(self.set_cam_id)
        start_time = self.set_start_time
        end_time = self.set_end_time

        pattern = r"\b\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}\b"

        width, height = 1200, 800
        im0 = np.ones((height, width, 3), np.uint8) * 255  # 白色的图片

        if self.set_start_time != 0 and self.set_end_time != 0:
            if re.match(pattern, start_time) and re.match(pattern, end_time):
                try:
                    # 连接数据库
                    self.db_manager.connect()
                    self.db_manager.create_tables()

                    # 查询时间范围内的车流量
                    result = self.db_manager.get_traffic_by_time_range(camera_id, start_time, end_time)

                    if result:
                        i_start = f"起始时间     {result['start_time']}"
                        i_end = f"结束时间     {result['end_time']}"
                        i_num = f"车流量         {result['total_volume']}"
                        i_cam_id = f"摄像头序号  {result['camera_number']}"
                        i_local = f"地理位置     {result['location']}"

                        im0 = ImageUtils.cv2ImgAddText(im0, str(i_start), 120, 100, textColor=(0, 0, 0), textSize=40)
                        im0 = ImageUtils.cv2ImgAddText(im0, str(i_end), 120, 180, textColor=(0, 0, 0), textSize=40)
                        im0 = ImageUtils.cv2ImgAddText(im0, str(i_num), 120, 260, textColor=(0, 0, 0), textSize=40)
                        im0 = ImageUtils.cv2ImgAddText(im0, str(i_cam_id), 120, 340, textColor=(0, 0, 0), textSize=40)
                        im0 = ImageUtils.cv2ImgAddText(im0, str(i_local), 120, 440, textColor=(0, 0, 0), textSize=40)

                        self.db_manager.close()
                    else:
                        text = "未找到对应时间的车流量数据"
                        im0 = ImageUtils.cv2ImgAddText(im0, str(text), 300, 200, textColor=(0, 0, 0), textSize=40)

                except ValueError:
                    text = "时间戳格式不正确，请使用正确的格式：2024-02-25 15:25"
                    im0 = ImageUtils.cv2ImgAddText(im0, str(text), 100, 200, textColor=(0, 0, 0), textSize=40)

            else:
                text = "时间戳格式不正确，请使用正确的格式：2024-02-25 15:25"
                im0 = ImageUtils.cv2ImgAddText(im0, str(text), 100, 200, textColor=(0, 0, 0), textSize=40)

            resize_scale = self.output_size / im0.shape[0]
            im0 = cv2.resize(im0, (0, 0), fx=resize_scale, fy=resize_scale)
            cv2.imwrite("images/tmp/upload_show_result.jpg", im0)
            self._img.setPixmap(QPixmap("images/tmp/upload_show_result.jpg"))

        else:
            text = "未设置摄像头序号或时间段"
            im0 = ImageUtils.cv2ImgAddText(im0, str(text), 300, 200, textColor=(0, 0, 0), textSize=40)

            resize_scale = self.output_size / im0.shape[0]
            im0 = cv2.resize(im0, (0, 0), fx=resize_scale, fy=resize_scale)
            cv2.imwrite("images/tmp/upload_show_result.jpg", im0)
            self._img.setPixmap(QPixmap("images/tmp/upload_show_result.jpg"))

    '''
    ***摄像头序号查询***
    '''

    def camera_search(self):
        """摄像头序号查询"""
        fileName, _ = QInputDialog.getText(self, '输入摄像头序号', '确认序号:')
        Name = self.tracker_utils.is_number(fileName)
        width, height = 1200, 800
        im0 = np.ones((height, width, 3), np.uint8) * 255  # 白色的图片
        if Name:
            # 连接数据库
            self.db_manager.connect()
            self.db_manager.create_tables()

            # 查询摄像头数据
            result = self.db_manager.search_camera(int(fileName))

            if result:
                formatted_data = f"'摄像头序号': {result[0]}, '地理位置': '{result[1]}'"
                im0 = ImageUtils.cv2ImgAddText(im0, str(formatted_data), 250, 200, textColor=(0, 0, 0), textSize=40)
            else:
                text = "未找到相关数据库信息"
                im0 = ImageUtils.cv2ImgAddText(im0, str(text), 400, 200, textColor=(0, 0, 0), textSize=40)

            self.db_manager.close()

        resize_scale = self.output_size / im0.shape[0]
        im0 = cv2.resize(im0, (0, 0), fx=resize_scale, fy=resize_scale)
        cv2.imwrite("images/tmp/upload_show_result1.jpg", im0)
        self._img.setPixmap(QPixmap("images/tmp/upload_show_result1.jpg"))

    def closeEvent(self, event):
        """关闭事件"""
        reply = QMessageBox.question(self,
                                     'quit',
                                     "Are you sure?",
                                     QMessageBox.Yes | QMessageBox.No,
                                     QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.close()
            event.accept()
        else:
            event.ignore()

    '''
    ### 视频关闭事件 ###
    '''

    def open_cam(self):
        """打开摄像头"""
        self.stopEvent.clear()
        self.webcam_detection_btn.setEnabled(False)
        self.mp4_detection_btn.setEnabled(False)
        self.vid_stop_btn.setEnabled(True)
        self.vid_source = self.cam_id
        self.webcam = True
        th = threading.Thread(target=self.detect_vid, daemon=True)
        th.start()

    '''
    ### 开启视频文件检测事件 ###
    '''

    def open_mp4(self):
        """打开视频文件"""
        fileName, fileType = QFileDialog.getOpenFileName(self, 'Choose file', '', '*.mp4 *.avi')
        if fileName:
            self.stopEvent.clear()
            self.webcam_detection_btn.setEnabled(False)
            self.mp4_detection_btn.setEnabled(False)
            self.vid_source = fileName
            self.webcam = False
            th = threading.Thread(target=self.detect_vid, daemon=True)
            th.start()

    '''
    ### 视频开启事件 ###
    '''
    # 视频和摄像头的主函数是一样的，不过是传入的source不同罢了

    def cam_id_select(self):
        """选择摄像头ID"""
        dialog = QDialog()
        dialog.setWindowTitle("选择摄像头ID")
        layout = QVBoxLayout()

        combobox = QComboBox()
        combobox.addItems(["0", "1", "2", "3"])

        layout.addWidget(combobox)

        # Create a horizontal layout for buttons
        buttons_layout = QHBoxLayout()

        confirm_button = QPushButton("确认")
        cancel_button = QPushButton("取消")

        buttons_layout.addWidget(confirm_button)
        buttons_layout.addWidget(cancel_button)

        # Add button layout to the main layout
        layout.addLayout(buttons_layout)

        dialog.setLayout(layout)

        # Connect buttons to accept and reject slots
        confirm_button.clicked.connect(dialog.accept)
        cancel_button.clicked.connect(dialog.reject)

        if dialog.exec_() == QDialog.Accepted:
            self.cam_id_set = combobox.currentText()
        else:
            self.cam_id_set = "5"  # Assuming you want a string as the default value

    def detect_vid(self):
        """视频检测"""
        camera_id = self.cam_id_set
        output_size = self.output_size
        source = str(self.vid_source)
        if source in ["0", "1", "2", "3"]:
            source = int(source)
            cap = cv2.VideoCapture(source, cv2.CAP_DSHOW)
        else:
            cap = cv2.VideoCapture(source)

        # 保存 cap 引用，供 close_vid() 主动释放
        self._cap = cap

        # 连接数据库
        self.db_manager.connect()
        self.db_manager.create_tables()

        camera_id = int(camera_id)
        location = self.location_id[camera_id]
        if not self.db_manager.camera_exists(camera_id):
            self.db_manager.cursor.execute(
                "INSERT INTO cameras (camera_number, location) VALUES (?, ?)",
                (camera_id, location)
            )
            self.db_manager.commit()

        self.count = self.count + 1
        while cap.isOpened():
            if self.stopEvent.is_set():
                break

            ret, img0 = cap.read()
            if not ret:
                break

            if self.stopEvent.is_set():
                break

            result = self.det.feedCap(img0, self.count)
            frame = result['frame']
            result_car_num = result['car_num']

            if self.stopEvent.is_set():
                break

            current_time = datetime.datetime.now().replace(second=0, microsecond=0).strftime('%Y-%m-%d %H:%M')
            self.db_manager.insert_traffic_data(current_time, result_car_num, camera_id)

            resize_scale = output_size / frame.shape[0]
            frame_resized = cv2.resize(frame, (0, 0), fx=resize_scale, fy=resize_scale)
            cv2.imwrite("images/tmp/single_result_vid.jpg", frame_resized)
            self.vid_img.setPixmap(QPixmap("images/tmp/single_result_vid.jpg"))

            if cv2.waitKey(25) & self.stopEvent.is_set() == True:
                break

        # 清理资源
        cap.release()
        self._cap = None
        self.db_manager.close()

        if not self.stopEvent.is_set():
            self.reset_vid()
        else:
            # 所有 UI 恢复统一在子线程中执行，避免与主线程竞争导致闪屏
            self.webcam_detection_btn.setEnabled(True)
            self.mp4_detection_btn.setEnabled(True)
            self.vid_img.setPixmap(QPixmap("images/UI/up.jpeg"))

    '''
    ### 界面重置事件 ###
    '''

    def reset_vid(self):
        """重置视频"""
        self.webcam_detection_btn.setEnabled(True)
        self.mp4_detection_btn.setEnabled(True)
        self.vid_img.setPixmap(QPixmap("images/UI/up.jpeg"))
        self.vid_source = self.cam_id
        self.webcam = True

    '''
    ### 视频重置事件 ###
    '''

    def close_vid(self):
        """停止视频 - 只设置标志和释放资源，UI 恢复由子线程统一处理"""
        self.stopEvent.set()
        # 主动释放 VideoCapture，打断子线程的 cap.read() 阻塞
        if hasattr(self, '_cap') and self._cap is not None:
            self._cap.release()
            self._cap = None


if __name__ == "__main__":
    cam_id = 0
    if cam_id in ["0", "1", "2", "3"]:
        cam_id = int(cam_id)

    app = QApplication(sys.argv)
    mainWindow = MainWindow(cam_id)
    mainWindow.show()
    sys.exit(app.exec_())
