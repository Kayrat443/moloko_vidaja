import streamlit as st
import pandas as pd
import os
import cv2
import numpy as np
from datetime import datetime, timedelta
from PIL import Image

# Настройка страницы
st.set_page_config(page_title="MILK STORE", layout="centered")

# --- СУПЕР-СТРОГИЙ ЧЕРНО-БЕЛЫЙ ДИЗАЙН ---
st.markdown("""
    <style>
    /* Фон всей страницы */
    [data-testid="stAppViewContainer"] { background-color: #ffffff !important; color: #000000 !important; }
    [data-testid="stHeader"] { background-color: #ffffff !important; }
    
    /* Имя сотрудника */
    .employee-title { color: #000000 !important; font-size: 34px !important; font-weight: 900 !important; text-align: center; margin-bottom: 20px; text-transform: uppercase; }

    /* Метрики (Норма / Остаток) */
    div[data-testid="stMetric"] { background-color: #ffffff !important; border: none !important; padding: 0px !important; text-align: center; }
    div[data-testid="stMetricLabel"] { color: #555555 !important; font-size: 18px !important; font-weight: bold !important; }
    div[data-testid="stMetricValue"] { color: #000000 !important; font-size: 44px !important; font-weight: 900 !important; }

    /* Поля ввода и кнопки */
    .stNumberInput input { color: #000000 !important; font-size: 24px !important; border: 2px solid #000000 !important; }
    .stTextInput input { color: #000000 !important; border: 2px solid #000000 !important; }
    
    /* Кнопка выдачи */
    .stButton>button { background-color: #000000 !important; color: white !important; height: 3.5em !important; font-size: 20px !important; font-weight: bold !important; border-radius: 5px !important; margin-top: 20px; }
    
    /* Боковое меню */
    [data-testid="stSidebar"] { background-color: #f8fafc; border-right: 1px solid #e2e8f0; }
    [data-testid="stSidebar"] * { color: #000000 !important; }
    </style>
    """, unsafe_allow_html=True)

# --- БАЗА ДАННЫХ ---
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

menu = st.sidebar.radio("НАВИГАЦИЯ", ["ВЫДАЧА", "АДМИН", "ОТЧЕТЫ"])

# --- 1. ВЫДАЧА ---
if menu == "ВЫДАЧА":
    st.markdown("<h1 style='text-align: center; color: #000000;'>🛒 Магазин</h1>", unsafe_allow_html=True)
    
    # Камера (с попыткой переключения на заднюю)
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
        else:
            st.warning("QR не распознан, попробуйте еще раз.")

    user_id = st.text_input("Введите номер вручную:", value=scanned_id if scanned_id else "")
    
    if user_id:
        db = st.session_state.db
        user = db[db['Табельный_Молоко'].astype(str) == str(user_id)]
        
        if not user.empty:
            idx = user.index[0]
            row = user.loc[idx]
            
            # --- ЧЕРНЫЙ ФИО НА БЕЛОМ ---
            st.markdown(f"<div class='employee-title'>{row['Сотрудник']}</div>", unsafe_allow_html=True)
            
            c1, c2 = st.columns(2)
            c1.metric("НОРМА", f"{row['Литр']} л")
            c2.metric("ОСТАТОК", f"{row['Остаток']} л")
            
            if row['Остаток'] > 0:
                st.write("### Количество к выдаче:")
                val = st.number_input("", 0.5, float(row['Остаток']), step=0.5, key="val_input")
                
                if st.button("ПОДТВЕРДИТЬ ВЫДАЧУ"):
                    st.session_state.db.at[idx, 'Остаток'] -= val
                    save_db(st.session_state.db)
                    log_tx(row['Табельный_Молоко'], row['Сотрудник'], val)
                    st.success("ГОТОВО")
                    st.rerun()
            else:
                st.error("БАЛАНС 0")
        else:
            st.error("Сотрудник не найден")

# --- 2. АДМИН (без изменений логики) ---
elif menu == "АДМИН":
    st.title("Управление")
    q = st.text_input("ФИО или Табельный")
    if q:
        res = st.session_state.db[st.session_state.db['Сотрудник'].str.contains(q, case=False) | (st.session_state.db['Табельный_Молоко'].astype(str) == q)]
        for i, r in res.iterrows():
            with st.expander(f"{r['Сотрудник']}"):
                new_v = st.number_input("Правка остатка", value=float(r['Остаток']), key=f"ad{i}")
                if st.button("Сохранить", key=f"s{i}"):
                    st.session_state.db.at[i, 'Остаток'] = new_v
                    save_db(st.session_state.db)
                    st.success("Ок")

# --- 3. ОТЧЕТЫ (без изменений логики) ---
elif menu == "ОТЧЕТЫ":
    st.title("Статистика")
    if os.path.exists('history.csv'):
        h = pd.read_csv('history.csv')
        st.dataframe(h.sort_values(by='Время', ascending=False), use_container_width=True)
    else:
        st.write("История пуста")
