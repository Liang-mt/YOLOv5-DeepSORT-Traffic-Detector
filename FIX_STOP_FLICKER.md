# 修复：点击停止检测后画面闪屏 / 需要点击两次才停止

## 问题现象

- **闪屏**：点击停止检测后，画面闪一下（先变白再变回检测画面，或反之）
- **卡住**：点击停止后画面不动了，但按钮没有恢复，需要再点一次停止才正常

## 问题原因

### 闪屏原因

`close_vid()` 和 `detect_vid()` 之间存在**竞态条件**：

```
close_vid()（主线程）          detect_vid()（子线程）
─────────────────────          ──────────────────────
stopEvent.set()
reset_vid()
  → vid_img.setPixmap(白屏)
                               还在 feedCap() 处理中...
                               处理完成
                               → vid_img.setPixmap(检测结果)  ← 又闪了一下
                               才检查到 stopEvent，退出循环
```

`reset_vid()` 在主线程立即重置了 UI，但子线程还没退出，还会再更新一次 UI，导致闪烁。

### 卡住原因

`feedCap()`（YOLOv5 检测 + DeepSORT 跟踪）耗时较长（几十到上百毫秒），子线程卡在里面时无法检查 `stopEvent`。同时 `cap.read()` 对摄像头也可能阻塞。只有执行到 `cv2.waitKey(25)` 时才能响应停止信号，导致响应延迟。

## 修复内容

### 修改 1：close_vid() 只负责停止标志和资源释放

**文件**：`ui2.py` — `close_vid()` 方法

```python
# ==================== 修复前 ====================
def close_vid(self):
    self.stopEvent.set()
    self.reset_vid()             # ← 与子线程的 reset_vid() 冲突，导致闪屏


# ==================== 修复后 ====================
def close_vid(self):
    # 只设置标志和释放资源，不操作 UI
    self.stopEvent.set()
    if hasattr(self, '_cap') and self._cap is not None:
        self._cap.release()      # ← 主动释放摄像头，打断 cap.read() 阻塞
        self._cap = None
```

**作用**：
- `cap.release()` 让子线程的 `cap.read()` 立即失败，子线程快速退出
- 不操作 UI，由子线程统一处理，避免两个线程同时操作 UI 导致闪屏

### 修改 2：detect_vid() 保存 cap 引用 + 增加检查点

**文件**：`ui2.py` — `detect_vid()` 方法

```python
# ==================== 修复前 ====================
while cap.isOpened():
    if self.stopEvent.is_set():    # 只在循环开始检查一次
        break
    ret, img0 = cap.read()
    if not ret:
        break
    result = self.det.feedCap(...)  # ← 耗时操作，期间无法响应停止
    ...处理帧...
    self.vid_img.setPixmap(...)
    if cv2.waitKey(25) & self.stopEvent.is_set() == True:
        break


# ==================== 修复后 ====================
self._cap = cap                    # ← 保存引用，供 close_vid() 释放

while cap.isOpened():
    if self.stopEvent.is_set():
        break
    ret, img0 = cap.read()
    if not ret:
        break
    if self.stopEvent.is_set():    # ← feedCap 前再检查一次
        break
    result = self.det.feedCap(...)
    if self.stopEvent.is_set():    # ← feedCap 后再检查一次
        break
    ...处理帧...
    self.vid_img.setPixmap(...)
    if cv2.waitKey(25) & self.stopEvent.is_set() == True:
        break

cap.release()                      # ← 循环结束后释放资源
self._cap = None
```

**作用**：在 `feedCap()` 前后各加一次检查，确保子线程在耗时操作的间隙也能响应停止信号。

### 修改 3：线程设为 daemon

**文件**：`ui2.py` — `open_cam()` 和 `open_mp4()` 方法

```python
# ==================== 修复前 ====================
th = threading.Thread(target=self.detect_vid)
th.start()


# ==================== 修复后 ====================
th = threading.Thread(target=self.detect_vid, daemon=True)
th.start()
```

**作用**：daemon 线程在主线程退出时自动结束，避免程序关闭时线程残留。

### 修改 4：区分主动停止和自然结束，子线程统一恢复 UI

**文件**：`ui2.py` — `detect_vid()` 方法末尾

```python
# ==================== 修复前 ====================
    self.db_manager.close()
    self.reset_vid()             # ← 不管什么原因结束都重置，与 close_vid() 冲突


# ==================== 修复后 ====================
    cap.release()
    self._cap = None
    self.db_manager.close()

    if not self.stopEvent.is_set():
        self.reset_vid()         # 自然结束（视频播完）时才重置
    else:
        # 所有 UI 恢复统一在子线程中执行，避免与主线程竞争导致闪屏
        self.webcam_detection_btn.setEnabled(True)
        self.mp4_detection_btn.setEnabled(True)
        self.vid_img.setPixmap(QPixmap("images/UI/up.jpeg"))
```

## 完整流程

| 操作 | 执行线程 | stopEvent | _cap 状态 | UI 操作 |
|------|---------|-----------|----------|---------|
| 启动检测 | 子线程 | `clear()` → False | 新建 Capture | 子线程更新画面 |
| 处理帧中 | 子线程 | False | 打开 | 子线程更新画面 |
| 点击停止 | 主线程 | `set()` → True | **`release()` 释放** | **不操作 UI** |
| 子线程退出前 | 子线程 | True | 已释放 | **子线程统一恢复初始图片** |
| 再次启动 | 子线程 | `clear()` → False | 新建 Capture | 子线程更新画面 |

**核心原则：UI 操作只在一个线程中执行，不会闪屏。**

## 核心思路

1. **单线程 UI**：`close_vid()` 只设置标志和释放资源，所有 UI 恢复统一由子线程执行，彻底消除竞态条件
2. **主动释放资源**：`close_vid()` 中调用 `cap.release()`，让子线程的 `cap.read()` 立即失败，不再卡住
3. **多点检查**：在循环开始、`feedCap()` 前后都检查 `stopEvent`，缩短响应延迟
4. **daemon 线程**：防止程序关闭时线程残留
