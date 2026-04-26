import streamlit as st
import pandas as pd
import sqlite3
import os
import cv2
import numpy as np
from datetime import datetime
import io
import json

st.set_page_config(page_title="MILK SYSTEM", layout="centered")

# --- СТИЛИ ---
st.markdown("""
    <style>
    [data-testid="stAppViewContainer"] { background-color: #ffffff !important; }
    h1, h2, h3, p, span, label { color: #000000 !important; }
    .stButton>button { background-color: #000000 !important; color: white !important; width: 100%; height: 3.5em; font-size: 18px; font-weight: bold; border-radius: 8px; }
    div[data-testid="stMetricValue"] { color: #000000 !important; font-size: 35px !important; font-weight: 900 !important; }
    .emp-info { text-align: center; margin-bottom: 20px; border: 1px solid #000; padding: 10px; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

DB_NAME = "milk_factory.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS employees 
                 (kod TEXT PRIMARY KEY, fio TEXT, position TEXT, days INTEGER, hours REAL, 
                  prev_left REAL, total_liters REAL, remaining_liters REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS history 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, kod TEXT, fio TEXT, amount REAL, date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS archives 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, filename TEXT, data TEXT, date TEXT, 
                  upload_snapshot TEXT)''') # Добавили snapshot для отката
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

    user_kod = st.text_input("КОД СОТРУДНИКА", value=scanned_kod)
    if user_kod:
        conn = sqlite3.connect(DB_NAME)
        user = pd.read_sql("SELECT * FROM employees WHERE kod = ?", conn, params=(user_kod.strip(),))
        if not user.empty:
            u = user.iloc[0]
            st.markdown(f"""
                <div class="emp-info">
                    <h2>{u['fio']}</h2>
                    <p>{u['position']}</p>
                    <p><b>Остаток: {u['remaining_liters']} л</b> (из них {u['total_liters']} л новые)</p>
                </div>
            """, unsafe_allow_html=True)
            amount = st.number_input("Выдать литров:", 0.5, float(u['remaining_liters']), step=0.5)
            if st.button("ПОДТВЕРДИТЬ"):
                new_rem = u['remaining_liters'] - amount
                cur = conn.cursor()
                cur.execute("UPDATE employees SET remaining_liters = ? WHERE kod = ?", (new_rem, u['kod']))
                cur.execute("INSERT INTO history (kod, fio, amount, date) VALUES (?, ?, ?, ?)", 
                            (u['kod'], u['fio'], amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                conn.commit()
                st.success("Готово!")
                st.rerun()
        else: st.error("Код не найден")
        conn.close()

# --- 2. ОТЧЕТЫ ---
elif menu == "ОТЧЕТЫ":
    st.title("📊 Статистика")
    conn = sqlite3.connect(DB_NAME)
    t1, t2 = st.tabs(["ТЕКУЩАЯ", "АРХИВЫ"])
    with t1:
        df = pd.read_sql("SELECT date as 'Дата', kod as 'Код', fio as 'ФИО', amount as 'Литры' FROM history ORDER BY id DESC", conn)
        st.dataframe(df, use_container_width=True)
    with t2:
        archives = pd.read_sql("SELECT id, filename, date FROM archives ORDER BY id DESC", conn)
        for _, arch in archives.iterrows():
            with st.expander(f"📁 {arch['filename']}"):
                res = conn.execute("SELECT data FROM archives WHERE id = ?", (arch['id'],)).fetchone()
                st.dataframe(pd.read_json(res[0]), use_container_width=True)
    conn.close()

# --- 3. АДМИН ---
elif menu == "АДМИН":
    st.title("⚙️ Админ-панель")
    
    # КНОПКА ОТМЕНЫ
    st.subheader("Откат изменений")
    if st.button("⏪ ОТМЕНИТЬ ПОСЛЕДНЮЮ ЗАГРУЗКУ EXCEL"):
        conn = sqlite3.connect(DB_NAME)
        last_arch = conn.execute("SELECT id, data, upload_snapshot FROM archives ORDER BY id DESC LIMIT 1").fetchone()
        
        if last_arch:
            arch_id, old_history_json, snapshot_json = last_arch
            # 1. Возвращаем историю выдач
            conn.execute("DELETE FROM history")
            old_h_df = pd.read_json(old_history_json)
            if not old_h_df.empty:
                old_h_df.to_sql('history', conn, if_exists='append', index=False)
            
            # 2. Возвращаем остатки сотрудников из снимка
            snapshot = json.loads(snapshot_json)
            for kod, rem in snapshot.items():
                conn.execute("UPDATE employees SET remaining_liters = ? WHERE kod = ?", (rem, kod))
            
            # 3. Удаляем этот архив
            conn.execute("DELETE FROM archives WHERE id = ?", (arch_id,))
            conn.commit()
            st.warning("Последняя загрузка отменена. Литры и история возвращены назад.")
            st.rerun()
        else:
            st.error("Нет загрузок для отмены.")
        conn.close()

    st.divider()
    
    st.subheader("Загрузка нового месяца")
    uploaded_file = st.file_uploader("Выберите файл .xlsx", type=["xlsx"])
    
    if uploaded_file:
        if st.button("🚀 НАЧАТЬ ЗАГРУЗКУ И ОБНОВЛЕНИЕ"):
            with st.spinner('Обработка файла... Подождите...'):
                try:
                    conn = sqlite3.connect(DB_NAME)
                    # ДЕЛАЕМ СНИМОК СОСТОЯНИЯ ПЕРЕД ЗАГРУЗКОЙ
                    current_stats = pd.read_sql("SELECT kod, remaining_liters FROM employees", conn)
                    snapshot_dict = dict(zip(current_stats['kod'], current_stats['remaining_liters']))
                    
                    current_hist = pd.read_sql("SELECT * FROM history", conn)
                    
                    # ОБРАБОТКА EXCEL
                    excel_data = pd.ExcelFile(uploaded_file)
                    added = 0
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
                                
                                cur = conn.cursor()
                                cur.execute("SELECT remaining_liters FROM employees WHERE kod = ?", (clean_kod,))
                                res = cur.fetchone()
                                if res:
                                    old_rem = res[0]
                                    cur.execute("UPDATE employees SET fio=?, prev_left=?, total_liters=?, remaining_liters=? WHERE kod=?",
                                                (str(fio), old_rem, new_lit, old_rem + new_lit, clean_kod))
                                else:
                                    cur.execute("INSERT INTO employees (kod,fio,position,days,hours,prev_left,total_liters,remaining_liters) VALUES (?,?,?,?,?,?,?,?)",
                                                (clean_kod, str(fio), str(r.get('должность','-')), int(r.get('дней',0)), float(r.get('часов',0)), 0.0, new_lit, new_lit))
                                added += 1
                    
                    # СОХРАНЯЕМ В АРХИВ ТОЛЬКО ЕСЛИ ОБНОВЛЕНИЕ ПРОШЛО
                    archive_name = f"Загрузка_от_{datetime.now().strftime('%d_%m_%H%M')}"
                    conn.execute("INSERT INTO archives (filename, data, date, upload_snapshot) VALUES (?, ?, ?, ?)", 
                                 (archive_name, current_hist.to_json(), datetime.now().strftime("%Y-%m-%d %H:%M"), json.dumps(snapshot_dict)))
                    conn.execute("DELETE FROM history") # Очистка текущей истории
                    
                    conn.commit()
                    conn.close()
                    st.success(f"УСПЕШНО! Обработано {added} сотрудников. Данные суммированы.")
                    st.balloons()
                except Exception as e: st.error(f"Ошибка: {e}")
