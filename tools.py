import cv2
from collections import deque
import numpy as np
from numpy import random
import sqlite3
import datetime
import re
import time


class DatabaseManager:
    """数据库管理类 - 负责所有数据库操作"""

    def __init__(self, db_path="traffic_data.db"):
        self.db_path = db_path
        self.conn = None
        self.cursor = None

    def connect(self):
        """连接数据库"""
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        return self.cursor

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()

    def commit(self):
        """提交事务"""
        if self.conn:
            self.conn.commit()

    def create_tables(self):
        """创建表结构"""
        if not self.cursor:
            self.connect()

        # 创建 traffic 表
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS traffic (
                id INTEGER PRIMARY KEY,
                timestamp DATETIME,
                traffic_volume INTEGER,
                camera_number INTEGER
            )
        ''')

        # 创建 cameras 表
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS cameras
                          (camera_number INTEGER,
                          location TEXT)''')
        self.commit()

    def camera_exists(self, camera_id):
        """检查摄像头是否存在"""
        self.cursor.execute("SELECT * FROM cameras WHERE camera_number = ?", (camera_id,))
        return self.cursor.fetchone() is not None

    def insert_traffic_data(self, timestamp, traffic_volume, camera_number):
        """插入交通数据"""
        last_timestamp = self.get_last_timestamp()

        if str(last_timestamp) == "0001-01-01 00:00:00":
            self.cursor.execute(
                "INSERT INTO traffic (timestamp, traffic_volume, camera_number) VALUES (?, ?, ?)",
                (timestamp, traffic_volume, camera_number)
            )
            self.commit()
        elif datetime.datetime.strptime(timestamp, '%Y-%m-%d %H:%M') > datetime.datetime.strptime(
                last_timestamp, '%Y-%m-%d %H:%M'):
            self.cursor.execute(
                "INSERT INTO traffic (timestamp, traffic_volume, camera_number) VALUES (?, ?, ?)",
                (timestamp, traffic_volume, camera_number)
            )
            self.commit()

    def get_last_timestamp(self):
        """获取最后时间戳"""
        self.cursor.execute("SELECT MAX(timestamp) FROM traffic")
        result = self.cursor.fetchone()
        if result[0]:
            return result[0]
        else:
            return datetime.datetime.min

    def get_traffic_data(self, timestamp):
        """查询交通数据"""
        self.cursor.execute("SELECT * FROM traffic WHERE timestamp = ?", (timestamp,))
        result = self.cursor.fetchone()
        if result:
            formatted_data = f"'序号': {result[0]}, '时间': '{result[1]}', '车流量': {result[2]}"
            return formatted_data
        else:
            return "未找到对应时间的车流量数据"

    def get_all_traffic_data(self):
        """获取所有交通数据"""
        self.cursor.execute("SELECT * FROM traffic")
        return self.cursor.fetchall()

    def search_camera(self, camera_id):
        """查询摄像头信息"""
        self.cursor.execute("SELECT * FROM cameras WHERE camera_number = ?", (int(camera_id),))
        return self.cursor.fetchone()

    def get_traffic_by_time_range(self, camera_id, start_timestamp, end_timestamp):
        """查询时间范围内的车流量"""
        # 直接用范围查询，统计该时间段内所有记录的车流量总和
        self.cursor.execute('''
            SELECT COALESCE(SUM(traffic_volume), 0), COUNT(*)
            FROM traffic
            WHERE camera_number = ? AND timestamp >= ? AND timestamp <= ?
        ''', (camera_id, start_timestamp, end_timestamp))
        result = self.cursor.fetchone()

        total_volume = result[0]
        record_count = result[1]

        if record_count > 0:
            camera_info = self.search_camera(camera_id)
            return {
                'start_time': start_timestamp,
                'end_time': end_timestamp,
                'total_volume': total_volume,
                'camera_number': camera_info[0] if camera_info else camera_id,
                'location': camera_info[1] if camera_info else "未知"
            }
        return None


