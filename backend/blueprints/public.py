from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, Response, current_app
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime
from sqlalchemy import or_
from sqlalchemy.orm import load_only, selectinload
from flask_mail import Message

from ..models import db, User, Flat, InteriorService, FlatImage, InteriorImage, Lead
from ..forms import LoginForm, ContactForm, RegisterForm
from ..extensions import limiter, mail
from ..utils import get_cached_value, extract_youtube_id, build_youtube_embed, build_youtube_watch, summarize_text, save_uploaded_image, parse_image_urls, coerce_float, coerce_int, collect_uploaded_images, delete_listing_media

public_bp = Blueprint('public', __name__)


def normalize_bd_phone(value):
    """Return a clean 11-digit Bangladeshi mobile number, or '' when invalid.

    Accepts what people actually type - +8801712345678, 8801712345678,
    01712345678, 017 1234 5678 - and always stores the canonical 11 digits.
    """
    import re
    if not value:
        return ''
    digits = re.sub(r'\D', '', str(value))
    if digits.startswith('880'):
        digits = '0' + digits[3:]
    elif len(digits) == 10 and digits.startswith('1'):
        digits = '0' + digits
    if re.match(r'^01[3-9]\d{8}$', digits):
        return digits
    return ''

def flat_card_payload(flat):
    return {
        'id': flat.id,
        'title': flat.title,
        'location': flat.location,
        'price': flat.price,
        'bhk': flat.bhk,
        'area_sqft': flat.area_sqft,
        'image_url': flat.image_url,
    }

def service_card_payload(service):
    return {
        'id': service.id,
        'provider_name': service.provider_name,
        'service_type': service.service_type,
        'description': service.description,
        'starting_price': service.starting_price,
        'image_url': service.image_url,
    }

@public_bp.route('/')
def index():
    cache_ttl = current_app.config['PUBLIC_CACHE_TTL']
    stats = get_cached_value(
        'public_stats', cache_ttl,
        lambda: {
            'flats': Flat.query.filter_by(status='approved').count(),
            'studios': InteriorService.query.filter_by(status='approved').count(),
        }
    )
    featured_flats = get_cached_value(
        'public_featured_flats_v1',
        cache_ttl,
        lambda: [
            flat_card_payload(flat)
            for flat in Flat.query.filter_by(status='approved').options(
                load_only(Flat.id, Flat.title, Flat.location, Flat.price, Flat.bhk, Flat.area_sqft, Flat.image_url, Flat.created_at)
            ).order_by(Flat.created_at.desc()).limit(3).all()
        ],
    )
    featured_services = get_cached_value(
        'public_featured_services_v1',
        cache_ttl,
        lambda: [
            service_card_payload(service)
            for service in InteriorService.query.filter_by(status='approved').options(
                load_only(InteriorService.id, InteriorService.provider_name, InteriorService.service_type, InteriorService.description, InteriorService.starting_price, InteriorService.image_url, InteriorService.created_at)
            ).order_by(InteriorService.created_at.desc()).limit(3).all()
        ],
    )
    return render_template(
        'index.html',
        stats=stats,
        featured_flats=featured_flats,
        featured_services=featured_services,
        meta_description=current_app.config['DEFAULT_META_DESCRIPTION'],
        meta_image=current_app.config['DEFAULT_OG_IMAGE'],
    )

@public_bp.route('/robots.txt')
def robots():
    admin_path = current_app.config.get('ADMIN_PATH', 'admin')
    rules = [
        'User-agent: *',
        f'Disallow: /{admin_path}',
        'Disallow: /preview',
        'Disallow: /login',
        'Disallow: /post-listing',
        f'Sitemap: {url_for("public.sitemap", _external=True)}',
    ]
    return Response('\n'.join(rules), mimetype='text/plain')

@public_bp.route('/sitemap.xml')
def sitemap():
    pages = []
    today = datetime.utcnow().date().isoformat()
    static_pages = ['public.index', 'public.flats', 'public.interior', 'public.login']
    for endpoint in static_pages:
        pages.append({'loc': url_for(endpoint, _external=True), 'lastmod': today})

    flats = Flat.query.filter_by(status='approved').with_entities(Flat.id, Flat.created_at).all()
    for flat_id, created_at in flats:
        lastmod = created_at.date().isoformat() if created_at else today
        pages.append({'loc': url_for('public.flat_detail', id=flat_id, _external=True), 'lastmod': lastmod})

    services = InteriorService.query.filter_by(status='approved').with_entities(
        InteriorService.id, InteriorService.created_at
    ).all()
    for service_id, created_at in services:
        lastmod = created_at.date().isoformat() if created_at else today
        pages.append({'loc': url_for('public.interior_detail', id=service_id, _external=True), 'lastmod': lastmod})

    xml = render_template('sitemap.xml', pages=pages)
    return Response(xml, mimetype='application/xml')

