import streamlit as st
import pandas as pd
import re
import unicodedata
import json
import os
import dateparser
from datetime import datetime

st.set_page_config(page_title="Hacka AT Points", page_icon="🏆", layout="wide")

TEAMS = {
    "Shreks": ["henrique guaré romano", "PK PJ", "Enzo Yai Michellin PJ"],
    "Phineas": ["camila santiago PJ", "João Victor", "André Ricardo PJ Dados", "Maria C Lemos"],
    "Tartarugas": ["Mac-Knight PJ", "André Morooka", "Renan Gutemberg", "Lucas Yamada"],
    "Pandas": ["theo PJ", "[CEE] Arthur", "Henrique Tavares PJ", "Gabriel Utida"],
    "Madagascar": ["Jurkas PJ", "beatriz harumi", "Pedro Augusto", "Francisco Toledo"]
}

POWER_OPTIONS = [
    "Nenhum",
    "P1: Escolher 3 empresas p/ triplicar pontos",
    "P2: Quarta-feira, fichas do trainee duplicam (max 15pontos de bônus)",
    "P3: Sem limite em 1 empresa (max 6 ATs, max 15pts)",
    "P4: Triplica pontos do último trainee",
    "P5: Dar 6 empresas pra equipe (Apenas status)"
]

CONFIG_FILE = "powers_config.json"

def load_powers_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_powers_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

def clean_sender(sender):
    sender = re.sub(r'[\u200e\u200f\u202a-\u202e\u2066-\u2069]', '', sender)
    sender = re.sub(r'^[~\s\u202f]+', '', sender)
    return sender.strip()

def get_team(sender_name):
    sn_lower = sender_name.lower()
    for team, members in TEAMS.items():
        for member in members:
            m_clean = member.lower().strip()
            if m_clean in sn_lower or sn_lower in m_clean:
                return team
    return "Unknown Team"

def get_points(role_str):
    role_str = role_str.lower()
    
    keywords_3 = [
        r'\bceo\b', r'\bcfo\b', r'\bcto\b', r'\bcio\b', r'\bcmo\b', r'\bcoo\b', r'\bcdo\b', r'\bcco\b', r'\bchro\b', r'\bvp\b', 
        'diretor', 'director', 'sócio', 'socio', 'partner', 'founder', 'presidente', 'president', 'executivo', 'executive', 'c-level', 'chief'
    ]
    if any(re.search(kw, role_str) for kw in keywords_3):
        return 3
        
    keywords_2 = ['head', 'líder', 'lider', 'leader', 'superintendente']
    if any(kw in role_str for kw in keywords_2):
        return 2
        
    keywords_1 = ['gerente', 'manager', 'coordenador', 'coordinator']
    if any(kw in role_str for kw in keywords_1):
        return 1
        
    return 0

def normalize_company(name):
    name = name.lower()
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('utf-8')
    name = re.sub(r'[^a-z0-9]', '', name)
    return name

def get_week_for_date(dt, config):
    for week_name, w_data in config.items():
        if 'start_date' in w_data and 'end_date' in w_data:
            sd = datetime.strptime(w_data['start_date'], "%Y-%m-%d").date()
            ed = datetime.strptime(w_data['end_date'], "%Y-%m-%d").date()
            if sd <= dt.date() <= ed:
                return week_name
    return None

