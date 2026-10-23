import { useState, useEffect } from "react";
import "./App.css";

const API_URL = "http://localhost:8000/api";

export default function App() {
  const [form, setForm] = useState({
    tipo_acervo: "livro",
    isbn_issn: "",
    titulo: "",
    subtitulo: "",
    autor_sobrenome: "",
    autor_nome: "",
    categoria_principal: "literatura",
    genero_literario: "romance_ficcao",
    origem_autor: "brasileira",
    publico_alvo: "adulto",
    editora: "",
    ano_publicacao: "",
    edicao: "1ª Ed.",
    paginas: "",
    idioma: "Português",
    capa_url: "",
    colecao: "Acervo Geral",
    quantidade_exemplares: 1,
    cdd_manual: "",
    cutter_manual: "",
  });

  const [preview, setPreview] = useState({
    cdd_gerado: "869.3",
    cutter_gerado: "---",
    etiqueta_lombada: "869.3 ---",
  });

  const [buscandoIsbn, setBuscandoIsbn] = useState(false);
  const [resultadoSalvo, setResultadoSalvo] = useState(null);
  const [erro, setErro] = useState(null);

  // Atualiza a pré-visualização da etiqueta em tempo real quando os dados mudam
  useEffect(() => {
    if (!form.titulo.trim() || !form.autor_sobrenome.trim()) return;

    const timer = setTimeout(async () => {
      try {
        const params = new URLSearchParams({
          titulo: form.titulo,
          autor_sobrenome: form.autor_sobrenome,
          tipo_acervo: form.tipo_acervo,
          categoria_principal: form.categoria_principal,
          genero_literario: form.genero_literario,
          origem_autor: form.origem_autor,
          publico_alvo: form.publico_alvo,
        });
        const res = await fetch(`${API_URL}/classificar-preview?${params}`);
        if (res.ok) {
          const data = await res.json();
          setPreview(data);
        }
      } catch {
        // Silencia erro de rede durante digitação
      }
    }, 250);

    return () => clearTimeout(timer);
  }, [
    form.titulo,
    form.autor_sobrenome,
    form.tipo_acervo,
    form.categoria_principal,
    form.genero_literario,
    form.origem_autor,
    form.publico_alvo,
  ]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  // Guardrail Visual: Se digitar "Machado de Assis" no campo de sobrenome, separa sozinho ao sair do campo!
  const handleAutorBlur = () => {
    const texto = form.autor_sobrenome.trim();
    if (!texto || texto.includes(",")) return;

    const partes = texto.split(/\s+/);
    if (partes.length > 1) {
      const sufixos = ["FILHO", "NETO", "SOBRINHO", "JUNIOR", "JR"];
      const ultima = partes[partes.length - 1].toUpperCase().replace(".", "");

      let sobrenome = "";
      let prenome = "";

      if (sufixos.includes(ultima) && partes.length >= 2) {
        sobrenome = `${partes[partes.length - 2].toUpperCase()} ${ultima}`;
        prenome = partes.slice(0, -2).join(" ");
      } else {
        sobrenome = partes[partes.length - 1].toUpperCase();
        prenome = partes.slice(0, -1).join(" ");
      }

      setForm((prev) => ({
        ...prev,
        autor_sobrenome: sobrenome,
        autor_nome: prev.autor_nome ? `${prev.autor_nome} ${prenome}`.trim() : prenome,
      }));
    } else {
      setForm((prev) => ({ ...prev, autor_sobrenome: texto.toUpperCase() }));
    }
  };

  // Busca automática pelo ISBN na API gratuita do Google Books
  const buscarPorIsbn = async () => {
    const isbnLimpo = form.isbn_issn.replace(/[^0-9X]/gi, "");
    if (isbnLimpo.length < 10) return;

    setBuscandoIsbn(true);
    setErro(null);

    try {
      const res = await fetch(`https://www.googleapis.com/books/v1/volumes?q=isbn:${isbnLimpo}`);
      const data = await res.json();

      if (data.totalItems > 0) {
        const info = data.items[0].volumeInfo;
        const autorCompleto = info.authors ? info.authors[0] : "";
        const partesAutor = autorCompleto.trim().split(/\s+/);
        const sobrenome = partesAutor.length > 0 ? partesAutor[partesAutor.length - 1].toUpperCase() : "";
        const prenome = partesAutor.length > 1 ? partesAutor.slice(0, -1).join(" ") : "";

        setForm((prev) => ({
          ...prev,
          isbn_issn: isbnLimpo,
          titulo: info.title || prev.titulo,
          subtitulo: info.subtitle || "",
          autor_sobrenome: sobrenome || prev.autor_sobrenome,
          autor_nome: prenome || prev.autor_nome,
          editora: info.publisher || prev.editora,
          ano_publicacao: info.publishedDate ? info.publishedDate.substring(0, 4) : prev.ano_publicacao,
          paginas: info.pageCount || prev.paginas,
          capa_url: info.imageLinks?.thumbnail || prev.capa_url,
        }));
      } else {
        setErro("ISBN não encontrado nas bases online. Preencha os campos manualmente.");
      }
    } catch {
      setErro("Erro ao consultar a API de ISBN. Verifique sua conexão.");
    } finally {
      setBuscandoIsbn(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErro(null);
    setResultadoSalvo(null);

    const payload = {
      ...form,
      isbn_issn: form.isbn_issn.trim() || null,
      subtitulo: form.subtitulo.trim() || null,
      editora: form.editora.trim() || null,
      ano_publicacao: form.ano_publicacao ? parseInt(form.ano_publicacao, 10) : null,
      paginas: form.paginas ? parseInt(form.paginas, 10) : null,
      quantidade_exemplares: parseInt(form.quantidade_exemplares, 10) || 1,
      cdd_manual: form.cdd_manual.trim() || null,
      cutter_manual: form.cutter_manual.trim() || null,
    };

    try {
      const res = await fetch(`${API_URL}/obras`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || "Erro ao salvar a obra no banco de dados.");
      }

      setResultadoSalvo(data);
    } catch (err) {
      setErro(err.message);
    }
  };

  return (
    <div className="layout-container">
      <header className="top-bar">
        <h1>Biblioteca Pública Municipal de São Marcos</h1>
        <span>Módulo de Catalogação Inteligente (CDD + Cutter)</span>
      </header>

      <main className="main-grid">
        {/* COLUNA ESQUERDA: FORMULÁRIO */}
        <form className="card-form" onSubmit={handleSubmit}>
          <h2>1. Identificação e Busca Rápida (Bipa e Salva)</h2>

          <div className="row">
            <div className="field">
              <label>Tipo de Acervo</label>
              <select name="tipo_acervo" value={form.tipo_acervo} onChange={handleChange}>
                <option value="livro">Livro</option>
                <option value="periodico">Periódico / Revista (Hemeroteca)</option>
                <option value="quadrinho">Quadrinhos / Mangá (Gibiteca)</option>
              </select>
            </div>

            <div className="field flex-2">
              <label>ISBN / ISSN (Use o leitor USB ou digite)</label>
              <div className="input-with-btn">
                <input
                  type="text"
                  name="isbn_issn"
                  placeholder="Ex: 9788535914849"
                  value={form.isbn_issn}
                  onChange={handleChange}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      buscarPorIsbn();
                    }
                  }}
                />
                <button type="button" className="btn-secondary" onClick={buscarPorIsbn} disabled={buscandoIsbn}>
                  {buscandoIsbn ? "Buscando..." : "Buscar ISBN"}
                </button>
              </div>
            </div>
          </div>

          <h2>2. Dados da Obra e Autoria</h2>

          <div className="row">
            <div className="field flex-2">
              <label>Título Principal *</label>
              <input
                type="text"
                name="titulo"
                required
                placeholder="Ex: O Tempo e o Vento"
                value={form.titulo}
                onChange={handleChange}
              />
            </div>

            <div className="field">
              <label>Subtítulo</label>
              <input
                type="text"
                name="subtitulo"
                placeholder="Ex: O Continente"
                value={form.subtitulo}
                onChange={handleChange}
              />
            </div>
          </div>

          <div className="row">
            <div className="field">
              <label>Último Sobrenome do Autor * (Ou cole o nome todo)</label>
              <input
                type="text"
                name="autor_sobrenome"
                required
                placeholder="Ex: VERISSIMO (ou Érico Veríssimo)"
                value={form.autor_sobrenome}
                onChange={handleChange}
                onBlur={handleAutorBlur}
              />
              <small className="hint">Se digitar o nome completo, o sistema separa automaticamente.</small>
            </div>

            <div className="field">
              <label>Nome / Prenome do Autor</label>
              <input
                type="text"
                name="autor_nome"
                placeholder="Ex: Érico"
                value={form.autor_nome}
                onChange={handleChange}
              />
            </div>
          </div>

          <h2>3. Classificação Temática Automática (Motor CDD)</h2>

          <div className="row">
            <div className="field">
              <label>Público-Alvo</label>
              <select name="publico_alvo" value={form.publico_alvo} onChange={handleChange}>
                <option value="adulto">Geral / Adulto</option>
                <option value="infantil">Infantil / Infantojuvenil (CDD 028.5)</option>
              </select>
            </div>

            <div className="field">
              <label>Área / Tema Principal</label>
              <select name="categoria_principal" value={form.categoria_principal} onChange={handleChange}>
                <option value="literatura">Literatura (Romances, Poesia, Contos)</option>
                <option value="historia_rs">História do RS / Região</option>
                <option value="historia_brasil">História do Brasil</option>
                <option value="historia_geral">História Geral</option>
                <option value="biografia">Biografia (920)</option>
                <option value="psicologia">Psicologia (150)</option>
                <option value="autoajuda">Autoajuda (158.1)</option>
                <option value="filosofia">Filosofia (100)</option>
                <option value="religiao">Religião (200)</option>
                <option value="direito">Direito (340)</option>
                <option value="educacao">Educação / Pedagogia (370)</option>
                <option value="computacao">Computação / Informática (004)</option>
                <option value="matematica">Matemática (510)</option>
                <option value="fisica">Física (530)</option>
                <option value="biologia">Biologia / Ciências (570)</option>
                <option value="medicina_saude">Medicina e Saúde (610)</option>
                <option value="artes">Artes e Música (700)</option>
                <option value="quadrinhos_mangas">Histórias em Quadrinhos (741.5)</option>
              </select>
            </div>
          </div>

          {form.categoria_principal === "literatura" && form.publico_alvo !== "infantil" && (
            <div className="row highlight-box">
              <div className="field">
                <label>Nacionalidade / Origem da Literatura</label>
                <select name="origem_autor" value={form.origem_autor} onChange={handleChange}>
                  <option value="brasileira">Brasileira (869)</option>
                  <option value="americana">Norte-Americana (810)</option>
                  <option value="inglesa">Inglesa / Britânica (820)</option>
                  <option value="francesa">Francesa (840)</option>
                  <option value="espanhola">Espanhola / Hispano-Americana (860)</option>
                  <option value="alema">Alemã (830)</option>
                  <option value="italiana">Italiana (850)</option>
                  <option value="portuguesa">Portuguesa (869)</option>
                  <option value="outras">Outras Origens (890)</option>
                </select>
              </div>

              <div className="field">
                <label>Gênero Literário</label>
                <select name="genero_literario" value={form.genero_literario} onChange={handleChange}>
                  <option value="romance_ficcao">Romance / Ficção (.3)</option>
                  <option value="conto_novela">Conto / Novela (.3)</option>
                  <option value="poesia">Poesia (.1)</option>
                  <option value="teatro_drama">Teatro / Drama (.2)</option>
                  <option value="cronica_ensaio">Crônica / Ensaio (.4)</option>
                  <option value="humor_satira">Humor / Sátira (.7)</option>
                </select>
              </div>
            </div>
          )}

          <h2>4. Detalhes Editoriais e Exemplares Físicos</h2>

          <div className="row">
            <div className="field">
              <label>Editora</label>
              <input type="text" name="editora" value={form.editora} onChange={handleChange} />
            </div>
            <div className="field">
              <label>Ano de Publicação</label>
              <input
                type="number"
                name="ano_publicacao"
                min="1450"
                max="2026"
                placeholder="Ex: 2020"
                value={form.ano_publicacao}
                onChange={handleChange}
              />
            </div>
            <div className="field">
              <label>Nº de Páginas</label>
              <input type="number" name="paginas" min="1" value={form.paginas} onChange={handleChange} />
            </div>
            <div className="field">
              <label>Qtd. de Cópias (Exemplares)</label>
              <input
                type="number"
                name="quantidade_exemplares"
                min="1"
                max="50"
                value={form.quantidade_exemplares}
                onChange={handleChange}
              />
            </div>
          </div>

          {erro && <div className="alert-error">{erro}</div>}

          <button type="submit" className="btn-submit">
            Confirmar e Salvar no Acervo
          </button>
        </form>

        {/* COLUNA DIREITA: ETIQUETA EM TEMPO REAL */}
        <aside className="preview-panel">
          <div className="sticky-box">
            <h3>Pré-visualização da Etiqueta</h3>
            <p className="subtitle">Calculada automaticamente pelo algoritmo</p>

            <div className="spine-label">
              <div className="label-header">BIBLIOTECA SÃO MARCOS</div>
              <div className="label-cdd">{form.cdd_manual || preview.cdd_gerado}</div>
              <div className="label-cutter">{form.cutter_manual || preview.cutter_gerado}</div>
              <div className="label-ex">Ex. 1</div>
            </div>

            <div className="meta-summary">
              <p>
                <strong>Entrada ABNT:</strong>{" "}
                {form.autor_sobrenome
                  ? `${form.autor_sobrenome}, ${form.autor_nome}`
                  : "Aguardando preenchimento..."}
              </p>
              <p>
                <strong>Coleção:</strong> {form.colecao}
              </p>
            </div>

            {resultadoSalvo && (
              <div className="alert-success">
                <h4>✅ Salvo no PostgreSQL!</h4>
                <p>
                  <strong>ID da Obra:</strong> #{resultadoSalvo.obra_id}
                </p>
                <p>
                  <strong>Etiqueta:</strong> {resultadoSalvo.etiqueta_chamada}
                </p>
                <p>
                  <strong>Tombos Gerados:</strong> {resultadoSalvo.tombos_gerados.join(", ")}
                </p>
              </div>
            )}
          </div>
        </aside>
      </main>
    </div>
  );
}