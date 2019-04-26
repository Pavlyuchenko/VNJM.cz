from flask import Flask, render_template, url_for, flash, redirect, request
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, login_user, current_user, logout_user, login_required, UserMixin
from datetime import datetime
from functools import wraps
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
import requests
from bs4 import BeautifulSoup
import atexit
from apscheduler.schedulers.background import BackgroundScheduler
import pyperclip


def article_download():
    idnes()
    seznam()
    lidovky()
    novinky()
    aktualne()
    reflex()
    e15()


scheduler = BackgroundScheduler()

scheduler.add_job(func=article_download, trigger="interval", seconds=10)
scheduler.start()

# Shut down the scheduler when exiting the app
atexit.register(lambda: scheduler.shutdown())

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///admin.db'
app.config['SECRET_KEY'] = 'f874123aa5dsf84af'

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'danger'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


sluzby = ["idnes", "seznam", "lidovky", "novinky"]


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    # idnes_count = db.relationship('idnes', backref='author', lazy=True)
    idnes = db.Column(db.Boolean)
    seznam = db.Column(db.Boolean)
    lidovky = db.Column(db.Boolean)
    novinky = db.Column(db.Boolean)
    aktualne = db.Column(db.Boolean)
    reflex = db.Column(db.Boolean)
    e15 = db.Column(db.Boolean)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)


