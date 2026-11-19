# Janela de Coleta

MVP do projeto de extensão. O estabelecimento publica uma janela de coleta (material, volume, dia e hora). O coletador confirma. A primeira confirmação válida reserva o horário, e as duas partes veem o mesmo acordo. Não há pagamento.

O mapa mostra só estabelecimentos, em Brasília e entorno. Telefone do coletador não aparece para ninguém.

## Contas

- Estabelecimento: `informal@example.com` — senha `demo1234` — Informal, Águas Claras
- Coletador: `lucas.gurgel@a.ucb.br` — senha `janela2026` — Lucas Gabriel de Oliveira Gurgel, pessoa física

O telefone do coletador fica no cadastro e não aparece nas telas. O start grava a coleta do piloto: publicada em 07/11/2026 às 16:00, confirmada por Lucas às 18:40, realizada em 08/11/2026 às 10:00.

## Subir na sua máquina

Com Docker:

```bash
docker compose up --build
```

Sem Docker, o projeto usa SQLite:

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
DEBUG=1 .venv/bin/python manage.py migrate
DEBUG=1 .venv/bin/python manage.py seed_demo
DEBUG=1 .venv/bin/python manage.py runserver
```

Abra `http://localhost:8000`.

## Railway

1. Crie um projeto e suba esta pasta (GitHub ou `railway up`). O deploy usa o `Dockerfile`.
2. Adicione um Postgres e ligue `DATABASE_URL` ao serviço web (`${{Postgres.DATABASE_URL}}`).
3. Variáveis do serviço web:
   - `SECRET_KEY`: uma chave longa, diferente da de desenvolvimento
   - `DEBUG`: `0`
   - `ALLOWED_HOSTS`: o domínio público, se não for o domínio padrão do Railway
   - `CSRF_TRUSTED_ORIGINS`: `https://seu-dominio` (com https)
4. O domínio `RAILWAY_PUBLIC_DOMAIN` já entra sozinho em hosts e CSRF.
5. Abra a URL. O start roda as migrações e a conta de demonstração.

O mapa usa OpenStreetMap. Não há chave de API para configurar.

## Produção

https://web-production-f5aa9bc5.up.railway.app

O branch `main` publica nesse endereço. O banco é Postgres no Railway. As contas são as desta página.

O bastidor em `/admin/` pede um superusuário: `python manage.py createsuperuser`.
