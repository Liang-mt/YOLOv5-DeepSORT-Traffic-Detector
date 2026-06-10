# 代码重构变更记录

## 概述

对 `ui2.py`、`tools.py`、`tracker.py`、`utils/BaseDetector.py` 进行了面向对象重构，移除了全局变量，优化了代码逻辑，并修复了停止检测时的闪屏问题。

---

## 一、tools.py 变更

### 1. 新增 `DatabaseManager` 类

将所有数据库操作封装为类方法，替代原来的独立函数。

```python
# ==================== 重构前 ====================
import sqlite3

def insert_traffic_data(cursor, conn, timestamp, traffic_volume, camera_number):
    last_timestamp = get_last_timestamp(cursor)
    if str(last_timestamp) == "0001-01-01 00:00:00":
        cursor.execute("INSERT INTO traffic ...")
    elif datetime.datetime.strptime(...) > ...:
        cursor.execute("INSERT INTO traffic ...")
        conn.commit()

def get_last_timestamp(cursor):
    cursor.execute("SELECT MAX(timestamp) FROM traffic")
    result = cursor.fetchone()
    if result[0]:
        return result[0]
    else:
        return datetime.datetime.min

def camera_exists(cursor, camera_id):
    cursor.execute("SELECT * FROM cameras WHERE camera_number = ?", (camera_id,))
    return cursor.fetchone() is not None


# ==================== 重构后 ====================
class DatabaseManager:
    def __init__(self, db_path="traffic_data.db"):
        self.db_path = db_path
        self.conn = None
        self.cursor = None

    def connect(self):
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        return self.cursor

    def close(self):
        if self.conn:
            self.conn.close()

    def commit(self):
        if self.conn:
            self.conn.commit()

    def create_tables(self):
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS traffic (...)''')
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS cameras (...)''')
        self.commit()

    def camera_exists(self, camera_id):
        self.cursor.execute("SELECT * FROM cameras WHERE camera_number = ?", (camera_id,))
        return self.cursor.fetchone() is not None

    def insert_traffic_data(self, timestamp, traffic_volume, camera_number):
        last_timestamp = self.get_last_timestamp()
        ...

    def get_last_timestamp(self):
        ...

    def get_traffic_data(self, timestamp):
        ...

    def get_all_traffic_data(self):
        ...

    def search_camera(self, camera_id):
        ...

    def get_traffic_by_time_range(self, camera_id, start_timestamp, end_timestamp):
        # 原来分散在 ui2.py 的 traffic_volume_query 中的查询逻辑集中到这里
        ...
```

### 2. 新增 `TrackerUtils` 类

将所有追踪器相关的工具函数和全局变量封装为类。

