import streamlit as st
import pandas as pd
import re
import unicodedata

st.set_page_config(page_title="Hacka AT Points", page_icon="🏆", layout="wide")

TEAMS = {
    "Shreks": ["henrique guaré romano", "PK PJ", "Enzo Yai Michellin PJ"],
    "Phineas": ["camila santiago PJ", "João Victor", "André Ricardo PJ Dados", "Maria C Lemos"],
    "Tartarugas": ["Mac-Knight PJ", "André Morooka", "Renan Gutemberg", "Lucas Yamada"],
    "Pandas": ["theo PJ", "[CEE] Arthur", "Henrique Tavares PJ", "Gabriel Utida"],
    "Madagascar": ["Jurkas PJ", "beatriz harumi", "Pedro Augusto", "Francisco Toledo"]
}

def clean_sender(sender):
    # Remove WhatsApp special characters and leading spaces/tildes
    # Sometimes WhatsApp includes BiDi control characters like \u202a, \u202c, \u200e, \u200f
    sender = re.sub(r'[\u200e\u200f\u202a-\u202e\u2066-\u2069]', '', sender)
    sender = re.sub(r'^[~\s\u202f]+', '', sender)
    return sender.strip()

def get_team(sender_name):
    sn_lower = sender_name.lower()
    for team, members in TEAMS.items():
        for member in members:
            # Check for inclusion in both directions
            m_clean = member.lower().strip()
            if m_clean in sn_lower or sn_lower in m_clean:
                return team
    return "Unknown Team"

def get_points(role_str):
    role_str = role_str.lower()
    
    # 3 points
    keywords_3 = [
        r'\bceo\b', r'\bcfo\b', r'\bcto\b', r'\bcio\b', r'\bcmo\b', r'\bcoo\b', r'\bcdo\b', r'\bcco\b', r'\bchro\b', r'\bvp\b', 
        'diretor', 'director', 'sócio', 'socio', 'partner', 'founder', 'presidente', 'president', 'executivo', 'executive', 'c-level', 'chief'
    ]
    if any(re.search(kw, role_str) for kw in keywords_3):
        return 3
        
    # 2 points
    keywords_2 = ['head', 'líder', 'lider', 'leader', 'superintendente']
    if any(kw in role_str for kw in keywords_2):
        return 2
        
    # 1 point
    keywords_1 = ['gerente', 'manager', 'coordenador', 'coordinator']
    if any(kw in role_str for kw in keywords_1):
        return 1
        
    return 0

def normalize_company(name):
    name = name.lower()
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('utf-8')
    name = re.sub(r'[^a-z0-9]', '', name)
    return name

@st.cache_data
def process_chat_text(text):
    # Regex to capture [DD/MM/YYYY, HH:MM:SS] Sender: Message
    pattern = r'\[(\d{2}/\d{2}/\d{4}, \d{2}:\d{2}:\d{2})\] (.*?): (.*?)(?=\n\[\d{2}/\d{2}/\d{4}, \d{2}:\d{2}:\d{2}\]|\Z)'
    matches = re.findall(pattern, text, re.DOTALL)
    
    fichas = []
    normalized_companies = set()
    
    for timestamp, sender, content in matches:
        content = content.strip()
        if 'ficha de at' not in content.lower():
            continue
            
        sender = clean_sender(sender)
        team = get_team(sender)
        
        empresa_match = re.search(r'Empresa:[ \t]*([^\n]+)', content, re.IGNORECASE)
        nome_match = re.search(r'(?:Nome do Cliente|Cliente):[ \t]*([^\n]+)', content, re.IGNORECASE)
        cargo_match = re.search(r'(?:Cargo do Cliente|Cargo do cliente|Cargo):[ \t]*([^\n]+)', content, re.IGNORECASE)
        
        empresa = empresa_match.group(1).strip() if empresa_match else ""
        nome = nome_match.group(1).strip() if nome_match else ""
        cargo = cargo_match.group(1).strip() if cargo_match else ""
        
        if not empresa:
            continue
            
        norm_emp = normalize_company(empresa)
        points = get_points(cargo)
        
        if norm_emp in normalized_companies:
            points_awarded = 0
            status = 'Duplicate'
        else:
            points_awarded = points
            status = 'Valid'
            normalized_companies.add(norm_emp)
            
        fichas.append({
            'Timestamp': timestamp,
            'Sender': sender,
            'Team': team,
            'Empresa': empresa,
            'Cliente': nome,
            'Cargo': cargo,
            'Role Points': points,
            'Points Awarded': points_awarded,
            'Status': status
        })
        
    return fichas

