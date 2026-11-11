"""Google Identity Services sign-in; all browser submissions use Flask CSRF."""
import secrets
import time
from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import login_user
from google.auth.transport.requests import Request
from google.oauth2 import id_token
from sqlalchemy.exc import IntegrityError

from ..extensions import limiter
from ..models import db, User, GoogleIdentity
from ..utils_security import generate_blind_index
from ..utils_username import validate_username, is_username_taken
from ..utils import safe_redirect_target
from .public import normalize_bd_phone

google_bp = Blueprint('google_auth', __name__)


def safe_next(value):
    return safe_redirect_target(value)


@google_bp.app_context_processor
def google_context():
    def google_button_context():
        if not current_app.config.get('GOOGLE_CLIENT_ID'):
            return None
        state = session.get('google_nonce', {})
        if time.time() - state.get('created', 0) > 600:
            state = {'value': secrets.token_urlsafe(32), 'created': time.time()}
            session['google_nonce'] = state
        return {'client_id': current_app.config['GOOGLE_CLIENT_ID'], 'nonce': state['value']}
    return {'google_button_context': google_button_context}


def finish(user, target=''):
    session.pop('google_pending', None)
    session.pop('google_nonce', None)
    login_user(user)
    return redirect(target or url_for('admin.admin_dashboard' if user.is_admin() else 'public.dashboard'))


@google_bp.post('/auth/google')
@limiter.limit('10 per minute')
def authenticate():
    if not current_app.config.get('GOOGLE_CLIENT_ID'):
        return 'Google sign-in is not configured.', 503
    nonce = session.pop('google_nonce', {})
    session.pop('google_pending', None)
    try:
        if time.time() - nonce.get('created', 0) > 600:
            raise ValueError('Expired sign-in')
        claims = id_token.verify_oauth2_token(
            request.form.get('credential', ''), Request(),
            current_app.config['GOOGLE_CLIENT_ID'])
        if not nonce.get('value') or not secrets.compare_digest(str(claims.get('nonce', '')), nonce['value']):
            raise ValueError('Invalid nonce')
        if claims.get('email_verified') is not True or not claims.get('email') or not claims.get('sub'):
            raise ValueError('Missing verified identity')
        if len(claims['email']) > 120 or len(claims['sub']) > 255:
            raise ValueError('Invalid identity')
    except Exception:
        flash('Google sign-in could not be verified. Please try again or use your password.', 'danger')
        return redirect(url_for('public.login'))
    target = safe_next(request.form.get('next'))
    identity = GoogleIdentity.query.filter_by(subject=claims['sub']).first()
    if identity:
        return finish(identity.user, target)
    session['google_pending'] = {
        'subject': claims['sub'], 'email': claims['email'].lower(),
        'name': (claims.get('name') or claims['email'].split('@')[0])[:120],
        'created': time.time(), 'next': target,
    }
    return redirect(url_for('google_auth.complete'))


@google_bp.route('/auth/google/complete', methods=['GET', 'POST'])
@limiter.limit('5 per minute', methods=['POST'])
def complete():
    pending = session.get('google_pending', {})
    if not pending or time.time() - pending.get('created', 0) > 600:
        session.pop('google_pending', None)
        flash('Please continue with Google again to finish creating your account.', 'warning')
        return redirect(url_for('public.login'))
    existing = User.query.filter_by(email_hash=generate_blind_index(pending['email'])).first()
    entered = {'username': request.form.get('username', '').strip(),
               'phone': request.form.get('phone', '').strip()}
    error = None
    if request.method == 'POST':
        if existing:
            if not existing.check_password(request.form.get('password', '')):
                error = 'That password is incorrect. Use your existing FlatLand BD password to link Google.'
            elif GoogleIdentity.query.filter_by(user_id=existing.id).first():
                error = 'This account is already linked to another Google account. Please sign in with your password.'
            else:
                db.session.add(GoogleIdentity(subject=pending['subject'], user_id=existing.id))
                try:
                    db.session.commit()
                    return finish(existing, pending.get('next', ''))
                except IntegrityError:
                    db.session.rollback()
                    error = 'This Google account was just linked. Please sign in again.'
        else:
            valid, username = validate_username(entered['username'])
            phone = normalize_bd_phone(entered['phone'])
            if not valid:
                error = username
            elif is_username_taken(username):
                error = 'That username is taken. Please choose another.'
            elif not phone:
                error = 'Enter an 11-digit Bangladeshi mobile number, starting 013–019.'
            elif User.query.filter_by(phone_hash=generate_blind_index(phone)).first():
                error = 'That mobile number belongs to an existing account. Sign in to that account first; Google has not been linked.'
            elif request.form.get('confirm') != '1':
                error = 'Please confirm that your listing details will be accurate.'
            else:
                user = User(full_name=pending['name'], username=username, role='user')
                user.phone = phone
                user.email = pending['email']
                # An unguessable, discarded secret satisfies the legacy non-null
                # password column. Google members never need to set a password.
                user.set_password(secrets.token_urlsafe(64))
                db.session.add(user)
                try:
                    db.session.flush()
                    db.session.add(GoogleIdentity(subject=pending['subject'], user_id=user.id))
                    db.session.commit()
                    return finish(user, pending.get('next', ''))
                except IntegrityError:
                    db.session.rollback()
                    error = 'These details were just registered. Please sign in or try different details.'
        if error:
            flash(error, 'danger')
    return render_template('google_complete.html', pending=pending, existing=existing, entered=entered)
