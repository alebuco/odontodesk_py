# OdontoDesk em Python

Versão em **Python** do OdontoDesk: um sistema **web** (Flask). Ele roda num servidor, e computador, celular e tablet usam pelo navegador.

Ele usa o **mesmo banco de dados** (TiDB/MySQL) do OdontoDesk em JavaScript:
- mesmas tabelas;
- mesmos usuários e senhas;
- mesmo controle de versões e mesmo histórico.

Por isso os dois podem ser usados **ao mesmo tempo** durante a transição. O que é gravado aqui aparece no app do computador em poucos segundos, e vice-versa. Se os dois alterarem o mesmo registro ao mesmo tempo, ninguém sobrescreve ninguém: quem gravou por último é avisado e vê os dados atuais.

## O que já funciona (etapas 1 e 2, versão 0.2.0)

| Área | O que tem |
|---|---|
| **Acesso** | Login com os mesmos usuários e senhas do app atual. Bloqueio após 5 tentativas erradas. Troca de senha, que encerra as outras sessões. Permissões por perfil (Administrador, Dentista, Recepção, Auxiliar e os perfis criados no app). Primeiro acesso, para banco vazio. |
| **Painel** | Recebido, pago e saldo do mês. Consultas de hoje. Aniversariantes. Contas vencidas. |
| **Pacientes** | Busca por nome, CPF ou telefone, com ou sem pontuação. Cadastro e edição com validação de CPF, telefone e CEP; nome social; endereço em campos separados. Ficha com as abas Dados, Consultas e Pagamentos. |
| **Agenda** | Visão do dia, com os horários da clínica, e da semana. Filtro por dentista. Marcar, alterar, mudar a situação e excluir consultas. Aviso de choque de horário do mesmo dentista. Bloqueio de horário. |
| **Financeiro** | Fluxo de caixa do mês: recebido, pago, saldo realizado e projetado. Filtros. Lançamentos, inclusive repetidos mês a mês. Baixa. Recibo para imprimir. Exportação em CSV. Comissões e despesas por categoria. **Fechamento do período contábil**, só para o administrador: é o mesmo fechamento do app atual, e o que é fechado num app vale no outro. |
| **Prontuário** (etapa 2) | **Anamnese** com as mesmas perguntas do app (motivo da consulta, sim/não com observação, texto), com impressão. **Evolução clínica**: vinculada à consulta da agenda (que passa a "atendido"), busca e filtro por dentista, correção pelo autor em até 24 h (a versão anterior fica guardada e pode ser vista), depois disso só **adendos**, impressão. **Odontograma e planos de tratamento**: dentição permanente, decídua ou mista; clicar no dente e nas faces; procedimentos com código TUSS; situação planejado/realizado; valores e desconto; orçamento para imprimir ou enviar pelo WhatsApp; **aprovar e gerar cobrança** (entrada + parcelas no financeiro); concluir o plano. **Histórico** do paciente (consultas, procedimentos realizados, evoluções, receitas, documentos, pré-consulta). |
| **Segurança** | Proteção dos formulários (CSRF). Sessão com prazo de 12 horas. Cabeçalhos de segurança. Todas as gravações ficam no histórico (auditoria), com o computador "WEB-PYTHON". |

As outras áreas continuam no app do computador até as próximas etapas (veja o fim deste arquivo).

## Testar no seu computador (Windows ou Linux)