@st.cache_data
def parse_chat_text(text):
    pattern = r'\[(\d{2}/\d{2}/\d{4}, \d{2}:\d{2}:\d{2})\] (.*?): (.*?)(?=\n\[\d{2}/\d{2}/\d{4}, \d{2}:\d{2}:\d{2}\]|\Z)'
    matches = re.findall(pattern, text, re.DOTALL)
    
    fichas_raw = []
    
    for timestamp, sender, content in matches:
        content = content.strip()
        if 'ficha de at' not in content.lower():
            continue
            
        sender = clean_sender(sender)
        team = get_team(sender)
        
        empresa_match = re.search(r'Empresa:[ \t]*([^\n]+)', content, re.IGNORECASE)
        nome_match = re.search(r'(?:Nome do Cliente|Cliente):[ \t]*([^\n]+)', content, re.IGNORECASE)
        cargo_match = re.search(r'(?:Cargo do Cliente|Cargo do cliente|Cargo):[ \t]*([^\n]+)', content, re.IGNORECASE)
        data_match = re.search(r'(?:Data da Reunião|Data da reunião|Horário):[ \t]*([^\n]+)', content, re.IGNORECASE)
        
        empresa = empresa_match.group(1).strip() if empresa_match else ""
        nome = nome_match.group(1).strip() if nome_match else ""
        cargo = cargo_match.group(1).strip() if cargo_match else ""
        data_str = data_match.group(1).strip() if data_match else ""
        
        if not empresa:
            continue
            
        norm_emp = normalize_company(empresa)
        base_points = get_points(cargo)
        
        # NLP parse date
        dt_msg = datetime.strptime(timestamp, "%d/%m/%Y, %H:%M:%S")
        dt_meeting = dt_msg
        if data_str:
            clean_date_str = data_str.lower().replace('às', '').replace('as', '').replace('(', '').replace(')', '')
            parsed_dt = dateparser.parse(clean_date_str, languages=['pt'], settings={'RELATIVE_BASE': dt_msg, 'PREFER_DATES_FROM': 'current_period'})
            if parsed_dt:
                dt_meeting = parsed_dt
                
        fichas_raw.append({
            'Timestamp': timestamp,
            'Message Date': dt_msg,
            'Meeting Date': dt_meeting,
            'Sender': sender,
            'Team': team,
            'Empresa': empresa,
            'Norm_Empresa': norm_emp,
            'Cliente': nome,
            'Cargo': cargo,
            'Base Points': base_points
        })
        
    return fichas_raw

def apply_powers(fichas_raw, config):
    fichas = sorted(fichas_raw, key=lambda x: x['Message Date'])
    global_seen_companies = set()
    team_week_p3_count = {} 
    team_week_p3_points = {} 
    team_week_p2_points = {} 
    processed = []
    
    for f in fichas:
        team = f['Team']
        norm_emp = f['Norm_Empresa']
        pts = f['Base Points']
        mtg_date = f['Meeting Date']
        
        week = get_week_for_date(mtg_date, config)
        if not week:
            active_power = "Nenhum"
            power_data = {}
        else:
            power_data = config[week].get(team, {})
            active_power = power_data.get('power', 'Nenhum')
            
        final_pts = pts
        status = "Valid"
        
        is_duplicate = norm_emp in global_seen_companies
        
        p3_bypass = False
        if active_power.startswith("P3"):
            p3_company = normalize_company(power_data.get("p3_company", ""))
            if norm_emp == p3_company and p3_company != "":
                p3_pass_key = (team, week)
                p3_count = team_week_p3_count.get(p3_pass_key, 0)
                p3_pts = team_week_p3_points.get(p3_pass_key, 0)
                
                if p3_count < 6 and p3_pts < 15:
                    p3_bypass = True
                    can_add = min(pts, 15 - p3_pts)
                    final_pts = can_add
                    team_week_p3_count[p3_pass_key] = p3_count + 1
                    team_week_p3_points[p3_pass_key] = p3_pts + can_add
                    status = "Valid (P3 Extra ATs)"
        
        if is_duplicate and not p3_bypass:
            final_pts = 0
            status = "Duplicate"
        else:
            if not p3_bypass:
                global_seen_companies.add(norm_emp)
                
            if active_power.startswith("P1") and status == "Valid":
                p1_comps = [normalize_company(c) for c in power_data.get("p1_companies", [])]
                if norm_emp in p1_comps:
                    final_pts *= 3
                    status = "Valid (P1 3x)"
                    
            elif active_power.startswith("P2") and status == "Valid":
                p2_trainee = clean_sender(power_data.get("p2_trainee", ""))
                # Is meeting on Wednesday? (weekday() == 2)
                if f['Sender'] == p2_trainee and mtg_date.weekday() == 2:
                    p2_key = (team, week, p2_trainee)
                    curr_p2_pts = team_week_p2_points.get(p2_key, 0)
                    if curr_p2_pts < 15:
                        bonus = final_pts
                        bonus_allowed = min(bonus, 15 - curr_p2_pts)
                        final_pts += bonus_allowed
                        team_week_p2_points[p2_key] = curr_p2_pts + bonus_allowed
                        status = "Valid (P2 Quarta 2x)"
                        
            elif active_power.startswith("P4") and status == "Valid":
                p4_trainee = clean_sender(power_data.get("p4_trainee", ""))
                if f['Sender'] == p4_trainee:
                    final_pts *= 3
                    status = "Valid (P4 3x)"
                    
        f_copy = {
            'Timestamp': f['Timestamp'],
            'Meeting Date': f['Meeting Date'].strftime('%d/%m/%y %H:%M'),
            'Week': week if week else "Sem Semana Config.",
            'Sender': f['Sender'],
            'Team': f['Team'],
            'Empresa': f['Empresa'],
            'Cliente': f['Cliente'],
            'Cargo': f['Cargo'],
            'Base Points': pts,
            'Points Awarded': final_pts,
            'Status': status
        }
        processed.append(f_copy)
        
    return processed

