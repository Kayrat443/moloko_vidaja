import streamlit as st
import pandas as pd
import os
import cv2
import numpy as np
from datetime import datetime, timedelta

# Настройка страницы
st.set_page_config(page_title="MILK CONTROL", layout="centered")

# ЖЕСТКИЙ СТИЛЬ: Чтобы текст всегда был виден
st.markdown("""
    <style>
    /* Фон всей страницы */
    .main { background-color: #f1f5f9 !important; }
    
    /* Имя сотрудника - делаем жирным и темным */
    .employee-name {
        color: #0f172a !important;
        text-align: center;
        font-size: 32px !important;
        font-weight: 800 !important;
        margin-bottom: 20px;
        padding: 10px;
    }

    /* Карточки с метриками */
    div[data-testid="stMetric"] {
        background-color: #ffffff !important;
        border: 2px solid #cbd5e1 !important;
        padding: 20px !important;
        border-radius: 12px !important;
    }
    
    /* Цвет цифр в метриках */
    div[data-testid="stMetricValue"] {
        color: #1e40af !important;
        font-size: 36px !important;
        font-weight: bold !important;
    }

    /* Цвет подписей (Норма / Остаток) */
    div[data-testid="stMetricLabel"] {
        color: #475569 !important;
        font-size: 18px !important;
        font-weight: bold !important;
    }

    /* Кнопка выдачи */
    .stButton>button {
        background-color: #1e40af !important;
        color: white !important;
        height: 3.5em !important;
        font-size: 20px !important;
        font-weight: bold !important;
        border-radius: 10px !important;
        border: none !important;
        margin-top: 20px;
    }
    
    /* Поля ввода */
    input { color: #0f172a !important; }
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

menu = st.sidebar.radio("НАВИГАЦИЯ", ["🛒 МАГАЗИН", "⚙️ АДМИНКА", "📊 ОТЧЕТЫ"])

# --- 1. МАГАЗИН ---
if menu == "🛒 МАГАЗИН":
    st.markdown("<h2 style='text-align: center; color: #1e293b;'>🥛 Пункт выдачи</h2>", unsafe_allow_html=True)
    
    img_file = st.camera_input("СКАНЕР QR")
    scanned_id = None
    
    if img_file:
        file_bytes = np.asarray(bytearray(img_file.read()), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, 1)
        detector = cv2.QRCodeDetector()
        data, _, _ = detector.detectAndDecode(img)
        if data:
            scanned_id = data
            st.success(f"ID считан: {scanned_id}")
        else:
            st.error("QR не распознан. Наведите точнее.")

    user_id = st.text_input("Введите номер вручную, если не сканирует", value=scanned_id if scanned_id else "")
    
    if user_id:
        db = st.session_state.db
        user = db[db['Табельный_Молоко'].astype(str) == str(user_id)]
        
        if not user.empty:
            idx = user.index[0]
            row = user.loc[idx]
            
            # ВЫВОД ИМЕНИ (ТЕМНЫМ ЦВЕТОМ)
            st.markdown(f"<div class='employee-name'>{row['Сотрудник']}</div>", unsafe_allow_html=True)
            
            c1, c2 = st.columns(2)
            c1.metric("НОРМА", f"{row['Литр']} л")
            c2.metric("ОСТАТОК", f"{row['Остаток']} л")
            
            if row['Остаток'] > 0:
                st.markdown("<p style='color: #0f172a; font-weight: bold;'>Кол-во к выдаче:</p>", unsafe_allow_html=True)
                val = st.number_input("", 0.5, float(row['Остаток']), step=0.5, label_visibility="collapsed")
                
                if st.button("ПОДТВЕРДИТЬ ВЫДАЧУ"):
                    st.session_state.db.at[idx, 'Остаток'] -= val
                    save_db(st.session_state.db)
                    log_tx(row['Табельный_Молоко'], row['Сотрудник'], val)
                    st.success("Данные обновлены!")
                    st.rerun()
            else:
                st.error("БАЛАНС ПУСТ")
        else:
            st.error("СОТРУДНИК НЕ НАЙДЕН")

# --- ОСТАЛЬНЫЕ РАЗДЕЛЫ ---
elif menu == "⚙️ АДМИНКА":
    st.title("Админка")
    # Логика поиска и начисления остается прежней
    q = st.text_input("Поиск сотрудника")
    if q:
        res = st.session_state.db[st.session_state.db['Сотрудник'].str.contains(q, case=False) | (st.session_state.db['Табельный_Молоко'].astype(str) == q)]
        for i, r in res.iterrows():
            with st.expander(f"{r['Сотрудник']}"):
                new_v = st.number_input("Изменить остаток", value=float(r['Остаток']), key=f"ad{i}")
                if st.button("Сохранить", key=f"s{i}"):
                    st.session_state.db.at[i, 'Остаток'] = new_v
                    save_db(st.session_state.db)
                    st.success("Ок")

elif menu == "📊 ОТЧЕТЫ":
    st.title("Статистика")
    if os.path.exists('history.csv'):
        h = pd.read_csv('history.csv')
        st.dataframe(h.sort_values(by='Время', ascending=False), use_container_width=True)
    else:
        st.write("История пуста")
