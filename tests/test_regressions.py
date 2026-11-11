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
from backend.models import db, User, Flat, FlatImage, MediaAsset, Lead, PageView
from backend.utils import _STATS_CACHE, coerce_float, delete_media_url, get_cached_value


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

    def test_local_cleanup_cannot_delete_outside_upload_directory(self):
        protected = Path(app.static_folder, 'protected.txt')
        protected.write_text('keep me')
        Path(app.static_folder, 'uploads').mkdir()
        self.assertFalse(delete_media_url('/static/uploads/../protected.txt'))
        self.assertTrue(protected.exists())


if __name__ == '__main__':
    unittest.main()
