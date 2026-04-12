import streamlit as st
import pandas as pd
import os
import cv2
import numpy as np
from datetime import datetime, timedelta

# Настройка страницы
st.set_page_config(page_title="MILK SYSTEM", layout="centered")

# --- БЛОК УПРАВЛЕНИЯ ЦВЕТАМИ (МЕНЯЙ ТУТ) ---
st.markdown("""
    <style>
    /* 1. ОБЩИЙ ФОН ПРИЛОЖЕНИЯ */
    [data-testid="stAppViewContainer"] { background-color: #FFFFFF !important; }

    /* 2. ТЕКСТ В ПОЛЯХ ВВОДА (чтобы видел, что пишешь) */
    input { color: #000000 !important; background-color: #F8F9FA !important; }
    
    /* 3. КАРТОЧКА СОТРУДНИКА (РЕЗУЛЬТАТ) */
    .result-card {
        background-color: #FFFFFF !important; /* Фон карточки */
        padding: 20px;
        border-radius: 12px;
        border: 3px solid #000000; /* Черная рамка */
        margin-bottom: 20px;
    }

    /* 4. ТЕКСТ ВНУТРИ КАРТОЧКИ (ФИО, ЛИТРЫ) */
    .res-fio { color: #000000 !important; font-size: 28px !important; font-weight: bold; text-align: center; }
    .res-val { color: #000000 !important; font-size: 44px !important; font-weight: 900; text-align: center; }
    .res-label { color: #333333 !important; font-size: 18px; text-align: center; font-weight: bold; }
    
    /* 5. КНОПКИ */
    .stButton>button {
        background-color: #000000 !important;
        color: #FFFFFF !important;
        height: 3.5em;
        font-weight: bold;
    }

    /* 6. ВСЕ ОСТАЛЬНЫЕ ТЕКСТЫ */
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
            
            # РЕЗУЛЬТАТ (КАРТОЧКА)
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

# --- 2. РЕДАКТОР (ВСЁ ВЕРНУЛ) ---
elif menu == "РЕДАКТОР":
    st.title("⚙️ Редактор")
    t1, t2 = st.tabs(["Индивидуально", "Массово (Начислить всем)"])
    
    with t1:
        q = st.text_input("Поиск сотрудника")
        if q:
            res = st.session_state.db[st.session_state.db['Сотрудник'].str.contains(q, case=False) | (st.session_state.db['Табельный_Молоко'].astype(str) == q)]
            for i, r in res.iterrows():
                with st.expander(f"👤 {r['Сотрудник']} (ID: {r['Табельный_Молоко']})"):
                    new_v = st.number_input("Остаток вручную", value=float(r['Остаток']), key=f"e{i}")
                    if st.button("Сохранить", key=f"s{i}"):
                        st.session_state.db.at[i, 'Остаток'] = new_v
                        save_db(st.session_state.db)
                        st.success("Обновлено")
    with t2:
        n = st.number_input("Установить всем лимит (л):", 10.0)
        if st.button("ОБНОВИТЬ ВСЮ БАЗУ"):
            st.session_state.db['Остаток'] = n
            save_db(st.session_state.db)
            st.success(f"Всем начислено по {n} л")

# --- 3. СТАТИСТИКА (ВСЁ ВЕРНУЛ) ---
elif menu == "СТАТИСТИКА":
    st.title("📊 Статистика")
    if os.path.exists('history.csv'):
        h = pd.read_csv('history.csv')
        h['Время'] = pd.to_datetime(h['Время'])
        
        # ФИЛЬТРЫ
        period = st.radio("Период:", ["Сегодня", "Неделя", "Месяц", "Выбрать дату"], horizontal=True)
        today = datetime.now().date()
        
        if period == "Сегодня": h = h[h['Время'].dt.date == today]
        elif period == "Неделя": h = h[h['Время'].dt.date >= (today - timedelta(days=7))]
        elif period == "Месяц": h = h[h['Время'].dt.date >= (today - timedelta(days=30))]
        elif period == "Выбрать дату":
            rng = st.date_input("Диапазон дат:", [today, today])
            if len(rng) == 2:
                h = h[(h['Время'].dt.date >= rng[0]) & (h['Время'].dt.date <= rng[1])]
        
        st.metric("ИТОГО ВЫДАНО ЗА ПЕРИОД", f"{h['Литры'].sum()} л")
        st.dataframe(h.sort_values(by='Время', ascending=False), use_container_width=True)
    else: st.info("История пуста")
