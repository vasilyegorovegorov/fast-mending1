from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify,
)
import sqlite3
import pandas as pd
import os
import datetime
import time

app = Flask(__name__)
app.secret_key = "ключик_секретик"


def init_db():
    """Инициализация базы данных."""
    conn = sqlite3.connect("db.db")
    cursor = conn.cursor()
    cursor.execute("""  
        CREATE TABLE IF NOT EXISTS users (  
            id INTEGER PRIMARY KEY AUTOINCREMENT,  
            Имя TEXT NOT NULL,  
            profile_title TEXT NOT NULL,  -- Название профиля  
            password TEXT NOT NULL  
        )  
    """)
    cursor.execute("""  
        CREATE TABLE IF NOT EXISTS events (  
            id INTEGER PRIMARY KEY AUTOINCREMENT,  
            user_id INTEGER,  
            device_id INTEGER,  
            event_type TEXT,  
            value TEXT,  
            datetime_event DATETIME,
            label TEXT,  
            FOREIGN KEY (user_id) REFERENCES users (id)  
        )  
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_device_id ON events (device_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_datetime_event ON events (datetime_event);")
    conn.commit()
    conn.close()


init_db()


@app.route("/")
def home():
    """Главная страница."""
    name = session.get("name", None)
    return render_template("index.html", name=name)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Регистрация пользователя."""
    if request.method == "POST":
        name = request.form["name"]
        profile_title = request.form["profile_title"]
        password = request.form["password"]

        conn = sqlite3.connect("db.db")
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE Имя = ?", (name,))
        existing_user = cursor.fetchone()

        if existing_user:
            flash("Пользователь с таким именем уже существует. Пожалуйста, выберите другое имя.", "error")
            return redirect(url_for("register"))

        cursor.execute(
            "INSERT INTO users (Имя, profile_title, password) VALUES (?, ?, ?)",
            (name, profile_title, password),
        )
        conn.commit()
        conn.close()

        session["name"] = name
        session["user_id"] = cursor.lastrowid

        return redirect(url_for("home"))

    return render_template("reg.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Авторизация пользователя."""
    if request.method == "POST":
        profile_title = request.form["profile_title"]
        password = request.form["password"]

        conn = sqlite3.connect("db.db")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM users WHERE profile_title = ? AND password = ?",
            (profile_title, password),
        )
        user = cursor.fetchone()
        conn.close()

        if user:
            session["name"] = user[1]
            session["user_id"] = user[0]
            return redirect(url_for("home"))
        else:
            flash("Ошибка входа. Пожалуйста, проверьте название профиля и пароль.", "error")
            return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    """Выход из системы."""
    session.pop("name", None)
    session.pop("user_id", None)
    return redirect(url_for("home"))


@app.route("/upload", methods=["POST"])
def upload():
    """Загрузка и обработка CSV-файла."""
    start_time = time.time()  # Начало отсчета времени выполнения

    if "file" not in request.files:
        flash("No file part", "error")
        return redirect(url_for("home"))
    file = request.files["file"]
    if file.filename == "":
        flash("No selected file", "error")
        return redirect(url_for("home"))
    if file:
        upload_dir = "uploads"
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)
        filename = os.path.join(upload_dir, file.filename)
        file.save(filename)

        try:
            df = pd.read_csv(filename)
            print(df.head())
        except Exception as e:
            flash(f"Error reading CSV file: {e}", "error")
            return redirect(url_for("home"))

        user_id = session.get("user_id")

        num_postomats = df['DeviceID'].nunique()
        session['num_postomats'] = num_postomats

        def determine_label(row):
            """Определение метки для события."""
            event_type = row["EventType"].strip().lower()
            value = row["Value"].strip().lower() if pd.notna(row["Value"]) else ""

            print(f"Processing row: {event_type} | {value}")

            courier_machine = {
                "ошибкавыдачиотправления",
                "отказвобслуживании",
                "неудалосьсчитатькод",
                "замокзаблокирован",
                "дверцанеоткрылась",
            }

            mechanic = {
                "ошибкажесткогодиска",
                "ошибкапитания",
                "ошибкасканера",
                "ошибкасоединения",
                "сбойпо",
                "аварийноеотключение",
                "ошибкачтения",
                "ошибкапринтера",
                "проблемысвентиляцией",
                "высокаявлажность",
                "некорректнаяработазамков",
                "низкийзарядаккумулятора",
                "проблемысобновлениемпо",
                "проблемыссистемойбезопасности",
            }

            all_good = {
                "состояниеотделений",
                "перезагрузкаустройства",
                "предупреждение",
                "всеисправны",
                "связьстабильная",
                "работаетисправно",
                "обработказапроса",
                "входпользователя",
                "тестированиеустройствазавершено",
                "проверкасистемы",
                "обновлениесистемыбезопасности",
                "обновлениепо",
                "проверкасканераштрихкодов",
                "состояниеустройстваизменено",
            }

            check_need = {
                "перезагрузкаустройства",
                "отказвобслуживании",
                "проверкасостояниясети",
                "проверкаобновлений",
                "тестированиесистемы",
                "проверкасостояниязамков",
                "проверкаэнергоснабжения",
                "проверкасостояниякартриджа",
                "проверкасвязи",
                "проверкаячеек",
                "состояниеприемаотправлений",
            }

            courier_values = {
                "дверцанеоткрылась",
                "замокзаблокирован",
                "сбойпо",
                "неудалосьсчитатькод",
            }

            good_values = {
                "всеисправны",
                "перезагрузкаустройства",
                "ошибкасоединения",
                "успешно",
                "принято",
                "работаетисправно",
            }
            if event_type in courier_machine:
                print(f"EventType '{event_type}' matched in 'courier_machine'")
                return "нужна курьерская машина"

            elif event_type in mechanic:
                print(f"EventType '{event_type}' matched in 'mechanic'")
                return "нужен механик"

            elif event_type in all_good:
                print(f"EventType '{event_type}' matched in 'all_good'")
                return "все в порядке"

            elif event_type in check_need:
                print(f"EventType '{event_type}' matched in 'check_need'")

                if value:
                    print(f"Value is present: {value}")

                    if value in courier_values:
                        print(f"Value '{value}' matched in 'courier_values'")
                        return "нужна курьерская машина"

                    elif value in good_values:
                        print(f"Value '{value}' matched in 'good_values'")
                        return "все в порядке"

                    else:
                        print(f"Value '{value}' does not match known values, returning 'нужен механик'")
                        return "нужен механик"
                else:
                    print("Value is NaN or empty, returning 'нужен механик'")
                    return "нужен механик"

            else:
                print(f"EventType '{event_type}' is not recognized, returning 'неизвестно'")
                return "неизвестно"

        df["Label"] = df.apply(determine_label, axis=1)

        data_to_insert = [
            (
                user_id,
                int(row["DeviceID"][8:]),
                row["EventType"],
                row["Value"],
                row["Label"],
                row["Timestamp"],
            )
            for index, row in df.iterrows()
        ]

        conn = sqlite3.connect("db.db")
        cursor = conn.cursor()
        cursor.executemany(
            "INSERT INTO events (user_id, device_id, event_type, value, label, datetime_event) VALUES (?, ?, ?, ?, ?, ?)",
            data_to_insert,
        )
        conn.commit()
        conn.close()

        updated_postomat_status = get_updated_postomat_status()
        flash(f"Файл успешно загружен и обработан. Количество постаматов: {num_postomats}", "success")

        end_time = time.time()
        print(f"Время выполнения: {end_time - start_time} секунд")

        return jsonify(updated_postomat_status)


