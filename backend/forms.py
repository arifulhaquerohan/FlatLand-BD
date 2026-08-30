from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, TextAreaField, SelectField
from wtforms.validators import DataRequired, Email, Optional, Length, Regexp

# Bangladeshi mobile numbers are exactly 11 digits: 01[3-9] + 8 more digits.
BD_PHONE_REGEX = r'^01[3-9]\d{8}$'
BD_PHONE_MESSAGE = 'Enter an 11-digit Bangladeshi mobile number, e.g. 01712345678.'


class LoginForm(FlaskForm):
    identifier = StringField('Username, phone or email', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')


class RegisterForm(FlaskForm):
    full_name = StringField('Full Name', validators=[DataRequired(), Length(max=120)])
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=20)])
    phone = StringField('Mobile Number', validators=[
        DataRequired(),
        Length(min=11, max=11, message=BD_PHONE_MESSAGE),
        Regexp(BD_PHONE_REGEX, message=BD_PHONE_MESSAGE),
    ])
    email = StringField('Email (Optional)', validators=[Optional(), Email(), Length(max=120)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])


class ContactForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(max=100)])
    phone = StringField('Phone', validators=[DataRequired(), Length(max=20)])
    email = StringField('Email', validators=[Optional(), Email(), Length(max=120)])
    contact = StringField('Contact Info') # Catch-all sometimes used
    interest = StringField('Interest', validators=[Length(max=200)])
    message = TextAreaField('Message', validators=[DataRequired()])
    budget = StringField('Budget', validators=[Optional(), Length(max=50)])
    service_type = StringField('Service Type', validators=[Optional(), Length(max=100)])
    timeline = StringField('Timeline', validators=[Optional(), Length(max=50)])

    # Flatland allows submitting even if interest doesn't exist, so Optional for those.
