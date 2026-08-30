import csv
from io import StringIO
# pyrefly: ignore [missing-import]
from flask import Blueprint, request, render_template, redirect, url_for, flash, abort, Response, current_app
# pyrefly: ignore [missing-import]
from flask_login import current_user
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import joinedload, load_only
# pyrefly: ignore [missing-import]
from sqlalchemy import or_
# pyrefly: ignore [import-error]
from ..models import db, User, Flat, InteriorService, FlatImage, InteriorImage, Lead
# pyrefly: ignore [import-error]
from ..extensions import limiter
# pyrefly: ignore [import-error]
from ..utils import admin_required, get_listing_item, normalize_status, normalize_lead_status, LISTING_STATUSES, LEAD_STATUSES, coerce_int, coerce_float, save_uploaded_image, parse_image_urls, extract_youtube_id, collect_uploaded_images, paginate_query, get_cached_value, collect_admin_stats, normalize_preview_path, generate_listing_description

import os
import sys
import platform
from datetime import datetime, timedelta
# pyrefly: ignore [missing-import]
from flask import jsonify
# pyrefly: ignore [import-error]
from ..models import MediaAsset
# pyrefly: ignore [import-error]
from .. import cloudinary_service
# pyrefly: ignore [import-error]
from ..utils import delete_listing_media, delete_media_for_urls, media_provider_for_url, is_cloudinary_configured

admin_bp = Blueprint('admin', __name__)

# Cells that start with these characters are treated as formulas by
# spreadsheet apps. Prefixing them with a single quote stops CSV formula
# injection (e.g. a lead message beginning with "=" executing in Excel).
_CSV_FORMULA_PREFIXES = ('=', '+', '-', '@', '\t', '\r')

def _csv_safe(value):
    if value is None:
        return ''
    text = str(value)
    if text.startswith(_CSV_FORMULA_PREFIXES):
        return "'" + text
    return text

@admin_bp.route('/export/<item_type>')
@admin_required
@limiter.limit("20 per minute")
def export_data(item_type):
    status_filter = request.args.get('status', 'all').strip().lower()
    search = request.args.get('q', '').strip()

    output = StringIO()
    writer = csv.writer(output)

    if item_type == 'flats':
        if status_filter not in LISTING_STATUSES: status_filter = 'all'
        query = Flat.query.options(joinedload(Flat.owner))
        if status_filter in LISTING_STATUSES: query = query.filter_by(status=status_filter)
        if search:
            like = f"%{search}%"
            query = query.filter(or_(Flat.title.ilike(like), Flat.location.ilike(like)))
        writer.writerow(['id', 'title', 'location', 'price', 'bhk', 'area_sqft', 'status', 'owner', 'created_at', 'image_url', 'video_url'])
        for item in query.order_by(Flat.created_at.desc()).all():
            writer.writerow([_csv_safe(item.id), _csv_safe(item.title), _csv_safe(item.location), _csv_safe(item.price), _csv_safe(item.bhk), _csv_safe(item.area_sqft), _csv_safe(item.status), _csv_safe(item.owner.full_name if item.owner else ''), _csv_safe(item.created_at.isoformat() if item.created_at else ''), _csv_safe(item.image_url or ''), _csv_safe(item.video_url or '')])
        filename = 'flats.csv'
    elif item_type == 'services':
        if status_filter not in LISTING_STATUSES: status_filter = 'all'
        query = InteriorService.query.options(joinedload(InteriorService.provider))
        if status_filter in LISTING_STATUSES: query = query.filter_by(status=status_filter)
        if search:
            like = f"%{search}%"
            query = query.filter(InteriorService.provider_name.ilike(like))
        writer.writerow(['id', 'provider_name', 'service_type', 'starting_price', 'status', 'provider', 'created_at', 'image_url', 'portfolio_url'])
        for item in query.order_by(InteriorService.created_at.desc()).all():
            writer.writerow([_csv_safe(item.id), _csv_safe(item.provider_name), _csv_safe(item.service_type), _csv_safe(item.starting_price), _csv_safe(item.status), _csv_safe(item.provider.full_name if item.provider else ''), _csv_safe(item.created_at.isoformat() if item.created_at else ''), _csv_safe(item.image_url or ''), _csv_safe(item.portfolio_url or '')])
        filename = 'services.csv'
    elif item_type == 'leads':
        if status_filter not in LEAD_STATUSES: status_filter = 'all'
        query = Lead.query
        if status_filter in LEAD_STATUSES: query = query.filter_by(status=status_filter)
        if search:
            like = f"%{search}%"
            query = query.filter(or_(Lead.name.ilike(like), Lead.email.ilike(like), Lead.phone.ilike(like), Lead.message.ilike(like)))
        writer.writerow(['id', 'name', 'phone', 'email', 'interest', 'message', 'status', 'created_at'])
        for item in query.order_by(Lead.created_at.desc()).all():
            writer.writerow([_csv_safe(item.id), _csv_safe(item.name), _csv_safe(item.phone or ''), _csv_safe(item.email or ''), _csv_safe(item.interest or ''), _csv_safe(item.message), _csv_safe(item.status), _csv_safe(item.created_at.isoformat() if item.created_at else '')])
        filename = 'leads.csv'
    else:
        abort(404)

    response = Response(output.getvalue(), mimetype='text/csv')
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'
    return response

