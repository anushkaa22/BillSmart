from app import app, db, User, Product, Sale, Notification

with app.app_context():
    print('users', User.query.count(), 'products', Product.query.count())

client = app.test_client()
for path in ['/login', '/register', '/dashboard', '/inventory', '/billing', '/sales', '/customers', '/suppliers', '/reports', '/notifications']:
    response = client.get(path)
    print(path, response.status_code, response.location or '')

with client:
    client.get('/login')
    with client.session_transaction() as session:
        token = session['csrf_token']
    response = client.post('/login', data={'identity': 'admin', 'password': 'Admin@123', 'csrf_token': token})
    print('login', response.status_code, response.location or '')
    for path in ['/dashboard', '/inventory', '/billing', '/sales', '/customers', '/suppliers', '/reports', '/notifications', '/users', '/settings']:
        response = client.get(path)
        print('auth', path, response.status_code)
    with app.app_context():
        product = Product.query.filter(Product.quantity > 0).first()
        before = product.quantity
        product_id = product.id
    response = client.post('/billing/complete', json={'items': [{'id': product_id, 'quantity': 1}], 'discount': 0, 'tax': 0, 'payment_method': 'Cash'}, headers={'X-CSRFToken': token})
    print('sale', response.status_code, response.json)
    with app.app_context():
        print('stock_reduced', Product.query.get(product_id).quantity == before - 1, 'sales', Sale.query.count(), 'notifications', Notification.query.count())
    with client.session_transaction() as session:
        token = session['csrf_token']
    client.post('/logout', data={'csrf_token': token})

with app.app_context():
    staff = User.query.filter_by(role='staff').first()
    if not staff:
        staff = User(username='smoke_staff', email='smoke_staff@billsmart.local', role='staff')
        staff.set_password('Password123')
        db.session.add(staff)
        db.session.commit()
with client:
    client.get('/login')
    with client.session_transaction() as session:
        token = session['csrf_token']
    response = client.post('/login', data={'identity': 'smoke_staff', 'password': 'Password123', 'csrf_token': token})
    print('staff_login', response.status_code)
    print('staff_users_forbidden', client.get('/users').status_code)
    print('staff_settings_forbidden', client.get('/settings').status_code)
