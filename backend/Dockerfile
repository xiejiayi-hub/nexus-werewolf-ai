# 使用Python 3.10基础镜像
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 先复制依赖文件，利用Docker缓存
COPY requirements.txt .

# 安装依赖（清华源加速）
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制项目代码
COPY . .

# 暴露端口
EXPOSE 8000

# 启动命令（适配FastAPI）
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port=8000", "--reload"]