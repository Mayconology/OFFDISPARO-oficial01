# Receita Federal Payment Portal

## Overview

This Flask-based web application simulates a Brazilian Federal Revenue Service (Receita Federal) portal for tax payment regularization. Its primary purpose is to retrieve customer data, generate payment requests via PIX (Brazilian instant payment system), and process these payments through integrated APIs. The project aims to provide a streamlined, user-friendly interface for tax payment, integrating with external systems for lead management and payment processing.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Backend
- **Framework**: Flask (Python)
- **Session Management**: Flask sessions with environment-based secret key
- **Logging**: Python's built-in logging module (debug level)
- **HTTP Client**: Requests library
- **Payment Integration**: Primarily Iron Pay API, with a robust Brazilian PIX fallback system.
- **Customer Data**: Retrieval from an external lead database API.

### Frontend
- **Template Engine**: Jinja2
- **CSS Framework**: Tailwind CSS (CDN)
- **Icons**: Font Awesome 5.15.3
- **Custom Fonts**: Rawline font family
- **JavaScript**: Vanilla JS for interactive elements like countdown timers.
- **UI/UX Decisions**:
    - Dynamic content rendering based on customer data.
    - Integration of urgency elements (e.g., countdown timer, judicial warnings).
    - Responsive design for mobile compatibility.
    - Use of official seals (e.g., Ministry of Justice) for authenticity.

### System Design Choices
- **Data Flow**: Customer identification via UTM parameters or CPF lookup, session-based data persistence, validation, payment request generation, and PIX payment processing.
- **Error Handling**: Comprehensive logging, graceful fallbacks for missing data or API issues, and input validation.
- **Deployment**: Designed for Gunicorn WSGI server in production, with environment variable configuration.

## External Dependencies

### APIs
- **Lead Database API**: `https://api-lista-leads.replit.app/api/search/{phone}`
- **Iron Pay API**: `https://app.for4payments.com.br/api/v1` (for `POST /public/v1/transactions`)

### CDN Resources
- **Tailwind CSS**: `https://cdn.tailwindcss.com`
- **Font Awesome**: `https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.3/css/all.min.css`

### Environment Variables
- `SESSION_SECRET`: Flask session encryption key.
- `FOR4PAYMENTS_SECRET_KEY`: API authentication token for payment gateways.
- `PAYBETS_CLIENT_ID`: OAuth client ID for PayBets.
- `PAYBETS_CLIENT_SECRET`: OAuth client secret for PayBets.