```python
# ==================== 重构前 ====================
palette = (2 ** 11 - 1, 2 ** 15 - 1, 2 ** 20 - 1)
data_deque = {}
object_counter = {}
object_counter1 = {}
start_time = time.time()
reset_duration = 120
count_id = []
names = ["person", "bicycle", "car", ...]
class_to_index = {"person": 0, "bicycle": 1, ...}
index_to_class = {0: "person", 1: "bicycle", ...}

def is_number(input_str): ...
def compute_color_for_labels(label): ...
def get_direction(point1, point2): ...
def intersect(A, B, C, D): ...
def ccw(A, B, C): ...
def draw_border(img, pt1, pt2, color, thickness, r, d): ...
def UI_box(x, img, color=None, label=None, line_thickness=None): ...
def get_dicname(key, value, dic): ...
def sum_categories(dic): ...
def draw_boxes(count, img, bbox, names, object_id, identities=None, offset=(0, 0)):
    global start_time, object_counter, object_counter1
    ...


# ==================== 重构后 ====================
class TrackerUtils:
    # 常量定义为类属性
    NAMES = ["person", "bicycle", "car", ...]
    CLASS_TO_INDEX = {"person": 0, "bicycle": 1, ...}
    INDEX_TO_CLASS = {v: k for k, v in CLASS_TO_INDEX.items()}

    def __init__(self):
        # 全局变量改为实例变量
        self.palette = (2 ** 11 - 1, 2 ** 15 - 1, 2 ** 20 - 1)
        self.data_deque = {}
        self.object_counter = {}
        self.object_counter1 = {}
        self.start_time = time.time()
        self.reset_duration = 120
        self.count_id = []

    @staticmethod
    def is_number(input_str): ...

    @staticmethod
    def compute_color_for_labels(label): ...

    @staticmethod
    def get_direction(point1, point2): ...

    @staticmethod
    def intersect(A, B, C, D): ...

    @staticmethod
    def ccw(A, B, C): ...

    @staticmethod
    def draw_border(img, pt1, pt2, color, thickness, r, d): ...

    @staticmethod
    def UI_box(x, img, color=None, label=None, line_thickness=None): ...

    @staticmethod
    def get_dicname(key, value, dic): ...

    @staticmethod
    def sum_categories(dic): ...

    def reset_counters(self):
        self.object_counter = {}
        self.object_counter1 = {}

    def draw_boxes(self, count, img, bbox, names, object_id, identities=None, offset=(0, 0)):
        # 移除 global 声明，改为使用 self.xxx
        if time.time() - self.start_time >= self.reset_duration:
            self.reset_counters()
            self.start_time = time.time()
        ...

    def get_class_name(self, index): ...
    def get_class_index(self, class_name): ...
```

### 3. 删除的冗余代码

```python
# 以下全局变量和独立函数全部移除，不再保留
palette = ...
data_deque = {}
object_counter = {}
object_counter1 = {}
start_time = time.time()
reset_duration = 120
count_id = []
names = [...]
class_to_index = {...}
index_to_class = {...}

# 以下独立函数全部移入 TrackerUtils 类
def is_number(input_str): ...
def compute_color_for_labels(label): ...
def get_direction(point1, point2): ...
def intersect(A, B, C, D): ...
def ccw(A, B, C): ...
def draw_border(...): ...
def UI_box(...): ...
def get_dicname(...): ...
def sum_categories(...): ...
def draw_boxes(...): ...
```

---

## 二、tracker.py 变更

### 1. 新增 `DeepSortTracker` 类

```python
# ==================== 重构前 ====================
from deep_sort_pytorch.utils.parser import get_config
from deep_sort_pytorch.deep_sort import DeepSort
import torch
from tools import *

palette = (2 ** 11 - 1, 2 ** 15 - 1, 2 ** 20 - 1)
cfg = get_config()
cfg.merge_from_file("deep_sort_pytorch/configs/deep_sort.yaml")
deepsort = DeepSort(cfg.DEEPSORT.REID_CKPT,
                    max_dist=cfg.DEEPSORT.MAX_DIST, ...)

def plot_bboxes(image, bboxes, line_thickness=None): ...

def update_tracker(target_detector, image, count):
    _, bboxes = target_detector.detect(image)
    ...
    outputs = deepsort.update(xywhs, confss, clss, image)
    ...
    return total_num, image


# ==================== 重构后 ====================
from deep_sort_pytorch.utils.parser import get_config
from deep_sort_pytorch.deep_sort import DeepSort
import torch
import cv2
from tools import TrackerUtils
import time

class DeepSortTracker:
    def __init__(self, config_path="deep_sort_pytorch/configs/deep_sort.yaml", use_cuda=True):
        self.palette = (2 ** 11 - 1, 2 ** 15 - 1, 2 ** 20 - 1)
        self.cfg = self._load_config(config_path)
        self.deepsort = self._init_deepsort(use_cuda)
        self.utils = TrackerUtils()

    def _load_config(self, config_path):
        cfg = get_config()
        cfg.merge_from_file(config_path)
        return cfg

    def _init_deepsort(self, use_cuda):
        return DeepSort(
            self.cfg.DEEPSORT.REID_CKPT,
            max_dist=self.cfg.DEEPSORT.MAX_DIST,
            ...
            use_cuda=use_cuda
        )

    def plot_bboxes(self, image, bboxes, line_thickness=None): ...

    def update(self, target_detector, image, count):
        _, bboxes = target_detector.detect(image)
        ...
        outputs = self.deepsort.update(xywhs, confss, clss, image)
        ...
        return total_num, image

    def reset(self):
        self.utils.reset_counters()
        self.utils.data_deque = {}
        self.utils.start_time = time.time()
        self.utils.count_id = []
```

