import requests
import telebot
import json
import unicodedata
from datetime import date

TOKEN_TELEGRAM = "8160636089:AAFIRLZu-0Tim7GIfe933FLfUEvpcc9hmjM"
BASE_API = "https://www.jornalminasgerais.mg.gov.br/api/v1"
SITE_URL = "https://www.jornalminasgerais.mg.gov.br/"

bot = telebot.TeleBot(TOKEN_TELEGRAM)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Referer": SITE_URL,
    "Origin": "https://www.jornalminasgerais.mg.gov.br",
}

def remover_acentos(texto):
    if not texto: return ""
    return "".join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    ).upper()

def obter_token():
    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        session.get(SITE_URL, timeout=15)
        resp = session.post(
            f"{BASE_API}/Autenticacao/Autenticar",
            json={},
            timeout=20
        )
        print(f"[AUTH] Status: {resp.status_code} | Body: {resp.text[:200]}")
        data = resp.json()
        token = (
            data.get("dados") or
            data.get("token") or
            data.get("accessToken") or
            data.get("data") or ""
        )
        return session, token
    except Exception as e:
        print(f"[AUTH] Erro: {e}")
        return requests.Session(), None

def pesquisar_no_diario(nome):
    session, token = obter_token()
    nome_busca = remover_acentos(nome)
    hoje = date.today().strftime("%Y-%m-%d")

    params = {
        "DataPublicacaoInicial": "2026-03-01",
        "DataPublicacaoFinal": hoje,
        "TextoPesquisa": nome_busca,
        "DiarioExecutivo": "true",
        "DiarioMunicipios": "true",
        "DiarioTerceiros": "true",
        "EdicaoExtra": "true",
        "Pagina": 1,
        "RegistrosPorPagina": 20,
    }

    req_headers = dict(HEADERS)
    if token:
        req_headers["Authorization"] = f"Bearer {token}"

    try:
        resp = session.get(
            f"{BASE_API}/Pesquisa/PesquisarJornaisPaginados",
            params=params,
            headers=req_headers,
            timeout=30
        )
        print(f"[PESQUISA] Status: {resp.status_code}")
        data = resp.json()
        debug_info = (
            f"Token: {'SIM' if token else 'NAO'}\n"
            f"Status: {resp.status_code}\n"
            f"Chaves: {list(data.keys())}\n"
            f"Corpo: {json.dumps(data, ensure_ascii=False)[:600]}"
        )
        resultados = data.get("dados", [])
        if isinstance(resultados, dict):
            resultados = (
                resultados.get("itens") or
                resultados.get("lista") or
                resultados.get("registros") or
                resultados.get("items") or []
            )
        return resultados, debug_info
    except Exception as e:
        return [], f"Erro: {e}"

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message,
        "Monitor Diario Oficial MG\n\n"
        "Envie um NOME para pesquisar publicacoes desde 01/03/2026.\n\n"
        "/debug NOME  - mostra detalhes da busca")

@bot.message_handler(commands=['debug'])
def debug_busca(message):
    partes = message.text.split(" ", 1)
    if len(partes) < 2:
        bot.reply_to(message, "Use: /debug NOME COMPLETO")
        return
    nome = partes[1].strip()
    bot.send_message(message.chat.id, f"Executando debug para: {nome}")
    resultados, debug_info = pesquisar_no_diario(nome)
    for bloco in [debug_info[i:i+3000] for i in range(0, len(debug_info), 3000)]:
        bot.send_message(message.chat.id, bloco)
    bot.send_message(message.chat.id, f"Resultados: {len(resultados)}")

@bot.message_handler(func=lambda message: True)
def tratar_mensagem(message):
    nome = message.text.strip()
    if len(nome) < 3: return

    aviso = bot.send_message(message.chat.id, f"Buscando {nome}...")

    try:
        resultados, _ = pesquisar_no_diario(nome)

        if not resultados:
            bot.edit_message_text(
                "Nada encontrado de 01/03/2026 ate hoje.\n"
                "Use /debug NOME para detalhes.",
                chat_id=message.chat.id,
                message_id=aviso.message_id)
            return

        bot.delete_message(message.chat.id, aviso.message_id)
        bot.send_message(message.chat.id,
            f"{len(resultados)} resultado(s) encontrado(s):")

        for r in resultados:
            data_pub = (r.get("dataPublicacao") or r.get("data") or "")[:10]
            caderno  = r.get("tipoCaderno") or r.get("caderno") or "Executivo"
            id_jornal = r.get("idJornal") or r.get("id") or ""
            trecho   = r.get("textoResultado") or r.get("texto") or "Ver link"

            texto = (
                f"Data: {data_pub}\n"
                f"Caderno: {caderno}\n"
                f"Trecho: {str(trecho)[:400]}...\n"
            )
            if id_jornal:
                link = (
                    "https://www.jornalminasgerais.mg.gov.br"
                    f"/pagina-jornal/{id_jornal}"
                )
                texto += f"Link: {link}"

            bot.send_message(message.chat.id, texto,
                disable_web_page_preview=True)

    except Exception as e:
        print(f"Erro: {e}")
        bot.send_message(message.chat.id, "Erro na busca.")

if __name__ == "__main__":
    print("Bot iniciado!")
    bot.infinity_polling()
