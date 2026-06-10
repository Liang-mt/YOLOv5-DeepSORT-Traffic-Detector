import sqlite3

# 连接到数据库（如果不存在则会创建）
conn = sqlite3.connect('traffic_data.db')

# 创建一个游标对象来执行SQL语句
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

# 查询表中的所有信息
cursor.execute("SELECT id, timestamp, traffic_volume, camera_number FROM traffic")
rows = cursor.fetchall()

# 打印查询结果
for row in rows:
    print("序号:", row[0], "\t时间:", row[1], "\t车流量:", row[2], "\t摄像头ID:", row[3])

# 关闭游标和连接
cursor.close()
conn.close()