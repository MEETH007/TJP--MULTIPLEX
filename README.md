# 🎬 TJP MULTIPLEX — Serverless Movie Ticket Booking System

A lightweight, serverless movie ticket booking web application with automated email confirmations, dynamic QR-code ticket generation, and role-based administrative control.

[![Live Demo](https://img.shields.io/badge/Live_Demo-Render-blue?style=for-the-badge&logo=render)](https://your-app-name.onrender.com)
[![Database](https://img.shields.io/badge/Database-Supabase-3ECF8E?style=for-the-badge&logo=supabase)](https://supabase.com)
[![Mailing](https://img.shields.io/badge/Mails-Brevo-0B99FF?style=for-the-badge)](https://www.brevo.com)

---

## ⚡ Features

* **Real-Time Booking Flow:** Direct browser-to-database integration leveraging Supabase PostgreSQL.
* **Instant Digital Tickets:** Generates a unique, scannable QR verification code embedded directly on the confirmation pass.
* **Automated Email Dispatch:** Integrates Brevo transactional email APIs to deliver tickets to users upon reservation.
* **Secured Admin Control:** Password-protected dashboard enabling administrators to manage cinema schedules, update screenings, and monitor bookings.
* **Zero-Cold-Start Architecture:** Static client hosted on Render, abstracting traditional server overhead.

---

## 🛠️ Architecture & Tech Stack

* **Frontend:** Semantic HTML5, CSS3
* **Backend as a Service (BaaS):** [Supabase](https://supabase.com/) (PostgreSQL database, Row Level Security)
* **Email Service:** [Brevo](https://www.brevo.com/) (Transactional API)
* **Ticket Verification:** Client-side QR generation engine
* **Deployment & CI/CD:** [Render](https://render.com/) via GitHub webhooks
