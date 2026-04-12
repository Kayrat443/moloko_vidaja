import streamlit as st
import pandas as pd
import os
import cv2
import numpy as np
from datetime import datetime, timedelta

# Настройка страницы
st.set_page_config(page_title="MILK SYSTEM", layout="centered")

# --- СТИЛИ (ТЫ МОЖЕШЬ МЕНЯТЬ ЦВЕТА ТУТ) ---
st.markdown("""
    <style>
    [data-testid="stAppViewContainer"] { background-color: #FFFFFF !important; }
    input { color: #000000 !important; background-color: #F8F9FA !important; }
    
    .result-card {
        background-color: #FFFFFF !important;
        padding: 20px;
        border-radius: 12px;
        border: 3px solid #000000;
        margin-bottom: 20px;
    }

    .res-fio { color: #000000 !important; font-size: 28px !important; font-weight: bold; text-align: center; }
    .res-val { color: #000000 !important; font-size: 44px !important; font-weight: 900; text-align: center; }
    .res-label { color: #333333 !important; font-size: 18px; text-align: center; font-weight: bold; }
    
    .stButton>button {
        background-color: #000000 !important;
        color: #FFFFFF !important;
        height: 3.5em;
        font-weight: bold;
    }

    p, label, h1, h2, h3 { color: #000000 !important; }
    </style>
    """, unsafe_allow_html=True)

# --- ЛОГИКА ДАННЫХ ---
def load_db():
    df = pd.read_excel('itog.xlsx')
    if 'Остаток' not in df.columns:
        df['Остаток'] = df['Литр']
    return df

def save_db(df):
    df.to_excel('itog.xlsx', index=False)

def log_tx(id, name, qty):
    log_file = 'history.csv'
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = pd.DataFrame([[now, id, name, qty]], columns=['Время', 'ID', 'ФИО', 'Литры'])
    entry.to_csv(log_file, mode='a', header=not os.path.exists(log_file), index=False)

if 'db' not in st.session_state:
    st.session_state.db = load_db()

menu = st.sidebar.radio("НАВИГАЦИЯ", ["ВЫДАЧА", "РЕДАКТОР", "СТАТИСТИКА"])

# --- 1. ВЫДАЧА ---
if menu == "ВЫДАЧА":
    st.title("🥛 Выдача молока")
    img_file = st.camera_input("СКАНЕР")
    scanned_id = None
    if img_file:
        file_bytes = np.asarray(bytearray(img_file.read()), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, 1)
        data, _, _ = cv2.QRCodeDetector().detectAndDecode(img)
        if data: scanned_id = data

    user_id = st.text_input("Введите номер:", value=scanned_id if scanned_id else "")
    
    if user_id:
        db = st.session_state.db
        user = db[db['Табельный_Молоко'].astype(str) == str(user_id)]
        if not user.empty:
            idx, row = user.index[0], user.loc[user.index[0]]
            st.markdown(f"""
                <div class="result-card">
                    <div class="res-fio">{row['Сотрудник']}</div>
                    <div style="display: flex; justify-content: space-around; margin-top: 20px;">
                        <div><div class="res-label">НОРМА</div><div class="res-val">{row['Литр']} л</div></div>
                        <div><div class="res-label">ОСТАТОК</div><div class="res-val">{row['Остаток']} л</div></div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            if row['Остаток'] > 0:
                val = st.number_input("Кол-во к выдаче:", 0.5, float(row['Остаток']), step=0.5)
                if st.button("ПОДТВЕРДИТЬ"):
                    st.session_state.db.at[idx, 'Остаток'] -= val
                    save_db(st.session_state.db)
                    log_tx(row['Табельный_Молоко'], row['Сотрудник'], val)
                    st.rerun()
            else: st.error("БАЛАНС 0 ЛИТРОВ")
        else: st.error("СОТРУДНИК НЕ НАЙДЕН")

# --- 2. РЕДАКТОР ---
elif menu == "РЕДАКТОР":
    st.title("⚙️ Редактор")
    t1, t2 = st.tabs(["Индивидуально", "Массово (Начислить всем)"])
    with t1:
        q = st.text_input("Поиск сотрудника")
        if q:
            res = st.session_state.db[st.session_state.db['Сотрудник'].str.contains(q, case=False) | (st.session_state.db['Табельный_Молоко'].astype(str) == q)]
            for i, r in res.iterrows():
                with st.expander(f"👤 {r['Сотрудник']}"):
                    new_v = st.number_input("Остаток вручную", value=float(r['Остаток']), key=f"e{i}")
                    if st.button("Сохранить", key=f"s{i}"):
                        st.session_state.db.at[i, 'Остаток'] = new_v
                        save_db(st.session_state.db)
                        st.success("Обновлено")
    with t2:
        n = st.number_input("Установить всем лимит (л):", 10.0)
        if st.button("ОБНОВИТЬ ВСУ БАЗУ"):
            st.session_state.db['Остаток'] = n
            save_db(st.session_state.db)
            st.success("Всем начислено")

# --- 3. СТАТИСТИКА (С ФУНКЦИЕЙ ОЧИСТКИ) ---
elif menu == "СТАТИСТИКА":
    st.title("📊 Статистика")
    if os.path.exists('history.csv'):
        h = pd.read_csv('history.csv')
        h['Время'] = pd.to_datetime(h['Время'])
        
        period = st.radio("Период:", ["Сегодня", "Неделя", "Месяц", "Выбрать дату"], horizontal=True)
        today = datetime.now().date()
        
        if period == "Сегодня": h = h[h['Время'].dt.date == today]
        elif period == "Неделя": h = h[h['Время'].dt.date >= (today - timedelta(days=7))]
        elif period == "Месяц": h = h[h['Время'].dt.date >= (today - timedelta(days=30))]
        elif period == "Выбрать дату":
            rng = st.date_input("Диапазон дат:", [today, today])
            if len(rng) == 2:
                h = h[(h['Время'].dt.date >= rng[0]) & (h['Время'].dt.date <= rng
