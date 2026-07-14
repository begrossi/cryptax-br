# cryptax-br 🇧🇷

Ferramenta open-source e **local-first** para declaração de criptoativos à Receita Federal brasileira.

Seus dados ficam na sua máquina. Nenhuma transação ou chave de API é enviada a terceiros.

---

## O que faz

| Obrigação | O que calcula |
|---|---|
| **DARF mensal** | Ganho líquido por mês, isenção de R$&nbsp;35k (exchanges BR) vs. tributação integral (exchanges estrangeiras), alíquota progressiva, data de vencimento |
| **IRPF anual** | Posição de cada ativo em 31/12 pelo custo médio ponderado (código 89 — Bens e Direitos) |
| **IN RFB 1888/2019** | Meses com volume acima de R$&nbsp;30k em exchanges estrangeiras que exigem auto-declaração |
| **COAF** | Transações individuais acima de R$&nbsp;10k para ciência do limite de comunicação |

**Método de custo:** custo médio ponderado (exigido pela Receita Federal).

---

## Fontes de dados suportadas

**Exchanges — via [CCXT](https://github.com/ccxt/ccxt) (111 exchanges suportadas):**

Qualquer exchange suportada pelo CCXT pode ser conectada. Exemplos:

| Exchange | ID CCXT | Brasileira |
|---|---|---|
| Binance | `binance` | não |
| Foxbit | `foxbit` | ✅ sim |
| Mercado Bitcoin | `mercadobitcoin` | ✅ sim |
| Coinbase | `coinbaseadvanced` | não |
| Kraken | `kraken` | não |
| Bybit | `bybit` | não |
| OKX | `okx` | não |
| KuCoin | `kucoin` | não |

Ao adicionar uma carteira, escolha a exchange em uma lista filtrável com todos os 111 IDs disponíveis.

**On-chain (DeFi):**
- EVM: Ethereum, BSC, Polygon, Arbitrum, Base, Optimism
- Bitcoin (via mempool.space — sem chave de API)
- Solana (via RPC público — apenas SOL nativo; tokens SPL em breve)

**Preços históricos em BRL:** CoinGecko (cache local — nenhuma consulta repetida para a mesma data).

---

## Início rápido

### Opção 1 — Docker Compose (recomendado)

```bash
git clone https://github.com/begrossi/cryptax-br
cd cryptax-br

# Crie o arquivo de configuração
cp backend/.env.example backend/.env
# Edite backend/.env e defina SECRET_KEY com uma string aleatória

docker compose up -d
```

Acesse `http://localhost:3000`.

### Opção 2 — Desenvolvimento local

**Backend:**
```bash
cd backend
cp .env.example .env
uv sync
uv run uvicorn app.main:app --reload --port 8000
# API disponível em http://localhost:8000
# Documentação interativa em http://localhost:8000/docs
```

**Frontend:**
```bash
cd frontend
pnpm install
node_modules/.bin/next dev
# UI disponível em http://localhost:3000
```

### Requisitos

- Docker + Docker Compose, **ou**
- Python 3.12+ com [uv](https://docs.astral.sh/uv/) e Node.js 20+ com pnpm

---

## Configuração

Copie `backend/.env.example` para `backend/.env` e ajuste:

```env
# Obrigatório: string aleatória para criptografar suas chaves de API
SECRET_KEY=mude-para-uma-string-aleatoria-de-32-chars

# Opcional: chave da API CoinGecko para maior limite de requisições
# Sem chave, usa o tier gratuito (pode ser lento para históricos longos)
COINGECKO_API_KEY=

# Banco de dados (SQLite por padrão — zero configuração)
DATABASE_URL=sqlite+aiosqlite:///./cryptax.db
```

### Autenticação (opcional)

Para proteger o acesso à interface web com senha, defina estas variáveis no arquivo `.env` raiz (ao lado do `docker-compose.yml`):

```env
# Segredo para assinar o cookie de sessão (gere com: openssl rand -hex 32)
APP_SECRET=seu-segredo-aqui

# Senha de acesso — deixe vazio para desabilitar a autenticação
APP_PASSWORD=sua-senha-aqui
```

Com `APP_PASSWORD` definido, qualquer acesso não autenticado é redirecionado para `/login`. A sessão dura 30 dias (cookie `HttpOnly` + `SameSite=strict`). Sem a variável, o acesso é aberto.

### Autenticação da API (backend)

O backend (FastAPI) é um processo separado do frontend. Para que ele não fique
aberto a quem alcançar a porta 8000, defina um segredo compartilhado no `.env`
raiz — o proxy do frontend o envia automaticamente em cada requisição:

```env
# Segredo compartilhado entre frontend e backend (gere com: openssl rand -hex 32)
# Backend rejeita qualquer requisição sem ele. Vazio = backend aberto (dev local).
API_TOKEN=seu-token-aqui
```

Com `docker compose`, o backend fica exposto apenas em `127.0.0.1:8000` (o
frontend o acessa pela rede interna). Ao definir `API_TOKEN`, requisições sem o
header `X-API-Token` correto recebem `401`. Se vazio, o backend registra um aviso
no startup e permanece aberto — use apenas em dev local de usuário único.

---

## Como usar

1. **Adicione suas carteiras** em `/wallets`
   - Exchanges: escolha a exchange na lista filtrável, informe API Key + Secret (somente leitura é suficiente). Algumas exchanges (OKX, Coinbase Pro) exigem também uma _passphrase_.
   - On-chain: informe o endereço público (0x…)
   - Marque se a exchange é brasileira — isso afeta o cálculo do limite de isenção do DARF

2. **Sincronize** em `/sync` para importar o histórico de transações

3. **Consulte os relatórios:**
   - `/tax/darf` — DARF devido por mês com cálculo detalhado
   - `/tax/irpf` — Bens e Direitos para preencher a declaração anual
   - `/tax/gains` — Ganhos por ativo com custo médio ponderado passo a passo
   - `/tax/1888` — Meses que exigem auto-declaração (exchanges estrangeiras)
   - `/tax/coaf` — Transações acima do limite COAF

---

## Privacidade e segurança

- **Chaves de API** são criptografadas com AES-256 (Fernet) antes de serem salvas. A chave de criptografia vem do `SECRET_KEY` no seu `.env` — nunca sai da sua máquina.
- **Endereços on-chain** são públicos por natureza. A consulta ao Etherscan (e similares) revela o endereço a esses serviços — o mesmo acontece ao usar qualquer block explorer no browser.
- **Preços históricos** são buscados no CoinGecko e cacheados localmente. A consulta envia apenas o nome do ativo e a data, sem nenhum dado seu.
- **Nenhuma telemetria.** O projeto não faz nenhuma chamada de volta para os desenvolvedores.

---

## Desenvolvimento

```bash
# Testes do motor tributário (sem banco de dados)
cd backend
uv run pytest tests/ -v

# Todos os 13 cenários cobertos:
# - custo médio ponderado
# - DARF: isenção R$35k, exchanges estrangeiras, alíquota 15%
# - IN 1888: threshold R$30k
# - COAF: threshold R$10k
# - data de vencimento do DARF (último dia útil do mês seguinte)
```

### Estrutura do projeto

```
cryptax-br/
  backend/
    app/
      services/tax_engine.py       # Motor tributário (puro Python, sem I/O)
      integrations/exchanges/      # CCXTExchange — qualquer exchange via CCXT
      integrations/onchain/        # EVM (Etherscan-compatible), Solana, Bitcoin
      integrations/prices/         # CoinGecko com cache
      routers/                     # Endpoints FastAPI
      models/                      # SQLAlchemy ORM (SQLite / PostgreSQL)
    tests/
  frontend/
    src/app/                       # Páginas Next.js (App Router)
    src/components/TaxExplainer    # Componente didático de contexto regulatório
    src/lib/api.ts                 # Cliente HTTP tipado
  docker-compose.yml
```

---

## Contribuindo

PRs são bem-vindos. Áreas prioritárias:

- [x] Suporte a Bitcoin (mempool.space)
- [x] Suporte a Solana (RPC público — SOL nativo)
- [ ] Tokens SPL na Solana
- [ ] Exportação de relatório em PDF
- [ ] Importação de CSV de exchanges (fallback offline para exchanges sem API)
- [ ] Suporte a PostgreSQL como banco principal (já preparado no código)
- [ ] Auto-detecção de auto-transferências por correspondência de asset/valor/data entre carteiras

---

## Aviso legal

Esta ferramenta é fornecida para fins informativos e educacionais. Não constitui assessoria tributária ou jurídica. Consulte um contador para situações específicas. Os cálculos são baseados nas regras da Receita Federal vigentes em 2024/2025 (IN RFB 1888/2019, Lei 9.250/1995 art. 21).

---

## Licença

MIT © 2025
