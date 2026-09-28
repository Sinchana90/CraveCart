# CraveCart 🍽️

**CraveCart** is a Django-based food ordering web application that allows customers to explore restaurants, browse menus, manage their carts, and place food orders. It includes a customer-facing website and an admin panel, presented in a black-and-gold theme.

## Features

### Customer
- Sign up with email OTP verification and sign in securely.
- Reset a forgotten password using email OTP.
- Browse active restaurants and their available menu items.
- Save favorite restaurants.
- Add items to a cart and adjust quantities.
- Manage profile information and delivery addresses.
- Review the cart, select a delivery address, and place orders using **Cash on Delivery (COD)**.
- View an order confirmation after placing an order.

### Admin
- View dashboard counts for restaurants, menu items, and customers.
- Add, update, activate, and deactivate restaurants.
- Add, edit, and remove restaurant menu items.
- View registered customers.

## Tech Stack

- **Backend:** Python, Django
- **Database:** SQLite (development)
- **Frontend:** HTML, CSS, JavaScript
- **Email:** SMTP for OTP verification and password reset
- **Payment:** Cash on Delivery; Razorpay online payment integration is under development in the black-and-gold version.

## Getting Started

### Prerequisites

- Python installed
- Git installed

### Installation

1. Clone your repository:
   ```bash
   git clone https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
   cd YOUR_REPOSITORY
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv myenv
   ```
   On Windows:
   ```cmd
   myenv\Scripts\activate
   ```
   On macOS/Linux:
   ```bash
   source myenv/bin/activate
   ```
3. Install dependencies (if `requirements.txt` is included):
   ```bash
   pip install -r requirements.txt
   ```
4. Navigate to the folder containing `manage.py`, if necessary.
5. Configure the environment variables required by your `settings.py`. Keep secrets in a local `.env` file and **never commit it**. For example:
   ```dotenv
   DJANGO_SECRET_KEY=replace_with_your_own_secret_key
   EMAIL_HOST_PASSWORD=replace_with_your_email_app_password
   RAZORPAY_KEY_ID=replace_with_your_test_key_id
   RAZORPAY_KEY_SECRET=replace_with_your_test_key_secret
   ```
   Only include the Razorpay variables if online payment is configured. Ensure `settings.py` loads `.env` if you use this approach.
6. Apply migrations:
   ```bash
   python manage.py migrate
   ```
7. Start the development server:
   ```bash
   python manage.py runserver
   ```
8. Visit `http://127.0.0.1:8000/` in your browser.

## Project Structure

```text
CraveCart/
├── manage.py
├── cravecart/             # Django project settings and URLs
├── delivery/              # Models, views, routes, templates, and static files
├── requirements.txt       # Python dependencies, if generated
└── README.md
```

## Payment Status

Cash on Delivery is implemented. Razorpay online payment is planned/in progress for the black-and-gold version; do not use it for real payments until server-side verification and end-to-end testing are complete.

## Security Notes

- Do not upload `.env`, API secrets, email app passwords, or the local database containing real user data.
- Use environment variables for sensitive settings.
- Keep Django `DEBUG` disabled and configure `ALLOWED_HOSTS` appropriately before production deployment.

## Future Improvements

- Complete Razorpay online payment integration and payment verification.
- Add automated tests and production deployment configuration.

## Author

Created as a Django food ordering project.
