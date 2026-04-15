# 使用官方 Python 3.11 的轻量版镜像
FROM python:3.11-slim

LABEL maintainer="JaggerH"

# 设置非交互模式，避免 Docker 构建时的交互问题
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    ffmpeg \
    nodejs \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制应用代码到容器
COPY . /app

# 使用 Aliyun 镜像源加速 pip
RUN pip install -i https://mirrors.aliyun.com/pypi/simple/ -U pip \
    && pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 直接使用Python启动，避免shell脚本问题
CMD ["python3", "start.py"]
