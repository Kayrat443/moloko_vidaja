import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime

# Настройка страницы
st.set_page_config(page_title="MILK SYSTEM", layout="centered")

# --- СТРОГИЙ ДИЗАЙН ДЛЯ ПЛАНШЕТА ---
st.markdown("""
    <style>
    [data-testid="stAppViewContainer"] { background-color: #ffffff !important; }
    h1, h2, h3, p, span, label { color: #000000 !important; font-family: 'Arial', sans-serif; }
    .stButton>button { 
        background-color: #000000 !important; color: white !important; 
        width: 100%; height: 3em; font-size: 20px; font-weight: bold; border-radius: 8px;
    }
    div[data-testid="stMetric"] { 
        border: 2px solid #000000; padding: 15px; border-radius: 10px; text-align: center; 
    }
    div[data-testid="stMetricValue"] { color: #000000 !important; font-size: 40px !important; font-weight: 900 !important; }
    div[data-testid="stMetricLabel"] { color: #555555 !important; font-size: 18px !important; }
    </style>
    """, unsafe_allow_html=True)

# --- РАБОТА С БАЗОЙ ДАННЫХ (SQLite) ---
DB_NAME = "milk_factory.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Таблица сотрудников
    c.execute('''CREATE TABLE IF NOT EXISTS employees 
                 (kod TEXT PRIMARY KEY, fio TEXT, position TEXT, days INTEGER, total_liters REAL, remaining_liters REAL)''')
    # Таблица истории выдач
    c.execute('''CREATE TABLE IF NOT EXISTS history 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, kod TEXT, fio TEXT, amount REAL, date TEXT)''')
    conn.commit()
    conn.close()

init_db()

def get_db_connection():
    return sqlite3.connect(DB_NAME)

# --- МЕНЮ ---
menu = st.sidebar.radio("МЕНЮ", ["ВЫДАЧА", "ОТЧЕТЫ", "АДМИН"])

# --- 1. ВЫДАЧА ---
if menu == "ВЫДАЧА":
    st.markdown("<h1 style='text-align: center;'>🥛 ВЫДАЧА МОЛОКА</h1>", unsafe_allow_html=True)
    
    # Поле ввода (работает и со сканером, и вручную)
    user_kod = st.text_input("ОТСКАНИРУЙТЕ QR ИЛИ ВВЕДИТЕ КОД", placeholder="Например: 6871")
    
    if user_kod:
        conn = get_db_connection()
        user = pd.read_sql(f"SELECT * FROM employees WHERE kod = '{user_kod}'", conn)
        conn.close()
        
        if not user.empty:
            u = user.iloc[0]
            st.markdown(f"<h2 style='text-align: center;'>{u['fio']}</h2>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center;'>{u['position']} | Отработано: {u['days']} дн.</p>", unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            col1.metric("НОРМА", f"{u['total_liters']} л")
            col2.metric("ОСТАТОК", f"{u['remaining_liters']} л")
            
            if u['remaining_liters'] > 0:
                amount = st.number_input("Сколько литров выдать?", 0.5, float(u['remaining_liters']), step=0.5)
                if st.button("ПОДТВЕРДИТЬ ВЫДАЧУ"):
                    new_rem = u['remaining_liters'] - amount
                    conn = get_db_connection()
                    cur = conn.cursor()
                    # Обновляем остаток
                    cur.execute("UPDATE employees SET remaining_liters = ? WHERE kod = ?", (new_rem, user_kod))
                    # Записываем в историю
                    cur.execute("INSERT INTO history (kod, fio, amount, date) VALUES (?, ?, ?, ?)", 
                                (user_kod, u['fio'], amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                    conn.commit()
                    conn.close()
                    st.success(f"Выдано {amount} л. Остаток: {new_rem} л")
                    st.rerun()
            else:
                st.error("ВЫДАЧА ЗАПРЕЩЕНА: ОСТАТОК 0")
        else:
            st.error("СОТРУДНИК НЕ НАЙДЕН В БАЗЕ")

# --- 2. ОТЧЕТЫ ---
elif menu == "ОТЧЕТЫ":
    st.title("📊 История выдачи")
    conn = get_db_connection()
    hist_df = pd.read_sql("SELECT fio as 'ФИО', amount as 'Литры', date as 'Дата' FROM history ORDER BY id DESC", conn)
    conn.close()
    
    if not hist_df.empty:
        st.write(f"**Всего выдано за месяц:** {hist_df['Литры'].sum()} л")
        st.dataframe(hist_df, use_container_width=True)
    else:
        st.info("История пока пуста")

# --- 3. АДМИН (ЗАГРУЗКА БАЗЫ) ---
elif menu == "АДМИН":
    st.title("⚙️ Администрирование")
    
    st.subheader("Обновление базы на новый месяц")
    uploaded_file = st.file_uploader("Загрузите Excel-файл (колонки: Сотрудник, Код, Должность, Дней, Литр)", type=["xlsx"])
    
    if uploaded_file:
        if st.button("ОБНУЛИТЬ СТАРУЮ БАЗУ И ЗАГРУЗИТЬ НОВУЮ"):
            try:
                df = pd.read_excel(uploaded_file)
                # Чистим названия колонок от пробелов
                df.columns = [c.strip() for c in df.columns]
                
                # Проверка нужных колонок
                required = ['Сотрудник', 'Код', 'Должность', 'Дней', 'Литр']
                if all(col in df.columns for col in required):
                    conn = get_db_connection()
                    cur = conn.cursor()
                    # Удаляем старых сотрудников
                    cur.execute("DELETE FROM employees")
                    # Загружаем новых
                    for _, row in df.iterrows():
                        cur.execute("INSERT INTO employees (kod, fio, position, days, total_liters, remaining_liters) VALUES (?, ?, ?, ?, ?, ?)",
                                    (str(row['Код']), row['Сотрудник'], row['Должность'], int(row['Дней']), float(row['Литр']), float(row['Литр'])))
                    conn.commit()
                    conn.close()
                    st.success(f"Успешно загружено {len(df)} сотрудников!")
                else:
                    st.error(f"В файле нет нужных колонок! Нужно: {', '.join(required)}")
            except Exception as e:
                st.error(f"Ошибка при чтении файла: {e}")
    
    if st.checkbox("Показать список всех сотрудников в базе"):
        conn = get_db_connection()
        all_emp = pd.read_sql("SELECT * FROM employees", conn)
        conn.close()
        st.dataframe(all_emp)
