from sqlalchemy.orm import sessionmaker

from database.api import get_reports, uploadImage
from database.db import engine
from utils import resolveAccountJwt,makeAccountJwt

Session = sessionmaker(bind=engine)
session = Session()
print(uploadImage(session,"a.jpg",b'114514'))