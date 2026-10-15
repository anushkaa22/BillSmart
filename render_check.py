from app import app

client = app.test_client()
client.get('/login')
with client.session_transaction() as session:
    token = session['csrf_token']
client.post('/login', data={'identity': 'admin', 'password': 'Admin@123', 'csrf_token': token})
for path in ['/dashboard', '/invoice/1', '/inventory', '/billing', '/reports', '/notifications', '/users', '/settings']:
    response = client.get(path)
    print(path, response.status_code, len(response.data))
