# 使用 Python 官方镜像
FROM python:3.13-slim

# 设置工作目录
WORKDIR /app

# 设置时区
ENV TZ=Asia/Shanghai

# 更新时区信息
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 安装 uv
RUN pip install uv

# 复制项目文件到容器
COPY . /app

# 使用 uv 安装依赖
RUN uv sync --frozen

# 设置默认启动命令
CMD ["uv", "run", "python", "main.py"]
