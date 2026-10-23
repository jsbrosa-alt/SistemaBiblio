from sqlalchemy import String, Integer, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional, List
from database import Base

class Obra(Base):
    __tablename__ = "obras"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    tipo_acervo: Mapped[str] = mapped_column(String(20), default="livro") # livro, periodico, quadrinho
    isbn_issn: Mapped[Optional[str]] = mapped_column(String(20), unique=True, index=True)
    
    titulo: Mapped[str] = mapped_column(String(255), index=True)
    subtitulo: Mapped[Optional[str]] = mapped_column(String(255))
    autor_sobrenome: Mapped[str] = mapped_column(String(100), index=True)
    autor_nome: Mapped[str] = mapped_column(String(150))
    
    editora: Mapped[Optional[str]] = mapped_column(String(120))
    ano_publicacao: Mapped[Optional[int]] = mapped_column(Integer)
    edicao: Mapped[Optional[str]] = mapped_column(String(30))
    paginas: Mapped[Optional[int]] = mapped_column(Integer)
    idioma: Mapped[str] = mapped_column(String(30), default="Português")
    capa_url: Mapped[Optional[str]] = mapped_column(String(500))

    # Códigos de Biblioteconomia e Localização
    cdd: Mapped[str] = mapped_column(String(20), index=True)     # Ex: "869.3"
    cutter: Mapped[str] = mapped_column(String(20), index=True)  # Ex: "A848d"
    colecao: Mapped[str] = mapped_column(String(50), default="Acervo Geral")

    # Flexibilidade MARC 21 (Tradutor, notas, volume de revista, etc.)
    marc21_extras: Mapped[dict] = mapped_column(JSONB, default=dict)
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relação 1:N -> Uma Obra pode ter vários Exemplares físicos na estante
    exemplares: Mapped[List["Exemplar"]] = relationship(back_populates="obra", cascade="all, delete-orphan")


class Exemplar(Base):
    __tablename__ = "exemplares"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    obra_id: Mapped[int] = mapped_column(ForeignKey("obras.id"))
    
    codigo_tombo: Mapped[str] = mapped_column(String(50), unique=True, index=True) # Ex: "SM-00001"
    numero_exemplar: Mapped[int] = mapped_column(Integer, default=1)               # Ex. 1, Ex. 2...
    status: Mapped[str] = mapped_column(String(20), default="DISPONIVEL")          # DISPONIVEL, EMPRESTADO, MANUTENCAO

    obra: Mapped["Obra"] = relationship(back_populates="exemplares")

class CatalogoIsbnLocal(Base):
    """Base de consulta offline com milhares de ISBNs pré-carregados"""
    __tablename__ = "catalogo_isbn_local"

    isbn: Mapped[str] = mapped_column(String(20), primary_key=True, index=True)
    titulo: Mapped[str] = mapped_column(String(255))
    subtitulo: Mapped[Optional[str]] = mapped_column(String(255))
    autor_completo: Mapped[str] = mapped_column(String(255))
    editora: Mapped[Optional[str]] = mapped_column(String(120))
    ano: Mapped[Optional[int]] = mapped_column(Integer)
    paginas: Mapped[Optional[int]] = mapped_column(Integer)