def main():
    st.title("🏆 Hacka AT Points Dashboard")
    st.markdown("Acompanhamento de pontos da competição de prospecção.")
    
    uploaded_file = st.file_uploader("Peça ao Guaré para envio do histórico do whatsapp", type=["txt"])
    
    if uploaded_file is not None:
        text = uploaded_file.read().decode("utf-8")
        fichas = process_chat_text(text)
    else:
        st.info("Faça o upload do arquivo _chat.txt exportado do WhatsApp acima para visualizar os dados.")
        return
    
    if not fichas:
        st.warning("Nenhuma Ficha de AT encontrada no arquivo.")
        return
        
    df = pd.DataFrame(fichas)
    
    # KPIs
    total_valid = len(df[df['Status'] == 'Valid'])
    total_points = df['Points Awarded'].sum()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total de Fichas Enviadas", len(df))
    col2.metric("Fichas Válidas", total_valid)
    col3.metric("Total de Pontos", total_points)
    
    # Calculate Leaderboards before displaying
    team_points = df.groupby('Team')['Points Awarded'].sum().reset_index()
    team_points['Points Awarded'] = team_points['Points Awarded'].astype(float)
    # Apply 1.33 multiplier for Shreks due to 3 members
    team_points.loc[team_points['Team'] == 'Shreks', 'Points Awarded'] *= 1.33
    team_points['Points Awarded'] = team_points['Points Awarded'].round(2)
    team_points = team_points.sort_values(by='Points Awarded', ascending=False).reset_index(drop=True)
    team_points.index += 1
    
    ind_points = df.groupby(['Sender', 'Team'])['Points Awarded'].sum().reset_index()
    ind_points = ind_points.sort_values(by='Points Awarded', ascending=False).reset_index(drop=True)
    ind_points.index += 1

    st.divider()
    
    # Champion / Hero Cards
    top_team = team_points.iloc[0] if not team_points.empty else None
    top_ind = ind_points.iloc[0] if not ind_points.empty else None
    
    col_champ, col_hero = st.columns(2)
    with col_champ:
        if top_team is not None:
            st.success(f"🏆 **Champion (Equipe em 1º):** {top_team['Team']} com {top_team['Points Awarded']} pts")
    with col_hero:
        if top_ind is not None:
            st.info(f"🦸‍♂️ **Herói do Hacka (1º Individual):** {top_ind['Sender']} com {top_ind['Points Awarded']} pts")

    st.divider()
    col_team, col_ind = st.columns(2)
    
    with col_team:
        st.subheader("👥 Pontos por Equipe")
        st.dataframe(team_points, use_container_width=True)
        
    with col_ind:
        st.subheader("👤 Pontos Individuais")
        st.dataframe(ind_points, use_container_width=True)
    
    st.divider()
    
    st.subheader("📋 Histórico de Fichas")
    
    col_f1, col_f2, col_f3 = st.columns(3)
    
    with col_f1:
        status_options = ["Todos"] + sorted(df['Status'].unique().tolist())
        status_filter = st.selectbox("Filtrar Status", status_options)
        
    with col_f2:
        team_options = ["Todos"] + sorted(df['Team'].unique().tolist())
        team_filter = st.selectbox("Filtrar Equipe", team_options)
        
    with col_f3:
        # If a team is selected, we could conditionally filter the senders, or just show all for simplicity
        if team_filter != "Todos":
            sender_options = ["Todos"] + sorted(df[df['Team'] == team_filter]['Sender'].unique().tolist())
        else:
            sender_options = ["Todos"] + sorted(df['Sender'].unique().tolist())
        sender_filter = st.selectbox("Filtrar Remetente", sender_options)
    
    filtered_df = df
    if status_filter != "Todos":
        filtered_df = filtered_df[filtered_df['Status'] == status_filter]
    if team_filter != "Todos":
        filtered_df = filtered_df[filtered_df['Team'] == team_filter]
    if sender_filter != "Todos":
        filtered_df = filtered_df[filtered_df['Sender'] == sender_filter]
        
    st.dataframe(filtered_df, use_container_width=True)

if __name__ == "__main__":
    main()