@admin_bp.route('/', strict_slashes=False)
@admin_required
def admin_dashboard():
    tab = request.args.get('tab', 'dashboard')
    status_filter = request.args.get('status', 'all').strip().lower()
    search = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    if page < 1: page = 1
    if tab == 'leads' and status_filter not in LEAD_STATUSES: status_filter = 'all'
    if tab != 'leads' and status_filter not in LISTING_STATUSES: status_filter = 'all'

    recent_limit = current_app.config['ADMIN_DASHBOARD_RECENT_LIMIT']
    per_page = current_app.config['ADMIN_LISTINGS_PER_PAGE']
    flats_all, services_all, leads_all = [], [], []
    has_prev, has_next, prev_url, next_url = False, False, None, None

    if tab in {'dashboard', 'flats'}:
        flats_query = Flat.query.options(load_only(Flat.id, Flat.title, Flat.location, Flat.image_url, Flat.status, Flat.created_at), joinedload(Flat.owner).load_only(User.id, User.full_name))
        if status_filter in LISTING_STATUSES: flats_query = flats_query.filter_by(status=status_filter)
        if search:
            like = f"%{search}%"
            flats_query = flats_query.filter(or_(Flat.title.ilike(like), Flat.location.ilike(like)))
        flats_query = flats_query.order_by(Flat.created_at.desc())
        if tab == 'dashboard': flats_all = flats_query.limit(recent_limit).all()
        else: flats_all, has_prev, has_next = paginate_query(flats_query, page, per_page)

    if tab in {'dashboard', 'services'}:
        services_query = InteriorService.query.options(load_only(InteriorService.id, InteriorService.provider_name, InteriorService.service_type, InteriorService.image_url, InteriorService.status, InteriorService.created_at), joinedload(InteriorService.provider).load_only(User.id, User.full_name))
        if status_filter in LISTING_STATUSES: services_query = services_query.filter_by(status=status_filter)
        if search:
            like = f"%{search}%"
            services_query = services_query.filter(InteriorService.provider_name.ilike(like))
        services_query = services_query.order_by(InteriorService.created_at.desc())
        if tab == 'dashboard': services_all = services_query.limit(recent_limit).all()
        else: services_all, has_prev, has_next = paginate_query(services_query, page, per_page)

    if tab in {'dashboard', 'leads'}:
        leads_query = Lead.query.options(load_only(Lead.id, Lead.name, Lead.phone, Lead.email, Lead.interest, Lead.message, Lead.status, Lead.created_at))
        if status_filter in LEAD_STATUSES: leads_query = leads_query.filter_by(status=status_filter)
        if search:
            like = f"%{search}%"
            leads_query = leads_query.filter(or_(Lead.name.ilike(like), Lead.email.ilike(like), Lead.phone.ilike(like), Lead.message.ilike(like)))
        leads_query = leads_query.order_by(Lead.created_at.desc())
        if tab == 'dashboard': leads_all = leads_query.limit(recent_limit).all()
        else: leads_all, has_prev, has_next = paginate_query(leads_query, page, per_page)

    stats = get_cached_value('admin_stats', 30, collect_admin_stats)
    trend = get_cached_value('admin_trend_v1', 30, _build_trend)
    admin_filters = {'status': status_filter, 'q': search}
    
    if tab in {'flats', 'services', 'leads'}:
        page_params = {'tab': tab}
        if status_filter != 'all': page_params['status'] = status_filter
        if search: page_params['q'] = search
        if has_prev: prev_url = url_for('admin.admin_dashboard', page=page - 1, **page_params)
        if has_next: next_url = url_for('admin.admin_dashboard', page=page + 1, **page_params)

    status_options = [('all', 'All Status'), ('new', 'New'), ('contacted', 'Contacted'), ('closed', 'Closed')] if tab == 'leads' else [('all', 'All Status'), ('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')]
    filters_applied = bool(search or status_filter in (LEAD_STATUSES if tab == 'leads' else LISTING_STATUSES))
    
    return render_template('admin_dashboard.html', trend=trend, flats=flats_all, services=services_all, leads=leads_all, active_tab=tab, stats=stats, admin_filters=admin_filters, filters_applied=filters_applied, status_options=status_options, page=page, has_prev=has_prev, has_next=has_next, prev_url=prev_url, next_url=next_url)

