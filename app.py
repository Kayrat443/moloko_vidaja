import streamlit as st
import pandas as pd
import os
import cv2
import numpy as np
from datetime import datetime, timedelta

# --- КОНФИГУРАЦИЯ ---
st.set_page_config(page_title="СИСТЕМА УЧЕТА", layout="centered")

# --- ДИЗАЙН ---
st.markdown("""
    <style>
    .main { background-color: #f1f5f9; }
    
    /* Стилизация карточки сотрудника */
    .employee-card {
        background-color: #ffffff;
        padding: 25px;
        border-radius: 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        border: 1px solid #e2e8f0;
        text-align: center;
        margin-bottom: 20px;
    }
    
    /* Метрики */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 15px;
        padding: 15px;
    }
    
    /* Кнопки */
    .stButton>button {
        background-color: #1e293b;
        color: white;
        height: 3.5em;
        border-radius: 12px;
        font-weight: 600;
        width: 100%;
    }
    
    /* Красная кнопка очистки */
    .stButton>button[kind="secondary"] {
        background-color: #ef4444;
        color: white;
    }
    </style>
    """, unsafe_allow_html=True)

# --- ЛОГИКА ---
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

# --- БОКОВАЯ ПАНЕЛЬ ---
with st.sidebar:
    # Проверка логотипа в папке assets
    logo_path = "assets/logo.png"
    if os.path.exists(logo_path):
        st.image(logo_path, use_container_width=True)
    else:
        st.markdown("### 🥛 МОЛОКО-ПРО")
    
    st.markdown("---")
    menu = st.radio("МЕНЮ", ["🛒 МАГАЗИН", "⚙️ АДМИНКА", "📊 ОТЧЕТЫ"])

# --- 1. МАГАЗИН ---
if menu == "🛒 МАГАЗИН":
    st.markdown("<h1>Магазин выдачи</h1>", unsafe_allow_html=True)
    
    img_file = st.camera_input("Сканер QR")
    scanned_id = None
    
    if img_file:
        file_bytes = np.asarray(bytearray(img_file.read()), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, 1)
        data, _, _ = cv2.QRCodeDetector().detectAndDecode(img)
        if data:
            scanned_id = data
            st.toast("QR распознан")

    user_id = st.text_input("Табельный номер", value=scanned_id if scanned_id else "")
    
    if user_id:
        db = st.session_state.db
        user = db[db['Табельный_Молоко'].astype(str) == str(user_id)]
        
        if not user.empty:
            idx = user.index[0]
            row = user.loc[idx]
            
            st.markdown(f'<div class="employee-card"><h2>{row["Сотрудник"]}</h2></div>', unsafe_allow_html=True)
            
            c1, c2 = st.columns(2)
            c1.metric("НОРМА", f"{row['Литр']} л")
            c2.metric("ОСТАТОК", f"{row['Остаток']} л")
            
            if row['Остаток'] > 0:
                val = st.number_input("Выдать литров:", 0.5, float(row['Остаток']), step=0.5)
                if st.button("ПОДТВЕРДИТЬ ВЫДАЧУ"):
                    st.session_state.db.at[idx, 'Остаток'] -= val
                    save_db(st.session_state.db)
                    log_tx(row['Табельный_Молоко'], row['Сотрудник'], val)
                    st.success("Выдано!")
                    st.rerun()
            else:
                st.error("БАЛАНС ПУСТ")
        else:
            st.warning("Сотрудник не найден")

# --- 2. АДМИНКА ---
elif menu == "⚙️ АДМИНКА":
    st.title("Управление")
    t1, t2, t3 = st.tabs(["Правка", "Новый месяц", "Очистка"])
    
    with t1:
        q = st.text_input("Поиск по ФИО/ID")
        if q:
            res = st.session_state.db[st.session_state.db['Сотрудник'].str.contains(q, case=False) | (st.session_state.db['Табельный_Молоко'].astype(str) == q)]
            for i, r in res.iterrows():
                with st.expander(f"{r['Сотрудник']}"):
                    new_o = st.number_input("Остаток вручную", value=float(r['Остаток']), key=f"e{i}")
                    if st.button("Сохранить", key=f"s{i}"):
                        st.session_state.db.at[i, 'Остаток'] = new_o
                        save_db(st.session_state.db)
                        st.success("Обновлено")

    with t2:
        n = st.number_input("Норма на месяц:", 10.0)
        if st.button("ОБНОВИТЬ ВСЕМ БАЛАНС"):
            st.session_state.db['Остаток'] = n
            save_db(st.session_state.db)
            st.success("База обновлена")

    with t3:
        st.subheader("Очистка истории")
        if st.checkbox("Я хочу удалить всю историю выдач"):
            if st.button("🗑️ УДАЛИТЬ HISTORY.CSV"):
                if os.path.exists('history.csv'):
                    os.remove('history.csv')
                    st.success("История очищена")
                else:
                    st.info("Файл уже удален")

# --- 3. ОТЧЕТЫ ---
elif menu == "📊 ОТЧЕТЫ":
    st.title("История")
    if os.path.exists('history.csv'):
        h = pd.read_csv('history.csv')
        h['Время'] = pd.to_datetime(h['Время'])
        mode = st.radio("Период:", ["Сегодня", "Неделя", "Месяц", "Дата"], horizontal=True)
        today = datetime.now().date()
        
        if mode == "Сегодня": h = h[h['Время'].dt.date == today]
        elif mode == "Неделя": h = h[h['Время'].dt.date >= (today - timedelta(days=7))]
        elif mode == "Месяц": h = h[h['Время'].dt.date >= (today - timedelta(days=30))]
        elif mode == "Дата":
            rng = st.date_input("Диапазон", [today, today])
            if len(rng) == 2: h = h[(h['Время'].dt.date >= rng[0]) & (h['Время'].dt.date <= rng[1])]
        
        st.metric("ИТОГО ВЫДАНО", f"{h['Литры'].sum()} л")
        st.dataframe(h.sort_values('Время', ascending=False), use_container_width=True)
    else:
        st.info("История пуста")