# ETF网格交易系统 Docker镜像
FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制项目文件
COPY project/requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY project/ .

# 创建必要的目录
RUN mkdir -p logs data

# 环境变量
ENV PYTHONUNBUFFERED=1
ENV JQCLOUD_USERNAME=""
ENV JQCLOUD_PASSWORD=""

# 暴露端口
EXPOSE 5000

# 默认命令：运行Web监控面板
CMD ["python", "web/app.py"]