@admin_bp.route('/preview')
@admin_required
def preview():
    initial_path = normalize_preview_path(request.args.get('path', '/'))
    preview_pages = [{'label': 'Home', 'path': '/'}, {'label': 'Flats', 'path': '/flats'}, {'label': 'Interior', 'path': '/interior'}, {'label': 'Login', 'path': '/login'}]
    return render_template('preview.html', initial_path=initial_path, preview_pages=preview_pages)

@admin_bp.route('/approve/<item_type>/<int:id>', methods=['POST'])
@admin_required
@limiter.limit("30 per minute")
def approve_listing(item_type, id):
    item = get_listing_item(item_type, id)
    item.status = 'approved'
    db.session.commit()
    flash('Listing approved!', 'success')
    tab = 'flats' if item_type == 'flat' else 'services'
    return redirect(request.referrer or url_for('admin.admin_dashboard', tab=tab))

@admin_bp.route('/delete/<item_type>/<int:id>', methods=['POST'])
@admin_required
@limiter.limit("20 per minute")
def delete_listing(item_type, id):
    item = get_listing_item(item_type, id)
    delete_listing_media(item)
    db.session.delete(item)
    db.session.commit()
    flash('Listing deleted!', 'success')
    tab = 'flats' if item_type == 'flat' else 'services'
    return redirect(request.referrer or url_for('admin.admin_dashboard', tab=tab))

@admin_bp.route('/status/<item_type>/<int:id>', methods=['POST'])
@admin_required
@limiter.limit("60 per minute")
def update_listing_status(item_type, id):
    status = normalize_status(request.form.get('status'))
    if not status: abort(400)
    item = get_listing_item(item_type, id)
    item.status = status
    db.session.commit()
    flash('Listing status updated!', 'success')
    return redirect(request.referrer or url_for('admin.admin_dashboard'))

@admin_bp.route('/leads/<int:id>/status', methods=['POST'])
@admin_required
@limiter.limit("60 per minute")
def update_lead_status(id):
    status = normalize_lead_status(request.form.get('status'))
    if not status: abort(400)
    lead = Lead.query.get_or_404(id)
    lead.status = status
    db.session.commit()
    flash('Lead status updated!', 'success')
    return redirect(request.referrer or url_for('admin.admin_dashboard', tab='leads'))

@admin_bp.route('/leads/<int:id>/delete', methods=['POST'])
@admin_required
@limiter.limit("30 per minute")
def delete_lead(id):
    lead = Lead.query.get_or_404(id)
    db.session.delete(lead)
    db.session.commit()
    flash('Lead deleted!', 'success')
    return redirect(request.referrer or url_for('admin.admin_dashboard', tab='leads'))

@admin_bp.route('/bulk/<item_type>', methods=['POST'])
@admin_required
@limiter.limit("30 per minute")
def bulk_update_listings(item_type):
    action = request.form.get('action', '').strip().lower()
    ids = [coerce_int(value, 0) for value in request.form.getlist('ids')]
    ids = [item_id for item_id in ids if item_id > 0]
    if not ids:
        flash('Select at least one listing.', 'warning')
        return redirect(request.referrer or url_for('admin.admin_dashboard'))

    if item_type == 'flat': model = Flat; redirect_tab = 'flats'
    elif item_type == 'interior': model = InteriorService; redirect_tab = 'services'
    else: abort(404)

    query = model.query.filter(model.id.in_(ids))
    count = len(ids)
    if action in LISTING_STATUSES:
        query.update({'status': action}, synchronize_session=False)
        db.session.commit()
        flash(f'{count} listing(s) updated to {action}!', 'success')
    elif action == 'delete':
        for row in query.all():
            delete_listing_media(row)
        query.delete(synchronize_session=False)
        db.session.commit()
        flash(f'{count} listing(s) permanently deleted!', 'success')
    else: abort(400)
    return redirect(request.referrer or url_for('admin.admin_dashboard', tab=redirect_tab))

