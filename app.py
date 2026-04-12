import streamlit as st
import pandas as pd
import os
from datetime import datetime

# Настройки оформления
st.set_page_config(page_title="Milk Store", page_icon="🥛", layout="centered")

# --- ФУНКЦИИ РАБОТЫ С ДАННЫМИ ---
def load_db():
    # Загружаем основной список
    df = pd.read_excel('itog.xlsx')
    # Если еще нет столбца Остаток, создаем его на основе нормы (Литр)
    if 'Остаток' not in df.columns:
        df['Остаток'] = df['Литр']
    return df

def save_db(df):
    df.to_excel('itog.xlsx', index=False)

def log_transaction(nomer, fio, amount):
    # Записываем историю выдачи в отдельный файл
    log_file = 'history.csv'
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_entry = pd.DataFrame([[now, nomer, fio, amount]], 
                             columns=['Дата_Время', 'ID', 'ФИО', 'Выдано_литров'])
    
    if os.path.exists(log_file):
        new_entry.to_csv(log_file, mode='a', header=False, index=False)
    else:
        new_entry.to_csv(log_file, index=False)

# --- ИНТЕРФЕЙС ---
st.title("🥛 Система выдачи молока")

# Инициализируем базу в сессии
if 'db' not in st.session_state:
    st.session_state.db = load_db()

menu = st.sidebar.selectbox("Навигация", ["🛒 Выдача (Магазин)", "⚙️ Админ-панель", "📊 Статистика"])

if menu == "🛒 Выдача (Магазин)":
    st.subheader("Сканирование сотрудника")
    
    # Поле для ввода номера (сюда будет попадать цифра со сканера или вручную)
    user_id_input = st.text_input("Введите табельный номер или используйте сканер", key="id_input")
    
    if user_id_input:
        db = st.session_state.db
        # Ищем сотрудника
        user_data = db[db['Табельный_Молоко'].astype(str) == str(user_id_input)]
        
        if not user_data.empty:
            idx = user_data.index[0]
            person = user_data.loc[idx]
            
            # Показываем карточку сотрудника
            st.info(f"**Сотрудник:** {person['Сотрудник']}\n\n**Должность:** {person['Должность']}")
            
            col1, col2 = st.columns(2)
            col1.metric("Положено всего", f"{person['Литр']} л")
            col2.metric("Осталось сейчас", f"{person['Остаток']} л", delta_color="normal")
            
            if person['Остаток'] > 0:
                amount_to_give = st.number_input("Сколько литров выдаем?", min_value=0.0, max_value=float(person['Остаток']), step=0.5)
                
                if st.button("✅ ПОДТВЕРДИТЬ ВЫДАЧУ", use_container_width=True):
                    # Обновляем остаток в памяти
                    st.session_state.db.at[idx, 'Остаток'] -= amount_to_give
                    # Сохраняем в файл
                    save_db(st.session_state.db)
                    # Пишем в историю
                    log_transaction(person['Табельный_Молоко'], person['Сотрудник'], amount_to_give)
                    
                    st.success(f"Выдано {amount_to_give} л. Остаток: {st.session_state.db.at[idx, 'Остаток']} л")
                    st.balloons()
            else:
                st.error("Лимит молока исчерпан!")
        else:
            st.warning("Сотрудник не найден. Проверьте номер.")

elif menu == "⚙️ Админ-панель":
    st.subheader("Управление базой")
    
    # Кнопка обновления на месяц
    new_month_val = st.number_input("Установить новую норму всем (литров)", value=10.0)
    if st.button("🔄 Начислить всем на новый месяц"):
        st.session_state.db['Остаток'] = new_month_val
        st.session_state.db['Литр'] = new_month_val
        save_db(st.session_state.db)
        st.success(f"Всем сотрудникам начислено по {new_month_val} литров!")

    st.divider()
    st.write("### Поиск и редактирование")
    search_fio = st.text_input("Поиск по Фамилии")
    if search_fio:
        filtered = st.session_state.db[st.session_state.db['Сотрудник'].str.contains(search_fio, case=False)]
        st.dataframe(filtered[['Сотрудник', 'Табельный_Молоко', 'Остаток']])

elif menu == "📊 Статистика":
    st.subheader("Отчет по выдаче")
    if os.path.exists('history.csv'):
        history_df = pd.read_csv('history.csv')
        st.write("Последние операции:")
        st.dataframe(history_df.tail(10))
        
        # Кнопка скачивания
        csv = history_df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Скачать полный отчет (CSV)", csv, "milk_report.csv", "text/csv")
    else:
        st.info("История выдач пока пуста.")
