import streamlit as st
import pandas as pd
import sqlite3
import os
import cv2
import numpy as np
from datetime import datetime
import io

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
    # total_liters - это сколько начислено в ПОСЛЕДНЕМ месяце
    # remaining_liters - это ОБЩИЙ ОСТАТОК (старое + новое)
    c.execute('''CREATE TABLE IF NOT EXISTS employees 
                 (kod TEXT PRIMARY KEY, fio TEXT, position TEXT, days INTEGER, hours REAL, 
                  prev_left REAL, total_liters REAL, remaining_liters REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS history 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, kod TEXT, fio TEXT, amount REAL, date TEXT, period TEXT)''')
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
                    <p>{u['position']} | {u['days']} дн. ({u['hours']} ч.)</p>
                    <p style='color: blue;'>Остаток с прошлого месяца: {u['prev_left']} л</p>
                    <p style='color: green;'>Начислено в этом месяце: {u['total_liters']} л</p>
                </div>
            """, unsafe_allow_html=True)
            
            c1, c2 = st.columns(2)
            c1.metric("ОБЩИЙ ДОСТУП", f"{u['remaining_liters']} л")
            c2.metric("ВСЕГО ВЫДАНО", f"{(u['prev_left'] + u['total_liters']) - u['remaining_liters']:.1f} л")
            
            if u['remaining_liters'] > 0:
                amount = st.number_input("Выдать литров:", 0.5, float(u['remaining_liters']), step=0.5)
                if st.button("ПОДТВЕРДИТЬ ВЫДАЧУ"):
                    new_rem = u['remaining_liters'] - amount
                    cur = conn.cursor()
                    cur.execute("UPDATE employees SET remaining_liters = ? WHERE kod = ?", (new_rem, u['kod']))
                    cur.execute("INSERT INTO history (kod, fio, amount, date, period) VALUES (?, ?, ?, ?, ?)", 
                                (u['kod'], u['fio'], amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), datetime.now().strftime("%Y-%m")))
                    conn.commit()
                    st.success("Выдано!")
                    st.rerun()
        else:
            if user_kod: st.error("СОТРУДНИК НЕ НАЙДЕН")
        conn.close()

# --- 2. ОТЧЕТЫ ---
elif menu == "ОТЧЕТЫ":
    st.title("📊 Статистика")
    conn = sqlite3.connect(DB_NAME)
    
    tab1, tab2 = st.tabs(["Текущий месяц", "Архив (Старая статистика)"])
    
    with tab1:
        current_period = datetime.now().strftime("%Y-%m")
        df = pd.read_sql("SELECT date as 'Дата', kod as 'Код', fio as 'ФИО', amount as 'Литры' FROM history WHERE period = ? ORDER BY id DESC", conn, params=(current_period,))
        if not df.empty:
            st.dataframe(df, use_container_width=True)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            st.download_button("📥 СКАЧАТЬ ТЕКУЩИЙ ОТЧЕТ", data=output.getvalue(), file_name=f"milk_current_{current_period}.xlsx")
        else:
            st.info("В этом месяце выдач еще не было")

    with tab2:
        df_old = pd.read_sql("SELECT date as 'Дата', kod as 'Код', fio as 'ФИО', amount as 'Литры', period as 'Период' FROM history WHERE period != ? ORDER BY id DESC", conn, params=(current_period,))
        if not df_old.empty:
            st.dataframe(df_old, use_container_width=True)
        else:
            st.info("Архив пуст")
    
    conn.close()

# --- 3. АДМИН ---
elif menu == "АДМИН":
    st.title("⚙️ Обновление базы (Новый месяц)")
    st.warning("При загрузке нового файла остатки сотрудников СОХРАНЯЮТСЯ и плюсуются к новым литрам.")
    
    uploaded_file = st.file_uploader("Загрузите новый Excel .xlsx", type=["xlsx"])
    
    if uploaded_file and st.button("ЗАГРУЗИТЬ И ПРИБАВИТЬ ЛИТРЫ"):
        try:
            excel_data = pd.ExcelFile(uploaded_file)
            added_count = 0
            conn = sqlite3.connect(DB_NAME)
            cur = conn.cursor()
            
            for sheet_name in excel_data.sheet_names:
                df_raw = excel_data.parse(sheet_name)
                header_idx = -1
                for i in range(len(df_raw)):
                    row_vals = [str(v).strip().lower() for v in df_raw.iloc[i].values]
                    if 'сотрудник' in row_vals and 'код' in row_vals:
                        header_idx = i
                        break
                
                if header_idx != -1:
                    df_final = excel_data.parse(sheet_name, skiprows=header_idx + 1)
                    df_final.columns = [str(c).strip().lower() for c in df_final.columns]
                    
                    for _, row in df_final.iterrows():
                        fio = row.get('сотрудник')
                        kod = row.get('код')
                        if pd.isna(kod) or pd.isna(fio): continue
                        
                        clean_kod = str(int(float(kod)))
                        new_liters = float(row.get('литр', 0))
                        
                        # ПРОВЕРЯЕМ, ЕСТЬ ЛИ ОН В БАЗЕ
                        cur.execute("SELECT remaining_liters FROM employees WHERE kod = ?", (clean_kod,))
                        existing_user = cur.fetchone()
                        
                        if existing_user:
                            # Если есть, прибавляем к остатку
                            old_rem = existing_user[0]
                            total_rem = old_rem + new_liters
                            cur.execute("""UPDATE employees SET fio=?, position=?, days=?, hours=?, 
                                           prev_left=?, total_liters=?, remaining_liters=? WHERE kod=?""",
                                        (str(fio), str(row.get('должность','-')), int(row.get('дней',0)), 
                                         float(row.get('часов',0)), old_rem, new_liters, total_rem, clean_kod))
                        else:
                            # Если новый человек
                            cur.execute("INSERT INTO employees VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                        (clean_kod, str(fio), str(row.get('должность','-')), int(row.get('дней',0)), 
                                         float(row.get('часов',0)), 0.0, new_liters, new_liters))
                        added_count += 1
            
            conn.commit()
            conn.close()
            st.success(f"База обновлена! Обработано {added_count} чел. Остатки суммированы.")
        except Exception as e:
            st.error(f"Ошибка: {e}")