@admin_bp.route('/leads/bulk', methods=['POST'])
@admin_required
@limiter.limit("30 per minute")
def bulk_update_leads():
    action = request.form.get('action', '').strip().lower()
    ids = [coerce_int(value, 0) for value in request.form.getlist('ids')]
    ids = [item_id for item_id in ids if item_id > 0]
    if not ids:
        flash('Select at least one lead.', 'warning')
        return redirect(request.referrer or url_for('admin.admin_dashboard', tab='leads'))

    query = Lead.query.filter(Lead.id.in_(ids))
    count = len(ids)
    if action in LEAD_STATUSES:
        query.update({'status': action}, synchronize_session=False)
        db.session.commit()
        flash(f'{count} lead(s) updated to {action}!', 'success')
    elif action == 'delete':
        query.delete(synchronize_session=False)
        db.session.commit()
        flash(f'{count} lead(s) permanently deleted!', 'success')
    else: abort(400)
    return redirect(request.referrer or url_for('admin.admin_dashboard', tab='leads'))

@admin_bp.route('/edit/<item_type>/<int:id>', methods=['GET', 'POST'])
@admin_required
@limiter.limit("60 per minute")
def edit_listing(item_type, id):
    item = get_listing_item(item_type, id)
    if request.method == 'POST':
        status = normalize_status(request.form.get('status'))
        if status: item.status = status

        image_file = request.files.get('image_file')
        gallery_files = request.files.getlist('image_files')
        gallery_urls = parse_image_urls(request.form.get('image_urls', ''))
        old_cover_url = item.image_url
        uploaded_url = save_uploaded_image(image_file)
        if image_file and image_file.filename and not uploaded_url: flash('Unsupported image type. Use PNG, JPG, or WEBP.', 'warning')
        image_url = request.form.get('image_url', '').strip()
        if uploaded_url: item.image_url = uploaded_url
        elif image_url: item.image_url = image_url
        # If the cover photo was replaced, remove the old file from storage
        # (Cloudinary or local disk) so it does not stay orphaned.
        if old_cover_url and old_cover_url != item.image_url:
            delete_media_for_urls([old_cover_url])

        if item_type == 'flat':
            item.title = request.form.get('title', '').strip()
            item.location = request.form.get('location', '').strip()
            item.description = request.form.get('description', '').strip()
            item.price = coerce_float(request.form.get('price'), item.price or 0)
            item.bhk = coerce_int(request.form.get('bhk'), item.bhk or 1)
            item.area_sqft = coerce_int(request.form.get('area_sqft'), item.area_sqft or 0)
            raw_video_url = request.form.get('video_url', '').strip()
            item.video_url = raw_video_url if extract_youtube_id(raw_video_url) else None
            remove_ids = [coerce_int(value, 0) for value in request.form.getlist('remove_image_ids')]
            remove_ids = [value for value in remove_ids if value > 0]
            if remove_ids:
                doomed = FlatImage.query.filter(FlatImage.flat_id == item.id, FlatImage.id.in_(remove_ids)).all()
                delete_media_for_urls([image.image_url for image in doomed])
                for image in doomed:
                    db.session.delete(image)
            extra_urls, invalid = collect_uploaded_images(gallery_files)
            if invalid: flash('Some gallery images were not accepted. Use PNG, JPG, or WEBP.', 'warning')
            existing_count = FlatImage.query.filter_by(flat_id=item.id).count()
            remaining_slots = max(0, current_app.config['MAX_GALLERY_IMAGES'] - existing_count)
            for url in (extra_urls + gallery_urls)[:remaining_slots]:
                if url and url != item.image_url: db.session.add(FlatImage(flat=item, image_url=url))
        else:
            item.provider_name = request.form.get('provider_name', '').strip()
            item.service_type = request.form.get('service_type', '').strip()
            item.description = request.form.get('description', '').strip()
            item.portfolio_url = request.form.get('portfolio_url', '').strip()
            item.starting_price = coerce_float(request.form.get('starting_price'), item.starting_price or 0)
            remove_ids = [coerce_int(value, 0) for value in request.form.getlist('remove_image_ids')]
            remove_ids = [value for value in remove_ids if value > 0]
            if remove_ids:
                doomed = InteriorImage.query.filter(InteriorImage.service_id == item.id, InteriorImage.id.in_(remove_ids)).all()
                delete_media_for_urls([image.image_url for image in doomed])
                for image in doomed:
                    db.session.delete(image)
            extra_urls, invalid = collect_uploaded_images(gallery_files)
            if invalid: flash('Some gallery images were not accepted. Use PNG, JPG, or WEBP.', 'warning')
            existing_count = InteriorImage.query.filter_by(service_id=item.id).count()
            remaining_slots = max(0, current_app.config['MAX_GALLERY_IMAGES'] - existing_count)
            for url in (extra_urls + gallery_urls)[:remaining_slots]:
                if url and url != item.image_url: db.session.add(InteriorImage(service=item, image_url=url))

        db.session.commit()
        flash('Listing updated successfully!', 'success')
        return redirect(url_for('admin.admin_dashboard', tab='flats' if item_type == 'flat' else 'services'))

    template = 'admin_edit_flat.html' if item_type == 'flat' else 'admin_edit_service.html'
    return render_template(template, item=item)


