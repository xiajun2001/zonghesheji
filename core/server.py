# -*- encoding: utf-8 -*-
import json
################################################################################
# curl "127.0.0.1:5000/classapi" -F"top=5" -F"net=inc" -F"lang=cn" -F"file=@tiger.jpg"
################################################################################

import os, uuid
from core import app, network
from flask import Flask, request, render_template, url_for, redirect
from core import network
import mysql.connector
from datetime import datetime
import redis

# 创建 redis 数据库连接
redis_conn = redis.StrictRedis(host='localhost', port=6379, db=0)

# 创建 MySQL 数据库连接
conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="root",
    database="classification"
)
cursor = conn.cursor()

ERROR = '{"tags": [], "result": 1}'
ALLOWED_EXTENSIONS = set(['jpg', 'png', 'bmp'])

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS

@app.route('/classapi', methods=['GET', 'POST'])
def predict():
    if request.method == 'POST':
        top = 5 if request.form['top'] == None else int(request.form['top'])
        net = 'inc' if request.form['net'] == None else request.form['net']
        if request.form['net'] == 'inc':
            thenet = 'InceptionV3'
        else:
            thenet = 'Resnet50'
        file = request.files['file']
        if file and allowed_file(file.filename):
            path = os.path.join(app.config['UPLOAD_FOLDER'], str(uuid.uuid1()))
            file.save(path)
            tags_json = network.predict(path, top, net)
            # 转为字典，提取tagname
            tags_dict = json.loads(tags_json)

            # 将预测结果保存到 mysql 数据库
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # 获取当前时间并格式化为 YYYY-MM-DD
            print(tags_dict["tags"][0]['tag_name'])
            sql = "INSERT INTO tagprediction (path, predictiction, timestamp, model) VALUES (%s, %s, %s, %s)"
            val = (path, tags_dict["tags"][0]['tag_name'], now, thenet)  # 假设预测结果为列表，取第一个结果的置信度
            cursor.execute(sql, val)
            conn.commit()

            # 将预测结果存入 Redis 数据库
            data = {
                "path": path,
                "prediction": tags_dict["tags"][0]['tag_name'],
                "timestamp": now,
                "model": thenet
            }

            # 将数据以 JSON 格式存储在 Redis 中
            redis_key = "tagprediction:{}".format(uuid.uuid1())
            redis_conn.set(redis_key, json.dumps(data))

            # 设置数据过期时间，例如设置为 24 小时
            redis_conn.expire(redis_key, 24 * 60 * 60)

            return tags_json
    return ERROR

@app.route('/', methods=['GET', 'POST'])
def test():
    return render_template('index.html')


@app.route('/data', methods=['GET'])
def get_data():
    # 从 Redis 中获取数据
    redis_data = redis_conn.lrange('tagprediction', 0, -1)

    # 如果 Redis 中的数据条目大于 10，则直接使用 Redis 中的数据
    if len(redis_data) > 10:
        print("redis")
        # 为每个字段设置序号
        numbered_data = []
        for index, data_str in enumerate(redis_data):
            data_dict = json.loads(data_str)
            numbered_row = [index + 1] + [data_dict[key] for key in data_dict]
            numbered_data.append(numbered_row)
    else:
        # 从 MySQL 中获取数据
        print("mysql")
        cursor.execute("SELECT path,predictiction,timestamp,model FROM tagprediction")
        mysql_data = cursor.fetchall()

        # 检查 MySQL 数据是否已经存在于 Redis 中
        for row in mysql_data:
            data_dict = {
                "path": row[0],
                "prediction": row[1],
                "timestamp": row[2].strftime('%Y-%m-%d %H:%M:%S'),
                "model": row[3]
            }
            data_str = json.dumps(data_dict)
            if data_str not in redis_data:
                # 将数据存入 Redis 中
                redis_conn.rpush('tagprediction', data_str)

        # 为每个字段设置序号
        numbered_data = []
        for index, row in enumerate(mysql_data):
            numbered_row = [index + 1] + list(row)
            numbered_data.append(numbered_row)

    # 将数据传递给模板进行渲染
    return render_template('data.html', data=numbered_data)


@app.route('/delete/<path:path>', methods=['GET'])
def delete_data(path):
    # 从 Redis 中删除指定数据项
    path = './' + path.replace('/', '\\')
    escaped_path = path

    redis_data = redis_conn.lrange('tagprediction', 0, -1)
    for data_str in redis_data:
        data_dict = json.loads(data_str)
        # print(data_str)
        if data_dict["path"] == escaped_path:
            redis_conn.lrem('tagprediction', 0, data_str)

    # 从 MySQL 中删除数据
    cursor.execute("DELETE FROM tagprediction WHERE path = %s", (path,))
    conn.commit()

    # 重定向到数据页面
    return redirect(url_for('get_data'))
