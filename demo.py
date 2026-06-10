from AIDetector_pytorch import Detector
from tools import *
import imutils
import time
import cv2
import sqlite3
import datetime

def main():
    # 连接数据库（如果不存在，则会自动创建一个）
    conn = sqlite3.connect('traffic_data.db')

    # 创建游标
    cursor = conn.cursor()

    # 创建表（如果不存在的话）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS traffic (
            id INTEGER PRIMARY KEY,
            timestamp DATETIME,
            traffic_volume INTEGER,
            camera_number INTEGER
        )
    ''')


    # 创建表
    cursor.execute('''CREATE TABLE IF NOT EXISTS B
                      (camera_number INTEGER, 
                      location TEXT)''')
    name = 'demo'
    det = Detector()
    cap = cv2.VideoCapture("./video/test3.mp4")
    fps = int(cap.get(5))
    print('fps:', fps)
    t = int(1000/fps)

    videoWriter = None

    start_time = time.time()  # 记录开始时间

    while True:

        # try:
        _, im = cap.read()
        if im is None:
            break
        
        result = det.feedCap(im)
        # print(result["faces"])
        # print(result["face_bboxes"])
        result_img = result['frame']
        result_car_num = result['car_num']

        current_time = datetime.datetime.now().replace(second=0, microsecond=0).strftime('%Y-%m-%d %H:%M')
        insert_traffic_data(cursor,conn,current_time, result_car_num,0)
        # #result = imutils.resize(result, height=500)
        if videoWriter is None:
            fourcc = cv2.VideoWriter_fourcc('m', 'p', '4', 'v')  # opencv3.0
            videoWriter = cv2.VideoWriter('result.mp4', fourcc, fps, (result_img.shape[1], result_img.shape[0]))

        videoWriter.write(result_img)
        cv2.imshow(name, result_img)
        cv2.waitKey(t)

        if cv2.getWindowProperty(name, cv2.WND_PROP_AUTOSIZE) < 1:
            # 点x退出
            break
        # except Exception as e:
        #     print(e)
        #     break
    end_time = time.time()  # 记录结束时间
    duration = end_time - start_time  # 计算视频持续时间（秒）
    print(f"总时间是 {duration} s")
    cap.release()
    videoWriter.release()
    cv2.destroyAllWindows()

if __name__ == '__main__':
    
    main()