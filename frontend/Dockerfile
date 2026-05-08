# 使用Node.js 18基础镜像
FROM node:18-alpine

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY package.json package-lock.json ./

# 安装依赖
RUN npm install

# 复制项目代码
COPY . .

# 暴露端口
EXPOSE 3000

# 启动开发服务（适配Vite）
CMD ["npm", "run", "dev", "--", "--host"]