@public_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('public.index'))
        
    form = LoginForm()
    if request.method == 'POST':
        # Using WTF form validation if possible
        identifier = request.form.get('identifier', '').strip()
        password = request.form.get('password', '')
        remember = True if request.form.get('remember') else False
        
        from ..utils_security import generate_blind_index
        from sqlalchemy import or_
        
        from ..utils_username import normalize_username

        # One identifier field that accepts a username, an 11-digit
        # Bangladeshi mobile number, or an email - whichever the member
        # remembers. Full names are no longer accepted as a login.
        lookups = []
        username_clean = normalize_username(identifier)
        if username_clean:
            lookups.append(User.username == username_clean)
        phone_digits = normalize_bd_phone(identifier)
        if phone_digits:
            lookups.append(User.phone_hash == generate_blind_index(phone_digits))
        if '@' in identifier:
            lookups.append(User.email_hash == generate_blind_index(identifier.lower()))
        
        user = None
        if lookups:
            user = User.query.filter(or_(*lookups)).first()
        
        if user and user.check_password(password):
            login_user(user, remember=remember)
            from ..utils import safe_next_path
            next_page = request.args.get('next')
            if next_page:
                return redirect(safe_next_path())
            if user.is_admin():
                return redirect(url_for('admin.admin_dashboard'))
            return redirect(url_for('public.dashboard'))
        
        flash('Wrong username, mobile number, email or password.', 'danger')
    return render_template(
        'login.html',
        meta_description='Sign in to FlatLand BD.',
        meta_type='website',
    )

@public_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('public.index'))