1. Instale o **Python 3.11 ou mais novo**:
   - Windows: [python.org](https://www.python.org/downloads/). Na instalação, marque "Add python.exe to PATH".
   - Linux Mint: já vem instalado.
2. Abra o terminal na pasta `odontodesk-py`. No Windows: Explorador de Arquivos → barra de endereço → digite `cmd` → Enter. Rode:
   ```
   python -m venv venv
   venv\Scripts\activate            (no Linux: source venv/bin/activate)
   pip install -r requirements.txt
   python executar.py --configurar
   ```
3. Responda com os mesmos dados do banco que o app do computador usa (Configurações → Banco de dados):
   - tipo `mysql`;
   - endereço do TiDB;
   - porta `4000`;
   - banco, usuário e senha.

   A configuração fica em `config.json`. Esse arquivo tem a senha do banco: **não envie ao GitHub** (ele já está no `.gitignore`).
4. Abra **http://localhost:8650** e entre com o seu usuário e senha de sempre.

Nas próximas vezes, basta rodar: `venv\Scripts\activate` e depois `python executar.py`.

Para testar sem mexer nos dados reais, use `tipo: sqlite` no `--configurar`. Isso cria um banco de teste num arquivo e, no primeiro acesso, pede para cadastrar a clínica e o administrador.

## Colocar na nuvem (a máquina da Oracle, junto do servidor atual)

Pelo **Cloud Shell** da Oracle, como na instalação do Servidor OdontoDesk:
```
# envie o OdontoDesk-Python.zip para a máquina e entre nela, depois:
unzip -oq OdontoDesk-Python.zip
sudo bash odontodesk-py/nuvem/instalar.sh
```

O instalador faz o seguinte:
- **Banco:** aproveita os dados do banco do servidor atual (`/etc/odontodesk/servidor.json`), sem perguntar de novo.
- **Serviço:** cria o serviço `odontodesk-python`, que inicia sozinho e reinicia se cair.
- **Endereço:** publica o sistema pelo Tailscale, com HTTPS, em `https://odontodesk.taile019b8.ts.net:8443`.

O servidor atual continua funcionando como antes, em `https://odontodesk.taile019b8.ts.net`.

Como no app do celular, só os aparelhos com o **Tailscale ligado** na sua conta chegam ao sistema. Nenhuma porta fica aberta para a internet.

## Como o código está organizado (para manter e alterar)

```
odontodesk-py/
├── executar.py              inicia o sistema (e --configurar)
├── requirements.txt         pacotes: Flask, PyMySQL, waitress
├── odontodesk/
│   ├── app.py               cria a aplicação, versão, erros, segurança
│   ├── web.py               usuário logado, permissões (@exige), CSRF, formatos (dinheiro, datas)
│   ├── seguranca.py         senhas (PBKDF2), perfis e níveis de acesso
│   ├── br.py                CPF, CNPJ, telefone, CEP, endereço
│   ├── tempo.py             data e hora no fuso da clínica
│   ├── dados/
│   │   ├── esquema.py       tabelas e colunas (iguais às do app em JavaScript)
│   │   ├── drivers.py       conexão MySQL/TiDB e SQLite
│   │   └── store.py         ler, gravar (com versão), excluir, histórico
│   ├── rotas/               uma página por área: auth, painel, pacientes, agenda, financeiro, prontuario
│   ├── templates/           o HTML de cada página (Jinja2)
│   └── static/              estilo.css (o visual do app atual) e odonto.js (cliques no odontograma)
├── nuvem/instalar.sh        instalação na máquina virtual
└── testes/                  testes automáticos
```

Receitas para mudanças comuns:
- **Novo campo no paciente:**
  - inclua o campo em `CAMPOS` (rotas/pacientes.py) e no formulário (templates/paciente_form.html);
  - se não estiver em `esquema.py`, ele é guardado na coluna `dados` automaticamente.
- **Nova página:**
  - crie a função em `rotas/<área>.py` com `@bp.route(...)` e `@exige("<módulo>")`;
  - crie o HTML em `templates/`.
- **Gravar algo:** `store().salvar("patients", registro, acao="texto do histórico", usuario=web.nome_usuario())`.
  - Se outra pessoa alterou o registro antes, ele lança `Conflito`. Mostre um aviso e recarregue.

## Testes automáticos

```
python -m unittest discover -s testes -v
```

São 30 testes:
- dados, validações e senhas;
- páginas: login, permissões, pacientes, agenda, financeiro, fechamento de período e prontuário (anamnese, regras da evolução, odontograma, orçamento e parcelas);
- **convivência com o app em JavaScript**: o Python e o `server/store.js` original gravam e leem o mesmo banco, inclusive com conflitos. Esses testes precisam do Node.js e da pasta `odontodesk` ao lado; sem eles, são pulados.

## Próximas etapas

| Etapa | Conteúdo |
|---|---|
| 3 | Procedimentos e preços, Próteses, Estoque (lotes, validades, código de barras), Modelos de documentos, Configurações, Usuários e perfis |
| 4 | Receitas e documentos (impressão e assinatura digital ICP-Brasil A1), galeria e escaneamentos 3D (anexos), pré-consulta, importação do BlueDental, juntar e limpar dados |
| 5 | Agenda Google, backups, mensagens de WhatsApp |

**Diferença importante:** por ser um sistema web, ele precisa de internet para funcionar. O app do computador continua sendo a opção para trabalhar sem conexão.