@admin_bp.route('/api/generate-description', methods=['POST'])
@admin_required
@limiter.limit("10 per minute")
def generate_description():
    raw_notes = request.form.get('notes', '').strip()
    if not raw_notes:
        return jsonify({'ok': False, 'error': 'Add a few notes first: area, size, condition, what makes it special.'}), 400
    generated_text = generate_listing_description(raw_notes)
    if not generated_text:
        return jsonify({'ok': False, 'error': 'The writer could not produce a description. Please try again.'}), 502
    return jsonify({'ok': True, 'description': generated_text})

# --------------------------------------------------------------------------- #
#  Overview: real activity for the last 14 days
# --------------------------------------------------------------------------- #
def _build_trend(days=14):
    """Daily submission and enquiry counts, ready for the dashboard charts."""
    from sqlalchemy import func

    today = datetime.utcnow().date()
    start_date = today - timedelta(days=days - 1)
    start_dt = datetime.combine(start_date, datetime.min.time())

    listing_counts, lead_counts = {}, {}

    def _count_by_day(model, bucket):
        try:
            rows = db.session.query(
                func.date(model.created_at).label('day'),
                func.count(model.id),
            ).filter(model.created_at >= start_dt).group_by(func.date(model.created_at)).all()
        except Exception:
            rows = []
        for day, total in rows:
            if day:
                bucket[day] = int(total)

    # Aggregate in the database instead of pulling every row into Python.
    _count_by_day(Flat, listing_counts)
    _count_by_day(InteriorService, listing_counts)
    _count_by_day(Lead, lead_counts)

    listings_series, leads_series, day_rows = [], [], []
    for offset in range(days):
        day = start_date + timedelta(days=offset)
        listings = listing_counts.get(day, 0)
        leads = lead_counts.get(day, 0)
        listings_series.append(listings)
        leads_series.append(leads)
        day_rows.append({
            'label': day.strftime('%d %b'),
            'short': day.strftime('%d'),
            'listings': listings,
            'leads': leads,
        })

    peak = max([1] + listings_series + leads_series)
    for row in day_rows:
        row['listings_pct'] = int(round(row['listings'] * 100.0 / peak))
        row['leads_pct'] = int(round(row['leads'] * 100.0 / peak))

    total_listings = sum(listings_series)
    total_leads = sum(leads_series)
    if not total_listings and not total_leads:
        return None

    return {
        'days': day_rows,
        'listings': listings_series,
        'leads': leads_series,
        'total_listings': total_listings,
        'total_leads': total_leads,
        'peak': peak,
    }


