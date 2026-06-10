# ============================================================
# 配置项：选择使用哪个 deep_sort 实现
# 可选值："deep_sort_pytorch" 或 "deep_sort"
# ============================================================
#DEEPSORT_BACKEND = "deep_sort_pytorch"
DEEPSORT_BACKEND = "deep_sort"
# ============================================================

if DEEPSORT_BACKEND == "deep_sort_pytorch":
    from deep_sort_pytorch.utils.parser import get_config
    from deep_sort_pytorch.deep_sort import DeepSort
else:
    from deep_sort.utils.parser import get_config
    from deep_sort.deep_sort import DeepSort

import torch
import cv2
import numpy as np
from tools import TrackerUtils
import time

# 两个 backend 的配置文件路径和 checkpoint 路径
_CONFIG_PATHS = {
    "deep_sort_pytorch": "deep_sort_pytorch/configs/deep_sort.yaml",
    "deep_sort": "deep_sort/configs/deep_sort.yaml",
}


class DeepSortTracker:
    """DeepSort 追踪器管理类"""

    def __init__(self, config_path=None, use_cuda=True):
        """
        初始化 DeepSort 追踪器

        Args:
            config_path: 配置文件路径，None 则根据 DEEPSORT_BACKEND 自动选择
            use_cuda: 是否使用 CUDA
        """
        self.palette = (2 ** 11 - 1, 2 ** 15 - 1, 2 ** 20 - 1)
        if config_path is None:
            config_path = _CONFIG_PATHS[DEEPSORT_BACKEND]
        self.cfg = self._load_config(config_path)
        self.deepsort = self._init_deepsort(use_cuda)
        self.utils = TrackerUtils()

    def _load_config(self, config_path):
        """加载配置"""
        cfg = get_config()
        cfg.merge_from_file(config_path)
        return cfg

    def _init_deepsort(self, use_cuda):
        """初始化 DeepSort"""
        return DeepSort(
            self.cfg.DEEPSORT.REID_CKPT,
            max_dist=self.cfg.DEEPSORT.MAX_DIST,
            min_confidence=self.cfg.DEEPSORT.MIN_CONFIDENCE,
            nms_max_overlap=self.cfg.DEEPSORT.NMS_MAX_OVERLAP,
            max_iou_distance=self.cfg.DEEPSORT.MAX_IOU_DISTANCE,
            max_age=self.cfg.DEEPSORT.MAX_AGE,
            n_init=self.cfg.DEEPSORT.N_INIT,
            nn_budget=self.cfg.DEEPSORT.NN_BUDGET,
            use_cuda=use_cuda
        )

    def plot_bboxes(self, image, bboxes, line_thickness=None):
        """
        绘制边界框

        Args:
            image: 输入图像
            bboxes: 边界框列表 [(x1, y1, x2, y2, cls_id, pos_id), ...]
            line_thickness: 线条厚度

        Returns:
            绘制后的图像
        """
        tl = line_thickness or round(
            0.002 * (image.shape[0] + image.shape[1]) / 2) + 1
        for (x1, y1, x2, y2, cls_id, pos_id) in bboxes:
            if cls_id in ['person']:
                color = (0, 0, 255)
            else:
                color = (0, 255, 0)
            c1, c2 = (x1, y1), (x2, y2)
            cv2.rectangle(image, c1, c2, color, thickness=tl, lineType=cv2.LINE_AA)
            tf = max(tl - 1, 1)
            cls_id = self.utils.get_class_name(cls_id)
            t_size = cv2.getTextSize(cls_id, 0, fontScale=tl / 3, thickness=tf)[0]
            c2 = c1[0] + t_size[0], c1[1] - t_size[1] - 3
            cv2.rectangle(image, c1, c2, color, -1, cv2.LINE_AA)
            cv2.putText(
                image, '{} ID-{}'.format(cls_id, pos_id), (c1[0], c1[1] - 2), 0, tl / 3,
                [225, 255, 255], thickness=tf, lineType=cv2.LINE_AA
            )

        return image

    def update(self, target_detector, image, count):
        """
        更新追踪器

        Args:
            target_detector: 目标检测器
            image: 输入图像
            count: 计数器

        Returns:
            total_num: 总数
            image: 处理后的图像
        """
        _, bboxes = target_detector.detect(image)

        bbox_xywh = []
        confs = []
        clss = []

        for x1, y1, x2, y2, cls_id, conf in bboxes:
            obj = [int((x1 + x2) / 2), int((y1 + y2) / 2), x2 - x1, y2 - y1]
            bbox_xywh.append(obj)
            confs.append(conf)
            clss.append(int(self.utils.get_class_index(cls_id)))

        xywhs = torch.Tensor(bbox_xywh)
        confss = torch.Tensor(confs)

        outputs = self.deepsort.update(xywhs, confss, clss, image)

        total_num = 0
        if len(outputs) > 0:
            # deep_sort 返回 list of tuples: (x1,y1,x2,y2,cls,track_id)
            # deep_sort_pytorch 返回 numpy array: columns (x1,y1,x2,y2,track_id,cls)
            if isinstance(outputs, list):
                bbox_xyxy = np.array([o[:4] for o in outputs], dtype=np.float64)
                identities = np.array([o[5] for o in outputs], dtype=np.int64)
                object_id = np.array([o[4] for o in outputs], dtype=np.int64)
            else:
                bbox_xyxy = outputs[:, :4]
                identities = outputs[:, -2]
                object_id = outputs[:, -1]
            total_num, image = self.utils.draw_boxes(count, image, bbox_xyxy, self.utils.NAMES, object_id, identities)

        return total_num, image

    def reset(self):
        """重置追踪器状态"""
        self.utils.reset_counters()
        self.utils.data_deque = {}
        self.utils.start_time = time.time()
        self.utils.count_id = []
