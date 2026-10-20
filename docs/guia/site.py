"""Gera o site estático do guia (GitHub Pages) a partir do PDF e do sumário do LaTeX."""
from __future__ import annotations

import argparse
import html
import re
import shutil
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
TOC = RAIZ / "guia.toc"
TITULO = "Patentometria — guia passo a passo"
LIMPEZAS = [
    (re.compile(r"\\numberline\s*\{[^{}]*\}"), ""),
    (re.compile(r"\\[a-zA-Z@]+\*?(\[[^\]]*\])?"), ""),
    (re.compile(r"[{}]"), ""),
]


def limpar(texto: str) -> str:
    for padrao, sub in LIMPEZAS:
        texto = padrao.sub(sub, texto)
    return re.sub(r"\s+", " ", texto).strip()


def secoes() -> list[tuple[str, int]]:
    if not TOC.exists():
        return []
    itens = []
    for linha in TOC.read_text(encoding="utf-8").splitlines():
        m = re.search(r"\\contentsline \{section\}\{(.*)\}\{(\d+)\}", linha)
        if m:
            itens.append((limpar(m.group(1)), int(m.group(2))))
    return itens


def gerar(destino: Path) -> None:
    destino.mkdir(parents=True, exist_ok=True)
    shutil.copy2(RAIZ / "guia.pdf", destino / "guia.pdf")
    shutil.copy2(RAIZ / "site" / "style.css", destino / "style.css")
    if (RAIZ / "img").is_dir():
        shutil.copytree(RAIZ / "img", destino / "img", dirs_exist_ok=True)

    itens = "\n".join(
        f'<li><a href="guia.pdf#page={pagina}">{html.escape(titulo)}</a>'
        f'<span class="pag">p. {pagina}</span></li>'
        for titulo, pagina in secoes()
    )
    pagina = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{TITULO}</title>
<link rel="stylesheet" href="style.css"></head>
<body>
<header>
  <p class="sobre">Patentometria</p>
  <h1>{TITULO}</h1>
  <p class="sub">Uso e interpretação das funcionalidades, com capturas de tela e explicação de cada bloco.</p>
  <p><a class="botao" href="guia.pdf">Baixar o PDF</a>
     <a class="botao secundario" href="https://pypi.org/project/patentometria/">Instalar pelo PyPI</a></p>
</header>
<main>
  <section><h2>Sumário</h2><ol class="toc">{itens}</ol></section>
  <section><h2>Ler aqui</h2>
    <object data="guia.pdf" type="application/pdf" width="100%" height="900">
      <p>Seu navegador não exibe PDF embutido. <a href="guia.pdf">Abra o guia</a>.</p>
    </object>
  </section>
</main>
<footer>Guia gerado a partir de <code>docs/guia/guia.tex</code>. Publicado com GitHub Pages.</footer>
</body></html>
"""
    (destino / "index.html").write_text(pagina, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="_site")
    gerar(Path(parser.parse_args().out))


if __name__ == "__main__":
    main()
