# Hacka AT Points Dashboard 🏆

Bem-vindo(a) ao **Hacka AT Points Dashboard**, um pipeline de ETL desenvolvido em Python (com Streamlit e Pandas) para processar históricos de grupos do WhatsApp e construir uma interface interativa de acompanhamento de pontos de uma competição de prospecção comercial.

## Visão Geral

Este projeto nasceu para auditar a competição do "Hacka AT". A rotina funciona extraindo o texto padronizado "[Ficha de AT]" do histórico de conversas do WhatsApp (arquivo `.txt`), onde são registradas as interações. O software limpa as mensagens, rastreia duplicatas e concede pontos às equipes e membros com base no nível hierárquico (cargo) do cliente contatado.

### 🎯 Regras de Negócio e Pontuação

- **Apenas o primeiro envio vale:** O código dedupilca envios subsequentes para uma mesma empresa (independente de maiúsculas ou espaços) para garantir que apenas o "hunter" mais rápido pontue.
- **Pontos por Senioridade (Cargos):**
  - **3 Pontos (C-Level & Sócios):** Diretor, VP, C-level, Sócio, Partner, Founder, Presidente, Executivo.
  - **2 Pontos (Líderes):** Head, Líder, Superintendente.
  - **1 Ponto (Gerentes):** Gerente, Manager, Coordenador.
  - **0 Pontos:** Analistas, Especialistas (ou não-mapeados) não geram pontuação na competição de "Decisores", mas mantêm o registro da ficha na listagem geral.
- **Vantagem Justa (Balanceamento de Times):** Uma das equipes (o time *Shreks*) atua com apenas 3 membros (em contraste com 4 membros nos demais). A rotina aplica um multiplicador algébrico (`1.33x`) nos pontos totais da equipe para equilibrar as chances de vitória sem afetar as premiações das métricas de performance individual.

## 🛠 Bibliotecas e Ferramentas

- `Streamlit`: Para a rederização dos componentes na interface (Filtros, Quadros de honra das equipes/membros).
- `Pandas`: Para manipulação dos dados, cruzamento, cálculo de agrupamentos e estatísticas.
- `Regex (re)` & `unicodedata`: Para limpar strings das mensagens, apagar caracteres invisíveis provenientes da exportação do aplicativo e normalizar o nome das empresas no momento da deduplicação (Remoção de acentos e alfanuméricos falsos).

## 🚀 Como Executar Localmente

### Pré-requisitos
- Python instalado na sua máquina (>= 3.9 recomendado)

### 1. Clonando o Repositório e Preparando o Ambiente
Abra o seu terminal e insira os diretórios:
```bash
git clone https://github.com/hguareromanoo/hacka-wpp-processment.git
cd hacka-wpp-processment

# Crie um ambiente virtual (Opcional, mas recomendado)
python3 -m venv .venv
source .venv/bin/activate  # Mac / Linux
# No Windows utilize: .venv\Scripts\activate

# Instale as dependências
pip install -r requirements.txt
```

### 2. Rodando o Pipeline
Assim que todas as bibliotecas estiverem disponíveis, execute o servidor do Streamlit:
```bash
streamlit run app.py
```
*Isto irá abrir uma guia local no seu navegador padrão portando o dashboard.*

### 3. Extraindo os Dados do Whatsapp
Para gerar a massa de teste que o dashboard consome:
1. Abra a respectiva conversa (Grupo ou Individual) no aplicativo do WhatsApp em seu celular.
2. Acesse as opções do grupo e clique em **Exportar conversa** -> **Sem Mídia**.
3. O aquivo virá com a extensão remetente (Exemplo: `_chat.txt` ou `Histórico do WhatsApp ... .txt`).
4. Abra a interface rodando no localhost e clique no botão de Upload contendo a legenda **"Peça ao Guaré para envio do histórico do whatsapp"**.
5. Selecione seu `.txt` para ver todas as informações na tela!

## 🧩 Arquitetura Mapeada das Equipes

As seguintes equipes então cadastradas para acompanhamento:
- **Shreks**
- **Phineas**
- **Tartarugas** 
- **Pandas**
- **Madagascar**