### 2. 删除的冗余代码

```python
# 删除全局变量
palette = (2 ** 11 - 1, 2 ** 15 - 1, 2 ** 20 - 1)
cfg = get_config()
cfg.merge_from_file(...)
deepsort = DeepSort(...)

# 删除独立函数
def plot_bboxes(image, bboxes, line_thickness=None): ...
def update_tracker(target_detector, image, count): ...
```

---

## 三、utils/BaseDetector.py 变更

```python
# ==================== 重构前 ====================
from tracker import update_tracker

class baseDet(object):
    def __init__(self):
        self.img_size = 640
        self.threshold = 0.3
        self.stride = 1

    def build_config(self):
        self.faceTracker = {}
        self.faceClasses = {}
        self.faceLocation1 = {}
        self.faceLocation2 = {}
        self.frameCounter = 0
        self.currentCarID = 0
        self.recorded = []
        self.font = cv2.FONT_HERSHEY_SIMPLEX

    def feedCap(self, im, count):
        retDict = {}
        self.frameCounter += 1
        total, im = update_tracker(self, im, count)
        retDict['frame'] = im
        retDict['car_num'] = int(total)
        return retDict


# ==================== 重构后 ====================
from tracker import DeepSortTracker

class baseDet(object):
    def __init__(self):
        self.img_size = 640
        self.threshold = 0.3
        self.stride = 1
        self.tracker = DeepSortTracker()  # 实例化追踪器

    def build_config(self):
        self.faceTracker = {}
        self.faceClasses = {}
        self.faceLocation1 = {}
        self.faceLocation2 = {}
        self.frameCounter = 0
        self.currentCarID = 0
        self.recorded = []
        self.font = cv2.FONT_HERSHEY_SIMPLEX

    def feedCap(self, im, count):
        retDict = {}
        self.frameCounter += 1
        total, im = self.tracker.update(self, im, count)  # 调用实例方法
        retDict['frame'] = im
        retDict['car_num'] = int(total)
        return retDict
```

---

## 四、ui2.py 变更

### 1. 新增 `ImageUtils` 工具类

```python
# ==================== 重构前 ====================
def cv2ImgAddText(img, text, left, top, textColor=(0, 255, 0), textSize=20):
    if (isinstance(img, np.ndarray)):
        img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img)
    fontText = ImageFont.truetype("./font/platech.ttf", textSize, encoding="utf-8")
    draw.text((left, top), text, textColor, font=fontText)
    return cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR)


# ==================== 重构后 ====================
class ImageUtils:
    @staticmethod
    def cv2ImgAddText(img, text, left, top, textColor=(0, 255, 0), textSize=20):
        if isinstance(img, np.ndarray):
            img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img)
        fontText = ImageFont.truetype("./font/platech.ttf", textSize, encoding="utf-8")
        draw.text((left, top), text, textColor, font=fontText)
        return cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR)
```

### 2. 移除全局变量

```python
# ==================== 重构前 ====================
count = 0
set_cam_id = 0
cam_id_set = 0
set_start_time = 0
set_end_time = 0

class MainWindow(QTabWidget):
    def __init__(self):
        ...
        self.vid_source = cam_id  # 引用全局变量


# ==================== 重构后 ====================
# 全部删除，改为 MainWindow 的实例变量
class MainWindow(QTabWidget):
    def __init__(self, cam_id=0):
        ...
        self.count = 0
        self.set_cam_id = 0
        self.cam_id_set = 0
        self.set_start_time = 0
        self.set_end_time = 0
        self.cam_id = cam_id
        self.vid_source = cam_id  # 使用实例变量
```