@public_bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("5 per minute", methods=["POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('public.index'))
    
    form = RegisterForm()
    if request.method == 'POST':
        from ..utils_security import generate_blind_index
        from ..utils_username import validate_username, is_username_taken

        full_name = request.form.get('full_name', '').strip()
        raw_username = request.form.get('username', '').strip()
        raw_phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        # Keep what the visitor typed so a mistake never wipes the whole form.
        entered = {'full_name': full_name, 'username': raw_username,
                   'phone': raw_phone, 'email': email}

        def reject(message):
            flash(message, 'danger')
            return render_template('register.html', form=form, entered=entered)

        if not full_name:
            return reject('Please enter your full name.')

        username_ok, username_result = validate_username(raw_username)
        if not username_ok:
            return reject(username_result)
        username = username_result
        if is_username_taken(username):
            return reject('The username "%s" is already taken. Please choose another.' % username)

        phone = normalize_bd_phone(raw_phone)
        if not phone:
            return reject('Enter an 11-digit Bangladeshi mobile number, e.g. 01712345678.')

        if len(password) < 8:
            return reject('Password must be at least 8 characters.')

        if User.query.filter_by(phone_hash=generate_blind_index(phone)).first():
            flash('An account with this mobile number already exists. Please sign in.', 'danger')
            return redirect(url_for('public.login'))

        # Email is entirely optional - only checked when one was provided.
        if email:
            if User.query.filter_by(email_hash=generate_blind_index(email)).first():
                flash('An account with this email already exists. Please sign in.', 'danger')
                return redirect(url_for('public.login'))

        new_user = User(full_name=full_name, username=username)
        new_user.phone = phone
        if email:
            new_user.email = email
        new_user.set_password(password)

        db.session.add(new_user)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            return reject('That username was just taken. Please try a different one.')

        login_user(new_user)
        flash('Welcome to FlatLand BD, @%s!' % username, 'success')
        return redirect(url_for('public.dashboard'))

    return render_template('register.html', form=form, entered={})


@public_bp.route('/username-available')
@limiter.limit("40 per minute")
def username_available():
    """Live check used by the register form as the visitor types."""
    from flask import jsonify
    from ..utils_username import validate_username, is_username_taken, suggest_usernames

    raw = request.args.get('u', '')
    ok, result = validate_username(raw)
    if not ok:
        return jsonify({'status': 'invalid', 'message': result, 'suggestions': []})
    if is_username_taken(result):
        return jsonify({
            'status': 'taken',
            'username': result,
            'message': '@%s is already taken.' % result,
            'suggestions': suggest_usernames(result, limit=3),
        })
    return jsonify({
        'status': 'available',
        'username': result,
        'message': '@%s is available.' % result,
        'suggestions': [],
    })

@public_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.is_admin():
        return redirect(url_for('admin.admin_dashboard'))
    user_flats = Flat.query.filter_by(user_id=current_user.id).order_by(Flat.created_at.desc()).all()
    user_services = InteriorService.query.filter_by(user_id=current_user.id).order_by(InteriorService.created_at.desc()).all()
    return render_template('dashboard.html', flats=user_flats, services=user_services)

@public_bp.route('/listing/<item_type>/<int:id>/delete', methods=['POST'])
@login_required
@limiter.limit("20 per minute")
def delete_own_listing(item_type, id):
    """Let a member delete their own listing.

    The stored photos (Cloudinary or local disk) are removed at the same time
    so nothing is orphaned in storage.
    """
    if item_type == 'flat':
        item = Flat.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    elif item_type == 'interior':
        item = InteriorService.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    else:
        abort(404)
    delete_listing_media(item)
    db.session.delete(item)
    db.session.commit()
    flash('Listing deleted.', 'success')
    return redirect(url_for('public.dashboard'))

@public_bp.route('/contact', methods=['POST'])
@limiter.limit("10 per hour")
def contact():
    form = ContactForm()
    
    name = request.form.get('name', '').strip()
    phone = request.form.get('phone', '').strip()
    email = request.form.get('email', '').strip().lower()
    contact_info = request.form.get('contact', '').strip() # Fallback
    interest = request.form.get('interest', '').strip()[:40]
    message = request.form.get('message', '').strip()
    budget = request.form.get('budget', '').strip()
    service_type = request.form.get('service_type', '').strip()
    timeline = request.form.get('timeline', '').strip()

    if contact_info and not phone and not email:
        if '@' in contact_info:
            email = contact_info.lower()
        else:
            phone = contact_info

    meta_lines = []
    if budget: meta_lines.append(f"Budget: {budget}")
    if service_type: meta_lines.append(f"Service: {service_type}")
    if timeline: meta_lines.append(f"Timeline: {timeline}")
    if meta_lines: message = "\n".join(meta_lines + ([message] if message else []))

    if not name or not message:
        flash('Please provide your name and a message.', 'warning')
        return redirect(request.referrer or url_for('public.index'))

    if not phone and not email:
        flash('Please provide a contact number or email.', 'warning')
        return redirect(request.referrer or url_for('public.index'))

    lead = Lead(
        name=name,
        phone=phone,
        email=email,
        interest=interest,
        message=message,
        status='new',
    )
    db.session.add(lead)
    db.session.commit()
    
    # 2. EMAIL NOTIFICATIONS (Send email if mail is configured)
    try:
        if current_app.config.get('MAIL_SERVER') and current_app.config.get('ADMIN_EMAIL'):
            msg = Message(
                subject=f"New Lead from {name} - FlatlandBD",
                sender=current_app.config.get('MAIL_DEFAULT_SENDER'),
                recipients=[current_app.config.get('ADMIN_EMAIL')],
                body=f"New Contact Formulation:\nName: {name}\nPhone: {phone}\nEmail: {email}\nInterest: {interest}\n\nMessage:\n{message}"
            )
            mail.send(msg)
    except Exception as e:
        print("Mail sending failed:", e)

    flash('Thanks! We will contact you shortly.', 'success')
    return redirect(request.referrer or url_for('public.index'))

@public_bp.route('/flat/<int:id>')
def flat_detail(id):
    flat = Flat.query.options(
        load_only(Flat.id, Flat.title, Flat.description, Flat.price, Flat.location, Flat.area_sqft, Flat.bhk, Flat.image_url, Flat.video_url, Flat.status),
        selectinload(Flat.images).load_only(FlatImage.id, FlatImage.image_url),
    ).get_or_404(id)
    if flat.status != 'approved':
        if not current_user.is_authenticated or current_user.role != 'admin':
            abort(404)
    related_flats = Flat.query.filter(
        Flat.status == 'approved',
        Flat.id != flat.id,
    ).options(
        load_only(Flat.id, Flat.title, Flat.location, Flat.price, Flat.bhk, Flat.area_sqft, Flat.image_url, Flat.created_at)
    ).order_by(Flat.created_at.desc()).limit(3).all()
    return render_template(
        'flat_detail.html',
        flat=flat,
        related_flats=related_flats,
        video_embed_url=build_youtube_embed(flat.video_url),
        video_watch_url=build_youtube_watch(flat.video_url),
        meta_description=summarize_text(flat.description) or current_app.config['DEFAULT_META_DESCRIPTION'],
        meta_image=flat.image_url or current_app.config['DEFAULT_OG_IMAGE'],
        meta_type='article',
    )

@public_bp.route('/interior/<int:id>')
def interior_detail(id):
    service = InteriorService.query.options(
        load_only(InteriorService.id, InteriorService.provider_name, InteriorService.service_type, InteriorService.description, InteriorService.starting_price, InteriorService.image_url, InteriorService.portfolio_url, InteriorService.status),
        selectinload(InteriorService.images).load_only(InteriorImage.id, InteriorImage.image_url),
    ).get_or_404(id)
    if service.status != 'approved':
        if not current_user.is_authenticated or current_user.role != 'admin':
            abort(404)
    related_services = InteriorService.query.filter(
        InteriorService.status == 'approved',
        InteriorService.id != service.id,
    ).options(
        load_only(InteriorService.id, InteriorService.provider_name, InteriorService.service_type, InteriorService.description, InteriorService.starting_price, InteriorService.image_url, InteriorService.created_at)
    ).order_by(InteriorService.created_at.desc()).limit(3).all()
    return render_template(
        'interior_detail.html',
        service=service,
        related_services=related_services,
        meta_description=summarize_text(service.description) or current_app.config['DEFAULT_META_DESCRIPTION'],
        meta_image=service.image_url or current_app.config['DEFAULT_OG_IMAGE'],
        meta_type='article',
    )

@public_bp.route('/flats')
def flats():
    search = request.args.get('search', '').strip()
    bhk = request.args.get('bhk', 'all').strip()
    min_price = request.args.get('min_price', '').strip()
    max_price = request.args.get('max_price', '').strip()
    sort = request.args.get('sort', 'newest').strip()
    page = request.args.get('page', 1, type=int)
    if page < 1: page = 1
    
    per_page = current_app.config['LISTINGS_PER_PAGE']
    sort_options = {
        'newest': Flat.created_at.desc(),
        'price_low': Flat.price.asc(),
        'price_high': Flat.price.desc(),
        'area_high': Flat.area_sqft.desc(),
    }
    if sort not in sort_options: sort = 'newest'

    query = Flat.query.filter_by(status='approved').options(
        load_only(Flat.id, Flat.title, Flat.location, Flat.price, Flat.bhk, Flat.area_sqft, Flat.image_url, Flat.created_at)
    )

    if search:
        like = f"%{search}%"
        query = query.filter(or_(Flat.location.ilike(like), Flat.title.ilike(like)))

    if bhk and bhk != 'all':
        if bhk == '4plus': query = query.filter(Flat.bhk >= 4)
        else:
            try:
                if int(bhk): query = query.filter(Flat.bhk == int(bhk))
            except ValueError: pass

    try: min_price_val = float(min_price) if min_price else None
    except ValueError: min_price_val = None
    if min_price_val is not None: query = query.filter(Flat.price >= min_price_val)

    try: max_price_val = float(max_price) if max_price else None
    except ValueError: max_price_val = None
    if max_price_val is not None: query = query.filter(Flat.price <= max_price_val)

    total_matches = query.order_by(None).count()
    sort_clause = sort_options[sort]
    if sort == 'newest': query = query.order_by(sort_clause)
    else: query = query.order_by(sort_clause, Flat.created_at.desc())
    
    offset = (page - 1) * per_page
    flats_page = query.offset(offset).limit(per_page + 1).all()
    has_next = len(flats_page) > per_page
    has_prev = page > 1
    all_flats = flats_page[:per_page]
    
    filters = {'search': search, 'bhk': bhk, 'min_price': min_price, 'max_price': max_price, 'sort': sort}
    filters_applied = bool(search or (bhk and bhk != 'all') or min_price or max_price)
    
    filter_params = {k: v for k, v in filters.items() if v and v != 'all' and v != 'newest'}
    prev_url = url_for('public.flats', page=page - 1, **filter_params) if has_prev else None
    next_url = url_for('public.flats', page=page + 1, **filter_params) if has_next else None
    
    return render_template(
        'flats.html',
        flats=all_flats,
        filters=filters,
        filters_applied=filters_applied,
        total_matches=total_matches,
        page_listing_count=len(all_flats),
        sort=sort,
        page=page,
        has_prev=has_prev,
        has_next=has_next,
        prev_url=prev_url,
        next_url=next_url,
        meta_description='Browse verified flats for sale in Bangladesh.',
    )

@public_bp.route('/interior')
def interior():
    page = request.args.get('page', 1, type=int)
    if page < 1: page = 1
    per_page = current_app.config['LISTINGS_PER_PAGE']
    
    base_query = InteriorService.query.filter_by(status='approved').options(
        load_only(InteriorService.id, InteriorService.provider_name, InteriorService.service_type, InteriorService.description, InteriorService.starting_price, InteriorService.image_url, InteriorService.created_at)
    )
    total_services = base_query.order_by(None).count()
    query = base_query.order_by(InteriorService.created_at.desc())
    
    offset = (page - 1) * per_page
    services_page = query.offset(offset).limit(per_page + 1).all()
    has_next = len(services_page) > per_page
    has_prev = page > 1
    services = services_page[:per_page]
    
    prev_url = url_for('public.interior', page=page - 1) if has_prev else None
    next_url = url_for('public.interior', page=page + 1) if has_next else None
    
    return render_template(
        'interior.html',
        services=services,
        total_services=total_services,
        page=page,
        has_prev=has_prev,
        has_next=has_next,
        prev_url=prev_url,
        next_url=next_url,
        meta_description='Discover interior design studios and portfolios.',
    )

@public_bp.route('/post-listing', methods=['GET', 'POST'])
@login_required
@limiter.limit("30 per hour")
def post_listing():
    if request.method == 'POST':
        form_type = request.form.get('form_type')
        status = 'pending'
        image_file = request.files.get('image_file')
        gallery_files = request.files.getlist('image_files')
        gallery_urls = parse_image_urls(request.form.get('image_urls', ''))
        uploaded_url = save_uploaded_image(image_file)
        if image_file and image_file.filename and not uploaded_url: flash('Unsupported image type.', 'warning')

        if form_type == 'flat':
            raw_video_url = request.form.get('video_url', '').strip()
            video_url = raw_video_url if extract_youtube_id(raw_video_url) else None
            new_flat = Flat(
                title=request.form.get('title', '').strip(), location=request.form.get('location', '').strip(),
                price=coerce_float(request.form.get('price'), 0), bhk=coerce_int(request.form.get('bhk'), 0),
                area_sqft=coerce_int(request.form.get('area'), 0), description=request.form.get('description', '').strip(),
                image_url=uploaded_url or request.form.get('image_url', '').strip(), video_url=video_url, user_id=current_user.id
            )
            new_flat.status = status
            db.session.add(new_flat)
            extra_urls, invalid = collect_uploaded_images(gallery_files)
            for url in (extra_urls + gallery_urls)[:current_app.config['MAX_GALLERY_IMAGES']]:
                if url and url != new_flat.image_url: db.session.add(FlatImage(flat=new_flat, image_url=url))
        elif form_type == 'interior':
            if not current_user.is_admin():
                abort(403)
            new_service = InteriorService(
                provider_name=request.form.get('provider_name', '').strip(), service_type=request.form.get('service_type', '').strip(),
                starting_price=coerce_float(request.form.get('starting_price'), 0), description=request.form.get('description', '').strip(),
                portfolio_url=request.form.get('portfolio_url', '').strip(), image_url=uploaded_url or request.form.get('image_url', '').strip(),
                user_id=current_user.id
            )
            new_service.status = status
            db.session.add(new_service)
            extra_urls, invalid = collect_uploaded_images(gallery_files)
            for url in (extra_urls + gallery_urls)[:current_app.config['MAX_GALLERY_IMAGES']]:
                if url and url != new_service.image_url: db.session.add(InteriorImage(service=new_service, image_url=url))
        else: abort(400)

        skipped = len(invalid) if isinstance(invalid, (list, tuple, set)) else int(invalid or 0)
        if skipped:
            flash('%d photo(s) were skipped. Use PNG, JPG or WEBP files under the upload limit.' % skipped, 'warning')

        db.session.commit()
        flash('Listing posted successfully! It will appear after admin approval.', 'success')
        return redirect(url_for('public.dashboard'))
    # Members publish flats only. Interior studio profiles stay admin-managed.
    return render_template('post_listing.html', can_post_interior=current_user.is_admin())
