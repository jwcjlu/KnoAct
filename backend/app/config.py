import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./zhixueban.db")
# 生产示例：mysql+pymysql://user:pass@host:3306/zhixueban

# 动画渲染服务（render_service）地址；docker-compose 部署时指向 render 容器
RENDER_SERVICE_URL = os.getenv("KNOACT_RENDER_SERVICE_URL", "http://127.0.0.1:8011").rstrip("/")