### 3. 方法中移除 `global` 声明

```python
# ==================== 重构前 ====================
def select_cam_id(self):
    global set_cam_id          # ← 删除
    ...
    set_cam_id = combobox.currentText()  # 改为 self.set_cam_id

def select_time_range(self):
    global set_start_time, set_end_time  # ← 删除
    ...
    set_start_time = ...       # 改为 self.set_start_time
    set_end_time = ...         # 改为 self.set_end_time

def traffic_volume_query(self):
    global set_cam_id, set_start_time, set_end_time  # ← 删除
    camera_id = int(set_cam_id)       # 改为 self.set_cam_id
    start_time = set_start_time       # 改为 self.set_start_time
    ...

def detect_vid(self):
    global cam_id_set          # ← 删除
    global count               # ← 删除
    camera_id = cam_id_set     # 改为 self.cam_id_set
    count = count + 1          # 改为 self.count = self.count + 1


# ==================== 重构后 ====================
def select_cam_id(self):
    # 无 global 声明
    ...
    self.set_cam_id = combobox.currentText()

def select_time_range(self):
    ...
    self.set_start_time = ...
    self.set_end_time = ...

def traffic_volume_query(self):
    camera_id = int(self.set_cam_id)
    start_time = self.set_start_time
    ...

def detect_vid(self):
    camera_id = self.cam_id_set
    self.count = self.count + 1
```

### 4. 使用 `DatabaseManager` 类

```python
# ==================== 重构前 ====================
def traffic_volume_query(self):
    conn = sqlite3.connect("traffic_data.db")
    cursor = conn.cursor()
    cursor.execute('SELECT traffic_volume, id FROM traffic WHERE ...')
    result = cursor.fetchone()
    ...

def camera_search(self):
    conn = sqlite3.connect('traffic_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM cameras WHERE ...")
    ...

def detect_vid(self):
    conn = sqlite3.connect('traffic_data.db')
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS traffic ...')
    ...


# ==================== 重构后 ====================
# __init__ 中实例化
self.db_manager = DatabaseManager()

def traffic_volume_query(self):
    self.db_manager.connect()
    self.db_manager.create_tables()
    result = self.db_manager.get_traffic_by_time_range(camera_id, start_time, end_time)
    ...

def camera_search(self):
    self.db_manager.connect()
    self.db_manager.create_tables()
    result = self.db_manager.search_camera(int(fileName))
    ...

def detect_vid(self):
    self.db_manager.connect()
    self.db_manager.create_tables()
    ...
    self.db_manager.close()
```

### 5. 优化重复的按钮样式代码

```python
# ==================== 重构前 ====================
cam_id_button.setStyleSheet("QPushButton{color:white}"
                            "QPushButton:hover{background-color: rgb(2,110,180);}"
                            "QPushButton{background-color:rgb(48,124,208)}"
                            "QPushButton{border:2px}"
                            "QPushButton{border-radius:5px}"
                            "QPushButton{padding:5px 5px}"
                            "QPushButton{margin:5px 5px}")

time_button.setStyleSheet("QPushButton{color:white}"
                          "QPushButton:hover{background-color: rgb(2,110,180);}"
                          ... )  # 重复 6 次


# ==================== 重构后 ====================
def _get_button_style(self):
    return (
        "QPushButton{color:white}"
        "QPushButton:hover{background-color: rgb(2,110,180);}"
        "QPushButton{background-color:rgb(48,124,208)}"
        "QPushButton{border:2px}"
        "QPushButton{border-radius:5px}"
        "QPushButton{padding:5px 5px}"
        "QPushButton{margin:5px 5px}"
    )

button_style = self._get_button_style()
cam_id_button.setStyleSheet(button_style)
time_button.setStyleSheet(button_style)
up_img_button.setStyleSheet(button_style)
det_img_button.setStyleSheet(button_style)
```

### 6. 修复停止检测闪屏 + 需要点击两次才停止的问题

