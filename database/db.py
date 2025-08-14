from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from typing import Generator
import pymysql

from database.table import Base

# 数据库配置参数
DB_USER = "root"
DB_PASSWORD = "123456"
DB_HOST = "localhost"
DB_PORT = 3306
DB_NAME = "dense_platform"

def create_database_if_not_exists():
    """
    检查数据库是否存在，如果不存在则自动创建
    这个函数会在应用启动时被调用，确保数据库存在
    """
    try:
        # 首先连接到MySQL服务器（不指定数据库）
        connection = pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            charset='utf8mb4'
        )
        
        with connection.cursor() as cursor:
            # 检查数据库是否存在
            cursor.execute(f"SHOW DATABASES LIKE '{DB_NAME}'")
            result = cursor.fetchone()
            
            if not result:
                # 数据库不存在，创建它
                print(f"数据库 '{DB_NAME}' 不存在，正在创建...")
                cursor.execute(f"CREATE DATABASE {DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
                print(f"数据库 '{DB_NAME}' 创建成功！")
            else:
                print(f"数据库 '{DB_NAME}' 已存在")
        
        connection.close()
        
    except Exception as e:
        print(f"创建数据库时发生错误: {e}")
        raise e

# 在创建引擎之前先确保数据库存在
create_database_if_not_exists()

# Enhanced database engine with connection pooling and performance optimizations
engine = create_engine(
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
    echo=False,  # Disable echo in production for better performance
    poolclass=QueuePool,
    pool_size=20,  # Number of connections to maintain in the pool
    max_overflow=30,  # Additional connections that can be created on demand
    pool_pre_ping=True,  # Validate connections before use
    pool_recycle=3600,  # Recycle connections every hour to prevent timeout
    connect_args={
        "charset": "utf8mb4",
        "autocommit": False,
        "connect_timeout": 60,
        "read_timeout": 30,
        "write_timeout": 30,
    }
)

# 创建数据库会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建数据库表
Base.metadata.create_all(engine)

# FastAPI依赖注入函数：获取数据库会话
def get_db() -> Generator[Session, None, None]:
    """
    获取数据库会话的依赖注入函数
    用于FastAPI路由中的数据库操作
    自动管理会话的创建和关闭
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()