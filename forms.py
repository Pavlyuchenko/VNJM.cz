from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField
from wtforms.validators import Email, ValidationError
from main import User


class RegistrationForm(FlaskForm):
    email = StringField('Email', validators=[Email("Zadej opravdový email")])
    password = PasswordField('Heslo')
    submit = SubmitField('Zaregistovat')

    def validate_name(self, name):
        user = User.query.filter_by(name=name.data).first()

        if user:
            raise ValidationError('Tuto přezdívku už někdo používá')

        if name is None or len(name.data) > 15 or len(name.data) < 2:
            raise ValidationError('Jméno musí být delší než 2 a kratší než 15 znaků')

    def validate_email(self, email):
        email = User.query.filter_by(email=email.data).first()

        if email:
            raise ValidationError('Tento email už někdo používá')

    def validate_password(self, password):
        if password is None or len(password.data) < 6:
            raise ValidationError('Jméno musí být delší než 6 znaky')


class LoginForm(FlaskForm):
    email = StringField('Email:')
    password = PasswordField('Heslo:')
    remember = BooleanField('Zapamatuj si mě')
    submit = SubmitField('Přihlásit')