```python
# ==================== 重构前（闪屏 + 卡住） ====================
def detect_vid(self):
    ...
    while cap.isOpened():
        ret, img0 = cap.read()
        ...                        # feedCap() 耗时长，期间无法响应停止
        self.vid_img.setPixmap(...)
        if cv2.waitKey(25) & self.stopEvent.is_set() == True:
            self.stopEvent.clear()
            ...
            self.reset_vid()       # 主线程也会调 reset_vid，双重设置导致闪屏
            break

def close_vid(self):
    self.stopEvent.set()
    self.reset_vid()               # 立即重置 UI


# ==================== 重构后（修复闪屏 + 卡住） ====================
def detect_vid(self):
    self._cap = cap                # ← 保存引用，供 close_vid() 释放

    while cap.isOpened():
        if self.stopEvent.is_set():    # ← 循环开始就检查
            break
        ret, img0 = cap.read()
        if not ret:
            break
        if self.stopEvent.is_set():    # ← feedCap 前再检查
            break
        result = self.det.feedCap(...)
        if self.stopEvent.is_set():    # ← feedCap 后再检查
            break
        ...
        self.vid_img.setPixmap(...)
        if cv2.waitKey(25) & self.stopEvent.is_set() == True:
            break

    cap.release()                       # ← 循环结束后释放
    self._cap = None
    self.db_manager.close()
    if not self.stopEvent.is_set():
        self.reset_vid()
    else:
        self.webcam_detection_btn.setEnabled(True)
        self.mp4_detection_btn.setEnabled(True)

def close_vid(self):
    self.stopEvent.set()
    if hasattr(self, '_cap') and self._cap is not None:
        self._cap.release()             # ← 主动释放摄像头，打断 cap.read() 阻塞
        self._cap = None
    self.webcam_detection_btn.setEnabled(True)
    self.mp4_detection_btn.setEnabled(True)
    self.vid_img.setPixmap(QPixmap("images/UI/up.jpeg"))  # ← 恢复初始画面

def open_cam(self):
    self.stopEvent.clear()              # ← 启动前清除停止标志
    ...
    th = threading.Thread(target=self.detect_vid, daemon=True)  # ← daemon 线程
    ...

def open_mp4(self):
    self.stopEvent.clear()              # ← 启动前清除停止标志
    ...
    th = threading.Thread(target=self.detect_vid, daemon=True)  # ← daemon 线程
    ...
```

---

## 五、全局变量消除汇总

| 原全局变量 | 新位置 | 所在文件 |
|-----------|--------|---------|
| `count` | `MainWindow.count` | ui2.py |
| `set_cam_id` | `MainWindow.set_cam_id` | ui2.py |
| `cam_id_set` | `MainWindow.cam_id_set` | ui2.py |
| `set_start_time` | `MainWindow.set_start_time` | ui2.py |
| `set_end_time` | `MainWindow.set_end_time` | ui2.py |
| `palette` | `TrackerUtils.palette` | tools.py |
| `data_deque` | `TrackerUtils.data_deque` | tools.py |
| `object_counter` | `TrackerUtils.object_counter` | tools.py |
| `object_counter1` | `TrackerUtils.object_counter1` | tools.py |
| `start_time` | `TrackerUtils.start_time` | tools.py |
| `reset_duration` | `TrackerUtils.reset_duration` | tools.py |
| `count_id` | `TrackerUtils.count_id` | tools.py |
| `names` | `TrackerUtils.NAMES` | tools.py |
| `class_to_index` | `TrackerUtils.CLASS_TO_INDEX` | tools.py |
| `index_to_class` | `TrackerUtils.INDEX_TO_CLASS` | tools.py |
| `palette` | `DeepSortTracker.palette` | tracker.py |
| `cfg` | `DeepSortTracker.cfg` | tracker.py |
| `deepsort` | `DeepSortTracker.deepsort` | tracker.py |

---

## 六、支持切换 DeepSORT 后端

### 变更内容

**文件**：`tracker.py`

在文件顶部新增配置变量 `DEEPSORT_BACKEND`，支持在两套 DeepSORT 实现之间切换：

