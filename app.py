import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime
import io

# Настройка страницы
st.set_page_config(page_title="MILK SYSTEM", layout="centered")

# Дизайн (Черно-белый, контрастный)
st.markdown("""
    <style>
    [data-testid="stAppViewContainer"] { background-color: #ffffff !important; }
    h1, h2, h3, p, span, label { color: #000000 !important; }
    .stButton>button { background-color: #000000 !important; color: white !important; width: 100%; height: 3.5em; font-size: 18px; font-weight: bold; border-radius: 8px; }
    div[data-testid="stMetricValue"] { color: #000000 !important; font-size: 40px !important; font-weight: 900 !important; }
    .emp-info { text-align: center; margin-bottom: 20px; border-bottom: 1px solid #eee; padding-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

DB_NAME = "milk_factory.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Добавляем колонку hours в таблицу
    c.execute('''CREATE TABLE IF NOT EXISTS employees 
                 (kod TEXT PRIMARY KEY, fio TEXT, position TEXT, days INTEGER, hours REAL, total_liters REAL, remaining_liters REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS history 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, kod TEXT, fio TEXT, amount REAL, date TEXT)''')
    conn.commit()
    conn.close()

init_db()

menu = st.sidebar.radio("МЕНЮ", ["ВЫДАЧА", "ОТЧЕТЫ", "АДМИН"])

# --- 1. ВЫДАЧА ---
if menu == "ВЫДАЧА":
    st.markdown("<h1 style='text-align: center;'>🥛 ВЫДАЧА</h1>", unsafe_allow_html=True)
    user_kod = st.text_input("ВВЕДИТЕ КОД (QR)", key="user_kod_input")
    
    if user_kod:
        conn = sqlite3.connect(DB_NAME)
        user = pd.read_sql("SELECT * FROM employees WHERE kod = ?", conn, params=(user_kod.strip(),))
        
        if not user.empty:
            u = user.iloc[0]
            # Блок информации о сотруднике
            st.markdown(f"""
                <div class class="emp-info">
                    <h2 style='margin-bottom:0;'>{u['fio']}</h2>
                    <p style='font-size:18px; margin-top:5px;'>{u['position']}</p>
                    <p style='font-weight:bold;'>Отработано: {u['days']} дн. ({u['hours']} ч.)</p>
                </div>
            """, unsafe_allow_html=True)
            
            c1, c2 = st.columns(2)
            # Заменил "НОРМА" на "ЛИТРЫ" по твоей просьбе
            c1.metric("ЛИТРЫ", f"{u['total_liters']} л")
            c2.metric("ОСТАТОК", f"{u['remaining_liters']} л")
            
            if u['remaining_liters'] > 0:
                amount = st.number_input("Сколько литров выдать?", 0.5, float(u['remaining_liters']), step=0.5)
                if st.button("ПОДТВЕРДИТЬ ВЫДАЧУ"):
                    new_rem = u['remaining_liters'] - amount
                    cur = conn.cursor()
                    cur.execute("UPDATE employees SET remaining_liters = ? WHERE kod = ?", (new_rem, u['kod']))
                    cur.execute("INSERT INTO history (kod, fio, amount, date) VALUES (?, ?, ?, ?)", 
                                (u['kod'], u['fio'], amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                    conn.commit()
                    st.success("Выдано!")
                    st.rerun()
            else:
                st.error("ОСТАТОК 0")
        else:
            st.error("СОТРУДНИК НЕ НАЙДЕН")
        conn.close()

# --- 2. ОТЧЕТЫ ---
elif menu == "ОТЧЕТЫ":
    st.title("📊 Статистика")
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql("SELECT date as 'Дата', kod as 'Код', fio as 'ФИО', amount as 'Литры' FROM history ORDER BY id DESC", conn)
    
    if not df.empty:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        st.download_button("📥 СКАЧАТЬ ОТЧЕТ (EXCEL)", data=output.getvalue(), file_name="milk_report.xlsx")
        st.dataframe(df, use_container_width=True)
        
        if st.checkbox("Удалить историю?"):
            if st.button("ОЧИСТИТЬ СТАТИСТИКУ"):
                conn.execute("DELETE FROM history")
                conn.commit()
                st.rerun()
    else:
        st.info("История пуста")
    conn.close()

# --- 3. АДМИН ---
elif menu == "АДМИН":
    st.title("⚙️ Загрузка базы")
    uploaded_file = st.file_uploader("Загрузите файл .xlsx", type=["xlsx"])
    
    if uploaded_file and st.button("ОБНОВИТЬ ВСЕ ЛИСТЫ"):
        try:
            excel_data = pd.ExcelFile(uploaded_file)
            total_count = 0
            
            conn = sqlite3.connect(DB_NAME)
            cur = conn.cursor()
            cur.execute("DELETE FROM employees")
            
            for sheet_name in excel_data.sheet_names:
                df_raw = excel_data.parse(sheet_name)
                header_idx = -1
                for i in range(len(df_raw)):
                    row_values = [str(val).strip() for val in df_raw.iloc[i].values]
                    if 'Сотрудник' in row_values and 'Код' in row_values:
                        header_idx = i
                        break
                
                if header_idx != -1:
                    df_final = excel_data.parse(sheet_name, skiprows=header_idx + 1)
                    df_final.columns = [str(c).strip() for c in df_final.columns]
                    
                    for _, row in df_final.iterrows():
                        if pd.notna(row.get('Код')) and pd.notna(row.get('Сотрудник')):
                            try:
                                clean_kod = str(int(float(row['Код'])))
                                clean_fio = str(row['Сотрудник']).strip()
                                clean_pos = str(row.get('Должность', '-')).strip()
                                clean_days = int(row.get('Дней', 0))
                                clean_hours = float(row.get('Часов', 0)) # Добавили чтение часов
                                clean_litr = float(row.get('Литр', 0))
                                
                                cur.execute("INSERT OR REPLACE INTO employees VALUES (?, ?, ?, ?, ?, ?, ?)",
                                            (clean_kod, clean_fio, clean_pos, clean_days, clean_hours, clean_litr, clean_litr))
                                total_count += 1
                            except:
                                continue
            
            conn.commit()
            conn.close()
            st.success(f"Успешно! Загружено человек: {total_count}")
            st.balloons()
        except Exception as e:
            st.error(f"Ошибка: {e}")
