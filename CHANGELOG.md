# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- stage4: MVP ready for client demo — consolidated all features, froze non-essential commands, created complete documentation
- docs: Added STAGE4_COMPLETE.md — full project overview and sign-off
- docs: Added STAGE4_IMPLEMENTATION.md — implementation summary for Stage 4
- docs: Added MVP_DEMO.md — detailed demo guide with scenarios and admin commands
- docs: Added MVP_AUDIT.md — code quality and security audit report
- docs: Added DEMO_QUICK_START.md — quick start guide for running MVP

### Frozen (Intentionally Not Part of MVP Demo)
- feature: `/export_bookings` and `/export_reviews` — CSV export (marked as frozen, still implemented and tested)
- feature: `/add_exception`, `/list_exceptions` — Master exception management (marked as frozen)

### Notes
- **Status**: MVP Stage 4 complete and ready for client presentation
- **Tests**: All 60 tests passing (100% coverage of MVP features)
- **Documentation**: 4 new comprehensive guides created for demo and development
- **Next Stage**: Gather client feedback, plan Stage 5 (web admin panel, payment integration)

---

## [Stage 3] — Rating System & Reminders

### Added
- tests: Add end-to-end test verifying UI shows "❌ занято" for fully booked masters (tests/test_busy_master_display.py). ✅
- tests: Add manual request flow tests and stabilize booking-related tests (tests/test_booking_manual_request.py).
- feature: Add auto-review request after booking completion — admin command `/complete_booking` marks booking as completed and sends client a rating prompt (1-5 stars + optional comment). Reviews are saved to DB and admins are notified. Includes unit and E2E tests (tests/test_handlers_reviews_auto_request.py).
- feature: Support cancelling bookings without touching the database directly. Added:
  * admin command `/cancel_booking <id>` which marks booking cancelled and clears scheduled tasks
  * user command `/cancel_booking <id>` allowing clients to cancel their own bookings
  * corresponding unit and e2e tests (tests/test_booking_cancel.py, updated test_admin_e2e.py)
  * docs updated accordingly
- ux: Improve user experience with friendlier messages, emojis, examples, and clearer prompts across booking, review, and admin flows. Enhanced error messages and confirmations.
- feature: Stage 3 — display average ratings for masters and services in client UI. Shows master rating next to name and service average + count in service card. Tests added.
- feature: Admin CSV export: `/export_bookings` and `/export_reviews` commands. Exports `bookings` (id, date, time, service, master, client_name, phone, status) and `reviews` (booking_id, rating, comment, created_at). Implemented repo SQL methods, `app/export.py`, handlers and tests.
- feature: Stage 3 priority 3 — reminders: 24h and 1h before visit. Persists `reminded_24`/`reminded_1` flags. Schedule via `schedule_reminders()` and cancel via `cancel_reminders()`. E2E tests added.

### Fixed
- handlers: Ensure `InlineKeyboardMarkup` and `InlineKeyboardButton` are constructed compatibly with current test harness and aiogram usage (various small fixes in `app/handlers/booking.py`, `app/handlers/client.py`, `app/handlers/services.py`).

### Notes
- All tests pass locally: **60 passed**.
- Migration to aiogram 3.x and removal of temporary test shims postponed — will be scheduled as a separate task when a migration plan is approved.

---

(Generated on 2026-01-30)
