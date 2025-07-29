from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

from database.table import Base

# Enhanced database engine with connection pooling and performance optimizations
engine = create_engine(
    "mysql+pymysql://root:123456@localhost:3306/dense_platform",
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

Base.metadata.create_all(engine)