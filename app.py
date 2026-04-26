import streamlit as st
import pandas as pd
import sqlite3
import os
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
    div[data-testid="stMetricValue"] { color: #000000 !important; font-size: 40px !important; font-weight: 900 !important; }
    .stDataFrame { border: 1px solid #eeeeee; }
    </style>
    """, unsafe_allow_html=True)

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

# --- 1. ВЫДАЧА ---
if menu == "ВЫДАЧА":
    st.markdown("<h1 style='text-align: center;'>🥛 ВЫДАЧА МОЛОКА</h1>", unsafe_allow_html=True)
    user_kod = st.text_input("ВВЕДИТЕ КОД СОТРУДНИКА", placeholder="Например: 6871")
    
    if user_kod:
        conn = sqlite3.connect(DB_NAME)
        user = pd.read_sql(f"SELECT * FROM employees WHERE kod = '{user_kod}'", conn)
        
        if not user.empty:
            u = user.iloc[0]
            st.markdown(f"<h2 style='text-align: center;'>{u['fio']}</h2>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center;'>{u['position']}</p>", unsafe_allow_html=True)
            
            c1, c2 = st.columns(2)
            c1.metric("НОРМА", f"{u['total_liters']} л")
            c2.metric("ОСТАТОК", f"{u['remaining_liters']} л")
            
            if u['remaining_liters'] > 0:
                amount = st.number_input("Сколько выдать?", 0.5, float(u['remaining_liters']), step=0.5)
                if st.button("ПОДТВЕРДИТЬ ВЫДАЧУ"):
                    new_rem = u['remaining_liters'] - amount
                    cur = conn.cursor()
                    cur.execute("UPDATE employees SET remaining_liters = ? WHERE kod = ?", (new_rem, user_kod))
                    cur.execute("INSERT INTO history (kod, fio, amount, date) VALUES (?, ?, ?, ?)", 
                                (user_kod, u['fio'], amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                    conn.commit()
                    st.success(f"Выдано {amount} л. Остаток обновлен.")
                    st.rerun()
            else:
                st.error("БАЛАНС 0. ВЫДАЧА НЕВОЗМОЖНА.")
        else:
            st.error("СОТРУДНИК С ТАКИМ КОДОМ НЕ НАЙДЕН")
        conn.close()

# --- 2. ОТЧЕТЫ ---
elif menu == "ОТЧЕТЫ":
    st.title("📊 Статистика и Отчеты")
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql("SELECT date as 'Дата', kod as 'Код', fio as 'ФИО', amount as 'Литры' FROM history ORDER BY id DESC", conn)
    
    if not df.empty:
        st.write(f"**Всего выдано:** {df['Литры'].sum()} л")
        
        # Скачивание в Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Sheet1')
        st.download_button(label="📥 СКАЧАТЬ В EXCEL", data=output.getvalue(), file_name=f"report_milk_{datetime.now().date()}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        
        st.dataframe(df, use_container_width=True)
        
        # Очистка истории
        st.divider()
        if st.checkbox("Я хочу удалить всю историю выдач"):
            if st.button("⚠️ УДАЛИТЬ ВСЮ СТАТИСТИКУ"):
                cur = conn.cursor()
                cur.execute("DELETE FROM history")
                conn.commit()
                st.warning("История очищена.")
                st.rerun()
    else:
        st.info("История выдач пока пуста.")
    conn.close()

# --- 3. АДМИН ---
elif menu == "АДМИН":
    st.title("⚙️ Администрирование")
    st.write("Загрузите файл Excel. Программа обработает все листы в файле.")
    
    uploaded_file = st.file_uploader("Выбрать файл Excel", type=["xlsx"])
    
    if uploaded_file and st.button("ОБНОВИТЬ БАЗУ СОТРУДНИКОВ"):
        try:
            # Читаем все листы сразу
            all_sheets = pd.read_excel(uploaded_file, sheet_name=None)
            total_added = 0
            
            conn = sqlite3.connect(DB_NAME)
            cur = conn.cursor()
            cur.execute("DELETE FROM employees") # Чистим старых перед новой загрузкой
            
            for sheet_name, df_raw in all_sheets.items():
                # Ищем заголовок в каждом листе
                header_row = -1
                for i, row in df_raw.iterrows():
                    if 'Сотрудник' in row.values and 'Код' in row.values:
                        header_row = i
                        break
                
                if header_row != -1:
                    df = pd.read_excel(uploaded_file, sheet_name=sheet_name, skiprows=header_row + 1)
                    df.columns = [str(c).strip() for c in df.columns]
                    
                    for _, r in df.iterrows():
                        if pd.notna(r.get('Код')) and pd.notna(r.get('Сотрудник')):
                            try:
                                # Преобразуем код в строку без .0
                                k = str(int(r['Код']))
                                cur.execute("INSERT OR REPLACE INTO employees VALUES (?, ?, ?, ?, ?, ?)",
                                            (k, str(r['Сотрудник']), str(r['Должность']), int(r['Дней']), float(r['Литр']), float(r['Литр'])))
                                total_added += 1
                            except:
                                continue
            
            conn.commit()
            conn.close()
            st.success(f"Готово! Загружено {total_added} чел. из всех листов Excel.")
        except Exception as e:
            st.error(f"Ошибка: {e}")
