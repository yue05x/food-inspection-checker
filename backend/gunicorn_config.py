"""
Gunicorn 生产环境配置文件
用于在云服务器上运行 Flask 应用
"""
import multiprocessing

# 绑定地址和端口
# 127.0.0.1 表示只接受本地连接（通过 Nginx 代理）
bind = "127.0.0.1:8000"

# 工作进程数
# 建议设置为 CPU 核心数的 2-4 倍
workers = multiprocessing.cpu_count() * 2 + 1

# 工作模式
worker_class = "sync"

# 每个 worker 的线程数
threads = 2

# 超时时间（秒）
# OCR 处理可能需要较长时间，设置为 5 分钟
timeout = 300

# 最大请求数，达到后重启 worker（防止内存泄漏）
max_requests = 1000
max_requests_jitter = 50

# 日志配置
accesslog = "/var/log/gunicorn/access.log"
errorlog = "/var/log/gunicorn/error.log"
loglevel = "info"

# 进程名称
proc_name = "pdf-extraction"

# 守护进程模式（由 supervisor 管理，设为 False）
daemon = False

# 用户和组
# user = "www-data"
# group = "www-data"

# 预加载应用（提高性能，但调试时可设为 False）
preload_app = True
