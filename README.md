# 🎬 TJP MULTIPLEX — Full-Stack Movie Ticket Booking System

A full-stack movie ticket reservation web application featuring dynamic seat selection, automated Brevo email delivery, digital QR-code verification, and a secure administrative management dashboard.

[![Live Demo](https://img.shields.io/badge/Live_Demo-Render-46E3B7?style=for-the-badge&logo=render&logoColor=white)](https://your-app-name.onrender.com)
[![Backend](https://img.shields.io/badge/Backend-Python%20%7C%20Flask-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://flask.palletsprojects.com/)
[![Database](https://img.shields.io/badge/Database-Supabase-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)](https://supabase.com)
[![Mailing](https://img.shields.io/badge/Email-Brevo-0B99FF?style=for-the-badge)](https://www.brevo.com)

---

## 📖 Overview

TJP MULTIPLEX streamlines the end-to-end cinema ticketing workflow:
1. **Browse & Select:** Users browse current screenings and pick available seats via an interactive UI.
2. **Instant Reservation:** Booking requests are processed by a Python (Flask) backend and persisted in Supabase (PostgreSQL).
3. **Automated Ticket Delivery:** Brevo transactional email APIs dispatch digital confirmation passes with unique, scannable QR verification codes.
4. **Admin Governance:** A password-authenticated administrative dashboard allows theater operators to manage screening schedules and monitor reservations.

---

## 🛠️ Architecture & Tech Stack

| Layer | Technology | Purpose |
| :--- | :--- | :--- |
| **Structure** | HTML5 | Semantic document layout and clean accessibility |
| **Design** | CSS3 | Responsive UI, modern cards, and theater seat grids |
| **Interactivity** | Vanilla JavaScript | Client-side validation, seat state management, dynamic UI |
| **Backend** | Python + Flask | REST endpoints, booking validation, email orchestration |
| **Database** | Supabase (PostgreSQL) | Relational storage for shows, seats, and user reservations |
| **Email Service** | Brevo API | Transactional confirmation emails |
| **Ticket Verification** | External QR API | Dynamic QR generation tied to unique booking IDs |
| **Hosting & CI/CD** | Render | Automated build and deployment directly from GitHub |

---

## ⚡ System Flow
