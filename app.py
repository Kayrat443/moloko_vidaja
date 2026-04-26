import streamlit as st
import pandas as pd
import sqlite3
import os
import cv2
import numpy as np
from datetime import datetime

# Настройка страницы
st.set_page_config(page_title="MILK SYSTEM", layout="centered")

# Дизайн
st.markdown("""
    <style>
    [data-testid="stAppViewContainer"] { background-color: #ffffff !important; }
    h1, h2, h3, p, span, label { color: #000000 !important; }
    .stButton>button { background-color: #000000 !important; color: white !important; width: 100%; height: 3em; font-size: 20px; font-weight: bold; }
    div[data-testid="stMetricValue"] { color: #000000 !important; font-size: 40px !important; font-weight: 900 !important; }
    </style>
    """, unsafe_allow_html=True)

# База данных
DB_NAME = "milk_factory.db"
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS employees 
                 (kod TEXT PRIMARY KEY, fio TEXT, position TEXT, days INTEGER, total_liters REAL, remaining_liters REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS history 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, kod TEXT, fio TEXT, amount REAL, date TEXT)''')
    conn.commit()
    conn.close()

init_db()

menu = st.sidebar.radio("МЕНЮ", ["ВЫДАЧА", "ОТЧЕТЫ", "АДМИН"])

if menu == "ВЫДАЧА":
    st.markdown("<h1 style='text-align: center;'>🥛 ВЫДАЧА</h1>", unsafe_allow_html=True)
    user_kod = st.text_input("КОД СОТРУДНИКА (QR)")
    if user_kod:
        conn = sqlite3.connect(DB_NAME)
        user = pd.read_sql(f"SELECT * FROM employees WHERE kod = '{user_kod}'", conn)
        if not user.empty:
            u = user.iloc[0]
            st.markdown(f"<h2 style='text-align: center;'>{u['fio']}</h2>", unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            c1.metric("НОРМА", f"{u['total_liters']} л")
            c2.metric("ОСТАТОК", f"{u['remaining_liters']} л")
            if u['remaining_liters'] > 0:
                amount = st.number_input("Сколько выдать?", 0.5, float(u['remaining_liters']), step=0.5)
                if st.button("ПОДТВЕРДИТЬ"):
                    new_rem = u['remaining_liters'] - amount
                    cur = conn.cursor()
                    cur.execute("UPDATE employees SET remaining_liters = ? WHERE kod = ?", (new_rem, user_kod))
                    cur.execute("INSERT INTO history (kod, fio, amount, date) VALUES (?, ?, ?, ?)", 
                                (user_kod, u['fio'], amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                    conn.commit()
                    st.success("Выдано!")
                    st.rerun()
        else:
            st.error("Не найден")
        conn.close()

elif menu == "ОТЧЕТЫ":
    st.title("📊 Отчет")
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql("SELECT fio, amount, date FROM history ORDER BY id DESC", conn)
    st.dataframe(df, use_container_width=True)
    conn.close()

elif menu == "АДМИН":
    st.title("⚙️ Админ")
    uploaded_file = st.file_uploader("Загрузить Excel", type=["xlsx"])
    if uploaded_file and st.button("ОБНОВИТЬ БАЗУ"):
        try:
            df_raw = pd.read_excel(uploaded_file)
            header_row = 0
            for i, row in df_raw.iterrows():
                if 'Сотрудник' in row.values or 'Код' in row.values:
                    header_row = i + 1
                    break
            df = pd.read_excel(uploaded_file, skiprows=header_row)
            df.columns = [str(c).strip() for c in df.columns]
            
            conn = sqlite3.connect(DB_NAME)
            cur = conn.cursor()
            cur.execute("DELETE FROM employees")
            for _, r in df.iterrows():
                if pd.notna(r['Код']):
                    cur.execute("INSERT INTO employees VALUES (?, ?, ?, ?, ?, ?)",
                                (str(int(r['Код'])), r['Сотрудник'], r['Должность'], int(r['Дней']), float(r['Литр']), float(r['Литр'])))
            conn.commit()
            conn.close()
            st.success("База обновлена!")
        except Exception as e:
            st.error(f"Ошибка: {e}")
