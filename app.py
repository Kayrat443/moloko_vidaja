import streamlit as st
import pandas as pd
import os
import cv2
import numpy as np
from datetime import datetime, timedelta

# Настройка страницы
st.set_page_config(page_title="MILK SYSTEM", layout="centered")

# ТОЧЕЧНЫЕ СТИЛИ (ТОЛЬКО ДЛЯ РЕЗУЛЬТАТА)
st.markdown("""
    <style>
    /* Имя сотрудника - ЖЕСТКО ЧЕРНЫЙ */
    .emp-info-name {
        color: #000000 !important;
        font-size: 32px !important;
        font-weight: bold !important;
        text-align: center;
        margin-top: 20px;
    }
    
    /* Цифры ПОЛОЖЕНО / ОСТАТОК - ЖЕСТКО ЧЕРНЫЙ */
    div[data-testid="stMetricValue"] > div {
        color: #000000 !important;
        font-size: 44px !important;
        font-weight: 900 !important;
    }
    
    /* Подписи Норма / Остаток - ЖЕСТКО ЧЕРНЫЙ */
    div[data-testid="stMetricLabel"] > div {
        color: #000000 !important;
        font-weight: bold !important;
    }

    /* Сами блоки метрик - белые с черной рамкой */
    div[data-testid="stMetric"] {
        background-color: #ffffff !important;
        border: 2px solid #000000 !important;
        border-radius: 10px !important;
        padding: 10px !important;
    }
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
    st.title("🥛 ВЫДАЧА")
    
    img_file = st.camera_input("СКАНЕР")
    scanned_id = None
    
    if img_file:
        file_bytes = np.asarray(bytearray(img_file.read()), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, 1)
        detector = cv2.QRCodeDetector()
        data, _, _ = detector.detectAndDecode(img)
        if data:
            scanned_id = data

    user_id = st.text_input("Введите номер:", value=scanned_id if scanned_id else "")
    
    if user_id:
        db = st.session_state.db
        user = db[db['Табельный_Молоко'].astype(str) == str(user_id)]
        
        if not user.empty:
            idx = user.index[0]
            row = user.loc[idx]
            
            # ВЫВОД ДАННЫХ
            st.markdown(f"<div class='emp-info-name'>{row['Сотрудник']}</div>", unsafe_allow_html=True)
            
            c1, c2 = st.columns(2)
            c1.metric("ПОЛОЖЕНО", f"{row['Литр']} л")
            c2.metric("ОСТАТОК", f"{row['Остаток']} л")
            
            if row['Остаток'] > 0:
                val = st.number_input("Сколько литров выдаем?", 0.5, float(row['Остаток']), step=0.5)
                if st.button("ПОДТВЕРДИТЬ"):
                    st.session_state.db.at[idx, 'Остаток'] -= val
                    save_db(st.session_state.db)
                    log_tx(row['Табельный_Молоко'], row['Сотрудник'], val)
                    st.rerun()
            else:
                st.error("БАЛАНС 0")
        else:
            st.error("НЕ НАЙДЕН")

# --- 2. РЕДАКТОР ---
elif menu == "РЕДАКТОР":
    st.title("⚙️ РЕДАКТОР")
    q = st.text_input("Поиск сотрудника")
    if q:
        res = st.session_state.db[st.session_state.db['Сотрудник'].str.contains(q, case=False) | (st.session_state.db['Табельный_Молоко'].astype(str) == q)]
        for i, r in res.iterrows():
            with st.expander(f"{r['Сотрудник']}"):
                new_v = st.number_input("Изменить остаток", value=float(r['Остаток']), key=f"a{i}")
                if st.button("Сохранить", key=f"s{i}"):
                    st.session_state.db.at[i, 'Остаток'] = new_v
                    save_db(st.session_state.db)
                    st.success("Ок")

# --- 3. СТАТИСТИКА ---
elif menu == "СТАТИСТИКА":
    st.title("📊 СТАТИСТИКА")
    if os.path.exists('history.csv'):
        h = pd.read_csv('history.csv')
        st.dataframe(h.sort_values(by='Время', ascending=False), use_container_width=True)
