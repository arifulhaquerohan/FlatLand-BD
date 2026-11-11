"""Email password recovery with hashed, expiring, single-use credentials."""
import hashlib
import re
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from threading import Thread
from urllib.parse import urlsplit

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import logout_user
from flask_mail import Message
from werkzeug.security import generate_password_hash

from ..extensions import limiter, mail
from ..models import db, User, PasswordReset
from ..utils_security import generate_blind_index

password_reset_bp = Blueprint('password_reset', __name__)
GENERIC_MESSAGE = 'If that email belongs to an account, a reset link will arrive shortly. Check your inbox and spam folder.'


def fingerprint(value):
    return hashlib.sha256(value.encode()).hexdigest()


def recovery_ready():
    base = urlsplit(current_app.config.get('PASSWORD_RESET_BASE_URL', ''))
    valid_origin = (base.scheme == 'https' or (base.scheme == 'http' and base.hostname in ('localhost', '127.0.0.1')))
    return bool(valid_origin and base.netloc and not base.username and not base.password and
                not base.query and not base.fragment and not base.path.strip('/') and
                current_app.config.get('MAIL_SERVER') and current_app.config.get('MAIL_DEFAULT_SENDER'))


def deliver_reset(app, recipient, link, token_hash):
    with app.app_context():
        try:
            plain_body = (
                'We received a request to reset your FlatLand BD password.\n\n'
                f'{link}\n\n'
                'This link expires in 30 minutes and works once.\n'
                'If you did not request this, ignore this email. Your password has not changed.'
            )
            html_body = f'''<!doctype html>
<html lang="en">
  <body style="margin:0;background:#f3efe9;color:#1f2722;font-family:Arial,Helvetica,sans-serif;">
    <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">Reset your FlatLand BD password securely.</div>
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#f3efe9;padding:32px 16px;">
      <tr><td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:560px;background:#ffffff;border:1px solid #e4ddd3;">
          <tr><td style="height:6px;background:#a8541f;font-size:0;line-height:0;">&nbsp;</td></tr>
          <tr><td style="padding:30px 34px 22px;">
            <img src="cid:flatland-logo" width="180" height="49" alt="FlatLand BD" style="display:block;width:180px;height:auto;border:0;outline:none;text-decoration:none;">
          </td></tr>
          <tr><td style="padding:2px 34px 34px;">
            <p style="margin:0 0 10px;color:#a8541f;font-size:12px;font-weight:bold;letter-spacing:1.5px;text-transform:uppercase;">Account security</p>
            <h1 style="margin:0 0 14px;color:#1f2722;font-family:Georgia,serif;font-size:30px;line-height:1.15;font-weight:normal;">Reset your password</h1>
            <p style="margin:0;color:#616f66;font-size:15px;line-height:1.7;">We received a request to reset your FlatLand BD password. Use the button below to choose a new one.</p>
            <table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin:28px 0 24px;"><tr><td>
              <a href="{link}" style="display:inline-block;background:#a8541f;color:#ffffff;text-decoration:none;font-size:14px;font-weight:bold;line-height:48px;padding:0 24px;border-radius:6px;">Reset my password &nbsp;→</a>
            </td></tr></table>
            <p style="margin:0 0 8px;color:#616f66;font-size:13px;line-height:1.6;">This link expires in <strong style="color:#38453d;">30 minutes</strong> and works once.</p>
            <p style="margin:0;color:#616f66;font-size:13px;line-height:1.6;">If the button does not work, copy this link into your browser:</p>
            <p style="margin:8px 0 0;word-break:break-all;color:#2b6383;font-size:12px;line-height:1.6;">{link}</p>
          </td></tr>
          <tr><td style="padding:20px 34px 26px;border-top:1px solid #e4ddd3;background:#fbf9f6;">
            <p style="margin:0 0 7px;color:#38453d;font-size:13px;font-weight:bold;">Wasn’t you?</p>
            <p style="margin:0;color:#616f66;font-size:12px;line-height:1.6;">You can safely ignore this email. Your password will stay unchanged.</p>
          </td></tr>
        </table>
        <p style="margin:18px 0 0;color:#94a09a;font-size:11px;line-height:1.5;text-align:center;">FlatLand BD · Verified flats and interior studios in Bangladesh</p>
      </td></tr>
    </table>
  </body>
</html>'''
            message = Message(
                subject='Reset your FlatLand BD password', recipients=[recipient],
                sender=app.config['MAIL_DEFAULT_SENDER'],
                body=plain_body, html=html_body)
            logo_path = Path(app.root_path).parent / 'frontend' / 'static' / 'img' / 'logo.png'
            with logo_path.open('rb') as logo_file:
                message.attach(
                    filename='flatlandbd-logo.png',
                    content_type='image/png',
                    data=logo_file.read(),
                    disposition='inline',
                    headers={'Content-ID': '<flatland-logo>'},
                )
            mail.send(message)
        except Exception:
            # Never log the reset credential or private recipient details.
            app.logger.error('Password reset email delivery failed; check mail configuration.')
            PasswordReset.query.filter_by(token_hash=token_hash).delete()
            db.session.commit()