def get_updated_postomat_status():
    """Получение обновленного состояния постаматов."""
    conn = sqlite3.connect("db.db")
    cursor = conn.cursor()

    cursor.execute("""  
        SELECT device_id, label  
        FROM events  
        WHERE datetime_event = (  
            SELECT MAX(datetime_event)  
            FROM events AS sub  
            WHERE sub.device_id = events.device_id  
        )  
        ORDER BY device_id;  
    """)

    device_data = cursor.fetchall()
    conn.close()

    return [{"device_id": row[0], "status": row[1]} for row in device_data]


@app.route("/generate_rep1", methods=["GET"])
def generate_rep1():
    """Генерация отчета 1."""
    conn = sqlite3.connect("db.db")
    cursor = conn.cursor()
    cursor.execute("""  
        SELECT device_id, event_type, label, datetime_event  
        FROM events  
        WHERE datetime_event = (  
            SELECT MAX(datetime_event)  
            FROM events AS sub  
            WHERE sub.device_id = events.device_id  
        )  
        ORDER BY device_id;  
    """)
    device_data = cursor.fetchall()
    conn.close()

    labels = ["device_id", "event_type", "label", "datetime_event"]
    return jsonify([dict(zip(labels, data)) for data in device_data])


@app.route("/generate_rep3", methods=["GET"])
def generate_rep3():
    """Генерация отчета 3: количество неисправностей постаматов по дням."""
    conn = sqlite3.connect('db.db')
    cursor = conn.cursor()

    query = """
    SELECT 
        strftime('%Y-%m-%d', 
            substr(datetime_event, 7, 4) || '-' || 
            substr(datetime_event, 4, 2) || '-' || 
            substr(datetime_event, 1, 2)) AS date,
        COUNT(*) AS error_count
    FROM 
        events
    WHERE 
        label IN ('нужен механик', 'нужна курьерская машина')
    GROUP BY 
        date
    ORDER BY 
        date;
    """

    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()

    data = [{"date": row[0], "error_count": row[1]} for row in rows]
    return jsonify(data)


@app.route("/report1", methods=["GET"])
def report1():
    """Страница отчета 1."""
    return render_template("report_screen.html")

@app.route("/report3", methods=["GET"])
def report3():
    """Страница отчета 3."""
    return render_template("report_screen3.html")


if __name__ == "__main__":
    app.run(port=8087, debug=True)