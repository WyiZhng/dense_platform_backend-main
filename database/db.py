from sqlalchemy import create_engine

engine = create_engine(
    "mysql+pymysql://server:yqqlm2004@localhost:3306/dense_platform",
    echo=True
)