@password_reset_bp.after_request
def private_response(response):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['X-Robots-Tag'] = 'noindex, nofollow'
    return response


@password_reset_bp.route('/forgot-password', methods=['GET', 'POST'])
@limiter.limit('5 per 15 minutes', methods=['POST'])
@limiter.limit('3 per hour', methods=['POST'], key_func=lambda: generate_blind_index(request.form.get('email', '').strip().lower()[:120]))
def forgot():
    ready = recovery_ready()
    sent = False
    entered = request.form.get('email', '').strip().lower()
    error = None
    if request.method == 'POST':
        if not ready:
            error = 'Email recovery is temporarily unavailable. Please contact our team for help.'
        elif len(entered) > 120 or not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', entered):
            error = 'Enter a valid email address.'
        else:
            user = User.query.filter_by(email_hash=generate_blind_index(entered)).first()
            if user:
                token = secrets.token_urlsafe(32)
                token_hash = fingerprint(token)
                PasswordReset.query.filter(PasswordReset.expires_at <= datetime.utcnow()).delete()
                db.session.add(PasswordReset(
                    token_hash=token_hash, user_id=user.id,
                    password_fingerprint=fingerprint(user.password_hash),
                    expires_at=datetime.utcnow() + timedelta(minutes=30)))
                db.session.commit()
                link = current_app.config['PASSWORD_RESET_BASE_URL'] + url_for('password_reset.reset', token=token)
                app = current_app._get_current_object()
                if app.testing:
                    deliver_reset(app, user.email, link, token_hash)
                else:
                    Thread(target=deliver_reset, args=(app, user.email, link, token_hash), daemon=True).start()
            sent = True
    return render_template('password_recovery.html', mode='forgot', ready=ready,
                           sent=sent, error=error, entered=entered, generic_message=GENERIC_MESSAGE,
                           private_auth_page=True, canonical=url_for('password_reset.forgot', _external=True))


@password_reset_bp.route('/reset-password', methods=['GET', 'POST'])
@limiter.limit('10 per 15 minutes', methods=['POST'])
def reset():
    token = request.form.get('token', '') if request.method == 'POST' else request.args.get('token', '')
    record = None
    if 20 <= len(token) <= 128:
        record = PasswordReset.query.filter_by(token_hash=fingerprint(token)).first()
    valid = bool(record and record.expires_at > datetime.utcnow() and record.user and
                 secrets.compare_digest(record.password_fingerprint, fingerprint(record.user.password_hash)))
    error = None
    if request.method == 'POST' and valid:
        password = request.form.get('password', '')
        confirmation = request.form.get('confirm_password', '')
        if not 8 <= len(password) <= 128:
            error = 'Use a password between 8 and 128 characters.'
        elif password != confirmation:
            error = 'The passwords do not match. Please enter them again.'
        else:
            user_id, old_hash = record.user_id, record.user.password_hash
            # Atomic password comparison ensures concurrent uses of any outstanding
            # link can change the password only once, including across workers.
            live_link = db.session.query(PasswordReset.id).filter(
                PasswordReset.token_hash == fingerprint(token),
                PasswordReset.expires_at > datetime.utcnow()).exists()
            changed = User.query.filter_by(id=user_id, password_hash=old_hash).filter(live_link).update(
                {'password_hash': generate_password_hash(password)}, synchronize_session=False)
            if changed:
                PasswordReset.query.filter_by(user_id=user_id).delete(synchronize_session=False)
                db.session.commit()
                logout_user()
                flash('Your password has been reset. Sign in with your new password.', 'success')
                return redirect(url_for('public.login'))
            db.session.rollback()
            valid = False
    return render_template('password_recovery.html', mode='reset', valid=valid, token=token,
                           error=error, private_auth_page=True,
                           canonical=url_for('password_reset.reset', _external=True)), (200 if valid else 400)
