# --- ОБНОВЛЕННЫЙ БЛОК ЗАГРУЗКИ В АДМИНКЕ ---
elif menu == "АДМИН":
    st.title("⚙️ Администрирование")
    
    st.subheader("Обновление базы на новый месяц")
    uploaded_file = st.file_uploader("Загрузите Excel-файл", type=["xlsx"])
    
    if uploaded_file:
        if st.button("ОБНУЛИТЬ СТАРУЮ БАЗУ И ЗАГРУЗИТЬ НОВУЮ"):
            try:
                # Читаем файл целиком
                df_raw = pd.read_excel(uploaded_file)
                
                # Ищем строку, где находятся наши заголовки
                # Проходим по каждой строке, пока не найдем 'Сотрудник' или 'Код'
                header_row = 0
                for i, row in df_raw.iterrows():
                    if 'Сотрудник' in row.values or 'Код' in row.values:
                        header_row = i + 1
                        break
                
                # Перечитываем файл уже с правильного места
                df = pd.read_excel(uploaded_file, skiprows=header_row)
                
                # Чистим названия колонок
                df.columns = [str(c).strip() for c in df.columns]
                
                # Список необходимых колонок (как в твоем файле)
                required = ['Сотрудник', 'Код', 'Должность', 'Дней', 'Литр']
                
                if all(col in df.columns for col in required):
                    conn = sqlite3.connect("milk_factory.db")
                    cur = conn.cursor()
                    cur.execute("DELETE FROM employees") # Чистим старых
                    
                    count = 0
                    for _, row in df.iterrows():
                        # Проверяем, чтобы строка не была пустой
                        if pd.notna(row['Код']) and pd.notna(row['Сотрудник']):
                            cur.execute("INSERT INTO employees (kod, fio, position, days, total_liters, remaining_liters) VALUES (?, ?, ?, ?, ?, ?)",
                                        (str(int(row['Код'])), str(row['Сотрудник']), str(row['Должность']), int(row['Дней']), float(row['Литр']), float(row['Литр'])))
                            count += 1
                    
                    conn.commit()
                    conn.close()
                    st.success(f"Успешно загружено {count} сотрудников!")
                else:
                    st.error(f"Не найдены нужные колонки. В файле должны быть: {', '.join(required)}")
                    st.write("Сейчас в файле найдены:", list(df.columns))
            except Exception as e:
                st.error(f"Ошибка при чтении: {e}")