# --------------------------------------------------------------------------- #
#  Media library
# --------------------------------------------------------------------------- #
def _media_inventory(cap=600):
    """Every image the site references, newest first, with its storage home."""
    items = []

    def add(url, title, kind, edit_url):
        if not url:
            return
        items.append({
            'url': url,
            'title': title or 'Untitled',
            'kind': kind,
            'edit_url': edit_url,
            'provider': media_provider_for_url(url),
        })

    flats = (Flat.query
             .options(load_only(Flat.id, Flat.title, Flat.image_url, Flat.created_at))
             .order_by(Flat.created_at.desc()).limit(cap).all())
    for flat in flats:
        add(flat.image_url, flat.title, 'Flat cover',
            url_for('admin.edit_listing', item_type='flat', id=flat.id))

    services = (InteriorService.query
                .options(load_only(InteriorService.id, InteriorService.provider_name,
                                   InteriorService.image_url, InteriorService.created_at))
                .order_by(InteriorService.created_at.desc()).limit(cap).all())
    for service in services:
        add(service.image_url, service.provider_name, 'Studio cover',
            url_for('admin.edit_listing', item_type='interior', id=service.id))

    for image in (FlatImage.query.options(joinedload(FlatImage.flat))
                  .order_by(FlatImage.id.desc()).limit(cap).all()):
        parent = image.flat
        add(image.image_url, parent.title if parent else 'Flat gallery', 'Flat gallery',
            url_for('admin.edit_listing', item_type='flat', id=parent.id) if parent else None)

    for image in (InteriorImage.query.options(joinedload(InteriorImage.service))
                  .order_by(InteriorImage.id.desc()).limit(cap).all()):
        parent = image.service
        add(image.image_url, parent.provider_name if parent else 'Studio gallery', 'Studio gallery',
            url_for('admin.edit_listing', item_type='interior', id=parent.id) if parent else None)

    total = len(items)
    on_cdn = len([i for i in items if i['provider'] == 'cloudinary'])
    local = len([i for i in items if i['provider'] == 'local'])
    external = len([i for i in items if i['provider'] == 'external'])
    stats = {
        'total': total,
        'cloudinary': on_cdn,
        'local': local,
        'external': external,
        'cloud_percent': int(round(on_cdn * 100.0 / total)) if total else 0,
    }
    return items, stats


def _media_stats_counts():
    """Storage stats via lightweight URL scans - no joined loads or item dicts.

    The health page only needs the numbers, so it should not build the full
    media inventory (up to 2400 rows) just to count them.
    """
    counts = {'cloudinary': 0, 'local': 0, 'external': 0}

    def _scan(model, url_col):
        try:
            rows = db.session.query(url_col).filter(url_col.isnot(None)).all()
        except Exception:
            rows = []
        for (url,) in rows:
            if not url:
                continue
            provider = media_provider_for_url(url)
            if provider in counts:
                counts[provider] += 1

    _scan(Flat, Flat.image_url)
    _scan(InteriorService, InteriorService.image_url)
    _scan(FlatImage, FlatImage.image_url)
    _scan(InteriorImage, InteriorImage.image_url)

    total = sum(counts.values())
    counts['total'] = total
    counts['cloud_percent'] = int(round(counts['cloudinary'] * 100.0 / total)) if total else 0
    return counts


@admin_bp.route('/media')
@admin_required
def media_library():
    page = request.args.get('page', 1, type=int) or 1
    if page < 1:
        page = 1
    per_page = 48

    items, media_stats = _media_inventory()
    start = (page - 1) * per_page
    page_items = items[start:start + per_page]
    if not page_items and page > 1:
        return redirect(url_for('admin.media_library'))

    has_prev = page > 1
    has_next = (start + per_page) < len(items)

    return render_template(
        'admin_media.html',
        cloud=cloudinary_service.status(),
        media_stats=media_stats,
        media_items=page_items,
        stats=get_cached_value('admin_stats', 30, collect_admin_stats),
        page=page,
        has_prev=has_prev,
        has_next=has_next,
        prev_url=url_for('admin.media_library', page=page - 1) if has_prev else None,
        next_url=url_for('admin.media_library', page=page + 1) if has_next else None,
    )


@admin_bp.route('/media/test', methods=['POST'])
@admin_required
@limiter.limit("12 per minute")
def media_test():
    """Live Cloudinary handshake for the Test connection button."""
    result = cloudinary_service.ping()
    message = result.get('title', '')
    if result.get('detail'):
        message = message + ' - ' + result['detail']
    return jsonify({
        'ok': bool(result.get('ok')),
        'message': message,
        'cloud_name': (result.get('status') or {}).get('cloud_name', ''),
    })


# --------------------------------------------------------------------------- #
#  System health
# --------------------------------------------------------------------------- #
def _check(label, state, detail, hint=''):
    return {'label': label, 'status': state, 'detail': detail, 'hint': hint}