```python
# ==================== 重构前 ====================
from deep_sort_pytorch.utils.parser import get_config
from deep_sort_pytorch.deep_sort import DeepSort


# ==================== 重构后 ====================
# ============================================================
# 配置项：选择使用哪个 deep_sort 实现
# 可选值："deep_sort_pytorch" 或 "deep_sort"
# ============================================================
DEEPSORT_BACKEND = "deep_sort_pytorch"
# ============================================================

if DEEPSORT_BACKEND == "deep_sort_pytorch":
    from deep_sort_pytorch.utils.parser import get_config
    from deep_sort_pytorch.deep_sort import DeepSort
else:
    from deep_sort.utils.parser import get_config
    from deep_sort.deep_sort import DeepSort
```

同时 `DeepSortTracker.__init__` 根据 `DEEPSORT_BACKEND` 自动选择对应的配置文件路径：

```python
_CONFIG_PATHS = {
    "deep_sort_pytorch": "deep_sort_pytorch/configs/deep_sort.yaml",
    "deep_sort": "deep_sort/configs/deep_sort.yaml",
}

class DeepSortTracker:
    def __init__(self, config_path=None, use_cuda=True):
        if config_path is None:
            config_path = _CONFIG_PATHS[DEEPSORT_BACKEND]
        ...
```

### 使用方式

修改 `tracker.py` 第 7 行：

```python
# 默认使用 deep_sort_pytorch
DEEPSORT_BACKEND = "deep_sort_pytorch"

# 切换为 deep_sort
DEEPSORT_BACKEND = "deep_sort"
```

---

## 七、修复 deep_sort 的 yaml.load 兼容性问题

### 问题原因

切换到 `deep_sort` 后端时报错：

```
TypeError: load() missing 1 required positional argument: 'Loader'
```

`deep_sort/utils/parser.py` 中的 `yaml.load()` 没有显式指定 `Loader` 参数，新版 PyYAML（≥5.1）要求必须传入 `Loader`。而 `deep_sort_pytorch` 的 parser 已经修复过此问题。

### 修复内容

**文件**：`deep_sort/utils/parser.py` — 两处 `yaml.load()` 调用

```python
# ==================== 修复前 ====================
yaml.load(fo.read())            # ← 缺少 Loader 参数


# ==================== 修复后 ====================
yaml.load(fo.read(), Loader=yaml.FullLoader)   # ← 添加 Loader
```

---

## 八、修复 np.float 兼容性问题

### 问题原因

运行时报错：

```
AttributeError: module 'numpy' has no attribute 'float'.
`np.float` was a deprecated alias for the builtin `float`.
```

NumPy 1.20 废弃了 `np.float`，NumPy 1.24 彻底移除。`deep_sort` 和 `deep_sort_pytorch` 中多处使用了 `np.float`。

### 修复内容

将所有 `np.float` 替换为 `np.float64`：

| 文件 | 行 | 修改 |
|------|-----|------|
| `deep_sort/deep_sort/sort/detection.py` | 8 | `np.asarray(tlwh, dtype=np.float)` → `np.float64` |
| `deep_sort/deep_sort/sort/preprocessing.py` | 40 | `boxes.astype(np.float)` → `np.float64` |
| `deep_sort_pytorch/deep_sort/sort/preprocessing.py` | 40 | `boxes.astype(np.float)` → `np.float64` |
| `deep_sort_pytorch/deep_sort/sort - Copy/preprocessing.py` | 40 | `boxes.astype(np.float)` → `np.float64` |

---

## 九、修复 deep_sort 返回值格式兼容问题

### 问题原因

切换到 `deep_sort` 后端时报错：

```
TypeError: list indices must be integers or slices, not tuple
```

两套 backend 的 `update()` 返回值格式不同：

| 后端 | 返回类型 | 格式 |
|------|---------|------|
| `deep_sort` | list of tuples | `(x1, y1, x2, y2, cls_, track_id)` |
| `deep_sort_pytorch` | numpy array | 列顺序 `(x1, y1, x2, y2, track_id, cls_)` |

