from backend.main import app
print('ROUTES:')
for route in app.routes:
    print(route.path, route.name, getattr(route, 'methods', None))
