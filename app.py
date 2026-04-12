import streamlit as st
import pandas as pd
import os
import cv2
import numpy as np
from datetime import datetime, timedelta

# Чистый белый фон для всего приложения
st.set_page_config(page_title="MILK STORE", layout="centered")

st.markdown("""
    <style>
    /* Весь текст на странице делаем черным */
    .stApp, .stMarkdown, p, h1, h2, h3, span, label {
        color: #000000 !important;
    }
    /* Делаем фон чисто белым */
    .stApp {
        background-color: #ffffff !important;
    }
    /* Крупный шрифт для ФИО */
    .fio-text {
        font-size: 32px !important;
        font-weight: bold !important;
        color: #000000 !important;
        text-align: center;
        margin-top: 20px;
    }
    /* Настройка метрик (Литры) */
    [data-testid="stMetricValue"] {
        color: #000000 !important;
        font-size: 48px !important;
        font-weight: bold !important;
    }
    [data-testid="stMetricLabel"] {
        color: #333333 !important;
        font-size: 20px !important;
    }
    /* Кнопка */
    .stButton>button {
        background-color: #000000 !important;
        color: #ffffff !important;
        width: 100%;
        height: 3em;
        font-weight: bold;
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

menu = st.sidebar.radio("МЕНЮ", ["МАГАЗИН", "АДМИН", "ОТЧЕТЫ"])

if menu == "МАГАЗИН":
    st.markdown("<h1 style='text-align: center;'>🥛 ВЫДАЧА</h1>", unsafe_allow_html=True)
    
    # Стандартная камера (передняя)
    img_file = st.camera_input("СКАНЕР QR")
    scanned_id = None
    
    if img_file:
        file_bytes = np.asarray(bytearray(img_file.read()), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, 1)
        detector = cv2.QRCodeDetector()
        data, _, _ = detector.detectAndDecode(img)
        if data:
            scanned_id = data
            st.success(f"ID: {scanned_id}")

    user_id = st.text_input("Табельный номер:", value=scanned_id if scanned_id else "")
    
    if user_id:
        db = st.session_state.db
        user = db[db['Табельный_Молоко'].astype(str) == str(user_id)]
        
        if not user.empty:
            idx = user.index[0]
            row = user.loc[idx]
            
            # ЧЕРНЫЙ ТЕКСТ ФИО
            st.markdown(f"<div class='fio-text'>{row['Сотрудник']}</div>", unsafe_allow_html=True)
            
            # КРУПНЫЕ ЧЕРНЫЕ ЦИФРЫ
            c1, c2 = st.columns(2)
            c1.metric("НОРМА", f"{row['Литр']} л")
            c2.metric("ОСТАТОК", f"{row['Остаток']} л")
            
            if row['Остаток'] > 0:
                val = st.number_input("Сколько литров выдать?", 0.5, float(row['Остаток']), step=0.5)
                if st.button("ПОДТВЕРДИТЬ ВЫДАЧУ"):
                    st.session_state.db.at[idx, 'Остаток'] -= val
                    save_db(st.session_state.db)
                    log_tx(row['Табельный_Молоко'], row['Сотрудник'], val)
                    st.rerun()
            else:
                st.error("БАЛАНС 0 ЛИТРОВ")
        else:
            st.error("СОТРУДНИК НЕ НАЙДЕН")

elif menu == "АДМИН":
    st.title("Админка")
    q = st.text_input("Поиск")
    if q:
        res = st.session_state.db[st.session_state.db['Сотрудник'].str.contains(q, case=False) | (st.session_state.db['Табельный_Молоко'].astype(str) == q)]
        for i, r in res.iterrows():
            with st.expander(f"{r['Сотрудник']}"):
                new_v = st.number_input("Правка", value=float(r['Остаток']), key=f"a{i}")
                if st.button("Ок", key=f"s{i}"):
                    st.session_state.db.at[i, 'Остаток'] = new_v
                    save_db(st.session_state.db)
                    st.success("Изменено")

elif menu == "ОТЧЕТЫ":
    st.title("Отчеты")
    if os.path.exists('history.csv'):
        h = pd.read_csv('history.csv')
        st.dataframe(h.sort_values(by='Время', ascending=False), use_container_width=True)
