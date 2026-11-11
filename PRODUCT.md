# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary: Bengali-speaking flat seekers in Dhaka, Chattogram, and Sylhet — buyers and renters hunting for a home on a phone, burned before by fake listings. Secondary: flat owners and interior design studios who publish listings (owners may self-post; every listing passes team review). Internal: the FlatLand BD team runs the admin console (review queue, leads, media).

## Product Purpose

FlatLand BD is a real-estate marketplace for Bangladesh that pairs verified flat listings with interior design studios. It exists because listings that do not exist are the core failure of local property hunting; success is a seeker trusting the photos they see, getting a human on WhatsApp fast, and completing an enquiry, visit, or interior engagement.

## Positioning

Hybrid, human-verified model: the team checks listings before publish — owner identity and paperwork sighted, photos matched to the flat as it stands today, and agency-listed flats get site visits and visit coordination — while owners can still self-post into a review queue. A classifieds competitor could not truthfully copy the "checked by a human, photographed on site" commitment.

## Operating Context

Small Dhaka-based team operating from Hashem Mansion, Level-1, 48 Kazi Nazrul Islam Ave, Dhaka 1215; Saturday–Thursday, 10:00–20:00. Communication is WhatsApp-first with ~15-minute replies. Workflow: listing submitted → team review in the admin console → approved and published. Images served via Cloudinary with local fallback.

## Capabilities and Constraints

- Browse/search flats with filters (location, BHK, price, sort); interior studio directory with portfolios and starting prices
- Member accounts with username / mobile / email login; contact data encrypted at rest
- Members post listings (pending review) and delete their own; admin console with dashboard, approve/reject/edit/bulk-delete, lead pipeline + CSV export, media library, system health page
- Stack (from code, confirmed by use): Flask 3 + Jinja2 server-rendered templates, hand-written CSS/JS, no build step; SQLite in dev
- Explicitly undecided: scope and timeline of the Bengali UI. Bengali-first is the confirmed product direction (see Accessibility), but the current interface is English-only.

## Brand Commitments

- Name: **FlatLand BD**; logo assets in `frontend/static/img/` (`logo-icon.svg`, `logo-mark.svg`, `logo-mark-light.svg`)
- Voice: direct, honest, human — "we would rather list ten honest flats than a thousand ghosts"
- Binding service commitments the interface may state as fact: WhatsApp replies in ~15 minutes, enquiries answered same day (96%), zero brokerage surprises, browsing and enquiring free, publishing free

## Evidence on Hand

- Three real client testimonials in `frontend/templates/index.html` (Nusrat & Tanvir, Rifat H., Shahana K.) — confirmed genuine; reusable as fact
- All homepage service commitments (see Brand Commitments) — confirmed real, not placeholder copy
- Contact channels: +880 1712 458794 (call and WhatsApp)
- No listing data yet: database currently has zero flats/studios; real inventory arrives via the team pipeline — future work must never fabricate listings, counts, or reviews

## Product Principles

1. Verified truth beats inventory size — nothing publishes before the team checks it.
2. Fast human replies are the product — WhatsApp-speed response is a commitment, not support.
3. Bengali-first audience — design and content decisions must not foreclose Bengali; treat Bengali capability as a requirement, not a nice-to-have.
4. Costs stated up front — free for seekers, no hidden brokerage, prices published in full.
5. Owners self-serve, review is the gate — submission is easy; publication is earned.

## Accessibility & Inclusion

Bengali-first: the primary audience expects Bengali, so full Bengali UI and typography support (Noto Sans Bengali is already loaded for the ৳ symbol) is a product requirement; English remains supported. The audience is overwhelmingly mobile — phone-first behavior is the default evaluation target.