class TrackerUtils:
    """追踪器工具类 - 负责绘制和计算"""

    # 类别名称列表
    NAMES = [
        "person", "bicycle", "car", "motorbike", "aeroplane", "bus",
        "train", "truck", "boat", "traffic light", "fire hydrant",
        "stop sign", "parking meter", "bench", "bird", "cat",
        "dog", "horse", "sheep", "cow", "elephant", "bear",
        "zebra", "giraffe", "backpack", "umbrella", "handbag",
        "tie", "suitcase", "frisbee", "skis", "snowboard",
        "sports ball", "kite", "baseball bat", "baseball glove",
        "skateboard", "surfboard", "tennis racket", "bottle",
        "wine glass", "cup", "fork", "knife", "spoon", "bowl",
        "banana", "apple", "sandwich", "orange", "broccoli",
        "carrot", "hot dog", "pizza", "donut", "cake", "chair",
        "sofa", "pottedplant", "bed", "diningtable", "toilet",
        "tvmonitor", "laptop", "mouse", "remote", "keyboard",
        "cell phone", "microwave", "oven", "toaster", "sink",
        "refrigerator", "book", "clock", "vase", "scissors",
        "teddy bear", "hair drier", "toothbrush"
    ]

    CLASS_TO_INDEX = {
        "person": 0, "bicycle": 1, "car": 2, "motorbike": 3, "aeroplane": 4, "bus": 5,
        "train": 6, "truck": 7, "boat": 8, "traffic light": 9, "fire hydrant": 10,
        "stop sign": 11, "parking meter": 12, "bench": 13, "bird": 14, "cat": 15,
        "dog": 16, "horse": 17, "sheep": 18, "cow": 19, "elephant": 20, "bear": 21,
        "zebra": 22, "giraffe": 23, "backpack": 24, "umbrella": 25, "handbag": 26,
        "tie": 27, "suitcase": 28, "frisbee": 29, "skis": 30, "snowboard": 31,
        "sports ball": 32, "kite": 33, "baseball bat": 34, "baseball glove": 35,
        "skateboard": 36, "surfboard": 37, "tennis racket": 38, "bottle": 39,
        "wine glass": 40, "cup": 41, "fork": 42, "knife": 43, "spoon": 44, "bowl": 45,
        "banana": 46, "apple": 47, "sandwich": 48, "orange": 49, "broccoli": 50,
        "carrot": 51, "hot dog": 52, "pizza": 53, "donut": 54, "cake": 55, "chair": 56,
        "sofa": 57, "pottedplant": 58, "bed": 59, "diningtable": 60, "toilet": 61,
        "tvmonitor": 62, "laptop": 63, "mouse": 64, "remote": 65, "keyboard": 66,
        "cell phone": 67, "microwave": 68, "oven": 69, "toaster": 70, "sink": 71,
        "refrigerator": 72, "book": 73, "clock": 74, "vase": 75, "scissors": 76,
        "teddy bear": 77, "hair drier": 78, "toothbrush": 79
    }

    INDEX_TO_CLASS = {v: k for k, v in CLASS_TO_INDEX.items()}

    def __init__(self):
        self.palette = (2 ** 11 - 1, 2 ** 15 - 1, 2 ** 20 - 1)
        self.data_deque = {}
        self.object_counter = {}
        self.object_counter1 = {}
        self.start_time = time.time()
        self.reset_duration = 120
        self.count_id = []

    @staticmethod
    def is_number(input_str):
        """检查是否为数字"""
        pattern = r'^\d+$'
        return re.match(pattern, input_str) is not None

    @staticmethod
    def compute_color_for_labels(label):
        """根据类别计算颜色"""
        palette = (2 ** 11 - 1, 2 ** 15 - 1, 2 ** 20 - 1)
        if label == 2:  # Car
            color = (222, 82, 175)
        elif label == 5:  # Bus
            color = (0, 204, 255)
        elif label == 7:  # truck
            color = (0, 149, 255)
        else:
            color = [int((p * (label ** 2 - label + 1)) % 255) for p in palette]
        return tuple(color)

    @staticmethod
    def get_direction(point1, point2):
        """获取移动方向"""
        direction_str = ""

        # calculate y axis direction
        if point1[1] > point2[1]:
            direction_str += "South"
        elif point1[1] < point2[1]:
            direction_str += "North"

        # calculate x axis direction
        if point1[0] > point2[0]:
            direction_str += "East"
        elif point1[0] < point2[0]:
            direction_str += "West"

        return direction_str

    @staticmethod
    def intersect(A, B, C, D):
        """检测线段相交"""
        return TrackerUtils.ccw(A, C, D) != TrackerUtils.ccw(B, C, D) and \
               TrackerUtils.ccw(A, B, C) != TrackerUtils.ccw(A, B, D)

    @staticmethod
    def ccw(A, B, C):
        """判断三点是否逆时针"""
        return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])

    @staticmethod
    def draw_border(img, pt1, pt2, color, thickness, r, d):
        """绘制圆角边框"""
        x1, y1 = pt1
        x2, y2 = pt2
        # Top left
        cv2.line(img, (x1 + r, y1), (x1 + r + d, y1), color, thickness)
        cv2.line(img, (x1, y1 + r), (x1, y1 + r + d), color, thickness)
        cv2.ellipse(img, (x1 + r, y1 + r), (r, r), 180, 0, 90, color, thickness)
        # Top right
        cv2.line(img, (x2 - r, y1), (x2 - r - d, y1), color, thickness)
        cv2.line(img, (x2, y1 + r), (x2, y1 + r + d), color, thickness)
        cv2.ellipse(img, (x2 - r, y1 + r), (r, r), 270, 0, 90, color, thickness)
        # Bottom left
        cv2.line(img, (x1 + r, y2), (x1 + r + d, y2), color, thickness)
        cv2.line(img, (x1, y2 - r), (x1, y2 - r - d), color, thickness)
        cv2.ellipse(img, (x1 + r, y2 - r), (r, r), 90, 0, 90, color, thickness)
        # Bottom right
        cv2.line(img, (x2 - r, y2), (x2 - r - d, y2), color, thickness)
        cv2.line(img, (x2, y2 - r), (x2, y2 - r - d), color, thickness)
        cv2.ellipse(img, (x2 - r, y2 - r), (r, r), 0, 0, 90, color, thickness)

        cv2.rectangle(img, (x1 + r, y1), (x2 - r, y2), color, -1, cv2.LINE_AA)
        cv2.rectangle(img, (x1, y1 + r), (x2, y2 - r - d), color, -1, cv2.LINE_AA)

        cv2.circle(img, (x1 + r, y1 + r), 2, color, 12)
        cv2.circle(img, (x2 - r, y1 + r), 2, color, 12)
        cv2.circle(img, (x1 + r, y2 - r), 2, color, 12)
        cv2.circle(img, (x2 - r, y2 - r), 2, color, 12)

        return img

    @staticmethod
    def UI_box(x, img, color=None, label=None, line_thickness=None):
        """绘制边界框"""
        tl = line_thickness or round(0.002 * (img.shape[0] + img.shape[1]) / 2) + 1
        color = color or [random.randint(0, 255) for _ in range(3)]
        c1, c2 = (int(x[0]), int(x[1])), (int(x[2]), int(x[3]))
        cv2.rectangle(img, c1, c2, color, thickness=tl, lineType=cv2.LINE_AA)
        if label:
            tf = max(tl - 1, 1)
            t_size = cv2.getTextSize(label, 0, fontScale=tl / 3, thickness=tf)[0]

            img = TrackerUtils.draw_border(
                img, (c1[0], c1[1] - t_size[1] - 3),
                (c1[0] + t_size[0], c1[1] + 3), color, 1, 8, 2
            )

            cv2.putText(
                img, label, (c1[0], c1[1] - 2), 0, tl / 3,
                [225, 255, 255], thickness=tf, lineType=cv2.LINE_AA
            )

    @staticmethod
    def get_dicname(key, value, dic):
        """更新字典"""
        if key in ["car", "bus", "truck"]:
            dic[key] = value
        return dic

    @staticmethod
    def sum_categories(dic):
        """计算字典总和"""
        return sum(dic.values())

    def get_class_name(self, index):
        """获取类别名称"""
        return self.INDEX_TO_CLASS.get(index, "Unknown")

    def get_class_index(self, class_name):
        """获取类别索引"""
        return self.CLASS_TO_INDEX.get(class_name, -1)

    def reset_counters(self):
        """重置计数器"""
        self.object_counter = {}
        self.object_counter1 = {}

    def draw_boxes(self, count, img, bbox, names, object_id, identities=None, offset=(0, 0)):
        """绘制边界框和轨迹"""
        # Check if it's time to reset the counters
        if time.time() - self.start_time >= self.reset_duration:
            self.reset_counters()
            self.start_time = time.time()

        # 判断视频是否切换
        if count not in self.count_id:
            self.count_id.append(count)
            self.reset_counters()

        h, w, _ = img.shape
        line = [(0, int(0.66 * h)), (w, int(0.66 * h))]

        cv2.line(img, line[0], line[1], (46, 162, 112), 3)
        dic1 = {}
        dic2 = {}
        height, width, _ = img.shape

        # remove tracked point from buffer if object is lost
        for key in list(self.data_deque):
            if key not in identities:
                self.data_deque.pop(key)

        total = 0
        for i, box in enumerate(bbox):
            x1, y1, x2, y2 = [int(i) for i in box]
            x1 += offset[0]
            x2 += offset[0]
            y1 += offset[1]
            y2 += offset[1]
            center = (int((x2 + x1) / 2), int((y2 + y2) / 2))
            id = int(identities[i]) if identities is not None else 0
            if id not in self.data_deque:
                self.data_deque[id] = deque(maxlen=64)
            color = self.compute_color_for_labels(object_id[i])
            obj_name = names[object_id[i]]
            label = '{}{:d}'.format("", id) + ":" + '%s' % (obj_name)
            self.data_deque[id].appendleft(center)
            if len(self.data_deque[id]) >= 2:
                direction = self.get_direction(self.data_deque[id][0], self.data_deque[id][1])
                if self.intersect(self.data_deque[id][0], self.data_deque[id][1], line[0], line[1]):
                    cv2.line(img, line[0], line[1], (255, 255, 255), 3)
                    if "South" in direction:
                        if obj_name not in self.object_counter:
                            self.object_counter[obj_name] = 1
                        else:
                            self.object_counter[obj_name] += 1
                    if "North" in direction:
                        if obj_name not in self.object_counter1:
                            self.object_counter1[obj_name] = 1
                        else:
                            self.object_counter1[obj_name] += 1
            self.UI_box(box, img, label=label, color=color, line_thickness=2)
            for j in range(1, len(self.data_deque[id])):
                if self.data_deque[id][j - 1] is None or self.data_deque[id][j] is None:
                    continue
                thickness = int(np.sqrt(64 / float(j + j)) * 1.5)
                cv2.line(img, self.data_deque[id][j - 1], self.data_deque[id][j], color, thickness)
            for idx, (key, value) in enumerate(self.object_counter1.items()):
                cnt_str = str(key) + ":" + str(value)
                dic1 = self.get_dicname(key, value, dic1)
                cv2.line(img, (int(width - 0.28 * width), 25), (width, 25), [85, 45, 255], 40)
                cv2.putText(img, f'Traffic volume', (int(width - 0.28 * width), 35), 0, 1, [225, 255, 255],
                            thickness=2, lineType=cv2.LINE_AA)
                cv2.line(img, (width - 150, 65 + (idx * 40)), (width, 65 + (idx * 40)), [85, 45, 255], 30)
                cv2.putText(img, cnt_str, (width - 150, 75 + (idx * 40)), 0, 1, [255, 255, 255], thickness=2,
                            lineType=cv2.LINE_AA)
            for idx, (key, value) in enumerate(self.object_counter.items()):
                dic2 = self.get_dicname(key, value, dic2)
                cnt_str1 = str(key) + ":" + str(value)
                cv2.line(img, (20, 25), (int(0.28 * width), 25), [85, 45, 255], 40)
                cv2.putText(img, f'Traffic volume', (11, 35), 0, 1, [225, 255, 255], thickness=2,
                            lineType=cv2.LINE_AA)
                cv2.line(img, (20, 65 + (idx * 40)), (127, 65 + (idx * 40)), [85, 45, 255], 30)
                cv2.putText(img, cnt_str1, (11, 75 + (idx * 40)), 0, 1, [255, 255, 255], thickness=2,
                            lineType=cv2.LINE_AA)
            total = self.sum_categories(dic1) + self.sum_categories(dic2)
            tot = "total: " + str(total)
            if dic1 or dic2:
                cv2.putText(img, tot, (int(width / 2) - 75, 75 + 40), 0, 1, [0, 0, 255], thickness=2,
                            lineType=cv2.LINE_AA)

        return total, img

