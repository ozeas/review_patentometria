"""Ponto de entrada do aplicativo instalado (console script ``patentometria``).

Fluxo: resolve a pasta de dados do usuário, grava/lena a chave secreta, roda as
migrações e sobe o servidor waitress em 127.0.0.1, abrindo o navegador.
"""
from __future__ import annotations

import argparse
import logging
import os
import socket
import sys
import threading
import webbrowser
from importlib.metadata import PackageNotFoundError, version
from logging.handlers import RotatingFileHandler
from pathlib import Path

try:
    __version__ = version("patentometria")
except PackageNotFoundError:  # rodando do checkout, sem wheel instalado
    __version__ = "0.0.0+dev"

APP = "Patentometria"
VENDOR = "UFES"


def resolver_data_dir(valor: str | None) -> Path:
    """Pasta de dados: --data-dir > PATENTOMETRIA_DATA_DIR > pasta do usuário."""
    if valor:
        p = Path(valor).expanduser()
    elif os.environ.get("PATENTOMETRIA_DATA_DIR"):
        p = Path(os.environ["PATENTOMETRIA_DATA_DIR"]).expanduser()
    else:
        from platformdirs import user_data_dir

        p = Path(user_data_dir(APP, VENDOR))
    p = p.resolve()
    p.mkdir(parents=True, exist_ok=True)
    (p / "media").mkdir(exist_ok=True)
    (p / "logs").mkdir(exist_ok=True)
    return p


def garantir_secret_key(d: Path) -> str:
    """Cria a chave na primeira execução e devolve sempre a mesma."""
    f = d / "secret.key"
    if not f.exists():
        import secrets

        f.write_text(secrets.token_urlsafe(50), encoding="utf-8")
        try:
            f.chmod(0o600)
        except OSError:  # Windows não tem modo POSIX
            pass
    return f.read_text(encoding="utf-8").strip()


def encontrar_porta(host: str, inicio: int, tentativas: int = 10) -> int:
    """Primeira porta livre a partir de ``inicio``."""
    for porta in range(inicio, inicio + tentativas):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if sys.platform != "win32":
                # No Windows SO_REUSEADDR permite "roubar" porta já em uso.
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((host, porta))
            except OSError:
                continue
            return porta
    raise SystemExit(f"sem porta livre entre {inicio} e {inicio + tentativas - 1}")


def preparar_ambiente(d: Path, host: str) -> None:
    """Exporta as variáveis lidas por config.settings antes do django.setup()."""
    os.environ["PATENTOMETRIA_DATA_DIR"] = str(d)
    os.environ["PATENTOMETRIA_SECRET_KEY"] = garantir_secret_key(d)
    os.environ["PATENTOMETRIA_DEBUG"] = "0"
    hosts = {"127.0.0.1", "localhost"} if host in ("127.0.0.1", "localhost") else {host}
    os.environ["PATENTOMETRIA_ALLOWED_HOSTS"] = ",".join(sorted(hosts))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


def configurar_log(d: Path) -> None:
    h = RotatingFileHandler(d / "logs" / "patentometria.log", maxBytes=1_000_000,
                            backupCount=3, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(h)


def django_pronto() -> None:
    import django
    from django.core.management import call_command

    django.setup()
    call_command("migrate", interactive=False, verbosity=0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="patentometria")
    parser.add_argument("--version", action="version", version=f"patentometria {__version__}")
    parser.add_argument("--data-dir", default=None,
                        help="pasta de dados (padrão: pasta do usuário)")
    parser.add_argument("--check", action="store_true",
                        help="atalho para o comando check (usado pelos instaladores)")
    sub = parser.add_subparsers(dest="cmd")
    serve_p = sub.add_parser("serve", help="sobe a aplicação e abre o navegador")
    serve_p.add_argument("--host", default="127.0.0.1")
    serve_p.add_argument("--port", type=int, default=8080)
    serve_p.add_argument("--no-browser", action="store_true")
    sub.add_parser("migrate", help="cria/atualiza o banco e sai")
    sub.add_parser("check", help="migra, valida e sai (instalador e CI)")
    sub.add_parser("where", help="mostra a pasta de dados")
    manage_p = sub.add_parser("manage", help="executa um comando do manage.py")
    manage_p.add_argument("rest", nargs=argparse.REMAINDER)

    args = parser.parse_args(argv)
    if args.check and not args.cmd:
        args.cmd = "check"
    d = resolver_data_dir(args.data_dir)
    host = getattr(args, "host", "127.0.0.1")
    preparar_ambiente(d, host)
    configurar_log(d)

    if args.cmd == "where":
        print(d)
        return 0

    if args.cmd == "manage":
        import django
        from django.core.management import call_command, execute_from_command_line

        django.setup()
        if not (args.rest and args.rest[0] in ("migrate", "makemigrations")):
            call_command("migrate", interactive=False, verbosity=0)
        execute_from_command_line(["manage.py", *args.rest])
        return 0

    django_pronto()

    if args.cmd in ("migrate", "check"):
        if args.cmd == "check":
            from django.core.management import call_command

            call_command("check", verbosity=0)
        print(f"OK: banco migrado em {d}")
        return 0

    from django.core.wsgi import get_wsgi_application
    from waitress import serve

    app = get_wsgi_application()
    porta = encontrar_porta(host, args.port)
    url_host = "127.0.0.1" if host == "0.0.0.0" else host
    url = f"http://{url_host}:{porta}/"
    print(f"Patentometria {__version__} em {url}  (Ctrl+C para encerrar)")
    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        serve(app, host=host, port=porta, threads=8)
    except KeyboardInterrupt:
        print("\nencerrado")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
