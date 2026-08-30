from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

from werkzeug.security import generate_password_hash, check_password_hash

from .utils_security import encrypt_data, decrypt_data, generate_blind_index

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)

    # One username per customer, reserved for life of the account.
    # Nullable so accounts created before this feature keep working; every new
    # registration sets it, and existing rows are backfilled on first boot.
    username = db.Column(db.String(30), unique=True, nullable=True, index=True)

    phone_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    phone_encrypted = db.Column(db.String(255), nullable=False)
    
    email_hash = db.Column(db.String(64), unique=True, nullable=True, index=True)
    email_encrypted = db.Column(db.String(255), nullable=True)
    
    profile_picture = db.Column(db.String(500), nullable=True)
    
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='user') # user, designer, admin
    flats = db.relationship('Flat', backref='owner', lazy=True)
    interior_listings = db.relationship('InteriorService', backref='provider', lazy=True)

    @property
    def display_name(self):
        return self.full_name or self.username or 'Member'

    @property
    def phone(self):
        return decrypt_data(self.phone_encrypted)

    @phone.setter
    def phone(self, value):
        self.phone_encrypted = encrypt_data(value)
        self.phone_hash = generate_blind_index(value)
        
    @property
    def email(self):
        if not self.email_encrypted:
            return None
        return decrypt_data(self.email_encrypted)

    @email.setter
    def email(self, value):
        if value:
            self.email_encrypted = encrypt_data(value)
            self.email_hash = generate_blind_index(value.lower())
        else:
            self.email_encrypted = None
            self.email_hash = None

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.role == 'admin'

class Flat(db.Model):
    __table_args__ = (
        db.Index('idx_flat_status_created', 'status', 'created_at'),
        db.Index('idx_flat_status_price', 'status', 'price'),
        db.Index('idx_flat_status_bhk_price', 'status', 'bhk', 'price'),
    )
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False, index=True)
    location = db.Column(db.String(100), nullable=False, index=True)
    area_sqft = db.Column(db.Integer)
    bhk = db.Column(db.Integer, index=True)
    image_url = db.Column(db.String(500))
    video_url = db.Column(db.String(500))
    status = db.Column(db.String(20), default='pending', index=True) # pending, approved, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    images = db.relationship('FlatImage', backref='flat', lazy=True, cascade='all, delete-orphan', order_by='FlatImage.id')

class InteriorService(db.Model):
    __table_args__ = (
        db.Index('idx_interior_status_created', 'status', 'created_at'),
        db.Index('idx_interior_status_type_created', 'status', 'service_type', 'created_at'),
    )
    id = db.Column(db.Integer, primary_key=True)
    provider_name = db.Column(db.String(100), nullable=False)
    service_type = db.Column(db.String(100), nullable=False, index=True) # Full house, kitchen, etc
    description = db.Column(db.Text, nullable=False)
    starting_price = db.Column(db.Float, index=True)
    image_url = db.Column(db.String(500))
    portfolio_url = db.Column(db.String(500))
    status = db.Column(db.String(20), default='pending', index=True) # pending, approved, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    images = db.relationship('InteriorImage', backref='service', lazy=True, cascade='all, delete-orphan', order_by='InteriorImage.id')

class FlatImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    flat_id = db.Column(db.Integer, db.ForeignKey('flat.id', ondelete='CASCADE'), nullable=False, index=True)
    image_url = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

class InteriorImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(db.Integer, db.ForeignKey('interior_service.id', ondelete='CASCADE'), nullable=False, index=True)
    image_url = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

class MediaAsset(db.Model):
    """Storage metadata for files created by this application.

    Existing URL-only image records deliberately have no matching asset row, so
    cleanup never tries to delete media the application does not own.
    """
    id = db.Column(db.Integer, primary_key=True)
    image_url = db.Column(db.String(500), nullable=False, unique=True, index=True)
    storage_provider = db.Column(db.String(32), nullable=False)
    storage_key = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

class Lead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(40))
    email = db.Column(db.String(120))
    interest = db.Column(db.String(40))
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='new', index=True) # new, contacted, closed
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
