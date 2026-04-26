import streamlit as st
import pandas as pd
import sqlite3
import os
import cv2
import numpy as np
from datetime import datetime
import io

# Настройка страницы
st.set_page_config(page_title="MILK SYSTEM", layout="centered")

# Дизайн
st.markdown("""
    <style>
    [data-testid="stAppViewContainer"] { background-color: #ffffff !important; }
    h1, h2, h3, p, span, label { color: #000000 !important; }
    .stButton>button { background-color: #000000 !important; color: white !important; width: 100%; height: 3.5em; font-size: 18px; font-weight: bold; border-radius: 8px; }
    div[data-testid="stMetricValue"] { color: #000000 !important; font-size: 35px !important; font-weight: 900 !important; }
    .emp-info { text-align: center; margin-bottom: 20px; border: 1px solid #000; padding: 15px; border-radius: 10px; background-color: #f8f9fa; }
    </style>
    """, unsafe_allow_html=True)

DB_NAME = "milk_factory.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Создаем таблицы если их нет
    c.execute('''CREATE TABLE IF NOT EXISTS employees 
                 (kod TEXT PRIMARY KEY, fio TEXT, position TEXT, days INTEGER, hours REAL, 
                  prev_left REAL, total_liters REAL, remaining_liters REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS history 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, kod TEXT, fio TEXT, amount REAL, date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS last_upload_log 
                 (kod TEXT, added_amount REAL)''')
    conn.commit()
    conn.close()

init_db()

menu = st.sidebar.radio("МЕНЮ", ["ВЫДАЧА", "ОТЧЕТЫ", "АДМИН"])

# --- 1. ВЫДАЧА ---
if menu == "ВЫДАЧА":
    st.markdown("<h1 style='text-align: center;'>🥛 ВЫДАЧА</h1>", unsafe_allow_html=True)
    
    img_file = st.camera_input("СКАНЕР QR")
    scanned_kod = ""
    if img_file:
        file_bytes = np.asarray(bytearray(img_file.read()), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, 1)
        detector = cv2.QRCodeDetector()
        data, _, _ = detector.detectAndDecode(img)
        if data: scanned_kod = str(data).strip()

    user_kod = st.text_input("ВВЕДИТЕ КОД СОТРУДНИКА", value=scanned_kod)
    
    if user_kod:
        conn = sqlite3.connect(DB_NAME)
        user = pd.read_sql("SELECT * FROM employees WHERE kod = ?", conn, params=(user_kod.strip(),))
        if not user.empty:
            u = user.iloc[0]
            st.markdown(f"""
                <div class="emp-info">
                    <h2 style='margin:0;'>{u['fio']}</h2>
                    <p style='color:#555;'>{u['position']} | {u['days']} дн. ({u['hours']} ч.)</p>
                    <hr>
                    <p style='color:blue;'>Было: {u['prev_left']} л | Новое: {u['total_liters']} л</p>
                </div>
            """, unsafe_allow_html=True)
            
            c1, c2 = st.columns(2)
            c1.metric("ОСТАТОК", f"{u['remaining_liters']} л")
            c2.metric("ВЫДАНО", f"{(u['prev_left'] + u['total_liters']) - u['remaining_liters']:.1f} л")
            
            if u['remaining_liters'] > 0:
                amount = st.number_input("Сколько выдать?", 0.5, float(u['remaining_liters']), step=0.5)
                if st.button("ПОДТВЕРДИТЬ"):
                    new_rem = u['remaining_liters'] - amount
                    cur = conn.cursor()
                    cur.execute("UPDATE employees SET remaining_liters = ? WHERE kod = ?", (new_rem, u['kod']))
                    cur.execute("INSERT INTO history (kod, fio, amount, date) VALUES (?, ?, ?, ?)", 
                                (u['kod'], u['fio'], amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                    conn.commit()
                    st.success("Выдано!")
                    st.rerun()
        else: st.error("Код не найден")
        conn.close()

# --- 2. ОТЧЕТЫ ---
elif menu == "ОТЧЕТЫ":
    st.title("📊 История")
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql("SELECT date as 'Дата', kod as 'Код', fio as 'ФИО', amount as 'Литры' FROM history ORDER BY id DESC", conn)
    st.dataframe(df, use_container_width=True)
    if not df.empty:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        st.download_button("📥 СКАЧАТЬ В EXCEL", data=output.getvalue(), file_name="milk_report.xlsx")
    conn.close()

# --- 3. АДМИН ---
elif menu == "АДМИН":
    st.title("⚙️ Админ")
    
    # КНОПКА ОТМЕНЫ
    if st.button("⏪ ОТМЕНИТЬ ПОСЛЕДНЮЮ ЗАГРУЗКУ EXCEL"):
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        logs = cur.execute("SELECT kod, added_amount FROM last_upload_log").fetchall()
        if logs:
            for kod, amt in logs:
                cur.execute("UPDATE employees SET remaining_liters = remaining_liters - ?, total_liters = total_liters - ? WHERE kod = ?", (amt, amt, kod))
            cur.execute("DELETE FROM last_upload_log")
            conn.commit()
            st.warning("Загрузка отменена. Лишние литры вычтены.")
        else:
            st.info("Нечего отменять.")
        conn.close()

    st.divider()
    
    uploaded_file = st.file_uploader("Загрузить новый месяц (.xlsx)", type=["xlsx"])
    if uploaded_file and st.button("ОБНОВИТЬ И ПРИБАВИТЬ"):
        try:
            excel_data = pd.ExcelFile(uploaded_file)
            conn = sqlite3.connect(DB_NAME)
            cur = conn.cursor()
            cur.execute("DELETE FROM last_upload_log") # Чистим старый лог отмены
            
            total_added = 0
            for sheet in excel_data.sheet_names:
                df_raw = excel_data.parse(sheet)
                h_idx = -1
                for i in range(len(df_raw)):
                    row = [str(v).strip().lower() for v in df_raw.iloc[i].values]
                    if 'сотрудник' in row and 'код' in row:
                        h_idx = i; break
                
                if h_idx != -1:
                    df = excel_data.parse(sheet, skiprows=h_idx + 1)
                    df.columns = [str(c).strip().lower() for c in df.columns]
                    for _, r in df.iterrows():
                        kod, fio = r.get('код'), r.get('сотрудник')
                        if pd.isna(kod) or pd.isna(fio): continue
                        clean_kod = str(int(float(kod)))
                        new_lit = float(r.get('литр', 0))
                        
                        cur.execute("SELECT remaining_liters FROM employees WHERE kod = ?", (clean_kod,))
                        res = cur.fetchone()
                        if res:
                            old_rem = res[0]
                            cur.execute("UPDATE employees SET fio=?, position=?, days=?, hours=?, prev_left=?, total_liters=?, remaining_liters=? WHERE kod=?",
                                        (str(fio), str(r.get('должность','-')), int(r.get('дней',0)), float(r.get('часов',0)), old_rem, new_lit, old_rem + new_lit, clean_kod))
                        else:
                            cur.execute("INSERT INTO employees VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                        (clean_kod, str(fio), str(r.get('должность','-')), int(r.get('дней',0)), float(r.get('часов',0)), 0.0, new_lit, new_lit))
                        
                        cur.execute("INSERT INTO last_upload_log VALUES (?, ?)", (clean_kod, new_lit))
                        total_added += 1
            
            conn.commit()
            conn.close()
            st.success(f"Успешно! Добавлено {total_added} чел.")
            st.balloons()
        except Exception as e:
            st.error(f"Ошибка: {e}")
