import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./zhixueban.db")
# 生产示例：mysql+pymysql://user:pass@host:3306/zhixueban