def render_config_tab(config, config_file_path, df_fichas_raw):
    st.subheader("⚙️ Configurações Semanais de Poderes")
    
    unique_companies = []
    if df_fichas_raw is not None and not df_fichas_raw.empty:
        unique_companies = sorted(df_fichas_raw['Empresa'].dropna().unique().tolist())

    with st.expander("📝 Criar Nova Semana", expanded=False):
        if len(config) >= 2:
            st.info("As 2 semanas da competição já foram criadas! Não é necessário adicionar mais.")
        else:
            c1, c2, c3 = st.columns(3)
            new_week_name = c1.text_input("Nome da Semana (ex: Semana 1)")
            start_date = c2.date_input("Data de Início")
            end_date = c3.date_input("Data de Fim")
            if st.button("Adicionar Semana"):
                if new_week_name and new_week_name not in config:
                    config[new_week_name] = {
                        "start_date": str(start_date),
                        "end_date": str(end_date)
                    }
                    save_powers_config(config)
                    st.success(f"{new_week_name} adicionada!")
                    st.rerun()
                elif new_week_name in config:
                    st.error("Nome de semana já existe.")

    st.divider()

    if not config:
        st.info("Nenhuma semana configurada ainda.")
        return

    selected_week = st.selectbox("Selecione a Semana para Configurar Poderes:", list(config.keys()))
    week_data = config[selected_week]
    
    st.write(f"**Período:** {week_data.get('start_date')} até {week_data.get('end_date')}")
    
    st.write("### Poderes das Equipes")
    
    new_week_data = {"start_date": week_data.get('start_date'), "end_date": week_data.get('end_date')}
    
    for team in TEAMS.keys():
        st.markdown(f"**{team}**")
        current_team_conf = week_data.get(team, {})
        current_power = current_team_conf.get('power', "Nenhum")
        
        p_idx = POWER_OPTIONS.index(current_power) if current_power in POWER_OPTIONS else 0
        selected_p = st.selectbox(f"Poder - {team}", POWER_OPTIONS, index=p_idx, key=f"sel_p_{team}_{selected_week}")
        
        p1_sels = current_team_conf.get("p1_companies", [])
        p2_tr = current_team_conf.get("p2_trainee", TEAMS[team][0])
        p3_comp = current_team_conf.get("p3_company", "")
        p4_tr = current_team_conf.get("p4_trainee", TEAMS[team][0])
        
        if selected_p.startswith("P1"):
            p1_sels = st.multiselect(f"[{team}] P1: Escolha até 3 empresas", options=unique_companies, default=[c for c in p1_sels if c in unique_companies], max_selections=3, key=f"p1_{team}_{selected_week}")
        elif selected_p.startswith("P2"):
            p2_idx = TEAMS[team].index(p2_tr) if p2_tr in TEAMS[team] else 0
            p2_tr = st.selectbox(f"[{team}] P2: Escolha o Trainee (Quarta)", options=TEAMS[team], index=p2_idx, key=f"p2_{team}_{selected_week}")
        elif selected_p.startswith("P3"):
            p3_comp = st.selectbox(f"[{team}] P3: Escolha a Empresa s/ limite", options=[""] + unique_companies, index=(unique_companies.index(p3_comp)+1) if p3_comp in unique_companies else 0, key=f"p3_{team}_{selected_week}")
        elif selected_p.startswith("P4"):
            p4_idx = TEAMS[team].index(p4_tr) if p4_tr in TEAMS[team] else 0
            p4_tr = st.selectbox(f"[{team}] P4: Escolha o Último Trainee (3x)", options=TEAMS[team], index=p4_idx, key=f"p4_{team}_{selected_week}")
        
        new_week_data[team] = {
            "power": selected_p,
            "p1_companies": p1_sels,
            "p2_trainee": p2_tr,
            "p3_company": p3_comp,
            "p4_trainee": p4_tr
        }

        st.write("---")
        
    if st.button("Salvar Configurações", type="primary"):
        config[selected_week] = new_week_data
        save_powers_config(config)
        st.success("Configurações salvas com sucesso!")
        st.rerun()

