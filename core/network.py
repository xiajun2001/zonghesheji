import os
import json
import numpy as np
import torch
from torchvision import models, transforms
from PIL import Image

# 全局的类别索引到类别名称的映射字典
mDict = {}
mKey = []
data_path = 'core/imagenet_cn.txt'
for line in open(data_path, encoding='utf-8'):
    pro = line.strip().split(',')
    key = pro[0]
    mKey.append(key)
    value = ','.join(pro[1:])
    mDict[key] = value

########################################
# 加载预训练模型
torch.hub.set_dir('./model')
res = models.resnet50(pretrained=True)
res.eval()  # 设置模型为推断模式
inc = models.inception_v3(pretrained=True)
inc.eval()
########################################

# 图像预处理函数
def process_img(path):
    transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])
    img = Image.open(path)
    img = transform(img)
    img = img.unsqueeze(0)  # 添加批处理维度
    return img

# 预测函数
def predict(path, top, net):
    # 加载图像并进行预处理
    img = process_img(path)

    # 使用模型进行预测
    if net == 'res':
        outputs = res(img)
        model = res
    elif net == 'inc':
        outputs = inc(img)
        model = inc

    # 处理预测结果
    _, indices = torch.topk(outputs, top)
    probabilities = torch.nn.functional.softmax(outputs, dim=1)[0]  # 获取概率
    probabilities = probabilities.tolist()  # 转换为列表
    indices = indices.tolist()[0]  # 转换为列表

    # 获取类别标签
    labels = []
    for idx in indices:
        labels.append((idx, mDict[mKey[idx]]))

    # 返回结果
    return to_json(labels, probabilities)

# 转换为 JSON 格式的函数
def to_json(lst, probabilities):
    data = {}
    tags = []
    for l in lst:
        idx, name = l
        tags.append({"tag_name": name, "tag_confidence": round(float(probabilities[idx]), 3)})
    data['result'] = 0
    data['tags'] = tags
    return json.dumps(data, ensure_ascii=False)

# # 示例用法
# predict_result = predict('example.jpg', 5, 'res', 'en')
# print(predict_result)
