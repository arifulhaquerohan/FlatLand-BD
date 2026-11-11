"""Run with: venv/bin/python -m unittest discover -s tests -v.

Uses a temporary database and uploads directory; never the development data.
"""
import atexit
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

_sandbox = tempfile.TemporaryDirectory(prefix='flatland-tests-')
atexit.register(_sandbox.cleanup)
os.environ.update({
    'INSTANCE_PATH': _sandbox.name,
    'DATABASE_URL': 'sqlite:///' + _sandbox.name + '/test.db',
    'SECRET_KEY': 'regression-tests-session-key-1234567890',
    'DATA_ENCRYPTION_KEY': 'regression-tests-data-key-1234567890',
    'ADMIN_PASSWORD': '', 'REDIS_URL': '', 'RATELIMIT_STORAGE_URI': 'memory://',
    'MAIL_SERVER': '', 'ADMIN_PATH': 'test-console',
    'FORCE_HTTPS': '0', 'TRUST_PROXY': '0',
})

from backend.app import app
from backend.extensions import limiter
from backend.models import db, User, Flat, InteriorService, FlatImage, MediaAsset, Lead, PageView
from backend.utils import (_STATS_CACHE, coerce_float, delete_media_url,
                           get_cached_value, safe_redirect_target)


class RegressionTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, SESSION_COOKIE_SECURE=False)
        limiter.enabled = False
        self.context = app.app_context()
        self.context.push()
        db.drop_all()
        db.create_all()
        _STATS_CACHE.clear()
        self.client = app.test_client()
        self.user = User(full_name='Test Member', username='test_member', role='admin')
        self.user.phone = '01712345678'
        self.user.set_password('test-password')
        db.session.add(self.user)
        db.session.commit()
        self.user_id = self.user.id
        self.static = tempfile.TemporaryDirectory(dir=_sandbox.name)
        self.old_static = app.static_folder
        app.static_folder = self.static.name

    def tearDown(self):
        db.session.remove()
        app.static_folder = self.old_static
        self.context.pop()
        self.static.cleanup()

    def login(self):
        response = self.client.post('/login', data={
            'identifier': 'test_member', 'password': 'test-password',
        })
        self.assertEqual(response.status_code, 302)

    def test_login_redirect_only_accepts_same_site_paths(self):
        safe = '/dashboard?view=saved'
        response = self.client.post('/login', data={
            'identifier': 'test_member', 'password': 'test-password',
            'next': safe,
        })
        self.assertEqual(response.location, safe)

        for unsafe in ('//example.com', '/\\example.com', '/%2fexample.com',
                       '/%252fexample.com', '/%0d%0aLocation:example.com'):
            with self.subTest(target=unsafe):
                self.client.get('/logout')
                response = self.client.post('/login', data={
                    'identifier': 'test_member', 'password': 'test-password',
                    'next': unsafe,
                })
                self.assertTrue(response.location.endswith('/test-console/'))

    def test_redirect_validator_rejects_encoded_network_paths(self):
        self.assertEqual(safe_redirect_target('/flats?page=2'), '/flats?page=2')
        for unsafe in ('//example.com', '/%2fexample.com', '/%252fexample.com',
                       '/%5cexample.com', '/%00example.com'):
            with self.subTest(target=unsafe):
                self.assertEqual(safe_redirect_target(unsafe), '')

    def listing(self):
        flat = Flat(title='Test flat', location='Dhaka', description='A test flat',
                    price=100000, user_id=self.user_id, status='approved',
                    image_url='/static/uploads/cover.webp')
        flat.images.append(FlatImage(image_url='/static/uploads/gallery.webp'))
        db.session.add(flat)
        for name in ('cover', 'gallery'):
            path = Path(app.static_folder, 'uploads', name + '.webp')
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(b'test image')
            db.session.add(MediaAsset(image_url='/static/uploads/' + name + '.webp',
                                      storage_provider='local', storage_key=str(path)))
        db.session.commit()
        return flat

    def google_signin(self, subject='google-member', email='google@example.com', nonce='test-nonce'):
        import time
        app.config['GOOGLE_CLIENT_ID'] = 'test-client.apps.googleusercontent.com'
        with self.client.session_transaction() as state:
            state['google_nonce'] = {'value': 'test-nonce', 'created': time.time()}
        claims = {'sub': subject, 'email': email, 'email_verified': True,
                  'name': 'Google Member', 'nonce': nonce}
        with patch('backend.blueprints.google_auth.id_token.verify_oauth2_token', return_value=claims) as verify:
            response = self.client.post('/auth/google', data={'credential': 'signed-token'})
            verify.assert_called_once()
            self.assertEqual(verify.call_args.args[2], app.config['GOOGLE_CLIENT_ID'])
        return response

    def test_google_new_member_and_returning_login(self):
        from backend.models import GoogleIdentity
        response = self.google_signin()
        self.assertTrue(response.location.endswith('/auth/google/complete'))
        self.assertEqual(self.client.get(response.location).status_code, 200)
        response = self.client.post('/auth/google/complete', data={
            'username': 'google_member', 'phone': '01812345678', 'confirm': '1'})
        self.assertEqual(response.status_code, 302)
        identity = GoogleIdentity.query.one()
        self.assertEqual(identity.user.email, 'google@example.com')
        self.assertEqual(identity.user.role, 'user')
        self.client.get('/logout')
        self.google_signin()
        with self.client.session_transaction() as state:
            self.assertEqual(state['_user_id'], identity.user.get_id())

    def test_google_rejects_invalid_nonce_and_expired_pending(self):
        self.google_signin(nonce='wrong-nonce')
        with self.client.session_transaction() as state:
            self.assertNotIn('google_pending', state)
            self.assertNotIn('_user_id', state)
            state['google_pending'] = {'created': 0}
        self.assertEqual(self.client.post('/auth/google/complete').status_code, 302)

    def test_google_link_requires_existing_password(self):
        from backend.models import GoogleIdentity
        self.user.email = 'existing@example.com'
        db.session.commit()
        self.google_signin(email='existing@example.com')
        response = self.client.post('/auth/google/complete', data={'password': 'wrong'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(GoogleIdentity.query.count(), 0)
        self.client.post('/auth/google/complete', data={'password': 'test-password'})
        self.assertEqual(GoogleIdentity.query.one().user_id, self.user_id)

    def test_google_duplicate_phone_never_links_account(self):
        from backend.models import GoogleIdentity
        self.google_signin()
        response = self.client.post('/auth/google/complete', data={
            'username': 'google_member', 'phone': '01712345678', 'confirm': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(GoogleIdentity.query.count(), 0)

    def test_google_rejects_invalid_signature(self):
        import time
        app.config['GOOGLE_CLIENT_ID'] = 'test-client.apps.googleusercontent.com'
        with self.client.session_transaction() as state:
            state['google_nonce'] = {'value': 'test-nonce', 'created': time.time()}
        with patch('backend.blueprints.google_auth.id_token.verify_oauth2_token', side_effect=ValueError('bad signature')):
            response = self.client.post('/auth/google', data={'credential': 'forged-token'})
        self.assertTrue(response.location.endswith('/login'))
        with self.client.session_transaction() as state:
            self.assertNotIn('_user_id', state)
            self.assertNotIn('google_pending', state)

    def test_google_button_only_appears_when_configured(self):
        app.config['GOOGLE_CLIENT_ID'] = ''
        self.assertNotIn(b'g_id_onload', self.client.get('/register').data)
        app.config['GOOGLE_CLIENT_ID'] = 'test-client.apps.googleusercontent.com'
        for path in ('/login', '/register'):
            response = self.client.get(path)
            self.assertIn(b'g_id_onload', response.data)
            self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_google_csrf_required(self):
        app.config['WTF_CSRF_ENABLED'] = True
        try:
            self.client.post('/auth/google', data={'credential': 'token'})
            with self.client.session_transaction() as state:
                self.assertNotIn('google_pending', state)
                self.assertNotIn('_user_id', state)
        finally:
            app.config['WTF_CSRF_ENABLED'] = False

    def issue_reset(self):
        from urllib.parse import urlsplit, parse_qs
        self.user.email = 'member@example.com'
        db.session.commit()
        config = {'MAIL_SERVER': 'smtp.example.com', 'MAIL_DEFAULT_SENDER': 'noreply@example.com',
                  'PASSWORD_RESET_BASE_URL': 'https://flatland.example'}
        with patch.dict(app.config, config), patch('backend.blueprints.password_reset.mail.send') as send:
            response = self.client.post('/forgot-password', data={'email': 'member@example.com'},
                                        headers={'Host': 'attacker.example'})
            self.assertEqual(response.status_code, 200)
            send.assert_called_once()
            message = send.call_args.args[0]
            link = next(line for line in message.body.splitlines() if line.startswith('https://'))
            self.assertTrue(link.startswith('https://flatland.example/'))
            self.assertIn('Reset my password', message.html)
            self.assertIn('#a8541f', message.html)
            self.assertIn(link, message.html)
            self.assertIn('cid:flatland-logo', message.html)
            self.assertEqual(len(message.attachments), 1)
            self.assertEqual(message.attachments[0].content_type, 'image/png')
            self.assertEqual(message.attachments[0].headers['Content-ID'], '<flatland-logo>')
            return parse_qs(urlsplit(link).query)['token'][0]

    def test_password_reset_single_use_and_session_revocation(self):
        from backend.models import PasswordReset
        self.login()
        token = self.issue_reset()
        old_hash = self.user.password_hash
        self.assertNotEqual(PasswordReset.query.one().token_hash, token)
        recovery_client = app.test_client()
        page = recovery_client.get('/reset-password', query_string={'token': token})
        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.headers['Referrer-Policy'], 'no-referrer')
        self.assertEqual(page.headers['Cache-Control'], 'no-store')
        response = recovery_client.post('/reset-password', data={
            'token': token, 'password': 'new-long-password', 'confirm_password': 'new-long-password'})
        self.assertEqual(response.status_code, 302)
        db.session.expire_all()
        self.assertTrue(self.user.check_password('new-long-password'))
        self.assertNotEqual(self.user.password_hash, old_hash)
        self.assertEqual(PasswordReset.query.count(), 0)
        self.assertEqual(recovery_client.get('/reset-password', query_string={'token': token}).status_code, 400)
        self.assertEqual(self.client.get('/dashboard').status_code, 302)

    def test_password_reset_invalidates_all_outstanding_links(self):
        from backend.models import PasswordReset
        first = self.issue_reset()
        second = self.issue_reset()
        self.assertEqual(PasswordReset.query.count(), 2)
        self.client.post('/reset-password', data={
            'token': first, 'password': 'replacement-password', 'confirm_password': 'replacement-password'})
        self.assertEqual(self.client.get('/reset-password', query_string={'token': second}).status_code, 400)
        rejected = self.client.post('/login', data={'identifier': 'test_member', 'password': 'test-password'})
        self.assertEqual(rejected.status_code, 200)
        accepted = self.client.post('/login', data={'identifier': 'test_member', 'password': 'replacement-password'})
        self.assertEqual(accepted.status_code, 302)

    def test_password_reset_rejects_expired_and_forged_tokens(self):
        from backend.models import PasswordReset
        from datetime import datetime, timedelta
        token = self.issue_reset()
        PasswordReset.query.one().expires_at = datetime.utcnow() - timedelta(seconds=1)
        db.session.commit()
        for value in (token, 'forged-token-that-is-long-enough'):
            response = self.client.post('/reset-password', data={
                'token': value, 'password': 'new-password', 'confirm_password': 'new-password'})
            self.assertEqual(response.status_code, 400)
        self.assertTrue(self.user.check_password('test-password'))

    def test_password_reset_validation_preserves_valid_link(self):
        from backend.models import PasswordReset
        token = self.issue_reset()
        for password, confirmation in (('short', 'short'), ('new-password', 'different-password')):
            self.client.post('/reset-password', data={
                'token': token, 'password': password, 'confirm_password': confirmation})
            self.assertTrue(self.user.check_password('test-password'))
            self.assertEqual(PasswordReset.query.count(), 1)

    def test_password_reset_unknown_email_has_same_confirmation(self):
        self.issue_reset()
        config = {'MAIL_SERVER': 'smtp.example.com', 'MAIL_DEFAULT_SENDER': 'noreply@example.com',
                  'PASSWORD_RESET_BASE_URL': 'https://flatland.example'}
        with patch.dict(app.config, config), patch('backend.blueprints.password_reset.mail.send') as send:
            known = self.client.post('/forgot-password', data={'email': 'member@example.com'})
            unknown = self.client.post('/forgot-password', data={'email': 'unknown@example.com'})
            self.assertIn(b'If that email belongs to an account, a reset link will arrive shortly.', known.data)
            self.assertIn(b'If that email belongs to an account, a reset link will arrive shortly.', unknown.data)
            self.assertIn(b'Check your inbox and spam folder', unknown.data)
            self.assertEqual(send.call_count, 1)

    def test_password_recovery_sent_state_offers_resend(self):
        self.user.email = 'member@example.com'
        db.session.commit()
        config = {'MAIL_SERVER': 'smtp.example.com', 'MAIL_DEFAULT_SENDER': 'noreply@example.com',
                  'PASSWORD_RESET_BASE_URL': 'https://flatland.example'}
        with patch.dict(app.config, config), patch('backend.blueprints.password_reset.mail.send'):
            response = self.client.post('/forgot-password', data={'email': 'member@example.com'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Resend reset email', response.data)
        self.assertIn(b'Check your inbox and spam folder', response.data)

    def test_password_recovery_requires_configuration_and_csrf(self):
        from backend.models import PasswordReset
        with patch.dict(app.config, {'MAIL_SERVER': '', 'PASSWORD_RESET_BASE_URL': ''}):
            response = self.client.post('/forgot-password', data={'email': 'member@example.com'})
            self.assertIn(b'temporarily unavailable', response.data)
            self.assertEqual(PasswordReset.query.count(), 0)
        token = self.issue_reset()
        app.config['WTF_CSRF_ENABLED'] = True
        try:
            self.client.post('/reset-password', data={
                'token': token, 'password': 'new-password', 'confirm_password': 'new-password'})
            self.assertTrue(self.user.check_password('test-password'))
            self.assertEqual(PasswordReset.query.count(), 1)
        finally:
            app.config['WTF_CSRF_ENABLED'] = False

    def test_analytics_rejects_non_object_json(self):
        for payload in ([1], 'invalid', 42, True):
            with self.subTest(payload=payload):
                response = self.client.post('/collect', json=payload)
                self.assertEqual(response.status_code, 204)
        self.assertEqual(PageView.query.count(), 0)

    def test_analytics_excludes_configured_admin_and_classifies_ipad(self):
        headers = {'User-Agent': 'Mozilla/5.0 (iPad; CPU OS 17_0) Mobile/15E148'}
        self.client.post('/collect', json={'p': '/test-console/media'}, headers=headers)
        self.assertEqual(PageView.query.count(), 0)
        self.client.post('/collect', json={'p': '/flats'}, headers=headers)
        self.assertEqual(PageView.query.one().device, 'tablet')

    def test_huge_page_number_does_not_crash(self):
        for route in ('/flats', '/interior'):
            with self.subTest(route=route):
                self.assertEqual(self.client.get(route + '?page=' + '9' * 100).status_code, 200)

    def test_huge_bedroom_filter_does_not_crash(self):
        self.assertEqual(self.client.get('/flats?bhk=' + '9' * 100).status_code, 200)

    def test_contact_fallback_is_saved(self):
        for contact in ('visitor@example.com', '+880 1712 345678'):
            response = self.client.post('/contact', data={
                'name': 'Visitor', 'contact': contact, 'message': 'Please call me',
            })
            self.assertEqual(response.status_code, 302)
        self.assertEqual(Lead.query.count(), 2)
        self.assertEqual(Lead.query.order_by(Lead.id).first().email, 'visitor@example.com')

    def test_non_finite_prices_use_fallback(self):
        for value in ('nan', 'inf', '-inf', '1e1000'):
            self.assertEqual(coerce_float(value, 50), 50)

    def test_member_delete_clears_cache_and_media_metadata(self):
        flat = self.listing()
        flat_id = flat.id
        self.user.role = 'user'
        db.session.commit()
        self.login()
        get_cached_value('public_stats', 120, lambda: {'flats': 1})
        response = self.client.post('/listing/flat/%d/delete' % flat_id)
        self.assertEqual(response.status_code, 302)
        db.session.remove()
        self.assertIsNone(db.session.get(Flat, flat_id))
        self.assertEqual(FlatImage.query.count(), 0)
        self.assertEqual(MediaAsset.query.count(), 0)
        self.assertFalse(Path(app.static_folder, 'uploads/cover.webp').exists())
        self.assertFalse(Path(app.static_folder, 'uploads/gallery.webp').exists())
        self.assertNotIn('public_stats', _STATS_CACHE)

    def test_failed_edit_does_not_delete_existing_photos(self):
        flat = self.listing()
        self.login()
        with patch.object(db.session, 'commit', side_effect=RuntimeError('Database unavailable')):
            with self.assertRaises(RuntimeError):
                self.client.post('/test-console/edit/flat/%d' % flat.id, data={
                    'title': 'Updated', 'location': 'Dhaka', 'description': 'Updated',
                    'image_url': 'https://example.com/new.webp',
                    'remove_image_ids': str(flat.images[0].id),
                })
        db.session.rollback()
        for name in ('cover', 'gallery'):
            self.assertTrue(Path(app.static_folder, 'uploads', name + '.webp').exists())

    def test_successful_edit_removes_replaced_photos_and_metadata(self):
        flat = self.listing()
        self.login()
        response = self.client.post('/test-console/edit/flat/%d' % flat.id, data={
            'title': 'Updated', 'location': 'Dhaka', 'description': 'Updated',
            'image_url': 'https://example.com/new.webp',
            'remove_image_ids': str(flat.images[0].id),
        })
        self.assertEqual(response.status_code, 302)
        db.session.remove()
        self.assertEqual(MediaAsset.query.count(), 0)
        self.assertEqual(FlatImage.query.count(), 0)
        self.assertFalse(Path(app.static_folder, 'uploads/cover.webp').exists())
        self.assertFalse(Path(app.static_folder, 'uploads/gallery.webp').exists())

    def assert_admin_delete_cleans_media(self, bulk):
        self.login()
        flat = self.listing()
        if bulk:
            response = self.client.post('/test-console/bulk/flat', data={
                'ids': str(flat.id), 'action': 'delete',
            })
        else:
            response = self.client.post('/test-console/delete/flat/%d' % flat.id)
        self.assertEqual(response.status_code, 302)
        db.session.remove()
        self.assertEqual(Flat.query.count(), 0)
        self.assertEqual(FlatImage.query.count(), 0)
        self.assertEqual(MediaAsset.query.count(), 0)
        self.assertFalse(Path(app.static_folder, 'uploads/gallery.webp').exists())

    def test_admin_single_delete_cleans_media(self):
        self.assert_admin_delete_cleans_media(bulk=False)

    def test_admin_bulk_delete_cleans_media(self):
        self.assert_admin_delete_cleans_media(bulk=True)

    def test_shared_image_survives_deleting_one_listing(self):
        flat = self.listing()
        shared = Flat(title='Shared photo', location='Dhaka', description='Test',
                      price=200000, user_id=self.user.id, image_url=flat.image_url)
        db.session.add(shared)
        db.session.commit()
        self.login()
        self.client.post('/test-console/delete/flat/%d' % flat.id)
        db.session.remove()
        self.assertTrue(Path(app.static_folder, 'uploads/cover.webp').exists())
        self.assertEqual(MediaAsset.query.count(), 1)

    def test_public_and_admin_pages_render(self):
        flat = self.listing()
        for route in ('/', '/flats', '/interior', '/flat/%d' % flat.id,
                      '/login', '/register', '/sitemap.xml', '/robots.txt'):
            with self.subTest(route=route):
                self.assertEqual(self.client.get(route).status_code, 200)
        self.login()
        for route in ('/test-console', '/test-console?tab=services',
                      '/test-console?tab=leads', '/test-console/media',
                      '/test-console/system', '/test-console/preview',
                      '/test-console/edit/flat/%d' % flat.id, '/post-listing'):
            with self.subTest(route=route):
                self.assertEqual(self.client.get(route, follow_redirects=True).status_code, 200)
        self.assertEqual(self.client.get('/test-console?page=' + '9' * 100).status_code, 200)

    def test_admin_review_queue_links_to_each_pending_content_type(self):
        service = InteriorService(
            provider_name='Pending Studio', service_type='Full home',
            description='Pending interior studio', status='pending', user_id=self.user.id)
        db.session.add(service)
        db.session.commit()
        self.login()
        response = self.client.get('/test-console')
        self.assertEqual(response.status_code, 200)
        queue_cell = response.data.split(b'Awaiting review', 1)[1].split(b'</article>', 1)[0]
        self.assertIn(b'tab=services&amp;status=pending', queue_cell)
        self.assertNotIn(b'tab=flats&amp;status=pending', queue_cell)

        flat = self.listing()
        flat.status = 'pending'
        db.session.commit()
        _STATS_CACHE.clear()
        response = self.client.get('/test-console')
        queue_cell = response.data.split(b'Awaiting review', 1)[1].split(b'</article>', 1)[0]
        self.assertIn(b'tab=services&amp;status=pending', queue_cell)
        self.assertIn(b'tab=flats&amp;status=pending', queue_cell)

    def test_local_cleanup_cannot_delete_outside_upload_directory(self):
        protected = Path(app.static_folder, 'protected.txt')
        protected.write_text('keep me')
        Path(app.static_folder, 'uploads').mkdir()
        self.assertFalse(delete_media_url('/static/uploads/../protected.txt'))
        self.assertTrue(protected.exists())


if __name__ == '__main__':
    unittest.main()
