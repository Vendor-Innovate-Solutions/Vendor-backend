# Vendor ERP Backend

Enterprise-grade ERP backend built with Django 5.1.6 and PostgreSQL.

## 📁 Project Structure

```
Vendor-backend/
├── apps/               # Django applications (modular ERP components)
│   ├── accounting/     # Ledgers, vouchers, financial transactions
│   ├── company/        # Company, financial year, currency management
│   ├── hr/            # Human resources, employees
│   ├── inventory/     # Stock, warehouses, FIFO allocation
│   ├── invoice/       # Invoicing, billing
│   ├── logistics/     # Shipping, delivery
│   ├── orders/        # Sales & purchase orders
│   ├── party/         # Customers, suppliers, parties
│   ├── products/      # Product catalog
│   ├── reporting/     # Reports and analytics
│   ├── system/        # System utilities, audit logs
│   ├── users/         # User management
│   ├── voucher/       # Voucher management
│   └── workflow/      # Approval workflows
│
├── core/              # Core functionality
│   ├── auth/          # Authentication (custom user model)
│   ├── middleware/    # Custom middleware
│   ├── models/        # Base models
│   ├── permissions/   # Permission classes
│   ├── services/      # Business logic services
│   └── utils/         # Utility functions
│
├── integrations/      # Third-party integrations
│   ├── gst/          # GST compliance
│   ├── notifications/ # Email, SMS
│   ├── payments/     # Payment gateways
│   └── shipping/     # Shipping providers
│
├── docs/             # 📚 All project documentation
├── tests/            # 🧪 Test suites
├── scripts/          # 🔧 Utility scripts
│   ├── fixes/        # Database fix scripts
│   └── tests/        # Test runner scripts
│
├── logs/             # 📝 Application logs
├── docker/           # 🐳 Docker configuration
├── config/           # ⚙️ Configuration files
├── main/             # Django project settings
│
├── manage.py         # Django management script
├── requirements.txt  # Python dependencies
├── Procfile         # Deployment configuration
└── .gitignore       # Git ignore rules
```

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- PostgreSQL 14+
- Virtual environment

### Installation

1. **Create and activate virtual environment:**
   ```bash
   python -m venv env
   env\Scripts\activate  # Windows
   source env/bin/activate  # Linux/Mac
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure database:**
   - Update `main/settings.py` with your PostgreSQL credentials

4. **Run migrations:**
   ```bash
   python manage.py migrate
   ```

5. **Create superuser:**
   ```bash
   python manage.py createsuperuser
   ```

6. **Start development server:**
   ```bash
   python manage.py runserver
   ```

7. **Access admin panel:**
   - URL: http://127.0.0.1:8000/admin/
   - Default credentials: admin/admin123

## 📚 Documentation

All documentation is organized in the [`docs/`](docs/) folder:

- **[Setup Guide](docs/setup_guide.md)** - Detailed setup instructions
- **[Architecture](docs/ARCHITECTURE.md)** - System architecture overview
- **[API References](docs/)** - Complete API documentation
- **[Database ERD](docs/ERD_diagram.md)** - Database schema diagrams

See [`docs/README.md`](docs/README.md) for complete documentation index.

## 🧪 Testing

Run tests using pytest:

```bash
# Run all tests
python scripts/tests/run_all_tests.py

# Run specific test suite
pytest tests/test_posting_reversal.py -v

# Run with coverage
pytest tests/ --cov=core --cov=apps --cov-report=html
```

Test documentation: [`tests/TEST_DOCUMENTATION.md`](tests/TEST_DOCUMENTATION.md)

## 🔧 Utility Scripts

Located in `scripts/` folder:

- **Database Fixes**: `scripts/fixes/` - Scripts to fix database sequences and data
- **Test Runners**: `scripts/tests/` - Automated test execution scripts

## 📝 Key Features

- ✅ Multi-tenant company management
- ✅ Double-entry accounting system
- ✅ FIFO inventory management
- ✅ GST compliance (India)
- ✅ Invoice & payment tracking
- ✅ Sales & purchase orders
- ✅ Financial year management
- ✅ Approval workflows
- ✅ Audit trail & logging
- ✅ Retailer portal
- ✅ RESTful APIs with DRF
- ✅ JWT authentication

## 🛠️ Technology Stack

- **Framework**: Django 5.1.6
- **Database**: PostgreSQL 14+
- **API**: Django REST Framework
- **Authentication**: JWT (djangorestframework-simplejwt)
- **Testing**: pytest, pytest-django
- **Documentation**: Markdown

## 📦 Main Apps

| App | Purpose |
|-----|---------|
| **accounting** | Ledgers, vouchers, double-entry accounting |
| **company** | Multi-tenant company & financial year management |
| **inventory** | Stock management with FIFO allocation |
| **invoice** | Invoicing & billing |
| **orders** | Sales & purchase order processing |
| **party** | Customer & supplier management |
| **voucher** | Voucher posting & reversal |
| **workflow** | Approval workflow engine |

## 🔐 Security

- JWT-based authentication
- Role-based access control
- Audit logging for all transactions
- Financial year locking mechanism
- Company-level data isolation

## 📄 License

Proprietary - All rights reserved

## 👥 Contributing

This is a private project. For internal development guidelines, see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## 📞 Support

For documentation and technical queries, refer to the [`docs/`](docs/) folder or contact the development team.

---

**Version**: 1.0.0  
**Last Updated**: December 2025
