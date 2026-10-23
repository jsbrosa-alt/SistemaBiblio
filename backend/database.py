from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = "postgresql+psycopg://admin:senha_segura_local@localhost:5432/biblioteca_sm"

engine = create_engine(DATABASE_URL, echo=True) 
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

# Função que abre e fecha a conexão automaticamente a cada clique no formulário
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()