def main():
    config = load_powers_config()
    
    st.title("🏆 Hacka AT Points Dashboard")
    st.markdown("Acompanhamento de pontos da competição de prospecção.")
    
    st.divider()
    st.header("1. Carga de Dados")
    uploaded_file = st.file_uploader("Peça ao Guaré para envio do histórico do whatsapp", type=["txt"])
    
    if uploaded_file is None:
        st.info("⬆️ Faça o upload do arquivo _chat.txt exportado do WhatsApp acima para começar.")
        return
        
    text = uploaded_file.read().decode("utf-8")
    fichas_raw = parse_chat_text(text)
    
    if not fichas_raw:
        st.warning("⚠️ Nenhuma Ficha de AT encontrada no arquivo.")
        return
        
    df_raw = pd.DataFrame(fichas_raw)
    
    st.divider()
    st.header("2. Configuração Semanal")
    # Config UI with guarantees that df_raw exists
    render_config_tab(config, CONFIG_FILE, df_raw)
    
    st.divider()
    st.header("3. Resultado e Dashboard de Pontos")
    
    # Apply powers
    fichas_final = apply_powers(fichas_raw, config)
    df = pd.DataFrame(fichas_final)
    
    total_valid = len(df[~df['Status'].str.contains("Duplicate")])
    total_points = df['Points Awarded'].sum()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total de Fichas Enviadas", len(df))
    col2.metric("Fichas Válidas", total_valid)
    col3.metric("Total de Pontos (Bruto)", total_points)
    
    # Calculate Leaderboards before displaying
    team_points = df.groupby('Team')['Points Awarded'].sum().reset_index()
    team_points['Points Awarded'] = team_points['Points Awarded'].astype(float)
    team_points.loc[team_points['Team'] == 'Shreks', 'Points Awarded'] *= 1.33
    team_points['Points Awarded'] = team_points['Points Awarded'].round(2)
    team_points = team_points.sort_values(by='Points Awarded', ascending=False).reset_index(drop=True)
    team_points.index += 1
    
    ind_points = df.groupby(['Sender', 'Team'])['Points Awarded'].sum().reset_index()
    ind_points = ind_points.sort_values(by='Points Awarded', ascending=False).reset_index(drop=True)
    ind_points.index += 1

    st.write("")
    
    top_team = team_points.iloc[0] if not team_points.empty else None
    top_ind = ind_points.iloc[0] if not ind_points.empty else None
    
    col_champ, col_hero = st.columns(2)
    with col_champ:
        if top_team is not None:
            st.success(f"🏆 **Champion (Equipe em 1º):** {top_team['Team']} com {top_team['Points Awarded']} pts")
    with col_hero:
        if top_ind is not None:
            st.info(f"🦸‍♂️ **Herói do Hacka (1º Individual):** {top_ind['Sender']} com {top_ind['Points Awarded']} pts")

    st.write("")
    col_team, col_ind = st.columns(2)
    
    with col_team:
        st.subheader("👥 Pontos por Equipe")
        st.dataframe(team_points, use_container_width=True)
        
    with col_ind:
        st.subheader("👤 Pontos Individuais")
        st.dataframe(ind_points, use_container_width=True)
    
    st.divider()
    
    st.subheader("📋 Histórico de Fichas e Aplicação de Poderes")
    
    col_f0, col_f1, col_f2, col_f3 = st.columns(4)
    with col_f0:
        week_options = ["Todas"] + sorted(df['Week'].unique().tolist())
        week_filter = st.selectbox("Semana", week_options)
    with col_f1:
        status_options = ["Todos"] + sorted(df['Status'].unique().tolist())
        status_filter = st.selectbox("Status / Poder", status_options)
    with col_f2:
        team_options = ["Todos"] + sorted(df['Team'].unique().tolist())
        team_filter = st.selectbox("Equipe", team_options)
    with col_f3:
        if team_filter != "Todos":
            sender_options = ["Todos"] + sorted(df[df['Team'] == team_filter]['Sender'].unique().tolist())
        else:
            sender_options = ["Todos"] + sorted(df['Sender'].unique().tolist())
        sender_filter = st.selectbox("Remetente", sender_options)
    
    filtered_df = df
    if week_filter != "Todas":
        filtered_df = filtered_df[filtered_df['Week'] == week_filter]
    if status_filter != "Todos":
        filtered_df = filtered_df[filtered_df['Status'] == status_filter]
    if team_filter != "Todos":
        filtered_df = filtered_df[filtered_df['Team'] == team_filter]
    if sender_filter != "Todos":
        filtered_df = filtered_df[filtered_df['Sender'] == sender_filter]
        
    st.dataframe(filtered_df, use_container_width=True)

if __name__ == "__main__":
    main()
