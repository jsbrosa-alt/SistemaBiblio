from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any

class ObraCreateSchema(BaseModel):
    tipo_acervo: str = "livro" # livro, periodico, quadrinho
    isbn_issn: Optional[str] = None
    titulo: str = Field(..., min_length=1)
    subtitulo: Optional[str] = None
    autor_sobrenome: str = Field(..., min_length=1, description="Sobrenome ou nome completo")
    autor_nome: Optional[str] = Field(default="", description="Prenome (preenchido sozinho se colar tudo no sobrenome)")
    
    # NOVOS CAMPOS DO FORMULÁRIO PARA CÁLCULO AUTOMÁTICO DO CDD
    categoria_principal: str = Field(
        default="literatura",
        description="Ex: literatura, historia_brasil, historia_rs, psicologia, direito, computacao..."
    )
    genero_literario: Optional[str] = Field(
        default="romance_ficcao",
        description="Usado se categoria for literatura: romance_ficcao, poesia, conto_novela, cronica_ensaio..."
    )
    origem_autor: Optional[str] = Field(
        default="brasileira",
        description="Ex: brasileira, americana, inglesa, francesa, portuguesa..."
    )
    publico_alvo: str = Field(default="adulto", description="adulto ou infantil")

    # Opcionais: Se a bibliotecária deixar em branco, o algoritmo calcula sozinho!
    cdd_manual: Optional[str] = None
    cutter_manual: Optional[str] = None

    editora: Optional[str] = None
    ano_publicacao: Optional[int] = Field(None, ge=1450, le=2026)
    edicao: Optional[str] = "1ª Ed."
    paginas: Optional[int] = Field(None, gt=0)
    idioma: str = "Português"
    capa_url: Optional[str] = None
    colecao: str = "Acervo Geral"
    marc21_extras: Dict[str, Any] = {}
    quantidade_exemplares: int = Field(default=1, ge=1, le=50)

    @field_validator("autor_sobrenome")
    @classmethod
    def normalizar_sobrenome(cls, v: str) -> str:
        return v.strip().upper()