class Clanek(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    titulek = db.Column(db.String(1000), nullable=False)
    content = db.Column(db.Text, nullable=False)
    img = db.Column(db.String(500), nullable=False)
    date = db.Column(db.String(100), nullable=False)
    time = db.Column(db.String(10), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    sluzba = db.Column(db.Integer, nullable=False)
    order_date = db.Column(db.Integer, nullable=False)

from forms import RegistrationForm, LoginForm

admin = Admin(app)
admin.add_view(ModelView(User, db.session))
admin.add_view(ModelView(Clanek, db.session))


def login_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if current_user.is_authenticated:
            return f(*args, **kwargs)
        else:
            flash("Pro vstup na tuto stránku se musíš nejprve přihlásit", 'danger')
            return redirect(url_for('login'))
    return wrap


@app.route("/")
def novinky():
    sluzby = ['idnes', 'seznam', 'lidovky', 'novinky', 'aktualne', 'reflex', 'e15']
    return render_template('novinky.html', style="novinky.css", title="Vše na jednom místě", clanky=clanky(), sluzby=sluzby)


@app.route("/personalizace")
@login_required
def personalizace():
    return render_template('personalizace.html', style="personalizace.css", title="Personalizace")


@app.route('/vyber_sluzby')
@login_required
def vyber_sluzby():
    post = request.args.get('post', 0, type=int)
    if post == 0 and not current_user.idnes:
        current_user.idnes = True
    elif post == 0:
        current_user.idnes = False

    if post == 1 and not current_user.seznam:
        current_user.seznam = True
    elif post == 1:
        current_user.seznam = False

    if post == 2 and not current_user.lidovky:
        current_user.lidovky = True
    elif post == 2:
        current_user.lidovky = False

    if post == 3 and not current_user.novinky:
        current_user.novinky = True
    elif post == 3:
        current_user.novinky = False

    if post == 4 and not current_user.aktualne:
        current_user.aktualne = True
    elif post == 4:
        current_user.aktualne = False

    if post == 5 and not current_user.reflex:
        current_user.reflex = True
    elif post == 5:
        current_user.reflex = False

    if post == 6 and not current_user.e15:
        current_user.e15 = True
    elif post == 6:
        current_user.e15 = False

    db.session.commit()
    return ""


@app.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('novinky'))
    form = RegistrationForm()
    if form.validate_on_submit():
        password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(email=form.email.data, password=password)
        db.session.add(user)
        db.session.commit()
        flash(f'Účet byl vytvořen!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', title='Registrace', form=form, style="register.css")


@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('novinky'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            flash('Nyní jsi přihlášen', 'success')
            return redirect(next_page) if next_page else redirect(url_for('novinky'))
        else:
            flash('Přihlášení se nezdařilo. Zkontroluj si přezdívku a heslo.', 'danger')
    return render_template('login.html', title='Přihlášení', form=form, style="login.css")


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('novinky'))


def idnes():
    try:
        urls = ['https://www.idnes.cz/zpravy/cerna-kronika', 'https://www.idnes.cz/zpravy/domaci', 'https://www.idnes.cz/zpravy/zahranicni']
        now = datetime.now()
        year = str(now.year)
        month_number = str(now.strftime('%m'))
        day_number = str(now.strftime('%d'))
        for i in range(len(urls)):
            for j in range(2):
                url = requests.get(urls[i])
                soup = BeautifulSoup(url.text, features="html.parser")
                unique = True
                nadpis = " ".join(soup.select('.art h3')[j].text.split())
                clanky = Clanek.query.all()
                for clanek in clanky:
                    if clanek.titulek == nadpis:
                        unique = False
                if unique:
                    img = soup.select('.art img')[j]['src']
                    url_text = soup.select('.art a')[j]['href']
                    url_text = url_text.replace('/foto', '')

                    url = requests.get(url_text)
                    soup = BeautifulSoup(url.text, features="html.parser")

                    content = " ".join(soup.select('.opener')[0].text.split())
                    cont = True
                    for clanek in clanky:
                        if clanek.content == content:
                            cont = False

                    if cont:
                        date = " ".join(" ".join(soup.select('.time')[0].text.split()).split(',', 1)[0].split()[:3])
                        time = " ".join(soup.select('.time')[0].text.split()).split(',', 1)[0].split()[3]

                        if (int(date.split(" ")[-1].split(":")[0]) / 10) >= 1:
                            order_date = year + month_number + day_number + time.split(" ")[-1].split(":")[0] + time.split(" ")[-1].split(":")[1]
                        else:
                            order_date = year + month_number + day_number + str(0) + time.split(" ")[-1].split(":")[0] + time.split(" ")[-1].split(":")[1]

                        clanek = Clanek(titulek=nadpis, content=content, img=img, date=date, time=time, url=url_text, sluzba=0, order_date=order_date)
                        db.session.add(clanek)
                        db.session.commit()
                        print("Downloaded new article - iDnes")
    except Exception as e:
        print("Bug:", e)


def seznam():
    urls = ['https://www.seznamzpravy.cz/sekce/domaci', 'https://www.seznamzpravy.cz/sekce/zahranicni']
    now = datetime.now()
    den = str(now.day)
    month_number = int(now.month)
    month = str(month_conversion(month_number))
    year = str(now.year)
    month_number_date = str(now.strftime('%m'))
    day_number = str(now.strftime('%d'))
    for i in range(len(urls)):
        for j in range(2):
            url = requests.get(urls[i])
            soup = BeautifulSoup(url.text, features="html.parser")
            unique = True
            nadpis = soup.select('h3')[j].text
            clanky = Clanek.query.all()
            for clanek in clanky:
                if clanek.titulek == nadpis:
                    unique = False

            if unique:
                url_text = soup.select('.d_ba a')[j]['href']
                date = den + ". " + month + " " + year
                time = soup.select('.atm-date-formatted')[j].text

                url = requests.get(url_text)
                soup = BeautifulSoup(url.text, features="html.parser")

                content = soup.select('.e_g6')[0].text
                cont = True
                for clanek in clanky:
                    if clanek.content == content:
                        cont = False
                if cont:
                    try:
                        img = soup.select('.c_ab .atm-media-item-image-events img')[0]['src']
                    except:
                        img = soup.select('.d_ch .atm-media-item-image-events img')[0]['src']
                    if (int(date.split(" ")[-1].split(":")[0]) / 10) >= 1:
                        order_date = year + month_number_date + day_number + time.split(" ")[-1].split(":")[0] + time.split(" ")[-1].split(":")[1]
                    else:
                        order_date = year + month_number_date + day_number + str(0) + time.split(" ")[-1].split(":")[0] + time.split(" ")[-1].split(":")[1]

                    clanek = Clanek(titulek=nadpis, content=content, img=img, date=date, time=time, url=url_text, sluzba=1, order_date=order_date)
                    db.session.add(clanek)
                    db.session.commit()
                    print("Downloaded new article - Seznam")


def lidovky():
    urls = ['https://www.lidovky.cz/domov', 'https://www.lidovky.cz/svet']
    now = datetime.now()
    year = str(now.year)
    month_number = int(now.month)
    month_number_date = str(now.strftime('%m'))
    day_number = str(now.strftime('%d'))
    for i in range(len(urls)):
        for j in range(6):
            if j == 3:
                pass
            url = requests.get(urls[i])
            soup = BeautifulSoup(url.text, features="html.parser")
            unique = True
            nadpis_class = '#assembly-art-' + str(j+1)
            nadpis = soup.select(nadpis_class)[0].text
            clanky = Clanek.query.all()
            for clanek in clanky:
                if clanek.titulek == nadpis:
                    unique = False

            if unique:
                if soup.select('.art .art-info a') is not None:
                    url_text = soup.select('.art a')[j+j+1]['href']
                else:
                    url_text = soup.select('.art a')[j+j]['href']


                url = requests.get(url_text)
                soup = BeautifulSoup(url.text, features="html.parser")
                try:
                    content = soup.select('.opener')[0].text
                    cont = True
                    for clanek in clanky:
                        if clanek.content == content:
                            cont = False

                    if cont:
                        date = " ".join(soup.select('.time')[0].text.split()[:3])
                        time = "".join(soup.select('.time')[0].text.split()[3])
                        print(time)
                        img = soup.select('.equ-img img')[0]['src']
                        new_date = time.split(',')[0]
                        new_date = " ".join(new_date.split())
                        if (int(new_date.split(" ")[-1].split(":")[0]) / 10) >= 1:
                            order_date = year + month_number_date + day_number + new_date.split(" ")[-1].split(":")[0] + \
                                         new_date.split(" ")[-1].split(":")[1]
                        else:
                            order_date = year + month_number_date + day_number + str(0) + \
                                         new_date.split(" ")[-1].split(":")[0] + new_date.split(" ")[-1].split(":")[1]

                        clanek = Clanek(titulek=nadpis, content=content, img=img, date=date, time=time, url=url_text, sluzba=2,
                                        order_date=order_date)
                        db.session.add(clanek)
                        db.session.commit()
                        print("Downloaded new article - Lidovky")
                except Exception as e:
                    print(e)


def novinky():
    urls = ['https://www.novinky.cz/krimi/', 'https://www.novinky.cz/domaci/',
            'https://www.novinky.cz/zahranicni/']
    now = datetime.now()
    year = str(now.year)
    month_number = str(now.strftime('%m'))
    day_number = str(now.strftime('%d'))
    day = str(now.day)
    month = now.month
    month = str(month_conversion(month))
    for i in range(len(urls)):
        for j in range(2):
            url = requests.get(urls[i])
            soup = BeautifulSoup(url.text, features="html.parser")
            unique = True
            nadpis = soup.select('.likeInInfo a')[j].text
            clanky = Clanek.query.all()
            for clanek in clanky:
                if clanek.titulek == nadpis:
                    unique = False
            if unique:
                img = soup.select('.item img')[j]['src']
                url_text = soup.select('.likeInInfo a')[j]['href']

                time = soup.select('.time')[j].text
                url = requests.get(url_text)
                soup = BeautifulSoup(url.text, features="html.parser")
                content = soup.select('.perex')[0].text
                new_date = " ".join(time.split())

                cont = True
                for clanek in clanky:
                    if clanek.content == content:
                        cont = False
                if cont:
                    if (int(time.split(":")[0]) / 10) >= 1:
                        order_date = year + month_number + day_number + new_date.split(":")[0] + \
                                     new_date.split(":")[1]
                    else:
                        order_date = year + month_number + day_number + str(0) + new_date.split(":")[0] + \
                                     new_date.split(":")[1]

                    date = str(day + ". " + month + " " + year)

                    clanek = Clanek(titulek=nadpis, content=content, img=img, date=date, time=time, url=url_text,
                                    sluzba=3, order_date=order_date)
                    db.session.add(clanek)
                    db.session.commit()
                    print("Downloaded new article - Novinky")


def aktualne():
    urls = ['https://zpravy.aktualne.cz/domaci/', 'https://zpravy.aktualne.cz/zahranici/']
    now = datetime.now()
    year = str(now.year)
    month_number = str(now.strftime('%m'))
    day_number = str(now.strftime('%d'))
    day = str(now.day)
    month = now.month
    month = str(month_conversion(month))
    for i in range(len(urls)):
        for j in range(1, 3):
            url = requests.get(urls[i])
            soup = BeautifulSoup(url.text, features="html.parser")
            unique = True
            nadpis = soup.select('.titulek')[j+1].text
            clanky = Clanek.query.all()
            for clanek in clanky:
                if clanek.titulek == nadpis:
                    unique = False
            if unique:
                img = soup.select('.obrazek img')[j+1]['src']
                url_text = urls[i] + soup.select('.polozka .text a')[j]['href']

                url = requests.get(url_text)
                soup = BeautifulSoup(url.text, features="html.parser")
                content = soup.select('.perex')[0].text

                cont = True
                for clanek in clanky:
                    if clanek.content == content:
                        cont = False
                if cont:
                    date = day + ". " + month + " " + year + " "
                    order_date = str(year + month_number + day_number + str(now.strftime('%H')) + str(now.minute))
                    if len(content) > 300:
                        content = content[:300] + "..."
                    time = str(now.hour) + ":" + str(now.minute)
                    clanek = Clanek(titulek=nadpis, content=content, img=img, date=date, time=time, url=url_text, sluzba=4, order_date=order_date)
                    db.session.add(clanek)
                    db.session.commit()
                    print("Downloaded new article - Aktualne")


def reflex():
    urls = ['https://www.reflex.cz/kategorie/3025/zpravy']
    now = datetime.now()
    year = str(now.year)
    month_number = str(now.strftime('%m'))
    day_number = str(now.strftime('%d'))
    day = str(now.day)
    month = now.month
    month = str(month_conversion(month))
    for i in range(len(urls)):
        for j in range(2):
            url = requests.get(urls[i])
            soup = BeautifulSoup(url.text, features="html.parser")
            unique = True
            nadpis = soup.select('.title')[j].text
            clanky = Clanek.query.all()
            for clanek in clanky:
                if clanek.titulek == nadpis:
                    unique = False
            if unique:
                img = soup.select('.image-main img')[j]['src']
                url_text = soup.select('.title a')[j]['href']

                url = requests.get(url_text)
                soup = BeautifulSoup(url.text, features="html.parser")
                content = soup.select('.perex')[0].text

                cont = True
                for clanek in clanky:
                    if clanek.content == content:
                        cont = False
                if cont:
                    date = day + ". " + month + " " + year
                    time = soup.select('.datetime')[0].text.split()[4]
                    order_date = str(year + month_number + day_number + time.split(':')[0] + time.split(':')[1])
                    if len(content) > 300:
                        content = content[:300] + "..."

                    clanek = Clanek(titulek=nadpis, content=content, img=img, date=date, time=time, url=url_text, sluzba=5, order_date=order_date)
                    db.session.add(clanek)
                    db.session.commit()
                    print("Downloaded new article - Reflex")


def e15():
    urls = ['https://www.e15.cz/domaci', 'https://www.e15.cz/zahranicni']
    now = datetime.now()
    year = str(now.year)
    month_number = str(now.strftime('%m'))
    day_number = str(now.strftime('%d'))
    day = str(now.day)
    month = now.month
    month = str(month_conversion(month))
    for i in range(len(urls)):
        for j in range(2):
            url = requests.get(urls[i])
            soup = BeautifulSoup(url.text, features="html.parser")
            unique = True
            nadpis = soup.select('.title')[j+3].text
            clanky = Clanek.query.all()
            for clanek in clanky:
                if clanek.titulek == nadpis:
                    unique = False
            if unique:
                img = soup.select('.image-container img')[j]['src']
                url_text = soup.select('.title a')[j+3]['href']
                time = soup.select('.publication-date')[j].text.split()[2]

                url = requests.get(url_text)
                soup = BeautifulSoup(url.text, features="html.parser")
                content = soup.select('.perex')[0].text

                cont = True
                for clanek in clanky:
                    if clanek.content == content:
                        cont = False
                if cont:
                    date = day + ". " + month + " " + year
                    order_date = str(year + month_number + day_number + time.split(':')[0] + time.split(':')[1])
                    if len(content) > 300:
                        content = content[:300] + "..."

                    clanek = Clanek(titulek=nadpis, content=content, img=img, date=date, time=time, url=url_text, sluzba=6, order_date=order_date)
                    db.session.add(clanek)
                    db.session.commit()
                    print("Downloaded new article - E15")


def clanky():
    if current_user.is_authenticated:
        clanky = Clanek.query.order_by(Clanek.order_date.desc()).all()
        clanky_personalized = []
        for clanek in clanky:
            if clanek.sluzba == 0 and current_user.idnes:
                clanky_personalized.append(clanek)
            elif clanek.sluzba == 1 and current_user.seznam:
                clanky_personalized.append(clanek)
            elif clanek.sluzba == 2 and current_user.lidovky:
                clanky_personalized.append(clanek)
            elif clanek.sluzba == 3 and current_user.novinky:
                clanky_personalized.append(clanek)
            elif clanek.sluzba == 4 and current_user.aktualne:
                clanky_personalized.append(clanek)
            elif clanek.sluzba == 5 and current_user.reflex:
                clanky_personalized.append(clanek)
            elif clanek.sluzba == 6 and current_user.e15:
                clanky_personalized.append(clanek)
            elif clanek.sluzba == 7 and current_user.seznam:
                clanky_personalized.append(clanek)
        return clanky_personalized
    else:
        clanky = Clanek.query.order_by(Clanek.order_date.desc()).all()
        clanky_personalized = []
        for clanek in clanky:
            clanky_personalized.append(clanek)
        return clanky_personalized


def month_conversion(month):
    if month == 1:
        return "ledna"
    elif month == 2:
        return "února"
    elif month == 3:
        return "března"
    elif month == 4:
        return "dubna"
    elif month == 5:
        return "května"
    elif month == 6:
        return "června"
    elif month == 7:
        return "července"
    elif month == 8:
        return "srpna"
    elif month == 9:
        return "září"
    elif month == 10:
        return "října"
    elif month == 11:
        return "listopadu"
    elif month == 12:
        return "prosince"
