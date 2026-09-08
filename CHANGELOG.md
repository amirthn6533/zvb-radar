# Changelog

All notable changes to the ZVB Lead Radar and Telegram Bot service will be documented in this file.

## [2.0.0] - 2026-09-08
### Added
- **SQLite Database Architecture**: Replaced JSON flat-files with ACID-compliant \zvb_radar.db\ engine.
- **Lead Lifecycle State Machine**: 4-stage interactive pipeline (\Contacted\, \Remind in 2d\, \Won\, \Lost\).
- **Follow-up Reminders**: Scheduled notifications in 09:00 AM daily executive digest.
- **Pipeline Dashboard**: Added \/crm\ command displaying real-time deal flow metrics.
- **1-Click Email Proposal Dispatch**: Added automated Bulgarian proposal emailer via SMTP.

## [1.5.0] - 2026-09-06
### Added
- **7-Layer Anti-Spam Filter**: Regional geofencing for Sofia, keyword exclusions, and 80% Levenshtein similarity deduplication.
- **PDF Commercial Offer Generator**: Direct generation of branded ZVB proposals with official pricing.
- **Candidate Electrician CRM**: Interactive database for team recruitment and technician dispatching.

## [1.0.0] - 2026-09-05
### Added
- Initial release with multi-source scrapers for Bazar.bg, Alo.bg, Daibau, and MaistorPlus.
