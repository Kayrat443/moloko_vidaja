import streamlit as st
import pandas as pd
import os
import cv2
import numpy as np
from datetime import datetime, timedelta

# Настройка страницы
st.set_page_config(page_title="MILK SYSTEM", layout="centered")

# ЖЕСТКИЙ СТИЛЬ ДЛЯ ЧИТАЕМОСТИ
st.markdown("""
    <style>
    /* Весь текст на странице — черный */
    .stApp { background-color: #ffffff !important; }
    h1, h2, h3, p, span, label { color: #000000 !important; }
    
    /* ФИО сотрудника */
    .emp-name {
        color: #000000 !important;
        font-size: 32px !important;
        font-weight: bold !important;
        text-align: center;
        margin-bottom: 20px;
    }
    
    /* МЕТРИКИ (Положено и Остаток) — СТРОГО ЧЕРНЫЕ */
    div[data-testid="stMetricValue"] {
        color: #000000 !important;
        font-size: 44px !important;
        font-weight: 900 !important;
    }
    div[data-testid="stMetricLabel"] {
        color: #000000 !important;
        font-size: 20px !important;
        font-weight: bold !important;
    }
    div[data-testid="stMetric"] {
        border: 2px solid #000000 !important;
        padding: 15px !important;
        border-radius: 10px !important;
    }

    /* Кнопки и ввод */
    .stButton>button {
        background-color: #000000 !important;
        color: #ffffff !important;
        font-weight: bold;
        height: 3.5em;
    }
    input { color: #000000 !important; border: 1px solid #000000 !important; }
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

# --- МЕНЮ (ПЕРЕИМЕНОВАНО) ---
menu = st.sidebar.radio("НАВИГАЦИЯ", ["ВЫДАЧА", "РЕДАКТОР", "СТАТИСТИКА"])

# --- 1. ВЫДАЧА ---
if menu == "ВЫДАЧА":
    st.markdown("<h1 style='text-align: center;'>🥛 ВЫДАЧА</h1>", unsafe_allow_html=True)
    
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

    user_id = st.text_input("Введите номер вручную:", value=scanned_id if scanned_id else "")
    
    if user_id:
        db = st.session_state.db
        user = db[db['Табельный_Молоко'].astype(str) == str(user_id)]
        
        if not user.empty:
            idx = user.index[0]
            row = user.loc[idx]
            
            st.markdown(f"<div class='emp-name'>{row['Сотрудник']}</div>", unsafe_allow_html=True)
            
            c1, c2 = st.columns(2)
            c1.metric("ПОЛОЖЕНО", f"{row['Литр']} л")
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

# --- 2. РЕДАКТОР (СТАРАЯ УДОБНАЯ АДМИНКА) ---
elif menu == "РЕДАКТОР":
    st.title("⚙️ Редактор базы")
    
    tab1, tab2 = st.tabs(["Индивидуально", "Массово"])
    
    with tab1:
        q = st.text_input("Поиск (ФИО или Номер)")
        if q:
            res = st.session_state.db[st.session_state.db['Сотрудник'].str.contains(q, case=False) | (st.session_state.db['Табельный_Молоко'].astype(str) == q)]
            for i, r in res.iterrows():
                with st.expander(f"👤 {r['Сотрудник']} (ID: {r['Табельный_Молоко']})"):
                    new_val = st.number_input(f"Изменить остаток", value=float(r['Остаток']), key=f"edit_{i}")
                    if st.button("Сохранить", key=f"btn_{i}"):
                        st.session_state.db.at[i, 'Остаток'] = new_val
                        save_db(st.session_state.db)
                        st.success("Данные обновлены")
    
    with tab2:
        new_month = st.number_input("Начислить всем на новый месяц (л):", 10.0)
        if st.button("ОБНОВИТЬ ВСЕМ"):
            st.session_state.db['Остаток'] = new_month
            save_db(st.session_state.db)
            st.success("Готово!")

# --- 3. СТАТИСТИКА ---
elif menu == "СТАТИСТИКА":
    st.title("📊 Статистика выдачи")
    if os.path.exists('history.csv'):
        h = pd.read_csv('history.csv')
        st.dataframe(h.sort_values(by='Время', ascending=False), use_container_width=True)
    else:
        st.info("История пуста")
