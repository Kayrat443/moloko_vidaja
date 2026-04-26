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
    .status-box { padding: 10px; border-radius: 5px; margin-bottom: 10px; border: 1px solid #ccc; background-color: #e9ecef; }
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
    c.execute('''CREATE TABLE IF NOT EXISTS last_upload_log 
                 (kod TEXT, added_amount REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS archives 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, filename TEXT, data TEXT, date TEXT)''')
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
        if data: 
            scanned_kod = str(data).strip()
            st.toast(f"Код {scanned_kod} считан!")

    user_kod = st.text_input("ВВЕДИТЕ КОД СОТРУДНИКА", value=scanned_kod)
    if user_kod:
        conn = sqlite3.connect(DB_NAME)
        user = pd.read_sql("SELECT * FROM employees WHERE kod = ?", conn, params=(user_kod.strip(),))
        if not user.empty:
            u = user.iloc[0]
            st.markdown(f"""
                <div class="emp-info">
                    <h2 style='margin:0;'>{u['fio']}</h2>
                    <p>{u['position']} | {u['days']} дн. ({u['hours']} ч.)</p>
                    <hr>
                    <p style='color:blue;'>Остаток с прошлого: {u['prev_left']} л | Новое: {u['total_liters']} л</p>
                </div>
            """, unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            c1.metric("ОБЩИЙ ОСТАТОК", f"{u['remaining_liters']} л")
            c2.metric("ВЫДАНО", f"{(u['prev_left'] + u['total_liters']) - u['remaining_liters']:.1f} л")
            
            if u['remaining_liters'] > 0:
                amount = st.number_input("Сколько литров выдать?", 0.5, float(u['remaining_liters']), step=0.5)
                if st.button("ПОДТВЕРДИТЬ ВЫДАЧУ"):
                    new_rem = u['remaining_liters'] - amount
                    cur = conn.cursor()
                    cur.execute("UPDATE employees SET remaining_liters = ? WHERE kod = ?", (new_rem, u['kod']))
                    cur.execute("INSERT INTO history (kod, fio, amount, date) VALUES (?, ?, ?, ?)", 
                                (u['kod'], u['fio'], amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                    conn.commit()
                    st.success(f"Успешно выдано {amount} л!")
                    st.rerun()
            else: st.error("На балансе 0 литров.")
        else: st.error("Код не найден в базе.")
        conn.close()

# --- 2. ОТЧЕТЫ ---
elif menu == "ОТЧЕТЫ":
    st.title("📊 Статистика")
    conn = sqlite3.connect(DB_NAME)
    t1, t2 = st.tabs(["ТЕКУЩАЯ ВЫДАЧА", "АРХИВЫ"])
    
    with t1:
        df = pd.read_sql("SELECT date as 'Дата', kod as 'Код', fio as 'ФИО', amount as 'Литры' FROM history ORDER BY id DESC", conn)
        if not df.empty:
            st.dataframe(df, use_container_width=True)
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            st.download_button("📥 СКАЧАТЬ В EXCEL", data=buf.getvalue(), file_name="current_report.xlsx")
            
            if st.checkbox("Очистить текущую историю"):
                if st.button("УДАЛИТЬ ТЕКУЩИЕ ЗАПИСИ"):
                    conn.execute("DELETE FROM history")
                    conn.commit()
                    st.success("История очищена")
                    st.rerun()
        else: st.info("Нет текущих выдач")

    with t2:
        archives = pd.read_sql("SELECT id, filename, date FROM archives ORDER BY id DESC", conn)
        if archives.empty: st.info("Архивов пока нет")
        for _, arch in archives.iterrows():
            col_a, col_b = st.columns([4, 1])
            with col_a:
                with st.expander(f"📁 {arch['filename']}"):
                    res = conn.execute("SELECT data FROM archives WHERE id = ?", (arch['id'],)).fetchone()
                    arch_df = pd.read_json(io.StringIO(res[0]))
                    st.dataframe(arch_df, use_container_width=True)
                    
                    buf_a = io.BytesIO()
                    with pd.ExcelWriter(buf_a, engine='openpyxl') as writer:
                        arch_df.to_excel(writer, index=False)
                    st.download_button(f"Скачать {arch['id']}", data=buf_a.getvalue(), file_name=f"{arch['filename']}.xlsx", key=f"btn_{arch['id']}")
            with col_b:
                if st.button("🗑️", key=f"del_arch_{arch['id']}", help="Удалить этот архив"):
                    conn.execute("DELETE FROM archives WHERE id = ?", (arch['id'],))
                    conn.commit()
                    st.toast("Архив удален!")
                    st.rerun()
    conn.close()

# --- 3. АДМИН ---
elif menu == "АДМИН":
    st.title("⚙️ Админ-панель")
    
    # ОТКАТ
    st.subheader("1. Откат изменений")
    if st.button("⏪ ОТМЕНИТЬ ПОСЛЕДНЮЮ ЗАГРУЗКУ EXCEL"):
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        logs = cur.execute("SELECT kod, added_amount FROM last_upload_log").fetchall()
        if logs:
            for kod, amt in logs:
                cur.execute("UPDATE employees SET remaining_liters = remaining_liters - ?, total_liters = total_liters - ? WHERE kod = ?", (amt, amt, kod))
            cur.execute("DELETE FROM last_upload_log")
            conn.commit()
            st.success("Последняя загрузка отменена. Литры вычтены.")
        else: st.info("Нечего отменять.")
        conn.close()

    st.divider()
    
    # ЗАГРУЗКА
    st.subheader("2. Загрузка нового месяца")
    uploaded_file = st.file_uploader("Выберите .xlsx файл", type=["xlsx"])
    if uploaded_file and st.button("🚀 ЗАГРУЗИТЬ И ОБНОВИТЬ БАЗУ"):
        with st.spinner('Обработка...'):
            try:
                conn = sqlite3.connect(DB_NAME)
                # Архивируем текущую выдачу
                curr_h = pd.read_sql("SELECT * FROM history", conn)
                if not curr_h.empty:
                    arch_name = f"Отчет_{datetime.now().strftime('%d-%m-%Y_%H-%M')}"
                    conn.execute("INSERT INTO archives (filename, data, date) VALUES (?, ?, ?)", 
                                 (arch_name, curr_h.to_json(), datetime.now().strftime("%Y-%m-%d %H:%M")))
                    conn.execute("DELETE FROM history")

                excel_data = pd.ExcelFile(uploaded_file)
                cur = conn.cursor()
                cur.execute("DELETE FROM last_upload_log")
                count_upd, count_new = 0, 0
                
                for sheet in excel_data.sheet_names:
                    df_raw = excel_data.parse(sheet)
                    h_idx = -1
                    for i in range(len(df_raw)):
                        row = [str(v).strip().lower() for v in df_raw.iloc[i].values]
                        if 'сотрудник' in row and 'код' in row: h_idx = i; break
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
                                count_upd += 1
                            else:
                                cur.execute("INSERT INTO employees VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                            (clean_kod, str(fio), str(r.get('должность','-')), int(r.get('дней',0)), float(r.get('часов',0)), 0.0, new_lit, new_lit))
                                count_new += 1
                            cur.execute("INSERT INTO last_upload_log VALUES (?, ?)", (clean_kod, new_lit))
                
                conn.commit()
                conn.close()
                st.success(f"ГОТОВО! Обновлено: {count_upd}, Добавлено новых: {count_new}")
                st.balloons()
            except Exception as e: st.error(f"Ошибка: {e}")

    st.divider()
    
    # ПОЛНЫЙ СБРОС
    st.subheader("3. Сброс системы")
    if st.button("🔥 УДАЛИТЬ ВООБЩЕ ВСЁ"):
        st.session_state['kill_all'] = True
    
    if st.session_state.get('kill_all'):
        st.error("ВНИМАНИЕ! Это действие удалит всех сотрудников и все архивы навсегда.")
        if st.checkbox("Я подтверждаю полное уничтожение базы"):
            if st.button("ПОДТВЕРДИТЬ"):
                c = sqlite3.connect(DB_NAME)
                c.execute("DELETE FROM employees"); c.execute("DELETE FROM history")
                c.execute("DELETE FROM archives"); c.execute("DELETE FROM last_upload_log")
                c.commit(); c.close()
                st.session_state['kill_all'] = False
                st.success("Система полностью очищена.")
                st.rerun()