`tracker.py` 原来只按 numpy array 方式索引 `outputs[:, :4]`，对 list 不适用。

### 修复内容

**文件**：`tracker.py` — `update()` 方法

```python
# ==================== 修复前 ====================
outputs = self.deepsort.update(xywhs, confss, clss, image)

if len(outputs) > 0:
    bbox_xyxy = outputs[:, :4]          # ← list 不支持切片索引
    identities = outputs[:, -2]
    object_id = outputs[:, -1]


# ==================== 修复后 ====================
outputs = self.deepsort.update(xywhs, confss, clss, image)

if len(outputs) > 0:
    if isinstance(outputs, list):
        # deep_sort: list of (x1,y1,x2,y2,cls,track_id)
        bbox_xyxy = np.array([o[:4] for o in outputs], dtype=np.float64)
        identities = np.array([o[5] for o in outputs], dtype=np.int64)
        object_id = np.array([o[4] for o in outputs], dtype=np.int64)
    else:
        # deep_sort_pytorch: numpy array (x1,y1,x2,y2,track_id,cls)
        bbox_xyxy = outputs[:, :4]
        identities = outputs[:, -2]
        object_id = outputs[:, -1]
```

---

## 十、修复停止检测低概率闪屏

### 问题原因

之前虽然在 `close_vid()` 中恢复了初始画面，但子线程的 `feedCap()`（YOLOv5 + DeepSORT）可能还在处理中，处理完成后又执行了 `self.vid_img.setPixmap()`，**覆盖了主线程设置的初始图片**，导致低概率闪屏。

本质原因：**主线程和子线程同时操作同一个 UI 控件**（`vid_img`），存在竞态条件。

```
时间线：
close_vid()（主线程）          detect_vid()（子线程）
─────────────────────          ──────────────────────
stopEvent.set()
cap.release()
vid_img.setPixmap(初始图片)
                               feedCap() 刚好在执行（无法中断）
                               feedCap() 完成
                               vid_img.setPixmap(检测结果) ← 覆盖了初始图片！
                               检查 stopEvent → 退出
                               vid_img.setPixmap(初始图片) ← 又闪了一下
```

### 修复原则

**UI 操作只在一个线程中执行**，彻底消除竞态条件。

### 修复内容

**文件**：`ui2.py`

```python
# ==================== 修复前 ====================
def close_vid(self):
    self.stopEvent.set()
    if hasattr(self, '_cap') and self._cap is not None:
        self._cap.release()
        self._cap = None
    self.webcam_detection_btn.setEnabled(True)    # ← 主线程操作 UI
    self.mp4_detection_btn.setEnabled(True)       # ← 主线程操作 UI
    self.vid_img.setPixmap(QPixmap("images/UI/up.jpeg"))  # ← 主线程设置图片


# ==================== 修复后 ====================
def close_vid(self):
    # 只设置标志和释放资源，不操作 UI
    self.stopEvent.set()
    if hasattr(self, '_cap') and self._cap is not None:
        self._cap.release()
        self._cap = None


# ==================== 修复前（子线程末尾）====================
if not self.stopEvent.is_set():
    self.reset_vid()
else:
    self.webcam_detection_btn.setEnabled(True)
    self.mp4_detection_btn.setEnabled(True)
    # ← 不在这里重置图片，由 close_vid() 统一处理


# ==================== 修复后（子线程末尾）====================
if not self.stopEvent.is_set():
    self.reset_vid()
else:
    # 所有 UI 恢复统一在子线程中执行，避免与主线程竞争
    self.webcam_detection_btn.setEnabled(True)
    self.mp4_detection_btn.setEnabled(True)
    self.vid_img.setPixmap(QPixmap("images/UI/up.jpeg"))  # ← 子线程设置图片
```

### 完整流程

