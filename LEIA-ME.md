# OdontoDesk em Python

Versão em **Python** do OdontoDesk: um sistema **web** (Flask). Ele roda num servidor, e computador, celular e tablet usam pelo navegador.

Ele usa o **mesmo banco de dados** (TiDB/MySQL) do OdontoDesk em JavaScript:
- mesmas tabelas;
- mesmos usuários e senhas;
- mesmo controle de versões e mesmo histórico.

Por isso os dois podem ser usados **ao mesmo tempo** durante a transição. O que é gravado aqui aparece no app do computador em poucos segundos, e vice-versa. Se os dois alterarem o mesmo registro ao mesmo tempo, ninguém sobrescreve ninguém: quem gravou por último é avisado e vê os dados atuais.

## O que já funciona (etapas 1 a 4a, versão 0.4.0)

| Área | O que tem |
|---|---|
| **Acesso** | Login com os mesmos usuários e senhas do app atual. Bloqueio após 5 tentativas erradas. Troca de senha, que encerra as outras sessões. Permissões por perfil (Administrador, Dentista, Recepção, Auxiliar e os perfis criados no app). Primeiro acesso, para banco vazio. |
| **Painel** | Recebido, pago e saldo do mês. Consultas de hoje. Aniversariantes. Contas vencidas. |
| **Pacientes** | Busca por nome, CPF ou telefone, com ou sem pontuação. Cadastro e edição com validação de CPF, telefone e CEP; nome social; endereço em campos separados. Ficha com as abas Dados, Consultas e Pagamentos. |
| **Agenda** | Visão do dia, com os horários da clínica, e da semana. Filtro por dentista. Marcar, alterar, mudar a situação e excluir consultas. Aviso de choque de horário do mesmo dentista. Bloqueio de horário. |
| **Financeiro** | Fluxo de caixa do mês: recebido, pago, saldo realizado e projetado. Filtros. Lançamentos, inclusive repetidos mês a mês. Baixa. Recibo para imprimir. Exportação em CSV. Comissões e despesas por categoria. **Fechamento do período contábil**, só para o administrador: é o mesmo fechamento do app atual, e o que é fechado num app vale no outro. |
| **Prontuário** (etapa 2) | **Anamnese** com as mesmas perguntas do app (motivo da consulta, sim/não com observação, texto), com impressão. **Evolução clínica**: vinculada à consulta da agenda (que passa a "atendido"), busca e filtro por dentista, correção pelo autor em até 24 h (a versão anterior fica guardada e pode ser vista), depois disso só **adendos**, impressão. **Odontograma e planos de tratamento**: dentição permanente, decídua ou mista; clicar no dente e nas faces; procedimentos com código TUSS; situação planejado/realizado; valores e desconto; orçamento para imprimir ou enviar pelo WhatsApp; **aprovar e gerar cobrança** (entrada + parcelas no financeiro); concluir o plano. **Histórico** do paciente (consultas, procedimentos realizados, evoluções, receitas, documentos, pré-consulta). |
| **Procedimentos** (etapa 3) | Tabela por categoria, busca por nome, código ou categoria, filtro por fonte (TUSS, SUS, outros, sem código) e "só sem valor". Cadastro com validação do código (TUSS de 8 dígitos; SUS/SIGTAP de 10, formatado como 03.07.01.003-1) e aviso de código repetido. Reajuste de todos os valores em %. |
| **Próteses** (etapa 3) | Trabalhos com fases (envio, previsão, recebimento), já com as fases padrão de cada tipo. Situação: no laboratório, atrasado, na clínica, concluído. Atalhos "Enviar" e "Receber", com aviso ao protético pelo WhatsApp. Ordem de serviço para imprimir. Valor e pagamento ao protético, que pode virar conta a pagar no financeiro (respeita o período contábil fechado). Cadastro de protéticos. |
| **Estoque** (etapa 3) | Itens com código de barras, custo e estoque mínimo. Entradas com validade e lote, que podem virar despesa no financeiro. Saídas que não deixam o saldo negativo. Lotes por validade (sai primeiro o que vence antes). Alertas de reposição e de validade. Histórico com correção e exclusão de lançamentos (o saldo é ajustado). |
| **Modelos de documentos** (etapa 3) | Criar, editar e excluir os modelos (atestado, receituário, contrato, termo), com as mesmas variáveis do app. |
| **Configurações** (etapa 3) | Dados da clínica, com CPF/CNPJ validado (inclusive o CNPJ com letras), horário e intervalo da agenda e mensagens. Pré-consulta (WhatsApp da clínica e endereço do formulário). Dentistas e comissões. Perguntas da anamnese. Exportação de backup (.json). |
| **Usuários e acessos** (etapa 3, só o administrador) | Novo usuário com senha provisória (troca obrigatória no primeiro acesso, aqui ou no app do computador). Editar, desativar, excluir e redefinir senha. Tabela de permissões por tipo de acesso. Novos tipos de acesso. Encerramento da sessão por inatividade. Novo código de recuperação. Proteções: sempre fica um administrador ativo, e ninguém tira o próprio acesso de administrador. |
| **Galeria de imagens** (etapa 4a) | Fotos, radiografias, PDFs e escaneamentos intraorais (.stl): escolher ou arrastar para enviar. Fotos reduzidas para 1600 px, com miniatura. STL guardado compactado (malha indexada, sem perda, igual ao app do computador), com triângulos e medidas. **Visualizador 3D** no navegador: vários modelos juntos, cor, transparência, vistas, girar, **medir** em mm e salvar a imagem na galeria. Tudo fica no banco (tabela `anexos`), então o que entra aqui aparece no app do computador e vice-versa. |
| **Documentos e receitas** (etapa 4a) | Documentos a partir dos modelos, com as variáveis preenchidas, para conferir, salvar e imprimir. **Receitas** com a mesma base de medicamentos odontológicos do app: busca por nome genérico, comercial ou dosagem, posologias sugeridas, separação automática em receita simples, de **antimicrobiano** (2 vias, idade e sexo) e de **controle especial** (até 3 por receita, CPF e endereço), quantidade por extenso, uma ou duas vias por folha, repetir receita. As conferências são refeitas no servidor. PDFs assinados no app do computador podem ser abertos aqui. |
| **Pré-consulta** (etapa 4a) | Enviar o formulário pelo WhatsApp, e-mail ou link (oferecido ao agendar a primeira consulta, como no app). O mesmo formulário do site e o mesmo código `#ODPC1`. Importar a resposta: confere os dados cadastrais campo a campo, grava a anamnese e o motivo da consulta e pode levar os alertas de saúde às observações. Pendentes no painel. |
| **Limpar dados de exemplo** (etapa 4a, só o administrador) | Em Configurações: os dados de "Começar com dados de exemplo" já vêm marcados (mesma regra do app); marque também pacientes e lançamentos de teste. Exclui junto os registros e arquivos dos pacientes. Pede confirmação. |
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
├── requirements.txt         pacotes: Flask, PyMySQL, waitress, tzdata, Brotli, Pillow, numpy
├── odontodesk/
│   ├── app.py               cria a aplicação, versão, erros, segurança
│   ├── web.py               usuário logado, permissões (@exige), CSRF, formatos (dinheiro, datas)
│   ├── seguranca.py         senhas (PBKDF2), perfis e níveis de acesso
│   ├── br.py                CPF, CNPJ, telefone, CEP, endereço
│   ├── tempo.py             data e hora no fuso da clínica
│   ├── receitas.py          regras das receitas (tipos, vias, quantidade por extenso)
│   ├── limpar.py            o que é dado de exemplo e o que sai junto com cada paciente
│   ├── dados/
│   │   ├── esquema.py       tabelas e colunas (iguais às do app em JavaScript)
│   │   ├── drivers.py       conexão MySQL/TiDB e SQLite
│   │   ├── store.py         ler, gravar (com versão), excluir, histórico
│   │   ├── anexos.py        arquivos no banco (em partes, compactados, conferidos por SHA-256)
│   │   └── malha.py         compactação de STL (igual ao server/mesh-pack.js)
│   ├── rotas/               uma página por área: auth, painel, pacientes, agenda, financeiro, prontuario,
│   │                        cadastros (procedimentos, modelos, configurações), proteses, estoque, usuarios,
│   │                        galeria (e 3D), documentos (e receitas), preconsulta, limpar
│   ├── templates/           o HTML de cada página (Jinja2)
│   └── static/              estilo.css (o visual do app atual), odonto.js (odontograma), stl-viewer.js (3D),
│                            medicamentos.js e receita.js (formulário da receita)
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

São 51 testes:
- dados, validações e senhas;
- páginas: login, permissões, pacientes, agenda, financeiro, fechamento de período e prontuário (anamnese, regras da evolução, odontograma, orçamento e parcelas), procedimentos, modelos, configurações, próteses, estoque (lotes e saldo) e usuários e perfis;
- galeria (fotos, STL, outros arquivos), documentos, receitas (validações e impressão), pré-consulta (link e importação do código gerado pelo site) e limpeza de dados de exemplo (mesmo resultado do `limpar.js`);
- **convivência com o app em JavaScript**: anexos gravados por um são lidos pelo outro, byte a byte; o Python e o `server/store.js` original gravam e leem o mesmo banco, inclusive com conflitos. Esses testes precisam do Node.js e da pasta `odontodesk` ao lado; sem eles, são pulados.

## Próximas etapas

| Etapa | Conteúdo |
|---|---|
| 4b | Assinatura digital ICP-Brasil A1 das receitas e documentos (PDF gerado no servidor) e importação do BlueDental |
| 5 | Agenda Google, backups, mensagens de WhatsApp |

**Diferença importante:** por ser um sistema web, ele precisa de internet para funcionar. O app do computador continua sendo a opção para trabalhar sem conexão.