@admin_bp.route('/system')
@admin_required
def system_health():
    config = current_app.config
    stats = get_cached_value('admin_stats', 30, collect_admin_stats)
    media_stats = _media_stats_counts()

    secret = os.getenv('SECRET_KEY', '') or ''
    enc_key = os.getenv('DATA_ENCRYPTION_KEY', '') or ''
    admin_path = str(config.get('ADMIN_PATH', 'admin'))
    db_uri = str(config.get('SQLALCHEMY_DATABASE_URI', ''))
    is_sqlite = db_uri.startswith('sqlite')
    force_https = os.getenv('FORCE_HTTPS', '0') == '1'
    cookie_secure = bool(config.get('SESSION_COOKIE_SECURE'))
    trust_proxy = os.getenv('TRUST_PROXY', '0') == '1'
    redis_url = os.getenv('REDIS_URL', '') or os.getenv('RATELIMIT_STORAGE_URI', '')
    mail_ready = bool(os.getenv('MAIL_SERVER') and os.getenv('MAIL_USERNAME'))
    cloud = cloudinary_service.status()

    security_checks = [
        _check('Secret key', 'ok' if len(secret) >= 32 else 'fail',
               'Session signing key is ' + str(len(secret)) + ' characters.' if secret else 'SECRET_KEY is not set.',
               '' if len(secret) >= 32 else 'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'),
        _check('Contact data encryption', 'ok' if len(enc_key) >= 32 else 'fail',
               'Phone numbers and emails are encrypted at rest.' if len(enc_key) >= 32 else 'DATA_ENCRYPTION_KEY is missing or too short.',
               '' if len(enc_key) >= 32 else 'Set a 64-character hex value. Changing it later makes stored contacts unreadable.'),
        _check('Admin URL', 'ok' if admin_path.lower() not in ('admin', 'administrator', 'wp-admin') else 'warn',
               'Console lives at /' + admin_path,
               '' if admin_path.lower() not in ('admin', 'administrator', 'wp-admin') else 'Pick an unguessable ADMIN_PATH to cut bot traffic.'),
        _check('HTTPS cookies', 'ok' if (force_https and cookie_secure) else 'warn',
               'Session cookies are marked Secure.' if cookie_secure else 'Cookies can travel over plain HTTP.',
               '' if cookie_secure else 'Set FORCE_HTTPS=1 and SESSION_COOKIE_SECURE=1 once your SSL certificate is live.'),
        _check('Proxy headers', 'ok' if trust_proxy else 'warn',
               'Real visitor IPs are read from the reverse proxy.' if trust_proxy else 'Visitor IPs may all look identical.',
               '' if trust_proxy else 'Set TRUST_PROXY=1 on cPanel/Passenger so rate limiting works per visitor.'),
        _check('Debug mode', 'ok' if not current_app.debug else 'fail',
               'Debug is off, tracebacks stay private.' if not current_app.debug else 'Debug mode is ON in production.',
               '' if not current_app.debug else 'Never run with debug enabled on a public domain.'),
        _check('CSRF protection', 'ok' if config.get('WTF_CSRF_ENABLED', True) else 'fail',
               'Every form posts a CSRF token.', ''),
    ]

    storage_checks = [
        _check('Cloudinary delivery', 'ok' if cloud['configured'] else 'warn',
               ('Uploads go to cloud "' + cloud['cloud_name'] + '", folder ' + cloud['folder'] + '.')
               if cloud['configured'] else 'Not configured, so photos are saved on this server instead.',
               '' if cloud['configured'] else 'Add CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET, then restart.'),
        _check('Cloudinary library', 'ok' if cloud['sdk_available'] else 'warn',
               'Python package is installed.' if cloud['sdk_available'] else 'The cloudinary package is not installed.',
               '' if cloud['sdk_available'] else 'Run "Run Pip Install" in cPanel against requirements.txt.'),
        _check('Images on the CDN', 'ok' if media_stats['cloud_percent'] >= 80 else ('warn' if media_stats['total'] else 'ok'),
               str(media_stats['cloudinary']) + ' of ' + str(media_stats['total']) + ' images are served from Cloudinary ('
               + str(media_stats['cloud_percent']) + '%).',
               'Older images stay where they were uploaded. New uploads follow the current setting.'
               if media_stats['local'] else ''),
        _check('Local upload folder', 'ok' if os.access(os.path.join(current_app.static_folder, 'uploads'), os.W_OK)
               else 'warn',
               'Fallback folder is writable.',
               'Needed only when Cloudinary is off.'),
        _check('Upload ceiling', 'ok' if config.get('MAX_UPLOAD_MB', 6) >= 12 else 'warn',
               'Requests up to ' + str(config.get('MAX_UPLOAD_MB', 6)) + ' MB are accepted for up to '
               + str(config.get('MAX_GALLERY_IMAGES', 10)) + ' gallery photos.',
               '' if config.get('MAX_UPLOAD_MB', 6) >= 12 else 'Raise MAX_UPLOAD_MB so multi-photo uploads do not fail.'),
        _check('Database', 'ok' if not is_sqlite else 'warn',
               'MySQL/PostgreSQL connection in use.' if not is_sqlite else 'SQLite file database in use.',
               '' if not is_sqlite else 'Fine for a small site. Move to MySQL in cPanel before heavy traffic, and keep backups.'),
    ]

    perf_checks = [
        _check('Cache and rate limits', 'ok' if redis_url else 'warn',
               'Shared Redis store configured.' if redis_url else 'In-memory store: counters reset on every restart.',
               '' if redis_url else 'Optional. Add REDIS_URL if your host offers Redis.'),
        _check('Response compression', 'ok', 'Gzip/Brotli compression is active for HTML, CSS and JS.', ''),
        _check('Static caching', 'ok',
               'Static files are fingerprinted and cached for a year.', ''),
        _check('Email notifications', 'ok' if mail_ready else 'warn',
               'SMTP credentials present.' if mail_ready else 'No SMTP configured, leads live only in this console.',
               '' if mail_ready else 'Optional. Set MAIL_SERVER, MAIL_USERNAME and MAIL_PASSWORD to receive lead emails.'),
    ]

    pending_total = stats['pending_flats'] + stats['pending_services']
    content_checks = [
        _check('Review queue', 'ok' if pending_total == 0 else 'warn',
               'Nothing is waiting for review.' if pending_total == 0
               else str(pending_total) + ' submission(s) waiting for a decision.',
               '' if pending_total == 0 else 'Open the Flats or Studios tab and approve or reject them.'),
        _check('Unanswered leads', 'ok' if stats['new_leads'] == 0 else 'warn',
               'Every enquiry has been picked up.' if stats['new_leads'] == 0
               else str(stats['new_leads']) + ' new enquiry(ies) still marked New.',
               '' if stats['new_leads'] == 0 else 'Mark them Contacted once you have called or emailed.'),
        _check('Published pages', 'ok' if (stats['approved_flats'] + stats['approved_services']) else 'warn',
               str(stats['approved_flats']) + ' flats and ' + str(stats['approved_services'])
               + ' studios are live on the public site.',
               '' if (stats['approved_flats'] + stats['approved_services']) else 'Approve at least one listing so the homepage is not empty.'),
        _check('Tracked media records', 'ok', str(_safe_count(MediaAsset)) + ' uploads are tracked for cleanup.',
               'Deleting a listing now also deletes its photos from storage.'),
    ]

    check_groups = [
        {'name': 'Security', 'icon': 'shield', 'checks': security_checks},
        {'name': 'Images and storage', 'icon': 'cloud', 'checks': storage_checks},
        {'name': 'Performance and delivery', 'icon': 'zap', 'checks': perf_checks},
        {'name': 'Content hygiene', 'icon': 'clipboard-check', 'checks': content_checks},
    ]

    all_checks = [c for group in check_groups for c in group['checks']]
    ok_count = len([c for c in all_checks if c['status'] == 'ok'])
    warn_count = len([c for c in all_checks if c['status'] == 'warn'])
    fail_count = len([c for c in all_checks if c['status'] == 'fail'])
    summary = {
        'ok': ok_count,
        'warn': warn_count,
        'fail': fail_count,
        'total': len(all_checks),
        'percent': int(round(ok_count * 100.0 / len(all_checks))) if all_checks else 0,
    }

    runtime = [
        {'label': 'Python', 'value': sys.version.split()[0]},
        {'label': 'Flask', 'value': _package_version('flask')},
        {'label': 'Server', 'value': platform.system() + ' ' + platform.release()},
        {'label': 'Database', 'value': db_uri.split('://')[0] if '://' in db_uri else 'unknown'},
        {'label': 'Instance path', 'value': current_app.instance_path},
        {'label': 'Console path', 'value': '/' + admin_path},
        {'label': 'Server time (UTC)', 'value': datetime.utcnow().strftime('%d %b %Y, %H:%M')},
        {'label': 'Listings per page', 'value': str(config.get('LISTINGS_PER_PAGE', 9))},
    ]

    return render_template(
        'admin_system.html',
        summary=summary,
        check_groups=check_groups,
        runtime=runtime,
        stats=stats,
        media_stats=media_stats,
        cloud=cloud,
    )


def _safe_count(model):
    try:
        return model.query.count()
    except Exception:
        return 0


def _package_version(name):
    try:
        from importlib.metadata import version
        return version(name)
    except Exception:
        return 'unknown'