| 操作 | 执行线程 | stopEvent | UI 操作 |
|------|---------|-----------|---------|
| 启动检测 | 子线程 | `clear()` | 子线程更新画面 |
| 处理帧中 | 子线程 | False | 子线程更新画面 |
| 点击停止 | 主线程 | `set()` + `release()` | **不操作 UI** |
| 子线程退出前 | 子线程 | True | **子线程统一恢复初始图片** |

只有一个线程操作 UI → 不会闪屏。

---

## 十一、优化时间段选择界面

### 变更内容

**文件**：`ui2.py` — `select_time_range()` 方法重写

原来的 `QDateTimeEdit` 手动选择时间比较繁琐，改为带快捷按钮的分组布局：

```python
# ==================== 重构前 ====================
def select_time_range(self):
    dialog = QDialog()
    dialog.setWindowTitle("设置时间段")
    layout = QVBoxLayout()
    start_datetime_edit = QDateTimeEdit()
    end_datetime_edit = QDateTimeEdit()
    start_datetime_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
    end_datetime_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
    layout.addWidget(QLabel("开始时间:"))
    layout.addWidget(start_datetime_edit)
    layout.addWidget(QLabel("截止时间:"))
    layout.addWidget(end_datetime_edit)
    # 确认/取消按钮...


# ==================== 重构后 ====================
def select_time_range(self):
    dialog = QDialog()
    dialog.setWindowTitle("设置时间段")
    dialog.setMinimumWidth(380)
    layout = QVBoxLayout()

    # ===== 快捷时间按钮 =====
    quick_group = QGroupBox("快捷选择")
    quick_layout = QGridLayout()
    quick_presets = [
        ("今天", 0, 0),
        ("昨天", 1, 1),
        ("最近3天", 3, 0),
        ("最近7天", 7, 0),
        ("最近30天", 30, 0),
        ("本月", "month", 0),
    ]
    # 点击按钮自动填充开始和截止时间

    # ===== 自定义时间选择 =====
    custom_group = QGroupBox("自定义时间")
    # 时间选择器支持日历弹窗（setCalendarPopup）
```

新增功能：

| 功能 | 说明 |
|------|------|
| 快捷按钮 | 今天、昨天、最近3天、最近7天、最近30天、本月 |
| 日历弹窗 | 时间选择器点击可弹出日历选择日期 |
| 分组布局 | `QGroupBox` 分组框区分快捷选择和自定义时间 |
| 3×2 网格 | 快捷按钮按网格排列，紧凑美观 |

---

## 十二、修复车流量查询逻辑

### 问题原因

`get_traffic_by_time_range()` 使用**精确匹配**查询：

```python
# 原来的查询（有问题）
WHERE camera_number = ? AND timestamp = ?
```

数据库存储的是每分钟一条记录（如 `10:00, 10:01, 10:02, ...`），但查询只匹配选中的**精确时间点**。比如选了 `10:00 ~ 10:05`，实际只查了 `timestamp = 10:00` 和 `timestamp = 10:05` 这两条，中间的数据全被忽略。

### 修复内容

**文件**：`tools.py` — `DatabaseManager.get_traffic_by_time_range()` 方法

```python
# ==================== 修复前 ====================
def get_traffic_by_time_range(self, camera_id, start_timestamp, end_timestamp):
    # 精确匹配开始时间
    self.cursor.execute('''
        SELECT traffic_volume, id FROM traffic
        WHERE camera_number = ? AND timestamp = ?
    ''', (camera_id, start_timestamp))
    result_start = self.cursor.fetchone()

    # 精确匹配结束时间
    self.cursor.execute('''
        SELECT traffic_volume, id FROM traffic
        WHERE camera_number = ? AND timestamp = ?
    ''', (camera_id, end_timestamp))
    result_end = self.cursor.fetchone()

    if result_start and result_end:
        # 用 id 范围遍历，id 不连续会漏数据
        for i in range(result_start[1], result_end[1] + 1):
            ...
    return None


# ==================== 修复后 ====================
def get_traffic_by_time_range(self, camera_id, start_timestamp, end_timestamp):
    # 直接用范围查询 + SUM 聚合
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
```
